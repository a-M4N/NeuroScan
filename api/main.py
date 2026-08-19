"""
FastAPI app entrypoint for NeuroScan.

Responsible only for: app instantiation, wiring the model lifecycle
(load at startup, unload at shutdown), and mounting routers. Actual
endpoint logic lives in api/routers/.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.core import model_loader
from api.routers import predict,patients


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

app.include_router(predict.router)
app.include_router(patients.router)

@app.get("/health")
def health_check():
    """Basic liveness check — also confirms the model loaded successfully."""
    return {
        "status": "ok",
        "model_loaded": model_loader._registry.is_loaded,
    }