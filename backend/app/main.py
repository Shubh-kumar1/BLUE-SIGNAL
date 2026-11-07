import csv
import io
import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import requests
from fastapi import Depends, FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from werkzeug.utils import secure_filename

from app.database import get_db, engine
from app.models.post import Post
from app.models.report import Report
from app.models.user import User
from app.models.vote import Vote
from app.schemas import ImageClassificationRequest, LoginRequest, RegisterRequest, TextClassificationRequest, VoteRequest
from app.security import (
    authority_user,
    citizen_user,
    current_user,
    hash_password,
    is_legacy_password_hash,
    query_user,
    verify_password,
)
from app.services.classification_service import ClassificationService
from app.services.report_service import all_reports, create_post, create_report, map_reports, posts_with_votes, user_posts, user_profile
from app.services.sse_service import hotspot_listeners, post_listeners, publish, stream

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required")
if len(SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY must contain at least 32 characters")

classification_service = ClassificationService()
UPLOAD_FOLDER = Path(os.getenv("UPLOAD_FOLDER", "uploads")).resolve()
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


async def startup_healthcheck() -> None:
    with engine.connect() as connection:
        connection.exec_driver_sql("SELECT 1")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_healthcheck()
    classification_service.load_in_background()
    logger.info("FastAPI application started with PostgreSQL")
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title="BlueSignal API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:3001",
                   "https://blue-signal.vercel.app", "https://blue-signal-1648rv5mv-shubhamraj9493-9503s-projects.vercel.app"],
    allow_headers=["Content-Type", "Authorization"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_FOLDER)), name="uploads")


@app.exception_handler(HTTPException)
async def compatibility_http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})


@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "success", "message": "API is running"}


@app.get("/api/test")
def test_route() -> dict:
    return {"status": "success", "message": "FastAPI Backend is working!", "data": {"timestamp": datetime.now().isoformat()}}


@app.post("/api/auth/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    username = payload.username.strip()
    email = str(payload.email).strip().lower()
    if payload.role not in {"citizen", "authority"}:
        raise HTTPException(400, {"error": "Role must be citizen or authority"})
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(409, {"error": "Username already exists"})
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, {"error": "Email already exists"})
    user = User(username=username, email=email, password=hash_password(payload.password),
                role=payload.role, full_name=payload.full_name.strip())
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, {"error": "Username or email already exists"})
    return {"message": "User registered", "user_id": user.id}


@app.post("/api/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    username = payload.username.strip()
    user = db.scalar(select(User).where(User.username == username))
    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(401, {"error": "Invalid credentials"})
    if is_legacy_password_hash(user.password):
        user.password = hash_password(payload.password)
        db.commit()
    token = jwt.encode({"username": user.username, "role": user.role,
                        "exp": datetime.now(timezone.utc) + timedelta(hours=24)},
                       SECRET_KEY, algorithm="HS256")
    return {"token": token, "user": {"id": user.id, "username": user.username,
                                     "role": user.role, "full_name": user.full_name}}


@app.get("/api/auth/citizen/posts")
def citizen_posts(db: Session = Depends(get_db), user: User = Depends(citizen_user)) -> dict:
    return {"posts": user_posts(db, user.id)}


@app.post("/api/auth/citizen/posts")
async def create_citizen_post(request: Request,
                              db: Session = Depends(get_db), user: User = Depends(citizen_user)) -> dict:
    image = None
    if "application/json" in request.headers.get("content-type", ""):
        payload = await request.json()
        title = payload.get("title", "Flood Report")
        description = payload.get("description", "")
        latitude = payload.get("latitude")
        longitude = payload.get("longitude")
        location_name = payload.get("location_name", "Unknown Location")
        media_url = payload.get("media_url")
    else:
        form = await request.form()
        title = form.get("title") or "Flood Report"
        description = form.get("description") or ""
        latitude = float(form["latitude"]) if form.get("latitude") else None
        longitude = float(form["longitude"]) if form.get("longitude") else None
        location_name = form.get("location_name") or "Unknown Location"
        media_url = None
        image = form.get("image") if isinstance(form.get("image"), UploadFile) else None

    saved_path = None
    if image and image.filename:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(400, {"error": "Unsupported image type"})
        body = await image.read(MAX_UPLOAD_SIZE + 1)
        if len(body) > MAX_UPLOAD_SIZE:
            raise HTTPException(400, {"error": "Image file is too large"})
        filename = f"{uuid.uuid4().hex}_{secure_filename(image.filename)}"
        saved_path = UPLOAD_FOLDER / filename
        saved_path.write_bytes(body)
        media_url = f"/uploads/{filename}"

    urgency = classification_service.classify_urgency(description)
    flood_type = classification_service.classify_flood_type(description)
    post = create_post(db, user.id, title, description, media_url, latitude, longitude, location_name)
    summary = generate_summary(description, urgency.model_dump(), flood_type.model_dump(), location_name)
    report = create_report(db, post, user.id, urgency.class_name, flood_type.class_name,
                           urgency.confidence, summary, latitude, longitude, location_name)
    post.status = "verified"
    db.commit()
    db.refresh(post)
    db.refresh(report)

    image_result = classification_service.classify_image(str(saved_path)) if saved_path else None
    hotspot_payload = {"id": report.id, "post_id": post.id, "title": title,
                       "description": description, "urgency_level": urgency.class_name,
                       "flood_type": flood_type.class_name, "ai_summary": summary,
                       "latitude": latitude, "longitude": longitude,
                       "location_name": location_name, "status": post.status}
    publish(hotspot_listeners, {"type": "hotspot", "data": hotspot_payload})
    publish(post_listeners, {"type": "post", "data": posts_with_votes(db)[0] if posts_with_votes(db) else None})
    return {"message": "Post created successfully", "post_id": post.id, "report_id": report.id,
            "urgency": urgency.class_name, "flood_type": flood_type.class_name,
            "verified": True, "ai_summary": summary,
            "image_classification": image_result.model_dump() if image_result else None}


@app.get("/api/auth/authority/hotspots")
def hotspots(db: Session = Depends(get_db), user: User = Depends(authority_user)) -> dict:
    return {"hotspots": map_reports(db)}


@app.get("/api/posts")
def feed(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    return {"posts": posts_with_votes(db)}


@app.post("/api/posts/{post_id}/vote")
def vote(post_id: int, payload: VoteRequest, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    if payload.vote_type not in {"up", "down"}:
        raise HTTPException(400, {"error": "Invalid vote type"})
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(404, {"error": "Post not found"})
    if post.user_id == user.id:
        raise HTTPException(400, {"error": "Cannot vote on your own post"})
    vote_record = db.scalar(select(Vote).where(Vote.post_id == post_id, Vote.user_id == user.id))
    if vote_record:
        vote_record.vote_type = payload.vote_type
    else:
        db.add(Vote(post_id=post_id, user_id=user.id, vote_type=payload.vote_type))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(500, {"error": "Failed to record vote"})
    return {"message": "Vote recorded successfully"}


@app.get("/api/users/{user_id:int}")
def profile_by_id(user_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    profile = user_profile(db, user_id)
    if not profile:
        raise HTTPException(404, {"error": "User not found"})
    return {"user": profile}


@app.get("/api/users/{username}")
def profile_by_username(username: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    profile_user = db.scalar(select(User).where(User.username == username))
    if not profile_user:
        raise HTTPException(404, {"error": "User not found"})
    profile = user_profile(db, profile_user.id)
    return {"user": profile}


@app.get("/api/auth/authority/hotspots/stream")
def hotspot_stream(token: str | None = Query(default=None), db: Session = Depends(get_db)) -> StreamingResponse:
    query_user(db, token, "authority")
    return stream(hotspot_listeners, lambda: map_reports(db))


@app.get("/api/posts/stream")
def post_stream(token: str | None = Query(default=None), db: Session = Depends(get_db)) -> StreamingResponse:
    query_user(db, token)
    return stream(post_listeners, lambda: posts_with_votes(db))


@app.get("/api/auth/authority/reports/export")
def export_reports(format: str = Query(default="json"), token: str | None = Query(default=None),
                   db: Session = Depends(get_db)):
    query_user(db, token, "authority")
    rows = all_reports(db)
    export_rows = [{key: row.get(key) for key in ("report_id", "post_id", "title", "description", "urgency_level",
                                                   "flood_type", "confidence_score", "verified", "ai_summary",
                                                   "latitude", "longitude", "location_name", "created_at")}
                   for row in rows]
    if format.lower() == "csv":
        output = io.StringIO()
        if export_rows:
            writer = csv.DictWriter(output, fieldnames=list(export_rows[0]))
            writer.writeheader()
            writer.writerows(export_rows)
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": 'attachment; filename="reports.csv"'})
    return StreamingResponse(iter([json.dumps(export_rows, ensure_ascii=False, default=str)]), media_type="application/json",
                             headers={"Content-Disposition": 'attachment; filename="reports.json"'})


@app.post("/api/classify/text")
def classify_text(payload: TextClassificationRequest) -> dict:
    urgency = classification_service.classify_urgency(payload.text)
    flood = classification_service.classify_flood_type(payload.text)
    return {"status": "success", "data": {"text": payload.text,
                                           "urgency_classification": urgency.model_dump(),
                                           "flood_classification": flood.model_dump()}}


@app.post("/api/classify/image")
def classify_image(payload: ImageClassificationRequest) -> dict:
    if not os.path.isfile(payload.image_path):
        raise HTTPException(404, {"error": "Image file not found"})
    result = classification_service.classify_image(payload.image_path)
    return {"status": "success", "data": result.model_dump()}


def generate_summary(description: str, urgency: dict, flood: dict, location: str | None) -> str:
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        return "Issue: AI summary generation unavailable."
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={"model": "llama-3.1-70b-versatile",
                  "messages": [{"role": "system", "content": "Write a concise flood situation summary for decision-makers."},
                               {"role": "user", "content": f"Citizen text: {description}\nUrgency: {urgency.get('class_name')}\nHazard: {flood.get('class_name')}\nLocation: {location}"}],
                  "temperature": 0.2, "max_tokens": 180}, timeout=20)
        if response.ok:
            content = response.json().get("choices", [{}])[0].get("message", {}).get("content")
            if content:
                return content.strip()
    except Exception:
        logger.exception("AI summary generation failed")
    return "Issue: AI summary generation error."
