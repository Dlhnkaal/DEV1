import logging
import numpy as np

logger = logging.getLogger(__name__)


def build_features(data):
    return np.array([[
        1.0 if data.is_verified_seller else 0.0,
        min(data.images_qty, 10) / 10.0,
        min(len(data.description), 1000) / 1000.0,
        data.category / 100.0,
    ]])


def predict_violation(model, data):
    features = build_features(data)

    logger.info(
        "Predict request: seller_id=%s item_id=%s features=%s",
        data.seller_id,
        data.item_id,
        features.tolist(),
    )

    probabilities = model.predict_proba(features)
    violation_prob = float(probabilities[0][1])
    is_violation = violation_prob >= 0.5

    logger.info(
        "Prediction result: is_violation=%s probability=%.4f",
        is_violation,
        violation_prob,
    )

    return {
        "is_violation": is_violation,
        "probability": violation_prob,
    }