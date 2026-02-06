import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from models.advertisement import AdvModel, SimplePredictRequest
from services.advertisement import AdvertisementMLService
from errors import AdvertisementNotFoundError, ModelNotReadyError

class PredictionMLResponse(BaseModel):
    is_violation: bool = Field()
    probability: float = Field()

logger = logging.getLogger(__name__)
router = APIRouter()

def get_ml_service(request: Request) -> AdvertisementMLService:
    return request.app.state.ml_service

def require_model_ready(service: AdvertisementMLService = Depends(get_ml_service)) -> AdvertisementMLService:
    if not service.is_model_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model is not available")
    return service

@router.post("/predict", response_model=PredictionMLResponse, status_code=status.HTTP_200_OK)
async def predict_ml(dto: AdvModel, service: AdvertisementMLService = Depends(require_model_ready)) -> PredictionMLResponse:
    try:
        is_violation, probability = service.predict_ml(dto)
        return PredictionMLResponse(is_violation=is_violation, probability=probability)
    except Exception:
        logger.exception("ML prediction error")
        raise HTTPException(status_code=500, detail="Prediction failed")

@router.post("/simple_predict", response_model=PredictionMLResponse, status_code=status.HTTP_200_OK)
async def simple_predict(request: SimplePredictRequest, service: AdvertisementMLService = Depends(require_model_ready)) -> PredictionMLResponse:
    try:
        is_violation, probability = await service.simple_predict(request.item_id)
        return PredictionMLResponse(is_violation=is_violation, probability=probability)
    except AdvertisementNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Advertisement with id {request.item_id} not found")
    except Exception:
        logger.exception("Simple ML prediction error")
        raise HTTPException(status_code=500, detail="Prediction failed")