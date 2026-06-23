from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db import initialize_api_database
from backend.routes.favorites import router as favorites_router
from backend.routes.jobs import router as jobs_router
from backend.routes.reports import router as reports_router
from backend.services.job_service import get_stats


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_api_database()
    yield


app = FastAPI(
    title="Job Radar API",
    description="저장된 채용공고와 개인 매칭 결과를 탐색하는 API",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://tami-bang.github.io",
        *[origin.strip() for origin in os.getenv("JOB_RADAR_CORS_ORIGINS", "").split(",") if origin.strip()],
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(jobs_router)
app.include_router(favorites_router)
app.include_router(reports_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/stats")
def stats():
    return get_stats()
