import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request, Path
from models.moderation import (
    AsyncPredictRequest, 
    AsyncTaskStatusRequest,
    AsyncPredictionResponse, 
    ModerationStatusResponse
)
from services.moderation import AsyncModerationService
from errors import AdvertisementNotFoundError, ModerationTaskNotFoundError

logger = logging.getLogger(__name__)
router = APIRouter()

def get_moderation_service(request: Request) -> AsyncModerationService:
    return request.app.state.moderation_service

@router.post("/async_predict", response_model=AsyncPredictionResponse, status_code=status.HTTP_202_ACCEPTED)
async def async_predict(
    dto: AsyncPredictRequest, 
    service: AsyncModerationService = Depends(get_moderation_service)
) -> AsyncPredictionResponse:
    try:
        result = await service.start_moderation(dto)
        
        return AsyncPredictionResponse(
            task_id=result.task_id,
            status=result.status,
            message=result.message
        )
        
    except AdvertisementNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Failed to start moderation for item {dto.item_id}")
        raise HTTPException(status_code=500, detail="Failed to start moderation") from e

@router.get("/moderation_result/{task_id}", response_model=ModerationStatusResponse)
async def get_moderation_result(
    task_id: int = Path(..., gt=0),
    service: AsyncModerationService = Depends(get_moderation_service)
) -> ModerationStatusResponse:
    try:
        request_dto = AsyncTaskStatusRequest(task_id=task_id)
        result_in_db = await service.get_moderation_status(request_dto)
        
        return ModerationStatusResponse(
            task_id=result_in_db.id,
            status=result_in_db.status,
            is_violation=result_in_db.is_violation,
            probability=result_in_db.probability
        )
        
    except ModerationTaskNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Failed to get status for task {task_id}")
        raise HTTPException(status_code=500, detail="Internal server error") from e