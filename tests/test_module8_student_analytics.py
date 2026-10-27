import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from assessments.models import Assessment, AssessmentQuestion, AssessmentAttempt, StudentResponse

User = get_user_model()


class Module8StudentAnalyticsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            email="student_m8@test.com",
            password="StrongPassword123!",
            role="student"
        )
        self.educator = User.objects.create_user(
            email="educator_m8@test.com",
            password="StrongPassword123!",
            role="educator"
        )
        self.assessment = Assessment.objects.create(
            title="Thermodynamics Diagnostics",
            academic_type="school",
            subject="Physics",
            educator=self.educator,
            is_published=True
        )

    def test_attempt_duration_properties(self):
        """Test duration_seconds, duration_formatted, and incorrect_count properties."""
        start_time = timezone.now() - datetime.timedelta(minutes=4, seconds=35)
        end_time = timezone.now()

        attempt = AssessmentAttempt.objects.create(
            student=self.student,
            assessment=self.assessment,
            status='completed',
            started_at=start_time,
            completed_at=end_time,
            raw_score=7,
            accuracy=70.0,
            final_theta=0.85,
            final_se=0.32
        )
        # Update started_at directly because auto_now_add overrides on creation
        AssessmentAttempt.objects.filter(id=attempt.id).update(started_at=start_time)
        attempt.refresh_from_db()

        self.assertAlmostEqual(attempt.duration_seconds, 275, delta=3)
        self.assertEqual(attempt.duration_formatted, "4m 35s")
        self.assertEqual(attempt.incorrect_count, 3)

    def test_student_dashboard_context_and_tabs(self):
        """Test student dashboard renders tabs, past attempts, score, and Time Taken."""
        start_time = timezone.now() - datetime.timedelta(minutes=6, seconds=10)
        end_time = timezone.now()

        attempt = AssessmentAttempt.objects.create(
            student=self.student,
            assessment=self.assessment,
            status='completed',
            completed_at=end_time,
            raw_score=8,
            accuracy=80.0,
            final_theta=1.24,
            final_se=0.28
        )
        AssessmentAttempt.objects.filter(id=attempt.id).update(started_at=start_time)

        self.client.force_login(self.student)
        response = self.client.get(reverse('student_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('attempts', response.context)
        self.assertEqual(response.context['total_completed'], 1)
        self.assertEqual(response.context['avg_accuracy'], 80.0)
        self.assertEqual(response.context['latest_theta'], 1.24)

        # HTML Checks
        content = response.content.decode('utf-8')
        self.assertIn('Previously Attempted Tests & Results', content)
        self.assertIn('Thermodynamics Diagnostics', content)
        self.assertIn('8/10', content)
        self.assertIn('Time Taken', content)
        self.assertIn('6m 10s', content)
        self.assertIn('1.24', content)

    def test_student_dashboard_empty_state(self):
        """Test student dashboard shows empty state when no attempts exist."""
        self.client.force_login(self.student)
        response = self.client.get(reverse('student_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_completed'], 0)
        content = response.content.decode('utf-8')
        self.assertIn('No Attempted Assessments Yet', content)

    def test_detailed_results_view_and_justifications(self):
        """Test Goal 8.2 to 8.5: Question review, justifications, time taken, trajectory & ZPD."""
        start_time = timezone.now() - datetime.timedelta(minutes=5, seconds=20)
        end_time = timezone.now()

        attempt = AssessmentAttempt.objects.create(
            student=self.student,
            assessment=self.assessment,
            status='completed',
            completed_at=end_time,
            raw_score=7,
            accuracy=70.0,
            final_theta=0.92,
            final_se=0.31
        )
        AssessmentAttempt.objects.filter(id=attempt.id).update(started_at=start_time)

        # Create 10 questions and responses
        for seq in range(1, 11):
            is_correct = (seq <= 7)
            q = AssessmentQuestion.objects.create(
                assessment=self.assessment,
                question_text=f"What is thermodynamic principle #{seq}?",
                option_a="Principle A (Conservation of energy)",
                option_b="Principle B (Entropy increase)",
                option_c="Principle C (Absolute zero)",
                option_d="Principle D (Thermal equilibrium)",
                correct_answer="B",
                explanation=f"Principle #{seq} explanation: Entropy increases spontaneously in isolated systems.",
                topic="Thermodynamics" if seq <= 6 else "Heat Transfer",
                difficulty="Medium" if seq <= 5 else "Hard",
                discrimination_a=1.2,
                difficulty_b=round(-1.0 + (seq * 0.2), 2),
                source_reference="NCERT Physics Chapter 12"
            )
            StudentResponse.objects.create(
                attempt=attempt,
                question=q,
                question_sequence=seq,
                selected_option="B" if is_correct else "A",
                is_correct=is_correct,
                theta_before=0.0 + (seq * 0.1),
                theta_after=0.1 + (seq * 0.1),
                se_after=0.35 - (seq * 0.01),
                irt_information=1.45
            )

        self.client.force_login(self.student)
        response = self.client.get(reverse('student_assessment_completed', kwargs={'attempt_id': attempt.id}))

        self.assertEqual(response.status_code, 200)
        self.assertIn('review_data', response.context)
        self.assertEqual(len(response.context['review_data']), 10)
        self.assertEqual(len(response.context['topic_mastery']), 2)
        self.assertTrue(len(response.context['recommendations']) >= 1)

        content = response.content.decode('utf-8')

        # 1. User Requirement: Time Taken displayed
        self.assertIn('Time Taken', content)
        self.assertIn('5m 20s', content)

        # 2. User Requirement: Correct and Incorrect score cards
        self.assertIn('7 / 10', content)
        self.assertIn('70.0%', content)

        # 3. User Requirement: "See Justification for Correct Answer" button and detailed sections
        self.assertIn('See Justification for Correct Answer', content)
        self.assertIn('Entropy increases spontaneously in isolated systems', content)
        self.assertIn('Official Correct Answer: Option B', content)
        self.assertIn('Step-by-Step Pedagogical Justification', content)
        self.assertIn('Conceptual Foundation', content)
        self.assertIn('Key Examination Tip', content)

        # 4. Psychometrics & ZPD
        self.assertIn('IRT Ability Progression', content)
        self.assertIn('Zone of Proximal Development', content)

