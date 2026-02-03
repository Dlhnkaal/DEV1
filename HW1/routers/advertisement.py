from fastapi import APIRouter, status
from pydantic import BaseModel
from services.advertisement import AdvertisementService
from models.advertisement import AdvModel

class PredictionResponse(BaseModel):
    resp: bool

router = APIRouter()
advertisement_service = AdvertisementService()

@router.post("/predict", status_code=status.HTTP_200_OK, response_model=PredictionResponse)
async def predict(dto: AdvModel) -> PredictionResponse:
    result = advertisement_service.predict(dto)
    return PredictionResponse(resp=result)