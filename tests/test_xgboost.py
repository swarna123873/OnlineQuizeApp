import os
import tempfile
from django.test import TestCase
from ml.feature_engineering import (
    FEATURE_NAMES,
    extract_candidate_features,
    features_dict_to_vector
)
from ml.prediction_service import XGBoostPredictionService


class XGBoostFeatureEngineeringTests(TestCase):
    """
    Goal 2 Unit Tests: Feature Engineering & Target Leakage Prevention
    """

    def test_feature_names_completeness(self):
        """Feature list must contain all expected psychometric and behavioral predictors."""
        expected = [
            'current_theta',
            'current_se',
            'item_difficulty',
            'item_discrimination',
            'ability_diff',
            'irt_probability',
            'historical_topic_accuracy',
            'recent_streak_accuracy',
            'questions_answered_count',
        ]
        self.assertEqual(FEATURE_NAMES, expected)

    def test_no_target_leakage(self):
        """Extracted features must never contain the question answer, selection, or label."""
        features = extract_candidate_features(
            candidate_difficulty=0.5,
            candidate_discrimination=1.2,
            current_theta=0.2,
            current_se=0.8,
            historical_topic_accuracy=0.7,
            recent_responses=[True, False, True],
            total_answered=3
        )

        forbidden_keys = [
            'correct_answer',
            'selected_option',
            'is_correct',
            'label',
            'target',
            'raw_score',
            'accuracy'
        ]
        for key in forbidden_keys:
            self.assertNotIn(key, features)

    def test_extracted_feature_values_are_valid(self):
        """Feature dictionary must contain valid finite floats within expected bounds."""
        features = extract_candidate_features(
            candidate_difficulty=1.0,
            candidate_discrimination=1.5,
            current_theta=0.5,
            current_se=0.6,
            historical_topic_accuracy=0.8,
            recent_responses=[True, True],
            total_answered=2
        )

        self.assertEqual(len(features), len(FEATURE_NAMES))
        self.assertAlmostEqual(features['ability_diff'], -0.5, places=3)
        self.assertTrue(0.0 <= features['irt_probability'] <= 1.0)
        self.assertAlmostEqual(features['recent_streak_accuracy'], 1.0)
        self.assertEqual(features['questions_answered_count'], 2.0)

    def test_features_dict_to_vector_ordering(self):
        """Vector ordering must match FEATURE_NAMES strictly."""
        features = {name: float(idx) for idx, name in enumerate(FEATURE_NAMES)}
        vector = features_dict_to_vector(features)
        self.assertEqual(vector, [float(i) for i in range(len(FEATURE_NAMES))])


class XGBoostPredictionServiceFallbackTests(TestCase):
    """
    Goal 2 Unit Tests: Prediction Service & IRT-Only Fallback
    """

    def test_missing_model_triggers_clean_fallback(self):
        """If model file does not exist, service must report unavailable and return None."""
        service = XGBoostPredictionService(
            model_path='/nonexistent/path/model.json',
            meta_path='/nonexistent/path/meta.json'
        )

        self.assertFalse(service.is_available())
        self.assertEqual(service.get_model_version(), 'UNAVAILABLE')

        features = extract_candidate_features(
            candidate_difficulty=0.0,
            candidate_discrimination=1.2,
            current_theta=0.0,
            current_se=1.0
        )
        prediction = service.predict_probability(features)
        self.assertIsNone(prediction, "Missing model must return None to trigger IRT-only fallback.")


class XGBoostTrainingAndInferenceTests(TestCase):
    """
    Goal 3 Unit Tests: Reproducible Training Pipeline & Active Prediction
    """

    def test_train_pipeline_generates_artifacts_and_metrics(self):
        """Training pipeline must produce model JSON, metadata JSON, and valid held-out metrics."""
        from ml.train_xgboost import train_and_save_model

        with tempfile.TemporaryDirectory() as tmp_dir:
            meta = train_and_save_model(artifacts_dir=tmp_dir, n_samples=300, random_seed=99)

            model_file = os.path.join(tmp_dir, 'xgboost_model.json')
            meta_file = os.path.join(tmp_dir, 'model_metadata.json')

            self.assertTrue(os.path.exists(model_file))
            self.assertTrue(os.path.exists(meta_file))
            self.assertEqual(meta['status'], 'VALIDATED')
            self.assertIn('roc_auc', meta['metrics'])
            self.assertGreater(meta['metrics']['roc_auc'], 0.6)
            self.assertGreater(meta['metrics']['log_loss'], 0.0)

            # Test loading model from temp dir
            service = XGBoostPredictionService(model_path=model_file, meta_path=meta_file)
            self.assertTrue(service.is_available())
            self.assertEqual(service.get_model_version(), 'XGB-2PL-v1.0')

            features = extract_candidate_features(
                candidate_difficulty=0.0,
                candidate_discrimination=1.2,
                current_theta=1.0,
                current_se=0.5
            )
            prob = service.predict_probability(features)
            self.assertIsNotNone(prob)
            self.assertTrue(0.01 <= prob <= 0.99)

    def test_production_artifacts_active_prediction(self):
        """The persisted production model artifact must load and produce valid predictive probabilities."""
        from ml.prediction_service import get_prediction_service
        service = get_prediction_service()

        self.assertTrue(service.is_available(), "Persisted XGBoost model artifact should be loaded and available.")
        
        # Test easy item for high ability student
        easy_features = extract_candidate_features(
            candidate_difficulty=-1.5,
            candidate_discrimination=1.2,
            current_theta=1.5,
            current_se=0.4
        )
        p_easy = service.predict_probability(easy_features)

        # Test hard item for low ability student
        hard_features = extract_candidate_features(
            candidate_difficulty=1.5,
            candidate_discrimination=1.2,
            current_theta=-1.5,
            current_se=0.4
        )
        p_hard = service.predict_probability(hard_features)

        self.assertIsNotNone(p_easy)
        self.assertIsNotNone(p_hard)
        self.assertGreater(p_easy, p_hard, "High ability student on easy question must have higher predicted probability than low ability student on hard question.")

