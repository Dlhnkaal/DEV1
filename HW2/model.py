import numpy as np
import pickle
import logging
import os
from sklearn.linear_model import LogisticRegression
import mlflow.sklearn

logger = logging.getLogger(__name__)

def train_model():
    np.random.seed(42)
    X = np.random.rand(1000, 4)
    y = ((X[:, 0] < 0.3) & (X[:, 1] < 0.2)).astype(int)
    model = LogisticRegression()
    model.fit(X, y)
    return model

def save_model(model, path="model.pkl"):
    with open(path, "wb") as f:
        pickle.dump(model, f)

def load_model(path="model.pkl"):
    with open(path, "rb") as f:
        return pickle.load(f)

def register_mlflow_model():
    mlflow.sklearn.log_model(train_model(), "model", registered_model_name="ModerationModel")
    logger.info("Model registered in MLflow")

def load_mlflow_model(model_name="ModerationModel", stage="None"):
    model_uri = f"models:/{model_name}/{stage}"
    return mlflow.sklearn.load_model(model_uri)