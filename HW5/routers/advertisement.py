import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field

from models.advertisement import (
    AdvertisementWithUserBase,
    AdvertisementLite,
    CloseAdvertisementRequest,
    CloseAdvertisementResponse
)
from services.advertisement import AdvertisementMLService
from errors import AdvertisementNotFoundError, ModelNotReadyError

# Модель ответа для предсказания
class PredictionMLResponse(BaseModel):
    is_violation: bool = Field()
    probability: float = Field()

# Модель ответа для закрытия объявления
class CloseAdvertisementResponse(BaseModel):
    message: str = Field(description="Результат операции")
    item_id: int = Field(description="ID закрытого объявления")

logger = logging.getLogger(__name__)
router = APIRouter()

def get_ml_service(request: Request) -> AdvertisementMLService:
    return request.app.state.ml_service

@router.post("/predict", response_model=PredictionMLResponse, status_code=status.HTTP_200_OK)
async def predict(
    dto: AdvertisementWithUserBase,
    service: AdvertisementMLService = Depends(get_ml_service)
) -> PredictionMLResponse:
    try:
        is_violation, probability = service.predict(dto)
        return PredictionMLResponse(is_violation=is_violation, probability=probability)
    except ModelNotReadyError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model is not available"
        ) from e
    except Exception as e:
        logger.exception("ML prediction error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prediction failed"
        ) from e

@router.post("/simple_predict", response_model=PredictionMLResponse, status_code=status.HTTP_200_OK)
async def simple_predict(
    dto: AdvertisementLite,
    service: AdvertisementMLService = Depends(get_ml_service)
) -> PredictionMLResponse:
    try:
        is_violation, probability = await service.simple_predict(dto)
        return PredictionMLResponse(is_violation=is_violation, probability=probability)
    except AdvertisementNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Advertisement with id {dto.item_id} not found"
        ) from e
    except ModelNotReadyError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model is not available"
        ) from e
    except Exception as e:
        logger.exception("Simple ML prediction error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prediction failed"
        ) from e

@router.post("/close", response_model=CloseAdvertisementResponse, status_code=status.HTTP_200_OK)
async def close_advertisement(
    dto: CloseAdvertisementRequest,
    service: AdvertisementMLService = Depends(get_ml_service)
) -> CloseAdvertisementResponse:
    """
    Закрывает (удаляет) объявление по его ID.
    Также удаляет связанные результаты предсказаний из PostgreSQL и Redis.
    """
    success = await service.close_advertisement(dto)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Advertisement not found"
        )
    return CloseAdvertisementResponse(
        message="Advertisement closed successfully",
        item_id=dto.item_id
    )