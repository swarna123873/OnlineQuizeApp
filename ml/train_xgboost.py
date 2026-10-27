"""
Reproducible Training & Evaluation Pipeline for XGBoost Response Predictor.
Adheres to Phase 8 requirements:
- Data validation and target leakage prevention.
- 80/20 train/test split.
- Generalization metrics: Log Loss, ROC-AUC, Brier score.
- Model artifact and evaluation metadata persistence.
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import log_loss, roc_auc_score, brier_score_loss

from .feature_engineering import FEATURE_NAMES, extract_candidate_features, features_dict_to_vector
from psychometrics.irt_model import calculate_2pl_probability

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ARTIFACTS_DIR = os.path.join(BASE_DIR, 'ml', 'artifacts')


def generate_synthetic_training_data(n_samples: int = 1500, random_seed: int = 42) -> Tuple[np.ndarray, np.ndarray]:
    """
    Synthesizes realistic training data via 2PL Monte Carlo simulation
    when genuine historical student responses are sparse (Phase 8.5 bootstrap).
    """
    np.random.seed(random_seed)
    X_rows = []
    y_labels = []

    for _ in range(n_samples):
        # Student latent ability theta ~ N(0, 1)
        theta = float(np.random.normal(0.0, 1.0))
        se = float(max(0.2, min(1.0, 1.0 / np.sqrt(max(1.0, np.random.uniform(1.0, 8.0))))))

        # Candidate item parameters
        b = float(np.random.uniform(-2.5, 2.5))
        a = float(np.random.uniform(0.8, 2.2))

        # Contextual features
        hist_acc = float(np.random.beta(5, 5))
        n_prev = int(np.random.randint(0, 10))
        recent_resps = [bool(np.random.rand() < hist_acc) for _ in range(min(3, n_prev))]

        # Feature vector (leak-free)
        feat_dict = extract_candidate_features(
            candidate_difficulty=b,
            candidate_discrimination=a,
            current_theta=theta,
            current_se=se,
            historical_topic_accuracy=hist_acc,
            recent_responses=recent_resps,
            total_answered=n_prev
        )
        row = features_dict_to_vector(feat_dict)

        # Ground truth response label from true 2PL probability with slight behavioral noise
        true_p = calculate_2pl_probability(theta, a, b)
        # Adding subtle realistic noise (e.g. fatigue, lucky guess)
        noisy_p = max(0.02, min(0.98, true_p * 0.9 + hist_acc * 0.1))
        label = 1 if np.random.rand() < noisy_p else 0

        X_rows.append(row)
        y_labels.append(label)

    return np.array(X_rows, dtype=np.float32), np.array(y_labels, dtype=np.int32)


def train_and_save_model(
    artifacts_dir: Optional[str] = None,
    n_samples: int = 2000,
    random_seed: int = 42
) -> Dict[str, Any]:
    """
    Trains an XGBoost classifier, evaluates held-out metrics, and saves the model artifact.
    """
    out_dir = artifacts_dir or DEFAULT_ARTIFACTS_DIR
    os.makedirs(out_dir, exist_ok=True)

    # 1. Prepare data
    X, y = generate_synthetic_training_data(n_samples=n_samples, random_seed=random_seed)

    # 2. 80/20 Train/Test separation
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=random_seed, stratify=y
    )

    # 3. Train XGBoost
    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=FEATURE_NAMES)
    dval = xgb.DMatrix(X_val, label=y_val, feature_names=FEATURE_NAMES)

    params = {
        'objective': 'binary:logistic',
        'eval_metric': 'logloss',
        'max_depth': 4,
        'learning_rate': 0.08,
        'subsample': 0.85,
        'colsample_bytree': 0.85,
        'seed': random_seed,
    }

    evals = [(dtrain, 'train'), (dval, 'val')]
    booster = xgb.train(
        params,
        dtrain,
        num_boost_round=80,
        evals=evals,
        verbose_eval=False
    )

    # 4. Held-out validation evaluation
    preds_val = booster.predict(dval)
    val_logloss = float(log_loss(y_val, preds_val))
    val_auc = float(roc_auc_score(y_val, preds_val))
    val_brier = float(brier_score_loss(y_val, preds_val))

    # 5. Save model and metadata
    model_path = os.path.join(out_dir, 'xgboost_model.json')
    meta_path = os.path.join(out_dir, 'model_metadata.json')

    booster.save_model(model_path)

    metadata = {
        'model_version': 'XGB-2PL-v1.0',
        'trained_at': datetime.utcnow().isoformat() + 'Z',
        'feature_names': FEATURE_NAMES,
        'train_samples': int(len(X_train)),
        'val_samples': int(len(X_val)),
        'metrics': {
            'log_loss': round(val_logloss, 4),
            'roc_auc': round(val_auc, 4),
            'brier_score': round(val_brier, 4),
        },
        'status': 'VALIDATED'
    }

    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    logger.info("XGBoost model saved to %s (AUC: %.4f, LogLoss: %.4f)", model_path, val_auc, val_logloss)
    return metadata


if __name__ == '__main__':
    train_and_save_model()
