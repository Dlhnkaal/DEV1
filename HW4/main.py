from contextlib import asynccontextmanager
from typing import Dict, AsyncGenerator
from fastapi import FastAPI, Depends

from services.advertisement import AdvertisementMLService
from services.moderation import AsyncModerationService  

from routers.advertisement import router as ad_router
from routers.moderation import router as mod_router       

import sys
import os
import uvicorn
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    ml_service = AdvertisementMLService()
    app.state.ml_service = ml_service
    ml_service._load_model()
    
    moderation_service = AsyncModerationService()
    app.state.moderation_service = moderation_service
    
    await moderation_service.start() 
    
    logger.info("All services started successfully")

    yield
    
    await moderation_service.close()

app = FastAPI(title="Ad Moderation ML API", version="1.0.0", lifespan=lifespan)

@app.get("/")
async def root() -> Dict[str, str]:
    return {"message": "Advertisement Moderation ML API"}

app.include_router(ad_router, prefix="/advertisement", tags=["Advertisement"])
app.include_router(mod_router, prefix="/moderation", tags=["Moderation"])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)