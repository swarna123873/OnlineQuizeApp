from django.test import TestCase
from django.contrib.auth import get_user_model
from assessments.models import Assessment, AssessmentQuestion, AssessmentAttempt, StudentResponse
from assessments.adaptive_engine import AdaptiveEngine

User = get_user_model()


class AdaptiveEngineUnitTests(TestCase):
    """
    Goal 4 Unit Tests: Central Adaptive Engine & Ranking Policy (Phase 9)
    """

    def setUp(self):
        self.educator = User.objects.create_user(
            email="cat_educator@test.com", password="StrongPassword123!", role="educator"
        )
        self.student = User.objects.create_user(
            email="cat_student@test.com", password="StrongPassword123!", role="student"
        )

        self.assessment = Assessment.objects.create(
            educator=self.educator,
            academic_type="school",
            title="Physics Mechanics Adaptive Diagnostic",
            subject="Physics",
            is_published=True
        )

        # Create a pool of 15 questions with varying difficulties and topics
        self.topics = ["Kinematics", "Dynamics", "Work & Energy", "Rotational Motion"]
        self.questions = []
        for i in range(16):
            topic = self.topics[i % len(self.topics)]
            # Spread difficulties from -2.0 to +2.0
            diff = round(-2.0 + (i * 0.26), 2)
            q = AssessmentQuestion.objects.create(
                assessment=self.assessment,
                question_text=f"Question {i+1} on {topic} (b={diff})",
                option_a="A", option_b="B", option_c="C", option_d="D",
                correct_answer="A",
                topic=topic,
                difficulty="Medium",
                difficulty_b=diff,
                discrimination_a=1.4
            )
            self.questions.append(q)

        self.engine = AdaptiveEngine()

    def test_initial_question_selection_centers_at_zero(self):
        """Initial question should pick the question with difficulty closest to b=0.0."""
        q_init = self.engine.select_initial_question(self.assessment)
        self.assertIsNotNone(q_init)
        # Should be close to b=0.0
        self.assertLessEqual(abs(q_init.difficulty_b - 0.0), 0.5)

    def test_answered_questions_are_strictly_excluded(self):
        """Answered questions must never be re-selected by the adaptive engine."""
        attempt = AssessmentAttempt.objects.create(
            student=self.student,
            assessment=self.assessment,
            status='in_progress'
        )

        # Mark question 0 as answered
        StudentResponse.objects.create(
            attempt=attempt,
            question=self.questions[0],
            question_sequence=1,
            selected_option='A',
            is_correct=True,
            theta_before=0.0,
            theta_after=0.5,
            se_after=0.8
        )

        next_q, telemetry = self.engine.select_next_question(attempt, current_theta=0.5, current_se=0.8)
        self.assertIsNotNone(next_q)
        self.assertNotEqual(next_q.id, self.questions[0].id)
        self.assertEqual(telemetry['candidates_evaluated'], 15)

    def test_ability_shifts_selection_towards_matching_difficulty(self):
        """
        A high-ability student (theta=1.8) should be presented with a more challenging
        question than a low-ability student (theta=-1.8).
        """
        attempt_high = AssessmentAttempt.objects.create(student=self.student, assessment=self.assessment)
        attempt_low = AssessmentAttempt.objects.create(student=self.student, assessment=self.assessment)

        q_high, tel_high = self.engine.select_next_question(attempt_high, current_theta=1.8, current_se=0.5)
        q_low, tel_low = self.engine.select_next_question(attempt_low, current_theta=-1.8, current_se=0.5)

        self.assertIsNotNone(q_high)
        self.assertIsNotNone(q_low)
        self.assertGreater(q_high.difficulty_b, q_low.difficulty_b,
                           f"High theta={1.8} picked b={q_high.difficulty_b}, low theta={-1.8} picked b={q_low.difficulty_b}")

    def test_topic_diversity_balance(self):
        """Topics already tested multiple times should receive lower priority than untested topics."""
        attempt = AssessmentAttempt.objects.create(student=self.student, assessment=self.assessment)

        # Pre-populate 3 answers in "Kinematics"
        kinematics_qs = [q for q in self.questions if q.topic == "Kinematics"]
        for idx, q in enumerate(kinematics_qs[:3]):
            StudentResponse.objects.create(
                attempt=attempt,
                question=q,
                question_sequence=idx+1,
                selected_option='A',
                is_correct=True,
                theta_before=0.0,
                theta_after=0.0,
                se_after=0.8
            )

        next_q, telemetry = self.engine.select_next_question(attempt, current_theta=0.0, current_se=0.7)
        self.assertIsNotNone(next_q)
        # Should favor an under-tested topic like Dynamics, Work & Energy, or Rotational Motion
        self.assertNotEqual(next_q.topic, "Kinematics",
                            "Adaptive engine should prefer under-tested topics to maintain curriculum balance.")

    def test_telemetry_captures_mode_and_scores(self):
        """Engine telemetry must report mode, model version, Fisher information, and candidates evaluated."""
        attempt = AssessmentAttempt.objects.create(student=self.student, assessment=self.assessment)
        next_q, telemetry = self.engine.select_next_question(attempt, current_theta=0.2, current_se=0.6)

        self.assertIn(telemetry['mode'], ['IRT_ONLY', 'IRT_XGBOOST'])
        self.assertGreater(telemetry['calculated_information'], 0.0)
        self.assertEqual(telemetry['candidates_evaluated'], 16)


class AdaptiveAssessmentLiveFlowTests(TestCase):
    """
    Goal 5 Integration Tests: End-to-End Live CAT Exam Flow & Telemetry
    """

    def setUp(self):
        from django.test import Client
        self.client = Client()
        self.educator = User.objects.create_user(
            email="flow_educator@test.com", password="StrongPassword123!", role="educator"
        )
        self.student = User.objects.create_user(
            email="flow_student@test.com", password="StrongPassword123!", role="student"
        )
        self.assessment = Assessment.objects.create(
            educator=self.educator,
            academic_type="school",
            title="Algebra CAT Diagnostic",
            subject="Mathematics",
            is_published=True
        )

        # Create 14 questions across 3 topics
        for i in range(14):
            AssessmentQuestion.objects.create(
                assessment=self.assessment,
                question_text=f"Math Question {i+1}",
                option_a="A", option_b="B", option_c="C", option_d="D",
                correct_answer="B",
                topic=f"Topic_{i % 3}",
                difficulty="Medium",
                difficulty_b=-1.5 + (i * 0.25),
                discrimination_a=1.3
            )

    def test_complete_10_question_adaptive_flow_updates_theta(self):
        """
        Simulates student completing a 10-question adaptive assessment:
        - Ability theta updates after every response.
        - Question selection adapts dynamically.
        - 10th answer completes attempt with final theta and score.
        """
        from django.urls import reverse
        self.client.force_login(self.student)

        # Start attempt
        res_start = self.client.post(reverse('api_start_assessment'), {
            'assessment_id': self.assessment.id
        }, content_type='application/json')
        self.assertEqual(res_start.status_code, 201)
        attempt_id = res_start.data['attempt_id']
        attempt = AssessmentAttempt.objects.get(id=attempt_id)

        # Loop through 10 questions
        for seq in range(1, 11):
            # Load exam room to fetch active question
            url_exam = reverse('student_assessment_exam', kwargs={'attempt_id': attempt_id})
            res_exam = self.client.get(url_exam)
            self.assertEqual(res_exam.status_code, 200)

            active_q = res_exam.context['active_question']
            self.assertIsNotNone(active_q)

            # Answer correctly for first 8, incorrectly for last 2
            answer = "B" if seq <= 8 else "C"
            res_submit = self.client.post(reverse('api_submit_response'), {
                'attempt_id': attempt_id,
                'question_id': active_q.id,
                'selected_option': answer
            }, content_type='application/json')

            self.assertEqual(res_submit.status_code, 200)

            # Verify StudentResponse record
            resp = StudentResponse.objects.get(attempt=attempt, question_sequence=seq)
            self.assertIsNotNone(resp.theta_before)
            self.assertIsNotNone(resp.theta_after)
            self.assertIsNotNone(resp.se_after)
            self.assertGreater(resp.irt_information, 0.0)

            if seq == 1:
                # Correct answer on first question should push theta above prior 0.0
                self.assertGreater(resp.theta_after, 0.0)

            if seq < 10:
                self.assertFalse(res_submit.data['completed'])
            else:
                self.assertTrue(res_submit.data['completed'])

        # Verify final attempt completion metrics
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'completed')
        self.assertEqual(attempt.raw_score, 8)
        self.assertEqual(attempt.accuracy, 80.0)
        self.assertIsNotNone(attempt.final_theta)
        self.assertGreater(attempt.final_theta, 0.0, "Student answering 8/10 correctly must have positive ability theta.")
        self.assertIsNotNone(attempt.final_se)

