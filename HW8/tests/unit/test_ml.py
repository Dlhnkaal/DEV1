import pytest
import os
import tempfile
import numpy as np
from ml.model import train_model, save_model, load_model, load_mlflow_model
from unittest.mock import patch, MagicMock

class TestMLModel:
    @pytest.mark.parametrize("seed", [42, 123])
    def test_train_model(self, seed):
        np.random.seed(seed)
        model = train_model()
        assert hasattr(model, "predict")
        assert hasattr(model, "predict_proba")

    @pytest.mark.parametrize("path", ["test_model.pkl"])
    def test_save_and_load_model(self, path):
        model = train_model()
        try:
            save_model(model, path)
            assert os.path.exists(path)
            loaded = load_model(path)
            assert loaded is not None
            np.testing.assert_array_almost_equal(
                model.coef_, loaded.coef_
            )
        finally:
            if os.path.exists(path):
                os.remove(path)

    @pytest.mark.parametrize("model_name,stage", [("moderation-model", "Production")])
    @patch("ml.model.mlflow.sklearn.load_model")
    def test_load_mlflow_model(self, mock_load, model_name, stage):
        mock_model = MagicMock()
        mock_load.return_value = mock_model
        result = load_mlflow_model(model_name, stage)
        mock_load.assert_called_once_with(f"models:/{model_name}/{stage}")
        assert result == mock_model