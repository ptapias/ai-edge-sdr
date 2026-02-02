"""
LinkedIn AI SDR - FastAPI Application Entry Point
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .routers import (
    search_router,
    leads_router,
    campaigns_router,
    business_profiles_router,
)
from .routers.linkedin import router as linkedin_router

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
    yield
    # Shutdown
    logger.info("Shutting down LinkedIn AI SDR API...")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="AI-powered LinkedIn SDR for automated lead generation and outreach",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(search_router)
app.include_router(leads_router)
app.include_router(campaigns_router)
app.include_router(business_profiles_router)
app.include_router(linkedin_router)


@app.get("/")
def root():
    """Root endpoint - API info."""
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
def get_global_stats():
    """Get global statistics."""
    from .database import SessionLocal
    from .models import Lead, Campaign, BusinessProfile

    db = SessionLocal()
    try:
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
