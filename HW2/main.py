from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, HTTPException, status, Depends
from model import load_model
from services.advertisement import AdvertisementMLService
from routers.advertisement import router
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        app.state.ml_service = AdvertisementMLService()
        app.state.ml_service._load_model()  # Test load
        logger.info("Service started with ML model")
    except Exception as e:
        logger.error("Model init failed: %s", e)
    yield

app = FastAPI(title="Ad Moderation ML API", lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Ad Moderation ML API"}

@app.get("/health")
async def health(ml_service: AdvertisementMLService = Depends(lambda: app.state.ml_service)):
    return {"status": "healthy"}

app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8007)