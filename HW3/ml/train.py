import mlflow
from mlflow.sklearn import log_model
import logging
from ml.model import train_model, save_model
from mlflow.tracking import MlflowClient

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info(f"Training model")
    model = train_model()
    save_model(model, "model.pkl")
    logger.info(f"Local file model.pkl created")

    try:
        mlflow.set_tracking_uri("sqlite:///mlflow.db")
        mlflow.set_experiment("moderation-model")

        logger.info(f"Logging to MLflow")
        with mlflow.start_run():
            log_model(model, "model", registered_model_name="moderation-model")
        logger.info(f"Model registered in MLflow")
        
        logger.info(f"Setting model stage to Production")
        client = MlflowClient()
        
        latest_version = client.get_latest_versions("moderation-model", stages=["None"])[0]
        
        client.transition_model_version_stage(
            name="moderation-model",
            version=latest_version.version,
            stage="Production")
        logger.info(f"Model version {latest_version.version} transitioned to Production stage")
        
    except Exception as e:
        logger.error(f"MLflow skipped, maybe you don't have it installed or configured: {e}")