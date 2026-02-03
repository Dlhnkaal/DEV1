import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from models.advertisement import AdvModel
from services.services_advertisement import AdvertisementMLService

class PredictionMLResponse(BaseModel):
    is_violation: bool
    probability: float

logger = logging.getLogger(__name__)
router = APIRouter()

def get_ml_service(request: Request) -> AdvertisementMLService:
    return request.app.state.ml_service

@router.post("/predict", response_model=PredictionMLResponse, status_code=status.HTTP_200_OK)
async def predict_ml(dto: AdvModel, service: AdvertisementMLService = Depends(get_ml_service)) -> PredictionMLResponse:
    if service._model is None:
        raise HTTPException(status_code=503, detail="Model is not available")
    
    try:
        is_violation, probability = service.predict_ml(dto)
        return PredictionMLResponse(is_violation=is_violation, probability=probability)
    except Exception:
        logger.exception("ML prediction error")
        raise HTTPException(status_code=500, detail="Prediction failed")