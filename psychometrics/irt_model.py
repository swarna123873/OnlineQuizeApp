import math
from typing import Union, List

class IRTValidationError(ValueError):
    pass

def validate_item_parameters(a: float, b: float) -> None:
    """
    Validates that discrimination `a` is strictly positive and finite,
    and difficulty `b` is finite.
    """
    if not math.isfinite(a) or a <= 0:
        raise IRTValidationError(f"Discrimination parameter 'a' must be positive and finite. Received: {a}")
    if not math.isfinite(b):
        raise IRTValidationError(f"Difficulty parameter 'b' must be finite. Received: {b}")

def calculate_2pl_probability(theta: float, a: float, b: float) -> float:
    """
    Computes the 2-Parameter Logistic (2PL) response probability:
        P_i(theta) = 1 / (1 + exp(-a_i * (theta - b_i)))

    Parameters:
        theta: Latent student ability estimate.
        a: Item discrimination parameter (a > 0).
        b: Item difficulty parameter.

    Returns:
        Probability in (0, 1) that a student with ability theta answers correctly.
    """
    validate_item_parameters(a, b)
    if not math.isfinite(theta):
        raise IRTValidationError(f"Ability parameter 'theta' must be finite. Received: {theta}")

    exponent = -a * (theta - b)
    # Numerical safeguard to prevent overflow/underflow
    if exponent > 35.0:
        return 0.0
    elif exponent < -35.0:
        return 1.0

    return 1.0 / (1.0 + math.exp(exponent))

def calculate_item_information(theta: float, a: float, b: float) -> float:
    """
    Computes the Fisher Item Information for the 2PL model:
        I_i(theta) = a_i^2 * P_i(theta) * (1 - P_i(theta))

    Parameters:
        theta: Latent student ability estimate.
        a: Item discrimination parameter.
        b: Item difficulty parameter.

    Returns:
        Fisher information value at ability theta.
    """
    p = calculate_2pl_probability(theta, a, b)
    return (a ** 2) * p * (1.0 - p)

def calculate_test_information(theta: float, items: List[dict]) -> float:
    """
    Computes total test information across a collection of items at ability theta:
        I(theta) = sum_i I_i(theta)
    """
    total_info = 0.0
    for item in items:
        a = item.get('discrimination', 1.0)
        b = item.get('difficulty', 0.0)
        total_info += calculate_item_information(theta, a, b)
    return total_info
