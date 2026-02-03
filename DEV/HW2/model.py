import os
import pickle
import numpy as np
import mlflow
import mlflow.sklearn
from sklearn.linear_model import LogisticRegression

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
    return model

def save_model(model, path="model.pkl"):
    with open(path, "wb") as f:
        pickle.dump(model, f)

def load_model(path="model.pkl"):
    with open(path, "rb") as f:
        return pickle.load(f)
    
def load_model_from_mlflow(model_name: str, alias: str = "production"):
    mlflow.set_tracking_uri("sqlite:///mlflow.db")

    model_uri = f"models:/{model_name}@{alias}"
    return mlflow.sklearn.load_model(model_uri)


def get_model():
    use_mlflow = os.getenv("USE_MLFLOW", "false").lower() == "true"

    if use_mlflow:
        return load_model_from_mlflow("moderation-model")

    if os.path.exists("model.pkl"):
        return load_model()

    model = train_model()
    save_model(model)
    return model