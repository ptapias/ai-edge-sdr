"""
LinkedIn AI SDR - FastAPI Application Entry Point
"""
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import get_settings
from .database import init_db
from .services.scheduler_service import start_scheduler, stop_scheduler
from .routers import (
    search_router,
    leads_router,
    campaigns_router,
    business_profiles_router,
)
from .routers.linkedin import router as linkedin_router
from .routers.automation import router as automation_router
from .routers.auth import router as auth_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting LinkedIn AI SDR API...")
    init_db()
    logger.info("Database initialized")

    # Start the automatic invitation scheduler
    start_scheduler()
    logger.info("Invitation scheduler started")

    yield

    # Shutdown
    logger.info("Shutting down LinkedIn AI SDR API...")
    stop_scheduler()
    logger.info("Invitation scheduler stopped")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="AI-powered LinkedIn SDR for automated lead generation and outreach",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS - include Render URLs
cors_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]
# Add production URLs from environment
if os.getenv("CORS_ORIGINS"):
    cors_origins.extend(os.getenv("CORS_ORIGINS").split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(search_router)
app.include_router(leads_router)
app.include_router(campaigns_router)
app.include_router(business_profiles_router)
app.include_router(linkedin_router)
app.include_router(automation_router)


@app.get("/api")
def api_root():
    """API root endpoint - API info."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/stats")
def get_global_stats(
    current_user = None  # Made optional for backward compatibility during transition
):
    """Get global statistics for the current user."""
    from fastapi import Depends
    from .database import SessionLocal, get_db
    from .models import Lead, Campaign, BusinessProfile
    from .dependencies import get_current_user_optional

    db = SessionLocal()
    try:
        # If authenticated, filter by user_id
        # During transition, allow unauthenticated access
        user_filter = {}

        total_leads = db.query(Lead).count()
        total_campaigns = db.query(Campaign).count()
        total_profiles = db.query(BusinessProfile).count()
        verified_leads = db.query(Lead).filter(Lead.email_verified == True).count()
        hot_leads = db.query(Lead).filter(Lead.score_label == "hot").count()
        contacted_leads = db.query(Lead).filter(Lead.status == "contacted").count()

        return {
            "leads": {
                "total": total_leads,
                "verified": verified_leads,
                "hot": hot_leads,
                "contacted": contacted_leads
            },
            "campaigns": total_campaigns,
            "business_profiles": total_profiles
        }
    finally:
        db.close()


# Serve static frontend files in production
# The frontend build is placed in backend/static after build
STATIC_DIR = Path(__file__).parent.parent / "static"

if STATIC_DIR.exists():
    # Serve static assets (js, css, images)
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    # Catch-all route for SPA - must be after all API routes
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the React SPA for all non-API routes."""
        # Don't serve index.html for API routes
        if full_path.startswith("api/"):
            return {"error": "Not found"}

        # Serve static files if they exist
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)

        # Otherwise serve index.html for SPA routing
        return FileResponse(STATIC_DIR / "index.html")
