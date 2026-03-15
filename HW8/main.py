from contextlib import asynccontextmanager
from typing import Dict, AsyncGenerator
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import sentry_sdk

from services.advertisement import AdvertisementMLService
from services.moderation import AsyncModerationService

from routers.advertisement import router as ad_router
from routers.moderation import router as mod_router
from routers.auth import router as auth_router 
import os
import uvicorn
import logging
from http import HTTPStatus

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from clients.postgres import init_pg_pool, close_pg_pool
from clients.redis import init_redis, close_redis
from prometheus_fastapi_instrumentator import Instrumentator

from errors import UnauthorizedError, AuthorizedError

sentry_sdk.init(
    dsn="https://46a307ca7cdec2b541bbdeeeef29968d@o4511005189210112.ingest.de.sentry.io/4511008883015760",
    traces_sample_rate=1.0,
    send_default_pii=True,
    environment="development",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_pg_pool()
    logger.info("PostgreSQL pool initialized")
    
    await init_redis()
    logger.info("Redis initialized")
    
    ml_service = AdvertisementMLService()
    app.state.ml_service = ml_service
    ml_service._load_model()
    
    moderation_service = AsyncModerationService()
    app.state.moderation_service = moderation_service
    
    await moderation_service.start()
    
    logger.info("All services started successfully")
    
    yield
    
    await moderation_service.close()
    await close_redis()
    logger.info("Redis closed")
    await close_pg_pool()
    logger.info("PostgreSQL pool closed")

app = FastAPI(title="Ad Moderation ML API", version="1.0.0", lifespan=lifespan)

@app.exception_handler(UnauthorizedError)
async def unauthorized_error_handler(request: Request, _: UnauthorizedError):
    return JSONResponse(
        status_code=HTTPStatus.UNAUTHORIZED,
        content={"message": "User not authorized"},
    )

@app.exception_handler(AuthorizedError)
async def authorized_error_handler(request: Request, _: AuthorizedError):
    return JSONResponse(
        status_code=HTTPStatus.BAD_REQUEST,
        content={"message": "Login or password is not corrected"},
    )

@app.get("/")
async def root() -> Dict[str, str]:
    return {"message": "Advertisement Moderation ML API"}

app.include_router(ad_router, prefix="/advertisement", tags=["Advertisement"])
app.include_router(mod_router, prefix="/moderation", tags=["Moderation"])
app.include_router(auth_router, prefix="/auth", tags=["Auth"]) 

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)