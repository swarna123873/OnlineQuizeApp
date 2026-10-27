import math
from typing import List, Dict, Tuple, Optional
from .irt_model import calculate_2pl_probability, calculate_item_information, validate_item_parameters

class AbilityEstimator:
    """
    Psychometric ability estimation for the 2PL IRT model using
    Maximum a Posteriori (MAP) estimation with a normal prior N(prior_mean, prior_std^2).
    """

    def __init__(self, prior_mean: float = 0.0, prior_std: float = 1.0, bounds: Tuple[float, float] = (-4.0, 4.0)):
        self.prior_mean = prior_mean
        self.prior_std = prior_std
        self.bounds = bounds

    def log_posterior(self, theta: float, responses: List[Dict]) -> float:
        """
        Computes log posterior:
            ln P(theta | u) = sum_i [u_i * ln(P_i) + (1 - u_i) * ln(1 - P_i)] - (theta - mu)^2 / (2 * sigma^2)
        """
        eps = 1e-12
        ll = 0.0
        for resp in responses:
            u = 1.0 if resp['is_correct'] else 0.0
            a = resp['discrimination']
            b = resp['difficulty']
            p = calculate_2pl_probability(theta, a, b)
            p = max(eps, min(1.0 - eps, p))
            ll += u * math.log(p) + (1.0 - u) * math.log(1.0 - p)

        prior_penalty = -0.5 * ((theta - self.prior_mean) / self.prior_std) ** 2
        return ll + prior_penalty

    def d_log_posterior(self, theta: float, responses: List[Dict]) -> float:
        """
        First derivative of the log-posterior with respect to theta:
            d/dtheta = sum_i a_i * (u_i - P_i(theta)) - (theta - mu) / (sigma^2)
        """
        grad = 0.0
        for resp in responses:
            u = 1.0 if resp['is_correct'] else 0.0
            a = resp['discrimination']
            b = resp['difficulty']
            p = calculate_2pl_probability(theta, a, b)
            grad += a * (u - p)

        grad -= (theta - self.prior_mean) / (self.prior_std ** 2)
        return grad

    def d2_log_posterior(self, theta: float, responses: List[Dict]) -> float:
        """
        Second derivative (Hessian) of the log-posterior with respect to theta:
            d2/dtheta2 = - sum_i a_i^2 * P_i(theta) * (1 - P_i(theta)) - 1 / (sigma^2)
        This is strictly negative everywhere, guaranteeing strict concavity.
        """
        hess = 0.0
        for resp in responses:
            a = resp['discrimination']
            b = resp['difficulty']
            hess -= calculate_item_information(theta, a, b)

        hess -= 1.0 / (self.prior_std ** 2)
        return hess

    def estimate_ability(self, responses: List[Dict]) -> Dict:
        """
        Estimates theta using Newton-Raphson on the concave log-posterior function.
        Safeguarded with bounded step clipping and fallback to prior mean when no responses.

        Each element of `responses` is expected to have:
            - 'is_correct': bool or int (1/0)
            - 'difficulty': float (b parameter)
            - 'discrimination': float (a parameter)
        """
        # Case: No responses yet (Brand new student / start of test)
        if not responses:
            return {
                'theta': self.prior_mean,
                'standard_error': self.prior_std,
                'is_provisional': True,
                'convergence': True,
                'method': 'MAP_PRIOR',
                'items_count': 0,
                'message': 'Initial ability initialized to prior mean.'
            }

        # Filter and validate responses
        valid_responses = []
        for r in responses:
            try:
                a = float(r.get('discrimination', 1.0))
                b = float(r.get('difficulty', 0.0))
                validate_item_parameters(a, b)
                valid_responses.append({
                    'is_correct': bool(r.get('is_correct')),
                    'discrimination': a,
                    'difficulty': b
                })
            except Exception:
                continue

        if not valid_responses:
            return {
                'theta': self.prior_mean,
                'standard_error': self.prior_std,
                'is_provisional': True,
                'convergence': False,
                'method': 'FALLBACK_PRIOR',
                'items_count': 0,
                'message': 'No valid item parameters found; defaulted to prior.'
            }

        # Newton-Raphson iteration starting from prior_mean
        theta = self.prior_mean
        max_iter = 30
        tolerance = 1e-5
        converged = False

        for _ in range(max_iter):
            grad = self.d_log_posterior(theta, valid_responses)
            hess = self.d2_log_posterior(theta, valid_responses)

            if abs(hess) < 1e-12:
                break

            step = -grad / hess

            # Clip step to maintain numerical stability
            max_step = 1.0
            if step > max_step:
                step = max_step
            elif step < -max_step:
                step = -max_step

            new_theta = theta + step

            # Enforce bounds
            new_theta = max(self.bounds[0], min(self.bounds[1], new_theta))

            if abs(new_theta - theta) < tolerance:
                theta = new_theta
                converged = True
                break

            theta = new_theta

        # Compute posterior standard error: SE(theta) = 1 / sqrt(-hessian)
        final_hessian = self.d2_log_posterior(theta, valid_responses)
        info_value = max(1e-6, -final_hessian)
        se = 1.0 / math.sqrt(info_value)

        # Standard error is bounded by prior_std
        se = min(se, self.prior_std)

        return {
            'theta': round(theta, 4),
            'standard_error': round(se, 4),
            'is_provisional': True,  # labeled provisional until empirically calibrated
            'convergence': converged,
            'method': 'MAP',
            'items_count': len(valid_responses),
            'message': 'Ability estimated via 2PL MAP.'
        }
