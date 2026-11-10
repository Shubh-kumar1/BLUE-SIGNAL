import csv
import hmac
import io
import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
import requests
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.concurrency import run_in_threadpool
from werkzeug.utils import secure_filename

from app.database import SessionLocal, get_db, engine
from app.config import get_cors_origins
from app.models.post import Post
from app.models.ai_job import AIJob
from app.models.report import Report
from app.models.user import User
from app.models.vote import Vote
from app.schemas import (
    CitizenPostRequest,
    ImageClassificationRequest,
    LoginRequest,
    RegisterRequest,
    TextClassificationRequest,
    VoteRequest,
)
from app.security import (
    authority_user,
    citizen_user,
    current_user,
    hash_password,
    is_legacy_password_hash,
    query_user,
    verify_password,
)
from app.services.classification_service import (
    ClassificationResult,
    ClassificationService,
    ClassificationUnavailableError,
    ImageClassificationResult,
)
from app.services.ai_job_worker import AIJobWorker
from app.services.report_service import all_reports, create_post, create_report, map_reports, posts_with_votes, user_posts, user_profile
from app.services.sse_service import (
    hotspot_listeners,
    post_listeners,
    publish,
    start_postgres_listener,
    stop_postgres_listener,
    stream,
)

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
    ai_job_worker = AIJobWorker(UPLOAD_FOLDER, process_report)
    app.state.ai_job_worker = ai_job_worker
    ai_job_worker.start()
    postgres_listener = None
    try:
        postgres_listener = start_postgres_listener(engine, refresh_streams)
        logger.info("FastAPI application started with PostgreSQL")
        yield
    finally:
        ai_job_worker.stop()
        stop_postgres_listener(postgres_listener)
        engine.dispose()


app = FastAPI(title="BlueSignal API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_headers=["Content-Type", "Authorization"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_FOLDER)), name="uploads")


@app.exception_handler(HTTPException)
async def compatibility_http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled request error for %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


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
    if payload.role == "authority":
        registration_token = os.getenv("AUTHORITY_REGISTRATION_TOKEN")
        if not registration_token or not payload.authority_registration_token or not hmac.compare_digest(
            registration_token, payload.authority_registration_token
        ):
            raise HTTPException(403, {"error": "Authority registration requires a valid invitation"})
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


@app.post("/api/auth/citizen/posts", status_code=202)
async def create_citizen_post(request: Request, user: User = Depends(citizen_user)) -> dict:
    image = None
    form = None
    if "application/json" in request.headers.get("content-type", ""):
        payload = await request.json()
    else:
        form = await request.form()
        payload = dict(form)
        image = payload.pop("image", None)
        if not isinstance(image, StarletteUploadFile):
            image = None
    try:
        report_data = CitizenPostRequest.model_validate(payload)
    except ValidationError as exc:
        if form is not None:
            await form.close()
        raise HTTPException(422, {"error": "Invalid report data"}) from exc

    title = report_data.title.strip() or "Flood Report"
    description = report_data.description.strip()
    latitude = report_data.latitude
    longitude = report_data.longitude
    location_name = report_data.location_name.strip()
    media_url = report_data.media_url

    saved_path = None
    body = None
    try:
        if image and image.filename:
            try:
                if image.content_type not in ALLOWED_IMAGE_TYPES:
                    raise HTTPException(400, {"error": "Unsupported image type"})
                body = await image.read(MAX_UPLOAD_SIZE + 1)
                if len(body) > MAX_UPLOAD_SIZE:
                    raise HTTPException(400, {"error": "Image file is too large"})
                if not image_content_matches(image.content_type, body):
                    raise HTTPException(400, {"error": "Image content does not match its file type"})
            finally:
                await image.close()
    finally:
        if form is not None:
            await form.close()

    if image and image.filename:
        filename = f"{uuid.uuid4().hex}_{secure_filename(image.filename)}"
        saved_path = UPLOAD_FOLDER / filename
        try:
            await run_in_threadpool(saved_path.write_bytes, body)
        except OSError as exc:
            saved_path.unlink(missing_ok=True)
            logger.exception("Failed to store citizen image")
            raise HTTPException(500, {"error": "Failed to store uploaded image"}) from exc
        media_url = f"/uploads/{filename}"

    post_id, report_id, post_status = await run_in_threadpool(
        persist_citizen_report,
        user.id,
        title,
        description,
        media_url,
        latitude,
        longitude,
        location_name,
        saved_path,
    )
    return {
        "message": "Report received; AI processing is underway.",
        "post_id": post_id,
        "report_id": report_id,
        "status": post_status,
        "verified": False,
        "urgency": None,
        "flood_type": None,
        "ai_summary": None,
        "image_classification": None,
    }


def image_content_matches(content_type: str, body: bytes) -> bool:
    signatures = {
        "image/jpeg": (b"\xff\xd8\xff",),
        "image/png": (b"\x89PNG\r\n\x1a\n",),
        "image/gif": (b"GIF87a", b"GIF89a"),
    }
    if content_type == "image/webp":
        return len(body) >= 12 and body.startswith(b"RIFF") and body[8:12] == b"WEBP"
    return any(body.startswith(signature) for signature in signatures.get(content_type, ()))


def csv_safe_value(value: Any) -> Any:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def persist_citizen_report(
    user_id: int,
    title: str,
    description: str,
    media_url: str | None,
    latitude: float | None,
    longitude: float | None,
    location_name: str,
    saved_path: Path | None,
) -> tuple[int, int, str]:
    with SessionLocal() as db:
        try:
            post = create_post(
                db,
                user_id,
                title,
                description,
                media_url,
                latitude,
                longitude,
                location_name,
            )
            report = create_report(
                db,
                post,
                user_id,
                None,
                None,
                None,
                None,
                latitude,
                longitude,
                location_name,
            )
            db.add(
                AIJob(
                    report_id=report.id,
                    image_filename=saved_path.name if saved_path else None,
                )
            )
            db.commit()
            db.refresh(post)
            db.refresh(report)
            return post.id, report.id, post.status
        except Exception:
            db.rollback()
            if saved_path:
                try:
                    saved_path.unlink(missing_ok=True)
                except OSError:
                    logger.exception("Failed to remove an orphaned uploaded image")
            logger.exception("Failed to persist citizen report")
            raise HTTPException(500, {"error": "Failed to save report"})


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
        queue_stream_change(db)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(500, {"error": "Failed to record vote"})
    if db.get_bind().dialect.name != "postgresql":
        updated_post = next(
            (item for item in posts_with_votes(db) if item["id"] == post_id),
            None,
        )
        publish(post_listeners, {"type": "post", "data": updated_post})
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
    db.close()
    return stream(hotspot_listeners, load_hotspot_snapshot)


@app.get("/api/posts/stream")
def post_stream(token: str | None = Query(default=None), db: Session = Depends(get_db)) -> StreamingResponse:
    query_user(db, token)
    db.close()
    return stream(post_listeners, load_post_snapshot)


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
            writer.writerows(
                {
                    key: csv_safe_value(value)
                    for key, value in row.items()
                }
                for row in export_rows
            )
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": 'attachment; filename="reports.csv"'})
    return StreamingResponse(iter([json.dumps(export_rows, ensure_ascii=False, default=str)]), media_type="application/json",
                             headers={"Content-Disposition": 'attachment; filename="reports.json"'})


@app.post("/api/classify/text")
def classify_text(payload: TextClassificationRequest) -> dict:
    try:
        urgency = classification_service.classify_urgency(payload.text)
        flood = classification_service.classify_flood_type(payload.text)
    except ClassificationUnavailableError:
        raise HTTPException(503, {"error": "AI classification is temporarily unavailable"})
    return {"status": "success", "data": {"text": payload.text,
                                           "urgency_classification": urgency.model_dump(),
                                           "flood_classification": flood.model_dump()}}


@app.post("/api/classify/image")
def classify_image(payload: ImageClassificationRequest) -> dict:
    image_path = Path(payload.image_path).resolve()
    if not image_path.is_relative_to(UPLOAD_FOLDER):
        raise HTTPException(400, {"error": "Image path must reference an uploaded image"})
    if not image_path.is_file():
        raise HTTPException(404, {"error": "Image file not found"})
    try:
        result = classification_service.classify_image(str(image_path))
    except ClassificationUnavailableError:
        raise HTTPException(503, {"error": "AI classification is temporarily unavailable"})
    return {"status": "success", "data": result.model_dump()}


def process_report(report_id: int, image_path: str | None) -> bool:
    with SessionLocal() as task_db:
        report = task_db.get(Report, report_id)
        if report is None:
            logger.error("Queued report %s no longer exists", report_id)
            return False
        post = task_db.get(Post, report.post_id)
        if post is None:
            logger.error("Queued report %s has no post", report_id)
            return False
        description = post.description
        location_name = post.location_name

    analysis_result: tuple[
        ClassificationResult,
        ClassificationResult,
        ImageClassificationResult | None,
        str,
    ] | None = None
    try:
        urgency = classification_service.classify_urgency(description)
        flood_type = classification_service.classify_flood_type(description)
        image_result = None
        if image_path:
            image_result = classification_service.classify_image(image_path)
        summary = generate_summary(
            description,
            urgency.model_dump(),
            flood_type.model_dump(),
            location_name,
        )
        analysis_result = (urgency, flood_type, image_result, summary)
    except Exception:
        logger.exception("AI processing failed for report %s", report_id)

    with SessionLocal() as task_db:
        report = task_db.get(Report, report_id)
        if report is None:
            logger.error("Queued report %s disappeared during AI processing", report_id)
            return False
        post = task_db.get(Post, report.post_id)
        if post is None:
            logger.error("Post for report %s disappeared during AI processing", report_id)
            return False

        if analysis_result is not None:
            urgency, flood_type, image_result, summary = analysis_result
            report.urgency_level = urgency.class_name
            report.flood_type = flood_type.class_name
            report.confidence_score = urgency.confidence
            report.ai_summary = summary
            report.image_classification = image_result.model_dump() if image_result else None
            report.verified = True
            post.status = "verified"
        else:
            report.verified = False
            report.ai_summary = "AI processing failed. Please review this report manually."
            post.status = "processing_failed"
        queue_stream_change(task_db)
        task_db.commit()

        if task_db.get_bind().dialect.name == "postgresql":
            return analysis_result is not None

        updated_hotspot = next(
            (item for item in map_reports(task_db) if item["id"] == report_id),
            None,
        )
        posts = posts_with_votes(task_db)
        updated_post = next((item for item in posts if item["id"] == report.post_id), None)
        publish(hotspot_listeners, {"type": "hotspot", "data": updated_hotspot})
        publish(post_listeners, {"type": "post", "data": updated_post})
        return analysis_result is not None


def queue_stream_change(db: Session) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_notify('bluesignal_changes', 'refresh')"))


def refresh_streams() -> None:
    try:
        publish(
            hotspot_listeners,
            {"type": "snapshot", "data": load_hotspot_snapshot()},
        )
        publish(
            post_listeners,
            {"type": "snapshot", "data": load_post_snapshot()},
        )
    except Exception:
        logger.exception("Failed to refresh SSE snapshots after a database notification")


def load_hotspot_snapshot() -> list[dict]:
    with SessionLocal() as snapshot_db:
        return map_reports(snapshot_db)


def load_post_snapshot() -> list[dict]:
    with SessionLocal() as snapshot_db:
        return posts_with_votes(snapshot_db)


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
