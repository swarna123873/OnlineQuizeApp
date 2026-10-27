import math
from django.test import TestCase
from psychometrics.irt_model import (
    calculate_2pl_probability,
    calculate_item_information,
    calculate_test_information,
    validate_item_parameters,
    IRTValidationError,
)
from psychometrics.ability_estimation import AbilityEstimator


class IRTModelUnitTests(TestCase):
    """
    Goal 1 Unit Tests: Item Response Theory 2PL Formula & Fisher Information
    """

    def test_2pl_probability_at_difficulty(self):
        """When ability theta equals item difficulty b, probability must be exactly 0.5."""
        p = calculate_2pl_probability(theta=0.0, a=1.2, b=0.0)
        self.assertAlmostEqual(p, 0.5, places=5)

        p2 = calculate_2pl_probability(theta=1.5, a=2.0, b=1.5)
        self.assertAlmostEqual(p2, 0.5, places=5)

    def test_2pl_probability_directionality(self):
        """P(theta) must strictly increase as ability theta increases."""
        p_low = calculate_2pl_probability(theta=-2.0, a=1.5, b=0.0)
        p_mid = calculate_2pl_probability(theta=0.0, a=1.5, b=0.0)
        p_high = calculate_2pl_probability(theta=2.0, a=1.5, b=0.0)

        self.assertLess(p_low, p_mid)
        self.assertLess(p_mid, p_high)
        self.assertTrue(0.0 < p_low < 0.5)
        self.assertTrue(0.5 < p_high < 1.0)

    def test_2pl_discrimination_steepness(self):
        """Higher discrimination 'a' produces a steeper probability curve."""
        # For theta slightly above difficulty b=0:
        theta = 0.5
        p_flat = calculate_2pl_probability(theta=theta, a=0.5, b=0.0)
        p_steep = calculate_2pl_probability(theta=theta, a=2.5, b=0.0)

        self.assertGreater(p_steep, p_flat)

    def test_parameter_validation_rejects_invalid_values(self):
        """Non-positive discrimination or non-finite values must raise IRTValidationError."""
        with self.assertRaises(IRTValidationError):
            validate_item_parameters(a=0.0, b=1.0)

        with self.assertRaises(IRTValidationError):
            validate_item_parameters(a=-1.2, b=1.0)

        with self.assertRaises(IRTValidationError):
            validate_item_parameters(a=float('nan'), b=1.0)

        with self.assertRaises(IRTValidationError):
            validate_item_parameters(a=1.0, b=float('inf'))

    def test_fisher_item_information_peaks_at_difficulty(self):
        """
        Fisher Item Information I_i(theta) = a^2 * P * (1-P) peaks at theta = b
        where P=0.5, so max info = a^2 * 0.25.
        """
        a = 2.0
        b = 1.0
        expected_max_info = (a ** 2) * 0.25  # 4 * 0.25 = 1.0

        peak_info = calculate_item_information(theta=1.0, a=a, b=b)
        self.assertAlmostEqual(peak_info, expected_max_info, places=5)

        info_below = calculate_item_information(theta=0.0, a=a, b=b)
        info_above = calculate_item_information(theta=2.0, a=a, b=b)

        self.assertLess(info_below, peak_info)
        self.assertLess(info_above, peak_info)
        self.assertAlmostEqual(info_below, info_above, places=5)

    def test_test_information_is_sum_of_item_information(self):
        """Test Information must equal the arithmetic sum of individual item informations."""
        items = [
            {'discrimination': 1.0, 'difficulty': -0.5},
            {'discrimination': 1.5, 'difficulty': 0.0},
            {'discrimination': 1.2, 'difficulty': 0.8},
        ]
        theta = 0.2
        expected_sum = sum(
            calculate_item_information(theta, it['discrimination'], it['difficulty'])
            for it in items
        )
        total_info = calculate_test_information(theta, items)
        self.assertAlmostEqual(total_info, expected_sum, places=5)


class AbilityEstimationUnitTests(TestCase):
    """
    Goal 1 Unit Tests: Newton-Raphson Maximum a Posteriori (MAP) Ability Estimation
    """

    def setUp(self):
        self.estimator = AbilityEstimator(prior_mean=0.0, prior_std=1.0, bounds=(-4.0, 4.0))

    def test_empty_responses_returns_prior_mean(self):
        """When a student has answered 0 questions, ability defaults to prior mean."""
        res = self.estimator.estimate_ability([])
        self.assertEqual(res['theta'], 0.0)
        self.assertEqual(res['standard_error'], 1.0)
        self.assertTrue(res['is_provisional'])
        self.assertEqual(res['items_count'], 0)

    def test_correct_response_increases_theta(self):
        """Answering a question correctly must increase estimated ability theta above prior mean."""
        responses = [
            {'is_correct': True, 'discrimination': 1.2, 'difficulty': 0.0}
        ]
        res = self.estimator.estimate_ability(responses)
        self.assertGreater(res['theta'], 0.0)
        self.assertTrue(res['convergence'])
        self.assertLess(res['standard_error'], 1.0)

    def test_incorrect_response_decreases_theta(self):
        """Answering a question incorrectly must decrease estimated ability theta below prior mean."""
        responses = [
            {'is_correct': False, 'discrimination': 1.2, 'difficulty': 0.0}
        ]
        res = self.estimator.estimate_ability(responses)
        self.assertLess(res['theta'], 0.0)
        self.assertTrue(res['convergence'])
        self.assertLess(res['standard_error'], 1.0)

    def test_extreme_pattern_all_correct_bounded(self):
        """
        An all-correct response pattern (10/10) must produce a finite,
        positive theta strictly within the defined bounds [-4.0, 4.0].
        """
        responses = [
            {'is_correct': True, 'discrimination': 1.2, 'difficulty': (i - 5) * 0.4}
            for i in range(10)
        ]
        res = self.estimator.estimate_ability(responses)
        self.assertGreater(res['theta'], 1.0)
        self.assertLessEqual(res['theta'], 4.0)
        self.assertTrue(math.isfinite(res['theta']))
        self.assertTrue(math.isfinite(res['standard_error']))

    def test_extreme_pattern_all_incorrect_bounded(self):
        """
        An all-incorrect response pattern (0/10) must produce a finite,
        negative theta strictly within the defined bounds [-4.0, 4.0].
        """
        responses = [
            {'is_correct': False, 'discrimination': 1.2, 'difficulty': (i - 5) * 0.4}
            for i in range(10)
        ]
        res = self.estimator.estimate_ability(responses)
        self.assertLess(res['theta'], -1.0)
        self.assertGreaterEqual(res['theta'], -4.0)
        self.assertTrue(math.isfinite(res['theta']))
        self.assertTrue(math.isfinite(res['standard_error']))

    def test_mixed_responses_consistency(self):
        """A student with mostly correct answers must have higher theta than one with mostly incorrect."""
        high_responses = [
            {'is_correct': True, 'discrimination': 1.2, 'difficulty': 0.0},
            {'is_correct': True, 'discrimination': 1.2, 'difficulty': 0.5},
            {'is_correct': False, 'discrimination': 1.2, 'difficulty': 1.0},
        ]
        low_responses = [
            {'is_correct': False, 'discrimination': 1.2, 'difficulty': 0.0},
            {'is_correct': False, 'discrimination': 1.2, 'difficulty': -0.5},
            {'is_correct': True, 'discrimination': 1.2, 'difficulty': -1.0},
        ]
        res_high = self.estimator.estimate_ability(high_responses)
        res_low = self.estimator.estimate_ability(low_responses)

        self.assertGreater(res_high['theta'], res_low['theta'])
