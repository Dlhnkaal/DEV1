from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from services.predict_service import predict_violation

router = APIRouter()


class PredictRequest(BaseModel):
    seller_id: int
    is_verified_seller: bool
    item_id: int
    name: str
    description: str
    category: int
    images_qty: int


class PredictResponse(BaseModel):
    is_violation: bool
    probability: float


@router.post("/predict", response_model=PredictResponse)
async def predict(data: PredictRequest, request: Request):
    model = request.app.state.model

    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Model is not available"
        )

    try:
        result = predict_violation(model, data)
        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(e)}"
        )
