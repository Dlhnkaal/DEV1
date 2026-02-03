import pickle
import logging
import numpy as np
import mlflow.sklearn
from sklearn.linear_model import LogisticRegression
from typing import Optional

logger = logging.getLogger(__name__)

def train_model():
    """Обучает простую модель на синтетических данных."""
    np.random.seed(42)
    # Признаки: [is_verified_seller, images_qty, description_length, category]
    X = np.random.rand(1000, 4)
    # Целевая переменная: 1 = нарушение, 0 = нет нарушения
    y = (X[:, 0] < 0.3) & (X[:, 1] < 0.2)
    y = y.astype(int)
    
    model = LogisticRegression()
    model.fit(X, y)
    logger.info(f"Model learned")
    return model

def save_model(model: LogisticRegression, path: str = "model.pkl") -> None:
    with open(path, "wb") as f:
        pickle.dump(model, f)
    logger.info(f"Model saved to {path}")

def load_model(path: str = "model.pkl") -> LogisticRegression:
    with open(path, "rb") as f:
        model = pickle.load(f)
    logger.info(f"Model loaded from {path}")
    return model

def load_mlflow_model(model_name: str = "moderation-model", stage: str = "Production") -> LogisticRegression:
    model_uri = f"models:/{model_name}/{stage}"
    logger.info(f"Loading model from MLflow: {model_uri}")
    return mlflow.sklearn.load_model(model_uri)
