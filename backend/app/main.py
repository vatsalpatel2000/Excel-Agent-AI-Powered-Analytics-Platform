"""
FastAPI Main Application - Unified Excel Agent Backend

Production-grade API server with:
- Chat endpoints for agent interaction
- File upload endpoints
- Export/download endpoints
- Health checks and monitoring
"""

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.config import settings
from app.api import chat, files, export


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.EXPORT_DIR, exist_ok=True)
    print(f"📊 Excel Agent Backend started on {settings.API_HOST}:{settings.API_PORT}")
    print(f"   Model: {settings.OPENAI_MODEL}")
    print(f"   Max iterations: {settings.MAX_ITERATIONS}")
    
    yield
    
    # Shutdown
    print("📊 Excel Agent Backend shutting down...")


app = FastAPI(
    title="Excel Agent API",
    description="Production-grade Excel/CSV analysis agent with AI-powered insights",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(files.router, prefix="/api/files", tags=["Files"])
app.include_router(export.router, prefix="/api/export", tags=["Export"])

# Mount static files for exports
export_path = Path(settings.EXPORT_DIR)
export_path.mkdir(parents=True, exist_ok=True)
app.mount("/exports", StaticFiles(directory=str(export_path)), name="exports")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model": settings.OPENAI_MODEL,
        "redis_enabled": settings.REDIS_ENABLED,
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Excel Agent API",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )
