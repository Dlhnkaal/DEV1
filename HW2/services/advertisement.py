import logging
import numpy as np
import os
from dataclasses import dataclass
from models.advertisement import AdvModel
from model import load_model, load_mlflow_model

logger = logging.getLogger(__name__)

@dataclass
class AdvertisementMLService:
    model_path: str = "model.pkl"

    def _load_model(self):
        use_mlflow = os.getenv("USE_MLFLOW", "false").lower() == "true"
        try:
            if use_mlflow:
                model = load_mlflow_model()
            else:
                model = load_model(self.model_path)
            logger.info("Model loaded from %s", "MLflow" if use_mlflow else self.model_path)
            return model
        except Exception as e:
            logger.error("Model load failed: %s", e)
            raise

    def predict_ml(self, adv: AdvModel):
        model = self._load_model()
        logger.info("Predict for seller_id=%s, item_id=%s", adv.seller_id, adv.item_id)
        
        features = np.array([
            [1.0 if adv.is_verified_seller else 0.0,
             adv.images_qty / 10.0,
             len(adv.description) / 1000.0,
             adv.category / 100.0]])
        
        try:
            proba = model.predict_proba(features)[0][1] 
            is_violation = proba > 0.5
            logger.info("Prediction: is_violation=%s, probability=%.3f", is_violation, proba)
            return is_violation, float(proba)
        except Exception as e:
            logger.error("Prediction failed: %s", e)
            raise
