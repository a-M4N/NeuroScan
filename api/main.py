"""
FastAPI app entrypoint for NeuroScan.

Responsible only for: app instantiation, wiring the model lifecycle
(load at startup, unload at shutdown), and mounting routers. Actual
endpoint logic lives in api/routers/.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.core import model_loader
from api.routers import predict, patients

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    # Loads the tumor classifier + builds Grad-CAM ONCE, before the app
    # starts accepting requests. See api/core/model_loader.py.
    model_loader.load()

    yield  # <-- app runs here, handling requests

    # --- shutdown ---
    # Runs when the server is stopping (Ctrl+C, container stop, etc.)
    model_loader.unload()


app = FastAPI(
    title="NeuroScan API",
    description="AI-based brain MRI disease detection & reporting",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predict.router)
app.include_router(patients.router)

app.mount("/data", StaticFiles(directory="data"), name="data")

@app.get("/health")
def health_check():
    """Basic liveness check — also confirms the model loaded successfully."""
    return {
        "status": "ok",
        "model_loaded": model_loader._registry.is_loaded,
    }