from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from assessments.models import Assessment, AssessmentQuestion, AssessmentAttempt, StudentResponse, IntegrityEvent
from academics.models import SchoolAcademicContext

User = get_user_model()

class AssessmentEnvironmentGoal1Tests(TestCase):
    def setUp(self):
        self.client = Client()
        self.educator = User.objects.create_user(
            email="educator_env@test.com",
            password="StrongPassword123!",
            role="educator"
        )
        self.student = User.objects.create_user(
            email="student_env@test.com",
            password="StrongPassword123!",
            role="student"
        )

        self.school_ctx = SchoolAcademicContext.objects.create(
            educator=self.educator,
            school_name="National High School",
            board="CBSE",
            standard="Class 10",
            subject="Physics"
        )

        self.assessment = Assessment.objects.create(
            educator=self.educator,
            academic_type="school",
            school_context=self.school_ctx,
            title="Physics Dynamics Diagnostic",
            subject="Physics",
            is_published=True
        )

        # Create 10 sample questions
        for i in range(10):
            AssessmentQuestion.objects.create(
                assessment=self.assessment,
                question_text=f"Sample Question {i+1} on Dynamics",
                option_a=f"Option A for {i+1}",
                option_b=f"Option B for {i+1}",
                option_c=f"Option C for {i+1}",
                option_d=f"Option D for {i+1}",
                correct_answer="A",
                explanation=f"Explanation for question {i+1}",
                topic="Dynamics",
                difficulty="Medium",
                discrimination_a=1.2,
                difficulty_b=0.0
            )

    def test_instructions_requires_student_login(self):
        """Unauthenticated requests must redirect to login."""
        url = reverse('student_assessment_instructions', kwargs={'assessment_id': self.assessment.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login/', res.url)

    def test_instructions_educator_denied(self):
        """Educators attempting to access student test instructions are blocked/redirected."""
        self.client.force_login(self.educator)
        url = reverse('student_assessment_instructions', kwargs={'assessment_id': self.assessment.id})
        res = self.client.get(url)
        # @student_required redirects educators to login or educator dashboard
        self.assertEqual(res.status_code, 302)

    def test_instructions_student_renders_metadata(self):
        """Authenticated student successfully loads instructions with metadata and rules."""
        self.client.force_login(self.student)
        url = reverse('student_assessment_instructions', kwargs={'assessment_id': self.assessment.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Physics Dynamics Diagnostic")
        self.assertContains(res, "Anti-Cheat")
        self.assertContains(res, "3-Strike")
        self.assertContains(res, "15 Mins")

    def test_instructions_unpublished_assessment_404(self):
        """Unpublished assessments must return 404."""
        self.assessment.is_published = False
        self.assessment.save()
        self.client.force_login(self.student)
        url = reverse('student_assessment_instructions', kwargs={'assessment_id': self.assessment.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 404)

    def test_start_attempt_api_creates_in_progress_attempt(self):
        """POST to start-attempt API creates an AssessmentAttempt and returns redirect URL."""
        self.client.force_login(self.student)
        res = self.client.post(reverse('api_start_assessment'), {
            'assessment_id': self.assessment.id
        }, content_type='application/json')

        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data['success'])
        attempt_id = res.data['attempt_id']
        self.assertIn(f'/student/assessment/{attempt_id}/test/', res.data['redirect_url'])

        # Verify DB attempt state
        attempt = AssessmentAttempt.objects.get(id=attempt_id)
        self.assertEqual(attempt.student, self.student)
        self.assertEqual(attempt.assessment, self.assessment)
        self.assertEqual(attempt.status, 'in_progress')

    def test_start_attempt_api_resumes_existing_attempt(self):
        """If an in-progress attempt already exists, API returns the existing attempt without duplicating."""
        self.client.force_login(self.student)
        attempt = AssessmentAttempt.objects.create(
            student=self.student,
            assessment=self.assessment,
            status='in_progress'
        )

        res = self.client.post(reverse('api_start_assessment'), {
            'assessment_id': self.assessment.id
        }, content_type='application/json')

        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['attempt_id'], attempt.id)
        self.assertEqual(AssessmentAttempt.objects.filter(student=self.student, assessment=self.assessment).count(), 1)


class AssessmentEnvironmentGoals2To5Tests(TestCase):
    def setUp(self):
        self.client = Client()
        self.educator = User.objects.create_user(
            email="educator_env2@test.com",
            password="StrongPassword123!",
            role="educator"
        )
        self.student = User.objects.create_user(
            email="student_env2@test.com",
            password="StrongPassword123!",
            role="student"
        )

        self.assessment = Assessment.objects.create(
            educator=self.educator,
            academic_type="school",
            title="Algebra Diagnostic Test",
            subject="Mathematics",
            is_published=True
        )

        self.questions = []
        for i in range(12):
            q = AssessmentQuestion.objects.create(
                assessment=self.assessment,
                question_text=f"Algebra Question {i+1}: Solve for x in 2x + {i} = 10",
                option_a=f"x = {i}",
                option_b=f"x = {10 - i}",
                option_c=f"x = {(10 - i)/2}",
                option_d=f"x = {i + 5}",
                correct_answer="C",
                explanation=f"Explanation for question {i+1}",
                topic="Algebra",
                difficulty="Medium",
                discrimination_a=1.2,
                difficulty_b=0.0
            )
            self.questions.append(q)

        self.attempt = AssessmentAttempt.objects.create(
            student=self.student,
            assessment=self.assessment,
            status='in_progress'
        )

    def test_exam_room_renders_first_question_and_timer(self):
        """Goal 2: Exam room loads, shows Question 1 of 10, countdown timer and options."""
        self.client.force_login(self.student)
        url = reverse('student_assessment_exam', kwargs={'attempt_id': self.attempt.id})
        res = self.client.get(url)

        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Question 1 of 10")
        self.assertContains(res, "Algebra Diagnostic Test")
        self.assertContains(res, "timer-display")
        self.assertContains(res, "proctor-badge")
        self.assertContains(res, self.questions[0].question_text)

    def test_exam_room_other_student_forbidden(self):
        """A student cannot access another student's exam attempt."""
        other_student = User.objects.create_user(
            email="intruder@test.com",
            password="StrongPassword123!",
            role="student"
        )
        self.client.force_login(other_student)
        url = reverse('student_assessment_exam', kwargs={'attempt_id': self.attempt.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, 404)

    def test_integrity_warning_api_logs_strikes(self):
        """Goal 3: Integrity events are recorded and warning counter increments."""
        self.client.force_login(self.student)

        # Strike 1: Tab switch
        res1 = self.client.post(reverse('api_integrity_warning'), {
            'attempt_id': self.attempt.id,
            'event_type': 'tab_switch'
        }, content_type='application/json')

        self.assertEqual(res1.status_code, 200)
        self.assertFalse(res1.data['terminated'])
        self.assertEqual(res1.data['warning_count'], 1)
        self.assertEqual(self.attempt.integrity_events.count(), 1)

        # Strike 2: Fullscreen exit
        res2 = self.client.post(reverse('api_integrity_warning'), {
            'attempt_id': self.attempt.id,
            'event_type': 'fullscreen_exit'
        }, content_type='application/json')

        self.assertEqual(res2.status_code, 200)
        self.assertFalse(res2.data['terminated'])
        self.assertEqual(res2.data['warning_count'], 2)
        self.assertEqual(self.attempt.integrity_events.count(), 2)

    def test_integrity_warning_3rd_strike_terminates_attempt(self):
        """Goal 3: 3rd strike automatically terminates the attempt."""
        self.client.force_login(self.student)

        # Simulate 2 prior strikes
        IntegrityEvent.objects.create(attempt=self.attempt, event_type='fullscreen_exit', warning_number=1)
        IntegrityEvent.objects.create(attempt=self.attempt, event_type='tab_switch', warning_number=2)

        # Strike 3
        res3 = self.client.post(reverse('api_integrity_warning'), {
            'attempt_id': self.attempt.id,
            'event_type': 'clipboard_attempt'
        }, content_type='application/json')

        self.assertEqual(res3.status_code, 200)
        self.assertTrue(res3.data['terminated'])
        self.assertEqual(res3.data['warning_count'], 3)

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, 'terminated')
        self.assertIsNotNone(self.attempt.completed_at)

    def test_submit_response_api_records_and_advances(self):
        """Goal 4: Submitting an answer correctly logs response and advances sequence."""
        self.client.force_login(self.student)

        res = self.client.post(reverse('api_submit_response'), {
            'attempt_id': self.attempt.id,
            'question_id': self.questions[0].id,
            'selected_option': 'C'  # Correct answer is C
        }, content_type='application/json')

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['success'])
        self.assertFalse(res.data['completed'])
        self.assertTrue(res.data['is_correct'])
        self.assertEqual(res.data['sequence_answered'], 1)
        self.assertEqual(res.data['next_sequence'], 2)

        # Verify DB response
        resp = StudentResponse.objects.get(attempt=self.attempt, question_sequence=1)
        self.assertEqual(resp.selected_option, 'C')
        self.assertTrue(resp.is_correct)

    def test_exam_room_resumes_at_correct_sequence(self):
        """Goal 4 Resilience: Exam room resumes at Question 4 after 3 answered questions."""
        self.client.force_login(self.student)

        # Pre-answer 3 questions
        for i in range(3):
            StudentResponse.objects.create(
                attempt=self.attempt,
                question=self.questions[i],
                question_sequence=i+1,
                selected_option='C',
                is_correct=True,
                theta_before=0.0,
                theta_after=0.0,
                se_after=1.0
            )

        url = reverse('student_assessment_exam', kwargs={'attempt_id': self.attempt.id})
        res = self.client.get(url)

        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Question 4 of 10")
        # Should display 4th question (questions[3])
        self.assertContains(res, self.questions[3].question_text)

    def test_submit_10th_question_completes_attempt_with_scores(self):
        """Goal 5: Answering the 10th question finishes the attempt and computes score."""
        self.client.force_login(self.student)

        # Pre-answer 9 questions (7 correct, 2 incorrect)
        for i in range(9):
            is_corr = (i < 7)
            StudentResponse.objects.create(
                attempt=self.attempt,
                question=self.questions[i],
                question_sequence=i+1,
                selected_option='C' if is_corr else 'A',
                is_correct=is_corr,
                theta_before=0.0,
                theta_after=0.0,
                se_after=1.0
            )

        # Answer 10th question correctly
        res = self.client.post(reverse('api_submit_response'), {
            'attempt_id': self.attempt.id,
            'question_id': self.questions[9].id,
            'selected_option': 'C'
        }, content_type='application/json')

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['completed'])
        self.assertIn(f'/student/assessment/{self.attempt.id}/completed/', res.data['redirect_url'])

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, 'completed')
        self.assertEqual(self.attempt.raw_score, 8)  # 7 + 1 = 8 correct
        self.assertEqual(self.attempt.accuracy, 80.0)

    def test_completed_and_terminated_views(self):
        """Goal 5: Completed view displays final score, terminated view displays violation log."""
        self.client.force_login(self.student)

        # Mark attempt completed
        self.attempt.status = 'completed'
        self.attempt.raw_score = 9
        self.attempt.accuracy = 90.0
        self.attempt.save()

        completed_url = reverse('student_assessment_completed', kwargs={'attempt_id': self.attempt.id})
        res_comp = self.client.get(completed_url)
        self.assertEqual(res_comp.status_code, 200)
        self.assertContains(res_comp, "Assessment Submitted!")
        self.assertContains(res_comp, "9 / 10")
        self.assertContains(res_comp, "90.0%")

        # Test terminated attempt
        self.attempt.status = 'terminated'
        self.attempt.save()
        IntegrityEvent.objects.create(attempt=self.attempt, event_type='fullscreen_exit', warning_number=1)
        IntegrityEvent.objects.create(attempt=self.attempt, event_type='tab_switch', warning_number=2)
        IntegrityEvent.objects.create(attempt=self.attempt, event_type='clipboard_attempt', warning_number=3)

        term_url = reverse('student_assessment_terminated', kwargs={'attempt_id': self.attempt.id})
        res_term = self.client.get(term_url)
        self.assertEqual(res_term.status_code, 200)
        self.assertContains(res_term, "Assessment Terminated")
        self.assertContains(res_term, "Strike 1")
        self.assertContains(res_term, "Strike 2")
        self.assertContains(res_term, "Strike 3")

