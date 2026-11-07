# BlueSignal 🌊

AI-driven flood response platform that aggregates and validates citizen reports to provide authorities with real-time, location-based flood intelligence.

## Overview

BlueSignal is a full-stack application that combines citizen reporting with advanced AI to help emergency response authorities respond faster and more effectively to flood emergencies. The platform features:

- **Real-time flood monitoring** with live map visualization
- **AI-powered classification** of flood types and urgency levels
- **Image analysis** to verify and categorize flood reports
- **Citizen reporting system** with photo uploads and location tracking
- **Authority dashboard** with real-time hotspot tracking
- **Social media integration** for verification
- **Export capabilities** (JSON/CSV) for data analysis

## 🏗️ Architecture

### Tech Stack

**Backend:**
- FastAPI (Python) - REST API
- PostgreSQL - Database
- SQLAlchemy and Alembic - ORM and migrations
- Transformers (Hugging Face) - AI/ML models
- PyTorch - Deep learning framework
- JWT - Authentication
- Server-Sent Events (SSE) - Real-time updates

**Frontend:**
- React - UI framework
- Vite - Build tool
- React Router - Routing
- MapLibre GL - Map visualization
- Axios - HTTP client

### Project Structure

```
blue-signal/
├── backend/
│   ├── app.py              # FastAPI compatibility entry point
│   ├── app/main.py         # FastAPI application
│   ├── requirements.txt    # Python dependencies
│   ├── alembic/            # PostgreSQL migrations
│   └── test_backend.py     # API smoke tests
├── frontend/
│   ├── src/
│   │   ├── api/            # API client
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   ├── styles/         # CSS files
│   │   └── utils/          # Helper functions
│   ├── package.json        # Node dependencies
│   └── vite.config.js      # Vite configuration
├── .gitignore
├── LICENSE
└── README.md
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Node.js 16+ and npm
- API keys (optional):
  - Google API Key (for Gemini)
  - Groq API Key (for LLaMA models)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/shvn22k/blue-signal.git
   cd blue-signal
   ```

2. **Backend Setup:**
   ```bash
   cd backend
   
   # Create virtual environment (recommended)
   python -m venv venv
   
   # Activate virtual environment
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Set a unique signing key (required; generate a fresh value locally)
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   export SECRET_KEY="<paste-generated-value>"

   # AI provider keys are optional
   export GOOGLE_API_KEY="your-google-api-key"
   export GROQ_API_KEY="your-groq-api-key"
   ```

3. **Frontend Setup:**
   ```bash
   cd frontend
   npm install
   ```

### Running the Application

1. **Start the backend server:**
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```
   The API will be available at `http://127.0.0.1:8000`

2. **Start the frontend dev server:**
   ```bash
   cd frontend
   npm run dev
   ```
   The frontend will be available at `http://localhost:5173`

3. **Access the application:**
   - Open `http://localhost:5173` in your browser
   - Register as a citizen or authority user
   - Start reporting floods or monitoring the dashboard

During development, the frontend uses the local backend through the Vite proxy. For a deployed frontend using a different backend, set `VITE_API_BASE_URL` to its origin (without `/api`).

For local backend auth, set `SECRET_KEY` to a generated value at least 32 characters long. In Render, configure `SECRET_KEY` as a secret environment variable before deploying; changing it invalidates existing JWT sessions. The backend only loads AI models when `LOAD_AI_MODELS=true`, so login and signup do not require model initialization.

### Default Demo Accounts

The database is initialized with demo accounts:

- **Authority:** `admin` / `admin123`
- **Citizens:** 
  - `floodwatcher` / `password123`
  - `mumbai_resident` / `password123`
  - `weather_alert` / `password123`

On the Authority Portal, select **Fill demo credentials** to populate the admin login.

## 📱 Features

### For Citizens
- Submit flood reports with text, images, and location
- View community feed with voting system
- Real-time updates on flood conditions
- Profile management with authenticity scoring

### For Authorities
- Real-time hotspot map with flood locations
- AI-generated summaries for each report
- Export reports as JSON or CSV
- Verified report filtering
- Server-Sent Events for live updates

### AI Capabilities
- **Text Classification:** Urgency levels (Urgent Panic, Alert Caution, Safe Normal)
- **Flood Type Detection:** Urban Flooding, River Overflow, Flash Flood, etc.
- **Image Classification:** Visual flood verification with confidence scores
- **Report Generation:** AI-powered summaries for decision-makers

## 🔧 Configuration

### Environment Variables

Set these variables in your shell or hosting platform. The backend does not automatically load a `.env` file. `SECRET_KEY` is required and must be at least 32 characters long. Generate it locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"`; do not commit it.

```env
SECRET_KEY=<generated-random-value>
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
GOOGLE_API_KEY=your-google-api-key
GROQ_API_KEY=your-groq-api-key
```

For Vercel, `VITE_API_BASE_URL` is optional when using the default production API. If set, use the backend origin without a trailing slash or `/api`, then redeploy the frontend. Optional backend variables are `GOOGLE_API_KEY`, `GROQ_API_KEY`, and `LOAD_AI_MODELS`.

### CORS Configuration

Update the allowed origins in the CORS configuration in [backend/app/main.py](backend/app/main.py) if needed.

### Database

PostgreSQL tables are managed with Alembic. Configure `DATABASE_URL`, then initialize the schema from the backend directory:

```bash
alembic upgrade head
```

To migrate an existing SQLite database and preserve its records:

```bash
python scripts/migrate_sqlite_to_postgres.py /path/to/bluesignal.db
```

Validate the legacy database without changing PostgreSQL first:

```bash
python scripts/migrate_sqlite_to_postgres.py /path/to/bluesignal.db --dry-run
```

Back up PostgreSQL before destructive migrations. `bluesignal.db` and SQLite are no longer used.

## 🧪 Testing

### Backend Tests

```bash
cd backend
python test_backend.py  # Test API endpoints (requires the FastAPI server to be running)
```

### Frontend Tests

```bash
cd frontend
npm test
```

### API Health Check

```bash
curl http://127.0.0.1:8000/api/health
```

## 📡 API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get JWT token

### Citizen Endpoints
- `POST /api/auth/citizen/posts` - Create flood report
- `GET /api/auth/citizen/posts` - Get user's posts
- `GET /api/posts` - Get all posts (community feed)
- `POST /api/posts/<id>/vote` - Vote on a post
- `GET /api/posts/stream` - SSE stream for posts

### Authority Endpoints
- `GET /api/auth/authority/hotspots` - Get flood hotspots
- `GET /api/auth/authority/hotspots/stream` - SSE stream for hotspots
- `GET /api/auth/authority/reports/export` - Export reports (JSON/CSV)

### AI Endpoints
- `POST /api/classify/text` - Classify text urgency/flood type
- `POST /api/classify/image` - Classify flood image

### Utility
- `GET /api/health` - Health check
- `GET /api/test` - Test endpoint

## 🚢 Deployment

### Backend Deployment

1. Set environment variables on your hosting platform
2. Run PostgreSQL migrations: `alembic upgrade head`
3. Start FastAPI with an ASGI server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

### Frontend Deployment

```bash
cd frontend
npm run build
# Deploy the `dist/` folder to your hosting service
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
