"""
Central Adaptive Assessment Engine (Phase 9 of Master Prompt).
Integrates 2PL Item Response Theory (IRT) and XGBoost supervised prediction
to deliver computerized adaptive testing with balanced topic coverage.
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
from django.db.models import Count

from .models import Assessment, AssessmentQuestion, AssessmentAttempt, StudentResponse
from psychometrics.irt_model import calculate_2pl_probability, calculate_item_information
from ml.feature_engineering import extract_candidate_features
from ml.prediction_service import get_prediction_service

logger = logging.getLogger(__name__)


class AdaptiveEngine:
    """
    Decoupled adaptive engine responsible for:
    - Candidate question filtering & eligibility
    - IRT Fisher Item Information evaluation
    - XGBoost predictive probability scoring
    - Topic coverage & balance constraints
    - Multi-objective ranking & question selection
    """

    def __init__(self, top_info_tolerance: float = 0.20, target_p_success: float = 0.60):
        """
        Parameters:
            top_info_tolerance: fraction of peak Fisher Information within which
                                candidates are considered psychometrically optimal.
            target_p_success: Zone of Proximal Development (ZPD) target probability for XGBoost.
        """
        self.top_info_tolerance = top_info_tolerance
        self.target_p_success = target_p_success
        self.prediction_service = get_prediction_service()

    def select_initial_question(self, assessment: Assessment) -> Optional[AssessmentQuestion]:
        """
        Phase 9.2: Selects the initial question for a brand-new assessment attempt.
        Uses central difficulty (b closest to 0.0) with high discrimination.
        """
        questions = assessment.questions.all()
        if not questions.exists():
            return None

        # Sort by distance of difficulty_b from 0.0, tie-break by discrimination_a descending
        candidates = list(questions)
        candidates.sort(key=lambda q: (abs(q.difficulty_b - 0.0), -q.discrimination_a))
        return candidates[0]

    def select_next_question(
        self,
        attempt: AssessmentAttempt,
        current_theta: float,
        current_se: float
    ) -> Tuple[Optional[AssessmentQuestion], Dict[str, Any]]:
        """
        Phase 9.3 – 9.7: Evaluates remaining eligible candidate questions and
        selects the next item based on IRT information and XGBoost prediction.

        Returns:
            Tuple of (selected_question, telemetry_dict)
        """
        # 1. Candidate Eligibility & Answered Exclusion
        answered_ids = list(attempt.responses.values_list('question_id', flat=True))
        candidate_pool = list(attempt.assessment.questions.exclude(id__in=answered_ids))

        if not candidate_pool:
            return None, {'status': 'NO_CANDIDATES_REMAINING'}

        # 2. Topic Coverage Tracking
        topic_counts: Dict[str, int] = {}
        for resp in attempt.responses.select_related('question'):
            t = resp.question.topic
            topic_counts[t] = topic_counts.get(t, 0) + 1

        recent_responses = list(attempt.responses.order_by('question_sequence').values_list('is_correct', flat=True))
        total_answered = len(answered_ids)

        # 3. Compute IRT & XGBoost Signals for Each Candidate
        xgboost_available = self.prediction_service.is_available()
        evaluated_candidates = []

        for q in candidate_pool:
            a = q.discrimination_a
            b = q.difficulty_b

            # IRT metrics
            prob_irt = calculate_2pl_probability(current_theta, a, b)
            fisher_info = calculate_item_information(current_theta, a, b)

            # Historical topic accuracy for this student
            past_topic_responses = StudentResponse.objects.filter(
                attempt__student=attempt.student,
                question__topic=q.topic
            )
            topic_total = past_topic_responses.count()
            if topic_total > 0:
                hist_topic_acc = past_topic_responses.filter(is_correct=True).count() / topic_total
            else:
                hist_topic_acc = 0.5

            # XGBoost prediction
            prob_xgb = None
            if xgboost_available:
                feat = extract_candidate_features(
                    candidate_difficulty=b,
                    candidate_discrimination=a,
                    current_theta=current_theta,
                    current_se=current_se,
                    historical_topic_accuracy=hist_topic_acc,
                    recent_responses=recent_responses,
                    total_answered=total_answered
                )
                prob_xgb = self.prediction_service.predict_probability(feat)

            times_topic_tested = topic_counts.get(q.topic, 0)

            evaluated_candidates.append({
                'question': q,
                'fisher_info': fisher_info,
                'prob_irt': prob_irt,
                'prob_xgb': prob_xgb,
                'topic': q.topic,
                'times_topic_tested': times_topic_tested,
            })

        # 4. Multi-Objective Ranking Strategy (Phase 9.7)
        max_info = max(c['fisher_info'] for c in evaluated_candidates)
        # Psychometric tier: within top_info_tolerance of maximum Fisher information
        info_cutoff = max_info * (1.0 - self.top_info_tolerance)
        top_tier = [c for c in evaluated_candidates if c['fisher_info'] >= info_cutoff]

        if not top_tier:
            top_tier = evaluated_candidates

        mode_used = 'IRT_ONLY'

        if xgboost_available and any(c['prob_xgb'] is not None for c in top_tier):
            mode_used = 'IRT_XGBOOST'
            # Rank top-information candidates by proximity to target ZPD success probability
            # and penalize over-tested topics
            def ranking_key(c):
                p_hat = c['prob_xgb'] if c['prob_xgb'] is not None else c['prob_irt']
                zpd_distance = abs(p_hat - self.target_p_success)
                topic_penalty = c['times_topic_tested'] * 0.25
                return (zpd_distance + topic_penalty, -c['fisher_info'])

            top_tier.sort(key=ranking_key)
        else:
            mode_used = 'IRT_ONLY'
            # In IRT-only mode, maximize Fisher Information and prioritize under-tested topics
            def irt_key(c):
                topic_penalty = c['times_topic_tested'] * 0.15
                # Higher information is better, lower topic penalty is better
                return (c['times_topic_tested'], -c['fisher_info'])

            top_tier.sort(key=irt_key)

        selected_record = top_tier[0]
        selected_question = selected_record['question']

        telemetry = {
            'mode': mode_used,
            'model_version': self.prediction_service.get_model_version(),
            'current_theta': round(current_theta, 4),
            'current_se': round(current_se, 4),
            'calculated_information': round(selected_record['fisher_info'], 4),
            'predicted_prob': selected_record['prob_xgb'],
            'irt_prob': round(selected_record['prob_irt'], 4),
            'candidates_evaluated': len(candidate_pool),
            'selected_topic': selected_question.topic,
        }

        return selected_question, telemetry
