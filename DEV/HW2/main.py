from fastapi import FastAPI
from routes.predict import router as predict_router
from contextlib import asynccontextmanager
from model import get_model
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        model = get_model()
        app.state.model = model
        logger.info("Model loaded successfully")

    except Exception:
        logger.exception("Failed to load model")
        app.state.model = None

    yield


app = FastAPI(lifespan=lifespan)
app.include_router(predict_router)