import csv
import io
import json
import logging
import os
import queue
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
import requests
from fastapi import Body, Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from werkzeug.utils import secure_filename

import database
from app import security

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required")
if len(SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY must contain at least 32 characters")
security.SECRET_KEY = SECRET_KEY

UPLOAD_FOLDER = Path(os.getenv("UPLOAD_FOLDER", "uploads"))
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MAX_UPLOAD_SIZE = 10 * 1024 * 1024

text_classifier = None
flood_classifier = None
image_classifier = None
geolocator = None
hotspot_listeners: list[queue.Queue] = []
post_listeners: list[queue.Queue] = []


class ClassificationResult(BaseModel):
    class_name: str
    confidence: float


class ImageClassificationResult(BaseModel):
    type: str
    confidence: float
    prediction: str


def initialize_models() -> bool:
    global text_classifier, flood_classifier, image_classifier, geolocator
    if os.getenv("LIGHTWEIGHT_MODE", "false").lower() == "true":
        logger.info("LIGHTWEIGHT_MODE enabled - skipping AI model loading")
        return True
    try:
        import torch
        from transformers import pipeline
        from geopy.geocoders import Nominatim

        torch.set_num_threads(max(1, torch.get_num_threads()))
        text_classifier = pipeline("zero-shot-classification", model="typeform/distilbert-base-uncased-mnli")
        flood_classifier = pipeline("zero-shot-classification", model="typeform/distilbert-base-uncased-mnli")
        image_classifier = pipeline("zero-shot-image-classification", model="openai/clip-vit-base-patch32")
        geolocator = Nominatim(user_agent="flood_detection_app/1.0")
        logger.info("All models loaded successfully")
        return True
    except Exception as exc:
        logger.error("Error initializing models: %s", exc)
        return False


def classify_urgency(text: str) -> ClassificationResult:
    try:
        if text_classifier is None:
            raise RuntimeError("text_classifier not initialized")
        result = text_classifier(text, ["Urgent Panic", "Alert Caution", "Safe Normal"])
        return ClassificationResult(class_name=result["labels"][0], confidence=round(float(result["scores"][0]), 3))
    except Exception as exc:
        logger.error("Error in urgency classification: %s", exc)
        return ClassificationResult(class_name="Pipeline Error", confidence=0.0)


def classify_flood_type(text: str) -> ClassificationResult:
    try:
        if flood_classifier is None:
            raise RuntimeError("flood_classifier not initialized")
        labels = [
            "Urban Flooding", "River Overflow", "Flash Flood", "Drainage Failure",
            "Heavy Rain Accumulation", "Dam or Levee Breach", "Sewer Backup",
            "Groundwater Rise", "Landslide-Induced Flooding", "Coastal Storm Surge",
            "Other/Unknown Flood",
        ]
        result = flood_classifier(text, labels)
        return ClassificationResult(class_name=result["labels"][0], confidence=round(float(result["scores"][0]), 3))
    except Exception as exc:
        logger.error("Error in flood classification: %s", exc)
        return ClassificationResult(class_name="Pipeline Error", confidence=0.0)


def classify_flood_image(image_path: str) -> ImageClassificationResult:
    try:
        if image_classifier is None:
            raise RuntimeError("image_classifier not initialized")
        labels = [
            "severe urban flooding with shoulder-level stagnant water on streets",
            "severe urban flooding with streets and vehicles submerged",
            "moderate street flooding with pooled rainwater",
            "flash flood with rapid water flow in streets",
            "river overflow flooding nearby neighborhoods",
            "drainage failure causing waterlogging",
            "heavy rain accumulation on roads and low-lying areas",
            "dam or levee breach with downstream flooding",
            "sewer backup causing localized flooding",
            "groundwater rise flooding basements",
            "landslide-induced flooding with mud and water",
            "coastal storm surge flooding coastal roads",
            "normal street scene with no flooding",
        ]
        result = image_classifier(image_path, candidate_labels=labels)
        mapping = {
            "severe urban flooding with shoulder-level stagnant water on streets": "Urban Flooding (Severe, Stagnant)",
            "severe urban flooding with streets and vehicles submerged": "Urban Flooding (Severe)",
            "moderate street flooding with pooled rainwater": "Urban Flooding (Moderate)",
            "flash flood with rapid water flow in streets": "Flash Flood",
            "river overflow flooding nearby neighborhoods": "River Overflow",
            "drainage failure causing waterlogging": "Drainage Failure",
            "heavy rain accumulation on roads and low-lying areas": "Heavy Rain Accumulation",
            "dam or levee breach with downstream flooding": "Dam or Levee Breach",
            "sewer backup causing localized flooding": "Sewer Backup",
            "groundwater rise flooding basements": "Groundwater Rise",
            "landslide-induced flooding with mud and water": "Landslide-Induced Flooding",
            "coastal storm surge flooding coastal roads": "Coastal Storm Surge",
            "normal street scene with no flooding": "No Flooding",
        }
        prediction = result[0]["label"]
        return ImageClassificationResult(type=mapping.get(prediction, "Unknown"), confidence=round(float(result[0]["score"]), 3), prediction=prediction)
    except Exception as exc:
        logger.error("Error in image classification: %s", exc)
        return ImageClassificationResult(type="Pipeline Error", confidence=0.0, prediction="error")


def generate_report_summary(data: dict[str, Any]) -> str:
    try:
        if GROQ_API_KEY:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.1-70b-versatile",
                    "messages": [
                        {"role": "system", "content": "You are a disaster response analyst. Write a concise flood situation summary with severity, impact, and immediate actions."},
                        {"role": "user", "content": f"Citizen text: {data.get('text_report', '')}\nUrgency: {data.get('urgency_classification', {}).get('class_name', 'Unknown')}\nHazard: {data.get('flood_classification', {}).get('class_name', 'Unknown')}\nLocation: {data.get('location', {}).get('address', 'Unknown')}"},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 180,
                },
                timeout=20,
            )
            if response.ok and response.json().get("choices", [{}])[0].get("message", {}).get("content"):
                return response.json()["choices"][0]["message"]["content"].strip()
        return "Issue: AI summary generation unavailable."
    except Exception as exc:
        logger.error("Report generation error: %s", exc)
        return "Issue: AI summary generation error."


def notify_queues(listeners: list[queue.Queue], payload: dict[str, Any]) -> None:
    for listener in list(listeners):
        try:
            listener.put_nowait(payload)
        except queue.Full:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    if os.getenv("LOAD_AI_MODELS", "false").lower() == "true":
        initialize_models()
    else:
        logger.info("AI models disabled for lightweight startup")
    yield


app = FastAPI(title="BlueSignal API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://localhost:3000", "http://localhost:3001",
        "https://blue-signal.vercel.app",
        "https://blue-signal-1648rv5mv-shubhamraj9493-9503s-projects.vercel.app",
    ],
    allow_headers=["Content-Type", "Authorization"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_FOLDER)), name="uploads")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "success", "message": "API is running"}


@app.post("/api/auth/register", status_code=201)
def register(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    username = payload.get("username")
    email = payload.get("email")
    password = payload.get("password")
    role = payload.get("role", "citizen")
    full_name = payload.get("full_name", "")
    if not all(isinstance(value, str) and value.strip() for value in (username, email, password, role)):
        raise HTTPException(400, {"error": "Username, email, password, and role are required"})
    if role not in ("citizen", "authority"):
        raise HTTPException(400, {"error": "Role must be citizen or authority"})
    if len(username.strip()) > 64 or len(email.strip()) > 254:
        raise HTTPException(400, {"error": "Username or email is too long"})
    if len(password) < 6 or len(password) > 1024:
        raise HTTPException(400, {"error": "Password must be at least 6 characters long"})
    username = username.strip()
    email = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, {"error": "A valid email address is required"})
    full_name = full_name.strip() if isinstance(full_name, str) else ""
    try:
        if database.get_user_by_username(username):
            raise HTTPException(409, {"error": "Username already exists"})
        if database.get_user_by_email(email):
            raise HTTPException(409, {"error": "Email already exists"})
        user_id = database.create_user(username, email, security.hash_password(password), role, full_name)
        return {"message": "User registered", "user_id": user_id}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Registration failed")
        raise HTTPException(500, {"error": "Registration failed"})


@app.post("/api/auth/login")
def login(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    username = payload.get("username")
    password = payload.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        raise HTTPException(400, {"error": "Username and password are required"})
    user = database.get_user_by_username(username.strip())
    if not user or not security.verify_password(password, user["password"]):
        raise HTTPException(401, {"error": "Invalid credentials"})
    if security.is_legacy_password_hash(user["password"]):
        database.update_user_password(user["id"], security.hash_password(password))
    token = jwt.encode({"username": user["username"], "role": user["role"], "exp": datetime.now(timezone.utc) + timedelta(hours=24)}, SECRET_KEY, algorithm="HS256")
    return {"token": token, "user": {"id": user["id"], "username": user["username"], "role": user["role"], "full_name": user["full_name"]}}


@app.post("/api/auth/citizen/posts")
async def create_post(
    request: Request,
    image: UploadFile | None = File(default=None),
    user: dict = Depends(security.citizen_user),
) -> dict[str, Any]:
    if "application/json" in (request.headers.get("content-type") or ""):
        payload = await request.json()
        title = payload.get("title", "Flood Report")
        description = payload.get("description", "")
        latitude_value = payload.get("latitude")
        longitude_value = payload.get("longitude")
        location_name = payload.get("location_name", "Unknown Location")
        media_url = payload.get("media_url")
    else:
        form = await request.form()
        title = form.get("title") or "Flood Report"
        description = form.get("description") or ""
        latitude_value = float(form["latitude"]) if form.get("latitude") else None
        longitude_value = float(form["longitude"]) if form.get("longitude") else None
        location_name = form.get("location_name") or "Unknown Location"
        media_url = None

    saved_path = None
    if image is not None and image.filename:
        if image.content_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
            raise HTTPException(400, {"error": "Unsupported image type"})
        body = await image.read(MAX_UPLOAD_SIZE + 1)
        if len(body) > MAX_UPLOAD_SIZE:
            raise HTTPException(400, {"error": "Image file is too large"})
        filename = f"{uuid.uuid4().hex}_{secure_filename(image.filename)}"
        saved_path = UPLOAD_FOLDER / filename
        saved_path.write_bytes(body)
        media_url = f"/uploads/{filename}"

    urgency = classify_urgency(description)
    flood_type = classify_flood_type(description)
    post_id = database.create_post(user["id"], title, description, media_url, latitude_value, longitude_value, location_name)
    if not post_id:
        raise HTTPException(500, {"error": "Failed to create post"})
    summary = generate_report_summary({"text_report": description, "flood_classification": flood_type.model_dump(), "urgency_classification": urgency.model_dump(), "location": {"address": location_name}})
    image_result = classify_flood_image(str(saved_path)) if saved_path else None
    report_id = database.create_report(post_id, user["id"], urgency.class_name, flood_type.class_name, urgency.confidence, True, summary, latitude_value, longitude_value, location_name)
    database.update_post_status(post_id, "verified")

    notify_queues(hotspot_listeners, {"type": "hotspot", "data": {"id": report_id, "post_id": post_id, "title": title, "description": description, "urgency_level": urgency.class_name, "flood_type": flood_type.class_name, "ai_summary": summary, "latitude": latitude_value, "longitude": longitude_value, "location_name": location_name, "status": "verified"}})
    notify_queues(post_listeners, {"type": "post", "data": database.get_post_by_id(post_id)})
    return {"message": "Post created successfully", "post_id": post_id, "report_id": report_id, "urgency": urgency.class_name, "flood_type": flood_type.class_name, "verified": True, "ai_summary": summary, "image_classification": image_result.model_dump() if image_result else None}


@app.get("/api/auth/citizen/posts")
def citizen_posts(user: dict = Depends(security.citizen_user)) -> dict[str, Any]:
    return {"posts": database.get_posts_by_user(user["id"])}


@app.get("/api/auth/authority/hotspots")
def hotspots(user: dict = Depends(security.authority_user)) -> dict[str, Any]:
    return {"hotspots": database.get_reports_for_map()}


@app.get("/api/posts")
def posts(user: dict = Depends(security.current_user)) -> dict[str, Any]:
    return {"posts": database.get_all_posts_with_votes()}


@app.get("/api/auth/authority/reports/export")
def export_reports(token: str | None = Query(default=None), format: str = Query(default="json")):
    user = security.query_user(token, "authority")
    rows = []
    for report in database.get_all_reports():
        rows.append({key: report.get(key) for key in ("id", "post_id", "title", "description", "urgency_level", "flood_type", "confidence_score", "verified", "ai_summary", "latitude", "longitude", "location_name", "created_at")})
        rows[-1]["report_id"] = rows[-1].pop("id")
    if format.lower() == "csv":
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        from fastapi.responses import Response
        return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="reports.csv"'})
    from fastapi.responses import Response
    return Response(content=json.dumps(rows, ensure_ascii=False), media_type="application/json", headers={"Content-Disposition": 'attachment; filename="reports.json"'})


def stream_response(listeners: list[queue.Queue], snapshot) -> StreamingResponse:
    listener_queue: queue.Queue = queue.Queue()

    def generator():
        listeners.append(listener_queue)
        try:
            yield f"data: {json.dumps({'type': 'snapshot', 'data': snapshot()})}\n\n"
            while True:
                try:
                    message = listener_queue.get(timeout=25)
                    yield f"data: {json.dumps(message)}\n\n"
                except queue.Empty:
                    yield 'data: {"type": "keepalive"}\n\n'
        finally:
            try:
                listeners.remove(listener_queue)
            except ValueError:
                pass

    return StreamingResponse(generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})


@app.get("/api/auth/authority/hotspots/stream")
def hotspots_stream(token: str | None = Query(default=None)) -> StreamingResponse:
    security.query_user(token, "authority")
    return stream_response(hotspot_listeners, database.get_reports_for_map)


@app.get("/api/posts/stream")
def posts_stream(token: str | None = Query(default=None)) -> StreamingResponse:
    security.query_user(token)
    return stream_response(post_listeners, database.get_all_posts_with_votes)


@app.post("/api/posts/{post_id}/vote")
def vote(post_id: int, payload: dict[str, Any] = Body(...), user: dict = Depends(security.current_user)) -> dict[str, str]:
    vote_type = payload.get("vote_type")
    if vote_type not in ("up", "down"):
        raise HTTPException(400, {"error": "Invalid vote type"})
    post = database.get_post_by_id(post_id)
    if post and post["user_id"] == user["id"]:
        raise HTTPException(400, {"error": "Cannot vote on your own post"})
    if not database.vote_post(post_id, user["id"], vote_type):
        raise HTTPException(500, {"error": "Failed to record vote"})
    return {"message": "Vote recorded successfully"}


def public_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {key: profile[key] for key in ("username", "full_name", "authenticity_score", "created_at", "posts") if key in profile}


@app.get("/api/users/{username}")
def user_profile(username: str, user: dict = Depends(security.current_user)) -> dict[str, Any]:
    profile_user = database.get_user_by_username(username)
    if not profile_user:
        raise HTTPException(404, {"error": "User not found"})
    profile = database.get_user_profile(profile_user["id"])
    if not profile:
        raise HTTPException(500, {"error": "Failed to load profile"})
    return {"user": public_profile(profile)}


@app.get("/api/users/{user_id:int}")
def user_profile_by_id(user_id: int, user: dict = Depends(security.current_user)) -> dict[str, Any]:
    profile = database.get_user_profile(user_id)
    if not profile:
        raise HTTPException(404, {"error": "User not found"})
    return {"user": public_profile(profile)}


@app.post("/api/classify/text")
def classify_text(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    if not payload.get("text"):
        raise HTTPException(400, {"error": "Text field is required"})
    text = payload["text"]
    return {"status": "success", "data": {"text": text, "urgency_classification": classify_urgency(text).model_dump(), "flood_classification": classify_flood_type(text).model_dump()}}


@app.post("/api/classify/image")
def classify_image(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    image_path = payload.get("image_path") if payload else None
    if not image_path:
        raise HTTPException(400, {"error": "image_path field is required"})
    if not os.path.exists(image_path):
        raise HTTPException(404, {"error": "Image file not found"})
    return {"status": "success", "data": classify_flood_image(image_path).model_dump()}


@app.get("/api/test")
def test_route() -> dict[str, Any]:
    return {"status": "success", "message": "FastAPI Backend is working!", "data": {"timestamp": datetime.now().isoformat()}}
