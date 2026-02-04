import mlflow
from mlflow.sklearn import log_model
from model import train_model

mlflow.set_tracking_uri("sqlite:///mlflow.db")
mlflow.set_experiment("moderation-model")

with mlflow.start_run():
    model = train_model()
    log_model(model, artifact_path="model", registered_model_name="moderation-model")