from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class AsyncPredictRequest(BaseModel):
    item_id: int = Field(gt=0)


class AsyncTaskStatusRequest(BaseModel):
    task_id: int = Field(gt=0)


class ModerationResultInDB(BaseModel):
    id: int = Field(gt=0)
    item_id: int = Field(gt=0)
    status: str = Field(min_length=1)
    is_violation: Optional[bool] = Field(default=None)
    probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field()
    processed_at: Optional[datetime] = Field(default=None)


class ModerationTaskResult(BaseModel):
    task_id: int = Field(gt=0)
    status: str = Field(min_length=1)
    message: str = Field(default="Request accepted")


class AsyncPredictionResponse(BaseModel):
    task_id: int = Field(gt=0)
    status: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ModerationStatusResponse(BaseModel):
    task_id: int = Field(gt=0)
    status: str = Field(min_length=1)
    is_violation: Optional[bool] = Field(default=None)
    probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ModerationResultUpdate(BaseModel):
    status: str = Field(min_length=1)
    is_violation: Optional[bool] = Field(default=None)
    probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    error_message: Optional[str] = Field(default=None)

class TaskIdList(BaseModel):
    task_ids: List[int] = Field()