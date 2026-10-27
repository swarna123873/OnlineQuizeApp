"""
Feature Engineering for XGBoost Candidate Response Prediction.
Strictly prevents target leakage: features depend only on student performance
history and candidate item metadata available BEFORE the response is made.
"""
from typing import Dict, Any, List, Optional
import math
from psychometrics.irt_model import calculate_2pl_probability

FEATURE_NAMES = [
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


def extract_candidate_features(
    candidate_difficulty: float,
    candidate_discrimination: float,
    current_theta: float,
    current_se: float,
    historical_topic_accuracy: float = 0.5,
    recent_responses: Optional[List[bool]] = None,
    total_answered: int = 0
) -> Dict[str, float]:
    """
    Constructs the feature dictionary for a candidate question.

    Parameters:
        candidate_difficulty: b parameter of the candidate item.
        candidate_discrimination: a parameter of the candidate item.
        current_theta: student's current latent ability estimate theta.
        current_se: standard error of the current ability estimate.
        historical_topic_accuracy: student's past accuracy on this topic (default 0.5 if new).
        recent_responses: list of boolean correctness for the last answered items in this attempt.
        total_answered: number of questions answered so far in this attempt (0 to 9).

    Returns:
        Dictionary mapping feature names to numerical float values.
    """
    # Safe defaults and finite guards
    theta = float(current_theta) if math.isfinite(current_theta) else 0.0
    se = float(current_se) if math.isfinite(current_se) else 1.0
    b = float(candidate_difficulty) if math.isfinite(candidate_difficulty) else 0.0
    a = float(candidate_discrimination) if (math.isfinite(candidate_discrimination) and candidate_discrimination > 0) else 1.2

    ability_diff = theta - b

    # Compute 2PL response probability
    try:
        irt_prob = calculate_2pl_probability(theta, a, b)
    except Exception:
        irt_prob = 0.5

    # Historical topic accuracy in [0.0, 1.0]
    topic_acc = max(0.0, min(1.0, float(historical_topic_accuracy)))

    # Recent response accuracy (over up to last 3 questions)
    if recent_responses:
        slice_resp = recent_responses[-3:]
        streak_acc = sum(1.0 for r in slice_resp if r) / len(slice_resp)
    else:
        streak_acc = 0.5

    return {
        'current_theta': round(theta, 4),
        'current_se': round(se, 4),
        'item_difficulty': round(b, 4),
        'item_discrimination': round(a, 4),
        'ability_diff': round(ability_diff, 4),
        'irt_probability': round(irt_prob, 4),
        'historical_topic_accuracy': round(topic_acc, 4),
        'recent_streak_accuracy': round(streak_acc, 4),
        'questions_answered_count': float(total_answered),
    }


def features_dict_to_vector(features: Dict[str, float]) -> List[float]:
    """Converts a features dictionary to an ordered numerical vector matching FEATURE_NAMES."""
    return [float(features.get(name, 0.0)) for name in FEATURE_NAMES]
