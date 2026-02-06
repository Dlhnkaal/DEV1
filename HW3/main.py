from contextlib import asynccontextmanager
from typing import Dict, AsyncGenerator
from fastapi import FastAPI, Depends
from services.advertisement import AdvertisementMLService
from routers.advertisement import router, require_model_ready
import sys
import os
from main import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    use_mlflow = os.getenv("USE_MLFLOW", "false").lower() == "true"
    ml_service = AdvertisementMLService(is_use_mlflow=use_mlflow)
    app.state.ml_service = ml_service
    try:
        ml_service._load_model()
        logger.info("Service started with ML model successfully loaded")
    except Exception as e:
        logger.error(f"Model init failed: {e}")
    yield

app = FastAPI(title="Ad Moderation ML API", version="1.0.0", lifespan=lifespan)

@app.get("/", tags=["info"])
async def root() -> Dict[str, str]:
    return {"message": "Advertisement Moderation ML API"}

@app.get("/health", tags=["health"])
async def health(service: AdvertisementMLService = Depends(require_model_ready)) -> Dict[str, str]:
    return {"status": "healthy", "model": "ready"}

app.include_router(router, prefix="/advertisement", tags=["prediction"])

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8007)