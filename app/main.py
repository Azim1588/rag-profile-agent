from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware as FastAPICORSMiddleware
import os
from app.api.v1 import router as v1_router

app = FastAPI(
    title="RAG Profile Agent",
    description="RAG-based Profile Agent API with LangGraph",
    version="1.0.0"
)

# Add CORS middleware (FastAPI's built-in handles WebSockets better)
app.add_middleware(
    FastAPICORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(v1_router)

@app.get("/")
async def root():
    return {
        "message": "RAG Profile Agent API",
        "environment": os.getenv("ENVIRONMENT", "unknown"),
        "database": os.getenv("POSTGRES_HOST", "unknown"),
        "docs": "/docs",
        "health": "/health"
    }
