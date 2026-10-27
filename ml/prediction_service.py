"""
XGBoost Prediction Service for Adaptive Candidate Item Selection.
Provides probability estimation P(correct | x) with safe fallback to IRT-only mode
when a trained model artifact is missing or invalid.
"""
import os
import json
import logging
from typing import Optional, Dict, Any, List
import xgboost as xgb
import numpy as np

from django.conf import settings
from .feature_engineering import FEATURE_NAMES, features_dict_to_vector

logger = logging.getLogger(__name__)

BASE_DIR = getattr(settings, 'BASE_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_MODEL_DIR = os.path.join(BASE_DIR, 'ml', 'artifacts')
DEFAULT_MODEL_PATH = os.path.join(DEFAULT_MODEL_DIR, 'xgboost_model.json')
DEFAULT_META_PATH = os.path.join(DEFAULT_MODEL_DIR, 'model_metadata.json')


class XGBoostPredictionService:
    """
    Singleton-style service that loads and queries the trained XGBoost model.
    Falls back gracefully if the model has not yet been trained or loaded.
    """

    def __init__(self, model_path: Optional[str] = None, meta_path: Optional[str] = None):
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.meta_path = meta_path or DEFAULT_META_PATH
        self.model: Optional[xgb.Booster] = None
        self.metadata: Dict[str, Any] = {}
        self.is_loaded: bool = False
        self._load_model()

    def _load_model(self) -> None:
        """Loads the XGBoost booster and metadata from disk if available."""
        if not os.path.exists(self.model_path):
            self.is_loaded = False
            return

        try:
            booster = xgb.Booster()
            booster.load_model(self.model_path)
            self.model = booster

            if os.path.exists(self.meta_path):
                with open(self.meta_path, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            else:
                self.metadata = {'model_version': 'XGB-v1.0-unversioned'}

            self.is_loaded = True
        except Exception as e:
            logger.warning("Failed to load XGBoost model from %s: %s", self.model_path, e)
            self.model = None
            self.is_loaded = False

    def is_available(self) -> bool:
        """Returns True if a valid trained XGBoost model is loaded and ready."""
        return self.is_loaded and self.model is not None

    def get_model_version(self) -> str:
        """Returns the version string of the loaded model or 'UNAVAILABLE'."""
        if self.is_available():
            return self.metadata.get('model_version', 'XGB-v1.0')
        return 'UNAVAILABLE'

    def predict_probability(self, features: Dict[str, float]) -> Optional[float]:
        """
        Estimates the probability that the student will answer the candidate item correctly.
        Returns float in (0.0, 1.0) on success, or None on fallback/failure.
        """
        if not self.is_available():
            return None

        try:
            row_vector = features_dict_to_vector(features)
            dmatrix = xgb.DMatrix(np.array([row_vector]), feature_names=FEATURE_NAMES)
            preds = self.model.predict(dmatrix)
            prob = float(preds[0])

            # Numerical safety clamp
            prob = max(0.01, min(0.99, prob))
            return round(prob, 4)
        except Exception as e:
            logger.warning("XGBoost inference error: %s. Falling back to IRT-only mode.", e)
            return None


# Global singleton instance
_prediction_service_instance: Optional[XGBoostPredictionService] = None

def get_prediction_service() -> XGBoostPredictionService:
    global _prediction_service_instance
    if _prediction_service_instance is None:
        _prediction_service_instance = XGBoostPredictionService()
    return _prediction_service_instance
