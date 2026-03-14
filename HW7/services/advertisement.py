import logging
import numpy as np
import os
from typing import Optional
from dataclasses import dataclass, field

from models.advertisement import (
    AdvertisementWithUserBase,
    AdvertisementLite,
    CloseAdvertisementRequest,
    PredictionResult,
    ActionStatus
)

from repositories.advertisement import AdvertisementRepository
from repositories.moderation import ModerationRepository

from repositories.user import UserRepository
from errors import AdvertisementNotFoundError, ModelNotReadyError

from ml.model import load_model, load_mlflow_model
from sklearn.linear_model import LogisticRegression

import time
from metrics import (
    PREDICTIONS_TOTAL, 
    PREDICTION_DURATION, 
    PREDICTION_ERRORS_TOTAL, 
    MODEL_PREDICTION_PROBABILITY
)

logger = logging.getLogger(__name__)

@dataclass
class AdvertisementMLService:
    advertisement_repo: AdvertisementRepository = field(default_factory=AdvertisementRepository) 
    user_repo: UserRepository = field(default_factory=UserRepository) 
    moderation_repo: ModerationRepository = field(default_factory=ModerationRepository)

    model_path: str = "model.pkl"
    _model: Optional[LogisticRegression] = None
    _model_loaded: bool = field(default=False, init=False)

    def _get_model(self) -> LogisticRegression:
        if self._model is None:
            self._load_model()
            
        if self._model is None:
            PREDICTION_ERRORS_TOTAL.labels(error_type="model_unavailable").inc()
            raise ModelNotReadyError("Model is not initialized and could not be loaded")
            
        return self._model

    def predict(self, dto: AdvertisementWithUserBase) -> PredictionResult:
        model = self._get_model()
        
        logger.info(f"Predict for seller_id={dto.seller_id}, item_id={dto.item_id}")
        
        features = np.array([
            [1.0 if dto.is_verified_seller else 0.0,
             dto.images_qty / 10.0,
             len(dto.description) / 1000.0,
             dto.category / 100.0]
        ])

        start_time = time.time()
        
        try:
            proba = model.predict_proba(features)[0][1]
            
            inference_duration = time.time() - start_time
            PREDICTION_DURATION.observe(inference_duration)
            
            is_violation = proba > 0.5
            
            MODEL_PREDICTION_PROBABILITY.observe(float(proba))
            result_label = "violation" if is_violation else "no_violation"
            PREDICTIONS_TOTAL.labels(result=result_label).inc()
            
            logger.info(f"Prediction result: violation={is_violation}, prob={proba:.3f}")
            return PredictionResult(is_violation=is_violation, probability=float(proba))
            
        except Exception as e:
            PREDICTION_ERRORS_TOTAL.labels(error_type="prediction_error").inc()
            logger.error(f"Prediction failed: {e}")
            raise e

    def _load_model(self) -> None:
        is_use_mlflow = os.getenv("USE_MLFLOW", "false").lower() == "true"
        try:
            if is_use_mlflow:
                logger.info("Loading model from MLflow")
                loaded_model = load_mlflow_model()
                source = "MLflow"
            else:
                logger.info(f"Attempting to load model from local file: {self.model_path}")
                
                if os.path.exists(self.model_path):
                    loaded_model = load_model(self.model_path)
                    source = self.model_path
                    logger.info(f"Model successfully loaded from {source}")
                else:
                    logger.warning(f"Model file {self.model_path} not found, train new model")
                    
                    try:
                        from ml.model import train_model, save_model
                    except ImportError as e:
                        logger.error(f"Cannot import train_model: {e}")
                        raise RuntimeError(f"Cannot train model: {e}")
                    
                    loaded_model = train_model()
                    
                    try:
                        save_model(loaded_model, self.model_path)
                        source = f"Newly trained and saved to {self.model_path}"
                        logger.info(f"Model trained and saved to {self.model_path}")
                    except Exception as save_error:
                        logger.error(f"Failed to save model: {save_error}")
                        source = "Newly trained"
                        logger.warning("Model was trained but could not be saved")

            self._model = loaded_model
            self._model_loaded = True
            logger.info(f"Model successfully loaded from {source}")

        except Exception as e:
            logger.error(f"Model load failed: {e}")
            self._model = None
            self._model_loaded = False
            raise e

    async def simple_predict(self, dto: AdvertisementLite) -> PredictionResult:
        try:
            advertisement = await self.advertisement_repo.get_by_id_with_user(dto.item_id)

            if advertisement is None:
                raise AdvertisementNotFoundError(f"Advertisement with id {dto.item_id} not found")
            
            logger.info(f"Simple predict for item_id={dto.item_id}")
            
            return self.predict(advertisement)
            
        except Exception as e:
            logger.error(f"Simple prediction failed: {e}")
            raise e

    async def close_advertisement(self, dto: CloseAdvertisementRequest) -> ActionStatus:
        logger.info(f"Service: Closing advertisement id={dto.item_id}")
        task_ids_dto = await self.moderation_repo.get_task_ids_by_item_id(dto.item_id)

        for task_id in task_ids_dto.task_ids:
            await self.moderation_repo.delete_cache(task_id) 

        return await self.advertisement_repo.close(dto.item_id)
