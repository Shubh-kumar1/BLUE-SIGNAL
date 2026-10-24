from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import json
import os
from geopy.geocoders import Nominatim
import requests
# from phi.agent import Agent
# from phi.model.google import Gemini
from datetime import datetime, timedelta, timezone
import logging
import re
import sqlite3
import hmac
from pydantic import BaseModel, ValidationError
from typing import Dict, List, Optional, Union
import traceback
import jwt
import uuid
from werkzeug.utils import secure_filename
import time
import queue
import hashlib
import csv
import io
from werkzeug.security import check_password_hash, generate_password_hash

import database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
secret_key = os.getenv('SECRET_KEY')
if not secret_key:
    raise RuntimeError('SECRET_KEY environment variable is required')
if len(secret_key) < 32:
    raise RuntimeError('SECRET_KEY must contain at least 32 characters')
app.config['SECRET_KEY'] = secret_key

CORS(
    app,
    origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:3001",
        "https://blue-signal.vercel.app",
        "https://blue-signal-1648rv5mv-shubhamraj9493-9503s-projects.vercel.app"
    ],
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]

)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.static_folder = 'uploads'
app.add_url_rule('/uploads/<path:filename>', endpoint='uploaded_file', view_func=lambda filename: app.send_static_file(filename))

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "get your own api key")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "get your own api key")

logger.info(f"Google API Key loaded: {'Yes' if GOOGLE_API_KEY else 'No'}")
logger.info(f"Groq API Key loaded: {'Yes' if GROQ_API_KEY else 'No'}")

class Coordinates(BaseModel):
    latitude: float
    longitude: float

class CitizenData(BaseModel):
    user_id: str
    text_report: str
    image: Optional[str] = None
    coordinates: Coordinates
    timestamp: str

class SocialMediaData(BaseModel):
    date: str
    text: str
    media_urls: List[str] = []

class ClassificationResult(BaseModel):
    class_name: str
    confidence: float

class ImageClassificationResult(BaseModel):
    type: str
    confidence: float
    prediction: str

class LocationInfo(BaseModel):
    address: str
    latitude: float
    longitude: float

class ProcessedCitizenData(BaseModel):
    user_id: str
    text_report: str
    image: Optional[str]
    location: LocationInfo
    timestamp: str
    urgency_classification: ClassificationResult
    flood_classification: ClassificationResult
    image_classification: ImageClassificationResult
    verification_status: str
    analysis_report: str

class APIResponse(BaseModel):
    status: str
    message: Optional[str] = None
    data: Optional[Dict] = None
    error: Optional[str] = None

text_classifier = None
flood_classifier = None
image_classifier = None
geolocator = None
report_agent = None
verification_agent = None

hotspot_listeners = []
post_listeners = []

def hash_password(password: str) -> str:
    return generate_password_hash(password)

def verify_password(password: str, hashed: str) -> bool:
    if hashed.startswith(('scrypt:', 'pbkdf2:')):
        return check_password_hash(hashed, password)
    if re.fullmatch(r'[a-fA-F0-9]{64}', hashed):
        legacy_hash = hashlib.sha256(password.encode()).hexdigest()
        return hmac.compare_digest(legacy_hash, hashed)
    return False

def is_legacy_password_hash(hashed: str) -> bool:
    return re.fullmatch(r'[a-fA-F0-9]{64}', hashed) is not None

def initialize_models():
    global text_classifier, flood_classifier, image_classifier, geolocator, report_agent, verification_agent

    if os.getenv("LIGHTWEIGHT_MODE", "false").lower() == "true":
        logger.info("LIGHTWEIGHT_MODE enabled - skipping AI model loading")
        return True
    try:
        import torch
        from transformers import pipeline

        logger.info("Loading AI models...")
        try:
            torch.set_num_threads(max(1, torch.get_num_threads()))
        except Exception:
            pass
        
        text_classifier = pipeline(
            "zero-shot-classification",
            model="typeform/distilbert-base-uncased-mnli"
        )
        flood_classifier = pipeline(
            "zero-shot-classification",
            model="typeform/distilbert-base-uncased-mnli"
        )
        image_classifier = pipeline(
            "zero-shot-image-classification",
            model="openai/clip-vit-base-patch32"
        )
        geolocator = Nominatim(user_agent="flood_detection_app/1.0")
        
        # Gemini agent initialization commented out - requires phi-agent package
        # gemini_model = Gemini(id="gemini-1.5-flash", api_key=GOOGLE_API_KEY)
        # report_agent = Agent(...)
        # verification_agent = Agent(...)
        
        report_agent = None
        verification_agent = None
        
        logger.info("All models loaded successfully!")
        return True
    except Exception as e:
        logger.error(f"Error initializing models: {str(e)}")
        return False

def classify_urgency(text: str) -> ClassificationResult:
    try:
        if text_classifier is None:
            raise RuntimeError("text_classifier not initialized")
        labels = ["Urgent Panic", "Alert Caution", "Safe Normal"]
        result = text_classifier(text, labels)
        return ClassificationResult(
            class_name=result['labels'][0],
            confidence=round(float(result['scores'][0]), 3)
        )
    except Exception as e:
        logger.error(f"Error in urgency classification: {str(e)}")
        return ClassificationResult(class_name="Pipeline Error", confidence=0.0)

def classify_flood_type(text: str) -> ClassificationResult:
    try:
        if flood_classifier is None:
            raise RuntimeError("flood_classifier not initialized")
        labels = [
            "Urban Flooding",
            "River Overflow",
            "Flash Flood",
            "Drainage Failure",
            "Heavy Rain Accumulation",
            "Dam or Levee Breach",
            "Sewer Backup",
            "Groundwater Rise",
            "Landslide-Induced Flooding",
            "Coastal Storm Surge",
            "Other/Unknown Flood"
        ]
        result = flood_classifier(text, labels)
        return ClassificationResult(
            class_name=result['labels'][0],
            confidence=round(float(result['scores'][0]), 3)
        )
    except Exception as e:
        logger.error(f"Error in flood classification: {str(e)}")
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
            "normal street scene with no flooding"
        ]
        result = image_classifier(image_path, candidate_labels=labels)
        class_mapping = {
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
            "normal street scene with no flooding": "No Flooding"
        }
        top_prediction = result[0]['label']
        confidence = result[0]['score']
        return ImageClassificationResult(
            type=class_mapping.get(top_prediction, "Unknown"),
            confidence=round(float(confidence), 3),
            prediction=top_prediction
        )
    except Exception as e:
        logger.error(f"Error in image classification: {str(e)}")
        return ImageClassificationResult(type="Pipeline Error", confidence=0.0, prediction="error")

def get_location_from_coordinates(lat: float, lon: float) -> Optional[LocationInfo]:
    try:
        location = geolocator.reverse(f"{lat},{lon}")
        if location:
            return LocationInfo(
                address=location.address,
                latitude=location.latitude,
                longitude=location.longitude
            )
        return None
    except Exception as e:
        logger.error(f"Geocoding error: {e}")
        return None

def process_social_media_data(tweets_data: List[Dict]) -> Optional[Dict]:
    try:
        if not tweets_data:
            return None
        
        latest_tweet = tweets_data[0]
        
        urgency_result = classify_urgency(latest_tweet['text'])
        flood_result = classify_flood_type(latest_tweet['text'])
        
        return {
            'text': latest_tweet['text'],
            'date': latest_tweet['date'],
            'urgency': urgency_result.model_dump(),
            'flood_type': flood_result.model_dump(),
            'media_count': len(latest_tweet.get('media_urls', []))
        }
    except Exception as e:
        logger.error(f"Error processing social media data: {str(e)}")
        return None

def verify_data_with_agent(citizen_data: Dict, social_data: Dict) -> bool:
    try:
        verification_prompt = f"""
        Citizen Report: {citizen_data['text_report']}
        Citizen Flood Classification: {citizen_data['flood_classification']['class_name']} (confidence: {citizen_data['flood_classification']['confidence']})
        Citizen Urgency: {citizen_data['urgency_classification']['class_name']} (confidence: {citizen_data['urgency_classification']['confidence']})
        
        Social Media Report: {social_data['text']}
        Social Media Flood Classification: {social_data['flood_type']['class_name']} (confidence: {social_data['flood_type']['confidence']})
        Social Media Urgency: {social_data['urgency']['class_name']} (confidence: {social_data['urgency']['confidence']})
        
        Consider that both reports might be referring to the same flood event even if classified differently. 
        For example, urban flooding and street flooding can refer to the same event.
        """
        
        if not verification_agent:
            return fallback_verification(citizen_data, social_data)
        
        response = verification_agent.run(verification_prompt)
        verification_text = str(response.content).strip()
        logger.info(f"Verification agent response: {verification_text}")
        
        from transformers import pipeline
        verification_classifier = pipeline("zero-shot-classification", 
                                        model="typeform/distilbert-base-uncased-mnli")
        labels = ["positive agreement", "negative disagreement"]
        classification_result = verification_classifier(verification_text, labels)
        
        is_positive = classification_result['labels'][0] == "positive agreement"
        confidence = classification_result['scores'][0]
        logger.info(f"Verification classification: {classification_result['labels'][0]} (confidence: {confidence:.3f})")
        
        return is_positive
        
    except Exception as e:
        logger.error(f"Verification agent error: {e}")
        return False

def generate_report_with_agent(citizen_data: Dict) -> str:
    try:
        if GROQ_API_KEY:
            try:
                headers = {
                    'Authorization': f'Bearer {GROQ_API_KEY}',
                    'Content-Type': 'application/json'
                }
                system_prompt = (
                    "You are a disaster response analyst. Write a concise (≤90 words), "
                    "professional flood situation summary with: 1) Situation & severity, 2) Likely impact, "
                    "3) Immediate recommended actions. Avoid fluff, no emojis."
                )
                user_prompt = (
                    f"Citizen text: {citizen_data.get('text_report','')}\n"
                    f"Urgency: {citizen_data.get('urgency_classification',{}).get('class_name','Unknown')}\n"
                    f"Hazard: {citizen_data.get('flood_classification',{}).get('class_name','Unknown')}\n"
                    f"Location: {citizen_data.get('location',{}).get('address','Unknown')}\n"
                    "Summarize clearly for decision-makers."
                )
                payload = {
                    'model': 'llama-3.1-70b-versatile',
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt}
                    ],
                    'temperature': 0.2,
                    'max_tokens': 180
                }
                resp = requests.post(
                    'https://api.groq.com/openai/v1/chat/completions',
                    headers=headers,
                    json=payload,
                    timeout=20
                )
                if resp.ok:
                    data = resp.json()
                    content = data.get('choices',[{}])[0].get('message',{}).get('content','')
                    if content:
                        return content.strip()
                    logger.warning('Groq response missing content, falling back.')
                else:
                    logger.error(f"Groq API error {resp.status_code}: {resp.text}")
            except Exception as ge:
                    logger.error(f"Groq call failed: {ge}")

        if GOOGLE_API_KEY:
            try:
                from google import genai
                from google.genai import types as genai_types

                client = genai.Client(api_key=GOOGLE_API_KEY)
                system_instruction = (
                    "You are a disaster response analyst. Write a concise (≤90 words), "
                    "professional flood situation summary with: 1) Situation & severity, 2) Likely impact, "
                    "3) Immediate recommended actions. Avoid fluff, no emojis."
                )
                contents = (
                    f"Citizen text: {citizen_data.get('text_report','')}\n"
                    f"Urgency: {citizen_data.get('urgency_classification',{}).get('class_name','Unknown')}\n"
                    f"Hazard: {citizen_data.get('flood_classification',{}).get('class_name','Unknown')}\n"
                    f"Location: {citizen_data.get('location',{}).get('address','Unknown')}\n"
                    "Summarize clearly for decision-makers."
                )
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    config=genai_types.GenerateContentConfig(system_instruction=system_instruction),
                    contents=contents
                )
                txt = getattr(response, 'text', None)
                if txt:
                    return txt.strip()
                logger.warning('Gemini client response missing text, falling back.')
            except Exception as ge:
                logger.error(f"Gemini client call failed: {ge}")

        return "Issue: AI summary generation unavailable."
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        return "Issue: AI summary generation error."

def fallback_verification(citizen_data: Dict, social_data: Dict) -> bool:
    try:
        citizen_text = citizen_data['text_report'].lower()
        social_text = social_data['text'].lower()
        
        flood_keywords = ['flood', 'flooding', 'water', 'inundation', 'submerged', 'overflow']
        street_keywords = ['street', 'road', 'sidewalk', 'pavement', 'highway']
        building_keywords = ['building', 'house', 'shop', 'office', 'structure']
        
        citizen_has_flood = any(keyword in citizen_text for keyword in flood_keywords)
        citizen_has_street = any(keyword in citizen_text for keyword in street_keywords)
        citizen_has_building = any(keyword in citizen_text for keyword in building_keywords)
        
        social_has_flood = any(keyword in social_text for keyword in flood_keywords)
        social_has_street = any(keyword in social_text for keyword in street_keywords)
        social_has_building = any(keyword in social_text for keyword in building_keywords)
        
        citizen_urgency = citizen_data['urgency_classification']['class_name']
        social_urgency = social_data['urgency']['class_name']
        urgency_match = citizen_urgency in ['Severe Flooding', 'Moderate Waterlogging'] and social_urgency in ['Severe Flooding', 'Moderate Waterlogging']
        
        citizen_flood = citizen_data['flood_classification']['class_name']
        social_flood = social_data['flood_type']['class_name']
        
        related_floods = {
            'Urban Flooding': ['Street Flooding', 'Drainage Failure', 'Heavy Rain Accumulation'],
            'Street Flooding': ['Urban Flooding', 'Drainage Failure', 'Heavy Rain Accumulation'],
            'River Overflow': ['Flash Flood', 'Heavy Rain Accumulation'],
            'Flash Flood': ['River Overflow', 'Heavy Rain Accumulation']
        }
        
        flood_match = (
            citizen_flood == social_flood or
            citizen_flood in related_floods.get(social_flood, []) or
            social_flood in related_floods.get(citizen_flood, [])
        )
        
        keyword_match = (
            (citizen_has_flood and social_has_flood) or
            (citizen_has_street and social_has_street) or
            (citizen_has_building and social_has_building)
        )
        
        verification_result = (flood_match or keyword_match) and urgency_match
        logger.info(f"Fallback verification - Flood: {flood_match}, Keyword: {keyword_match}, Urgency: {urgency_match}")
        
        return verification_result
        
    except Exception as e:
        logger.error(f"Fallback verification error: {e}")
        return False

def token_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        authorization = request.headers.get('Authorization', '')
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return jsonify({'error': 'No token provided'}), 401
        try:
            data = jwt.decode(parts[1], app.config['SECRET_KEY'], algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        if not isinstance(data, dict) or not isinstance(data.get('username'), str):
            return jsonify({'error': 'Invalid token'}), 401

        try:
            current_user = database.get_user_by_username(data['username'])
        except sqlite3.Error:
            logger.exception('Database error while validating authenticated user')
            return jsonify({'error': 'Authentication service temporarily unavailable'}), 503

        if not current_user:
            return jsonify({'error': 'User not found'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'success', 'message': 'API is running'})

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'A JSON request body is required'}), 400

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'citizen')
    full_name = data.get('full_name', '')

    if not all(isinstance(value, str) and value.strip() for value in (username, email, password, role)):
        return jsonify({'error': 'Username, email, password, and role are required'}), 400
    if role not in ('citizen', 'authority'):
        return jsonify({'error': 'Role must be citizen or authority'}), 400
    if len(username.strip()) > 64 or len(email.strip()) > 254:
        return jsonify({'error': 'Username or email is too long'}), 400
    if len(password) < 6 or len(password) > 1024:
        return jsonify({'error': 'Password must be at least 6 characters long'}), 400
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email.strip()):
        return jsonify({'error': 'A valid email address is required'}), 400

    username = username.strip()
    email = email.strip().lower()
    full_name = full_name.strip() if isinstance(full_name, str) else ''

    try:
        if database.get_user_by_username(username):
            return jsonify({'error': 'Username already exists'}), 409
        if database.get_user_by_email(email):
            return jsonify({'error': 'Email already exists'}), 409

        user_id = database.create_user(username, email, hash_password(password), role, full_name)
        return jsonify({'message': 'User registered', 'user_id': user_id}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username or email already exists'}), 409
    except sqlite3.Error:
        logger.exception('Database error during registration')
        return jsonify({'error': 'Registration is temporarily unavailable'}), 500
    except Exception:
        logger.exception('Unexpected error during registration')
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'A JSON request body is required'}), 400

    username = data.get('username')
    password = data.get('password')
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    
    try:
        user = database.get_user_by_username(username.strip())
        if not user or not verify_password(password, user['password']):
            return jsonify({'error': 'Invalid credentials'}), 401

        if is_legacy_password_hash(user['password']):
            database.update_user_password(user['id'], hash_password(password))

        token = jwt.encode({
            'username': user['username'],
            'role': user['role'],
            'exp': datetime.now(timezone.utc) + timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')

        return jsonify({
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'role': user['role'],
                'full_name': user['full_name']
            }
        })
    except sqlite3.Error:
        logger.exception('Database error during login')
        return jsonify({'error': 'Login is temporarily unavailable'}), 503
    except Exception:
        logger.exception('Unexpected error during login')
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/auth/citizen/posts', methods=['POST'])
@token_required
def create_post(current_user):
    if current_user['role'] != 'citizen':
        return jsonify({'error': 'Unauthorized'}), 403
    
    media_url = None
    image_path = None
    if request.content_type and 'multipart/form-data' in request.content_type:
        form = request.form
        title = form.get('title', 'Flood Report')
        description = form.get('description', '')
        latitude = float(form.get('latitude')) if form.get('latitude') else None
        longitude = float(form.get('longitude')) if form.get('longitude') else None
        location_name = form.get('location_name', 'Unknown Location')
        file = request.files.get('image')
        if file and file.filename:
            filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(save_path)
            image_path = save_path
            media_url = f"/uploads/{filename}"
    else:
        data = request.json or {}
        title = data.get('title', 'Flood Report')
        description = data.get('description', '')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        location_name = data.get('location_name', 'Unknown Location')
        media_url = data.get('media_url')
    
    logger.info("Starting AI processing pipeline...")
    
    urgency_result = classify_urgency(description)
    flood_result = classify_flood_type(description)
    
    logger.info(f"Text classification - Urgency: {urgency_result.class_name}, Flood: {flood_result.class_name}")
    
    post_id = database.create_post(
        current_user['id'], title, description, media_url, latitude, longitude, location_name
    )
    
    if not post_id:
        return jsonify({'error': 'Failed to create post'}), 500
    
    verified = True
    ai_summary = generate_report_with_agent({
        'text_report': description,
        'flood_classification': flood_result.model_dump(),
        'urgency_classification': urgency_result.model_dump(),
        'location': {'address': location_name}
    })
    image_result = None
    if image_path:
        image_result = classify_flood_image(image_path)
    
    report_id = database.create_report(
        post_id, current_user['id'], urgency_result.class_name, 
        flood_result.class_name, urgency_result.confidence, verified, 
        ai_summary, latitude, longitude, location_name
    )
    
    database.update_post_status(post_id, 'verified' if verified else 'pending')
    
    logger.info(f"AI processing complete - Post ID: {post_id}, Report ID: {report_id}")

    try:
        payload = {
            'type': 'hotspot',
            'data': {
                'id': report_id,
                'post_id': post_id,
                'title': title,
                'description': description,
                'urgency_level': urgency_result.class_name,
                'flood_type': flood_result.class_name,
                'ai_summary': ai_summary,
                'latitude': latitude,
                'longitude': longitude,
                'location_name': location_name,
                'status': 'verified' if verified else 'pending'
            }
        }
        for q in list(hotspot_listeners):
            try:
                q.put_nowait(payload)
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Error notifying listeners: {e}")
    
    try:
        post_payload = {
            'type': 'post',
            'data': database.get_post_by_id(post_id)
        }
        for q in list(post_listeners):
            try:
                q.put_nowait(post_payload)
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Error notifying post listeners: {e}")

    return jsonify({
        'message': 'Post created successfully',
        'post_id': post_id,
        'report_id': report_id,
        'urgency': urgency_result.class_name,
        'flood_type': flood_result.class_name,
        'verified': verified,
        'ai_summary': ai_summary,
        'image_classification': image_result.model_dump() if image_result else None
    })

@app.route('/api/auth/citizen/posts', methods=['GET'])
@token_required
def get_citizen_posts(current_user):
    if current_user['role'] != 'citizen':
        return jsonify({'error': 'Unauthorized'}), 403
    
    posts = database.get_posts_by_user(current_user['id'])
    return jsonify({'posts': posts})

@app.route('/api/auth/authority/hotspots', methods=['GET'])
@token_required
def get_hotspots(current_user):
    if current_user['role'] != 'authority':
        return jsonify({'error': 'Unauthorized'}), 403
    reports = database.get_reports_for_map()
    return jsonify({'hotspots': reports})

@app.route('/api/auth/authority/hotspots/stream', methods=['GET'])
def hotspots_stream():
    """SSE stream for real-time hotspots. Expects JWT as query param 'token'."""
    token = request.args.get('token')
    if not token:
        return jsonify({'error': 'No token provided'}), 401
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = database.get_user_by_username(data['username'])
        if not user or user['role'] != 'authority':
            return jsonify({'error': 'Unauthorized'}), 403
    except Exception:
        return jsonify({'error': 'Invalid token'}), 401

    def event_stream():
        q = queue.Queue()
        hotspot_listeners.append(q)
        try:
            snapshot = database.get_reports_for_map() or []
            yield f"data: {json.dumps({'type': 'snapshot', 'data': snapshot})}\n\n"
        except Exception as e:
            logger.error(f"Snapshot error: {e}")

        try:
            while True:
                try:
                    msg = q.get(timeout=25)
                    yield f"data: {json.dumps(msg)}\n\n"
                except queue.Empty:
                    yield "data: {\"type\": \"keepalive\"}\n\n"
        finally:
            try:
                hotspot_listeners.remove(q)
            except ValueError:
                pass

    headers = {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'
    }
    return Response(stream_with_context(event_stream()), headers=headers)

@app.route('/api/posts', methods=['GET'])
@token_required
def get_all_posts(current_user):
    posts = database.get_all_posts_with_votes()
    return jsonify({'posts': posts})

@app.route('/api/auth/authority/reports/export', methods=['GET'])
def export_reports():
    """Export reports (no user details) as JSON or CSV. Auth via JWT token query param."""
    token = request.args.get('token')
    fmt = request.args.get('format', 'json').lower()
    if not token:
        return jsonify({'error': 'No token provided'}), 401
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = database.get_user_by_username(data['username'])
        if not user or user['role'] != 'authority':
            return jsonify({'error': 'Unauthorized'}), 403
    except Exception:
        return jsonify({'error': 'Invalid token'}), 401

    raw = database.get_all_reports()
    export_rows = []
    for r in raw:
        export_rows.append({
            'report_id': r.get('id'),
            'post_id': r.get('post_id'),
            'title': r.get('title'),
            'description': r.get('description'),
            'urgency_level': r.get('urgency_level'),
            'flood_type': r.get('flood_type'),
            'confidence_score': r.get('confidence_score'),
            'verified': r.get('verified'),
            'ai_summary': r.get('ai_summary'),
            'latitude': r.get('latitude'),
            'longitude': r.get('longitude'),
            'location_name': r.get('location_name'),
            'created_at': r.get('created_at')
        })

    if fmt == 'csv':
        if not export_rows:
            csv_data = ''
        else:
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=list(export_rows[0].keys()))
            writer.writeheader()
            writer.writerows(export_rows)
            csv_data = output.getvalue()
        headers = {
            'Content-Type': 'text/csv',
            'Content-Disposition': 'attachment; filename="reports.csv"'
        }
        return Response(csv_data, headers=headers)
    else:
        headers = {
            'Content-Type': 'application/json',
            'Content-Disposition': 'attachment; filename="reports.json"'
        }
        return Response(json.dumps(export_rows, ensure_ascii=False), headers=headers)

@app.route('/api/posts/stream', methods=['GET'])
def posts_stream():
    token = request.args.get('token')
    if not token:
        return jsonify({'error': 'No token provided'}), 401
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = database.get_user_by_username(data['username'])
        if not user:
            return jsonify({'error': 'Unauthorized'}), 403
    except Exception:
        return jsonify({'error': 'Invalid token'}), 401

    def event_stream():
        q = queue.Queue()
        post_listeners.append(q)
        try:
            snapshot = database.get_all_posts_with_votes() or []
            yield f"data: {json.dumps({'type': 'snapshot', 'data': snapshot})}\n\n"
        except Exception as e:
            logger.error(f"Post snapshot error: {e}")

        try:
            while True:
                try:
                    msg = q.get(timeout=25)
                    yield f"data: {json.dumps(msg)}\n\n"
                except queue.Empty:
                    yield "data: {\"type\": \"keepalive\"}\n\n"
        finally:
            try:
                post_listeners.remove(q)
            except ValueError:
                pass

    headers = {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'
    }
    return Response(stream_with_context(event_stream()), headers=headers)

@app.route('/api/posts/<int:post_id>/vote', methods=['POST'])
@token_required
def vote_on_post(current_user, post_id):
    data = request.json
    vote_type = data.get('vote_type')  # 'up' or 'down'
    
    if vote_type not in ['up', 'down']:
        return jsonify({'error': 'Invalid vote type'}), 400
    
    post = database.get_post_by_id(post_id)
    if post and post['user_id'] == current_user['id']:
        return jsonify({'error': 'Cannot vote on your own post'}), 400
    
    success = database.vote_post(post_id, current_user['id'], vote_type)
    if success:
        return jsonify({'message': 'Vote recorded successfully'})
    else:
        return jsonify({'error': 'Failed to record vote'}), 500

@app.route('/api/users/<username>', methods=['GET'])
@token_required
def get_user_profile_by_username(current_user, username):
    user = database.get_user_by_username(username)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    profile = database.get_user_profile(user['id'])
    if profile:
        return jsonify({'user': public_user_profile(profile)})
    else:
        return jsonify({'error': 'Failed to load profile'}), 500

@app.route('/api/users/<int:user_id>', methods=['GET'])
@token_required
def get_user_profile_by_id(current_user, user_id):
    profile = database.get_user_profile(user_id)
    if profile:
        return jsonify({'user': public_user_profile(profile)})
    else:
        return jsonify({'error': 'User not found'}), 404

def public_user_profile(profile):
    return {
        key: profile[key]
        for key in ('username', 'full_name', 'authenticity_score', 'created_at', 'posts')
        if key in profile
    }

@app.route('/api/classify/text', methods=['POST'])
def classify_text():
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify(APIResponse(
                status="error",
                error="Text field is required"
            ).dict()), 400
        
        text = data['text']
        urgency = classify_urgency(text)
        flood_type = classify_flood_type(text)
        
        return jsonify(APIResponse(
            status="success",
            data={
                "text": text,
                "urgency_classification": urgency.model_dump(),
                "flood_classification": flood_type.model_dump()
            }
        ).model_dump())
        
    except Exception as e:
        logger.error(f"Text classification error: {str(e)}")
        return jsonify(APIResponse(
            status="error",
            error=str(e)
        ).dict()), 500

@app.route('/api/classify/image', methods=['POST'])
def classify_image():
    try:
        data = request.get_json()
        if not data or 'image_path' not in data:
            return jsonify(APIResponse(
                status="error",
                error="image_path field is required"
            ).dict()), 400
        
        image_path = data['image_path']
        if not os.path.exists(image_path):
            return jsonify(APIResponse(
                status="error",
                error="Image file not found"
            ).dict()), 404
        
        result = classify_flood_image(image_path)
        return jsonify(APIResponse(
            status="success",
            data=result.model_dump()
        ).model_dump())
        
    except Exception as e:
        logger.error(f"Image classification error: {str(e)}")
        return jsonify(APIResponse(
            status="error",
            error=str(e)
        ).dict()), 500

@app.route('/api/test', methods=['GET'])
def test_route():
    return jsonify(APIResponse(
        status="success",
        message="Flask Backend is working!",
        data={"timestamp": datetime.now().isoformat()}
    ).model_dump())

database.init_db()

if os.getenv("LOAD_AI_MODELS", "false").lower() == "true":
    initialize_models()
else:
    logger.info("AI models disabled for lightweight deployment")

if __name__ == '__main__':
    logger.info("Initializing BlueSignal backend...")

    logger.info("Available endpoints:")
    logger.info("- POST /api/auth/register - User registration")
    logger.info("- POST /api/auth/login - User login")
    logger.info("- POST /api/auth/citizen/posts - Create citizen post")
    logger.info("- GET /api/auth/citizen/posts - Get citizen posts")
    logger.info("- GET /api/auth/authority/hotspots - Get flood hotspots")
    logger.info("- GET /api/auth/authority/reports - Get all reports")
    logger.info("- POST /api/classify/text - Text classification")
    logger.info("- POST /api/classify/image - Image classification")
    logger.info("- GET /api/health - Health check")
    logger.info("- GET /api/test - Test endpoint")
    
    logger.info("Starting Flask server on http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=True)
