import logging
import numpy as np
import os
from typing import Optional, Tuple
from dataclasses import dataclass, field

from models.advertisement import (
    AdvertisementWithUserBase,
    AdvertisementLite,
    CloseAdvertisementRequest)

from repositories.advertisement import AdvertisementRepository
from repositories.user import UserRepository
from errors import AdvertisementNotFoundError, ModelNotReadyError

from ml.model import load_model, load_mlflow_model
from sklearn.linear_model import LogisticRegression

logger = logging.getLogger(__name__)

@dataclass
class AdvertisementMLService:
    advertisement_repo: AdvertisementRepository = field(default_factory=AdvertisementRepository) 
    user_repo: UserRepository = field(default_factory=UserRepository) 

    model_path: str = "model.pkl"
    _model: Optional[LogisticRegression] = None
    _model_loaded: bool = field(default=False, init=False)

    def _get_model(self) -> LogisticRegression:
        if self._model is None:
            self._load_model()

        if self._model is None:
            raise ModelNotReadyError("Model is not initialized and could not be loaded")

        return self._model

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

    def predict(self, adv: AdvertisementWithUserBase) -> Tuple[bool, float]:
        model = self._get_model()

        logger.info(f"Predict for seller_id={adv.seller_id}, item_id={adv.item_id}")

        features = np.array([
            [1.0 if adv.is_verified_seller else 0.0,
             adv.images_qty / 10.0,
             len(adv.description) / 1000.0,
             adv.category / 100.0]])

        try:
            proba = model.predict_proba(features)[0][1]
            is_violation = proba > 0.5

            logger.info(f"Prediction result: violation={is_violation}, prob={proba:.3f}")
            return is_violation, float(proba)

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise e

    async def simple_predict(self, adv: AdvertisementLite) -> Tuple[bool, float]:
        try:
            advertisement = await self.advertisement_repo.get_by_id_with_user(adv.item_id)

            if advertisement is None:
                raise AdvertisementNotFoundError(f"Advertisement with id {adv.item_id} not found")
            
            logger.info(f"Simple predict for item_id={adv.item_id}")
            
            return self.predict(advertisement)
            
        except Exception as e:
            logger.error(f"Simple prediction failed: {e}")
            raise e

    async def close_advertisement(self, dto: CloseAdvertisementRequest) -> bool:
        logger.info(f"Service: Closing advertisement id={dto.item_id}")
        return await self.advertisement_repo.close(dto.item_id)