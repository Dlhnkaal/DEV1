import logging
import sentry_sdk
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from models.advertisement import (
    AdvertisementWithUserBase,
    AdvertisementLite,
    CloseAdvertisementRequest,
    CloseAdvertisementResponse
)

from errors import AdvertisementNotFoundError, ModelNotReadyError
from dependencies import MLServiceDepend, AuthDepend


class PredictionMLResponse(BaseModel):
    is_violation: bool = Field()
    probability: float = Field()


logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/predict", response_model=PredictionMLResponse, status_code=status.HTTP_200_OK)
async def predict(
    dto: AdvertisementWithUserBase,
    current_account: AuthDepend,
    service: MLServiceDepend
) -> PredictionMLResponse:
    try:
        prediction_result = await service.predict(dto)
        return PredictionMLResponse(
            is_violation=prediction_result.is_violation, 
            probability=prediction_result.probability
        )
    except ModelNotReadyError as e:
        sentry_sdk.capture_exception(e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model is not available"
        ) from e
    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.exception("ML prediction error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prediction failed"
        ) from e


@router.post("/simple_predict", response_model=PredictionMLResponse, status_code=status.HTTP_200_OK)
async def simple_predict(
    dto: AdvertisementLite,
    current_account: AuthDepend,
    service: MLServiceDepend
) -> PredictionMLResponse:
    try:
        prediction_result = await service.simple_predict(dto)
        return PredictionMLResponse(
            is_violation=prediction_result.is_violation, 
            probability=prediction_result.probability
        )
    except AdvertisementNotFoundError as e:
        sentry_sdk.capture_exception(e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Advertisement with id {dto.item_id} not found"
        ) from e
    except ModelNotReadyError as e:
        sentry_sdk.capture_exception(e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model is not available"
        ) from e
    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.exception("Simple ML prediction error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prediction failed"
        ) from e


@router.post("/close", response_model=CloseAdvertisementResponse, status_code=status.HTTP_200_OK)
async def close_advertisement(
    dto: CloseAdvertisementRequest,
    current_account: AuthDepend, 
    service: MLServiceDepend
) -> CloseAdvertisementResponse:
    action_status = await service.close_advertisement(dto)
    if not action_status.success:
        e = AdvertisementNotFoundError("Advertisement not found")
        sentry_sdk.capture_exception(e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Advertisement not found"
        )

    return CloseAdvertisementResponse(
        message="Advertisement closed successfully",
        item_id=dto.item_id
    )
