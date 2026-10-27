from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from academics.models import SchoolAcademicContext, CollegeAcademicContext

User = get_user_model()

class AcademicRecordsAndCascadingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.educator = User.objects.create_user(
            email="educator@school.edu",
            password="StrongPassword123!",
            role="educator"
        )
        self.student = User.objects.create_user(
            email="student@school.edu",
            password="StrongPassword123!",
            role="student"
        )

        # Register sample School record in DB
        self.school_ctx = SchoolAcademicContext.objects.create(
            educator=self.educator,
            school_name="Delhi Public School",
            board="CBSE",
            state="",
            standard="Class 10",
            subject="Mathematics"
        )

        # Register sample College record in DB
        self.college_ctx = CollegeAcademicContext.objects.create(
            educator=self.educator,
            college_name="IIT Bombay",
            degree="B.Tech",
            academic_year="3rd Year",
            branch="Computer Science & Engineering",
            classification="Core",
            subject="Operating Systems"
        )

    def test_school_context_persisted(self):
        """Verify school context is stored in database with educator link."""
        self.assertEqual(SchoolAcademicContext.objects.count(), 1)
        record = SchoolAcademicContext.objects.first()
        self.assertEqual(record.school_name, "Delhi Public School")
        self.assertEqual(record.board, "CBSE")
        self.assertEqual(record.standard, "Class 10")
        self.assertEqual(record.subject, "Mathematics")
        self.assertEqual(record.educator, self.educator)

    def test_college_context_persisted(self):
        """Verify college context is stored with valid degree, year, and subject classification."""
        self.assertEqual(CollegeAcademicContext.objects.count(), 1)
        record = CollegeAcademicContext.objects.first()
        self.assertEqual(record.college_name, "IIT Bombay")
        self.assertEqual(record.degree, "B.Tech")
        self.assertEqual(record.academic_year, "3rd Year")
        self.assertEqual(record.classification, "Core")
        self.assertEqual(record.subject, "Operating Systems")

    def test_school_cascading_dropdown_api(self):
        """Test cascading dropdown options come strictly from database records."""
        self.client.force_login(self.student)

        # 1. Fetch schools
        res = self.client.get(reverse('api_school_options'), {'field': 'school_name'})
        self.assertEqual(res.status_code, 200)
        self.assertIn("Delhi Public School", res.data['options'])

        # 2. Fetch boards for school
        res = self.client.get(reverse('api_school_options'), {
            'field': 'board',
            'school_name': 'Delhi Public School'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn("CBSE", res.data['options'])

        # 3. Fetch standards for school and board
        res = self.client.get(reverse('api_school_options'), {
            'field': 'standard',
            'school_name': 'Delhi Public School',
            'board': 'CBSE'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn("Class 10", res.data['options'])

        # 4. Fetch subjects
        res = self.client.get(reverse('api_school_options'), {
            'field': 'subject',
            'school_name': 'Delhi Public School',
            'board': 'CBSE',
            'standard': 'Class 10'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn("Mathematics", res.data['options'])

    def test_college_cascading_dropdown_api(self):
        """Test college cascading dropdown options come strictly from database records."""
        self.client.force_login(self.student)

        # 1. Colleges
        res = self.client.get(reverse('api_college_options'), {'field': 'college_name'})
        self.assertEqual(res.status_code, 200)
        self.assertIn("IIT Bombay", res.data['options'])

        # 2. Degrees for college
        res = self.client.get(reverse('api_college_options'), {
            'field': 'degree',
            'college_name': 'IIT Bombay'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn("B.Tech", res.data['options'])

        # 3. Years
        res = self.client.get(reverse('api_college_options'), {
            'field': 'academic_year',
            'college_name': 'IIT Bombay',
            'degree': 'B.Tech'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn("3rd Year", res.data['options'])

        # 4. Subjects
        res = self.client.get(reverse('api_college_options'), {
            'field': 'subject',
            'college_name': 'IIT Bombay',
            'degree': 'B.Tech',
            'academic_year': '3rd Year'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn("Operating Systems", res.data['options'])

    def test_matching_published_school_assessment_success(self):
        """Test student finds matching published school assessment when details match."""
        from assessments.models import Assessment, AssessmentQuestion

        # Create published assessment with 10 questions
        assessment = Assessment.objects.create(
            educator=self.educator,
            academic_type='school',
            school_context=self.school_ctx,
            title="Class 10 Math Mid-Term",
            subject="Mathematics",
            is_published=True
        )
        for i in range(10):
            AssessmentQuestion.objects.create(
                assessment=assessment,
                question_text=f"Question {i}",
                option_a="1", option_b="2", option_c="3", option_d="4",
                correct_answer="A",
                topic="Algebra",
                difficulty="Medium"
            )

        self.client.force_login(self.student)
        res = self.client.post(reverse('api_match_assessment'), {
            'academic_type': 'school',
            'school_name': 'Delhi Public School',
            'board': 'CBSE',
            'standard': 'Class 10',
            'subject': 'Mathematics'
        }, content_type='application/json')

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['found'])
        self.assertEqual(res.data['assessment']['id'], assessment.id)
        self.assertEqual(res.data['assessment']['title'], "Class 10 Math Mid-Term")

    def test_no_assessment_available_message(self):
        """When no matching assessment exists, returns the exact required message."""
        self.client.force_login(self.student)
        res = self.client.post(reverse('api_match_assessment'), {
            'academic_type': 'school',
            'school_name': 'Delhi Public School',
            'board': 'CBSE',
            'standard': 'Class 10',
            'subject': 'NonExistentSubject'
        }, content_type='application/json')

        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['found'])
        self.assertEqual(res.data['message'], "No assessment is currently available for your selected academic details.")

    def test_matching_published_college_assessment_success(self):
        """Test student finds matching published college assessment."""
        from assessments.models import Assessment, AssessmentQuestion

        assessment = Assessment.objects.create(
            educator=self.educator,
            academic_type='college',
            college_context=self.college_ctx,
            title="OS Semester Assessment",
            subject="Operating Systems",
            is_published=True
        )
        for i in range(10):
            AssessmentQuestion.objects.create(
                assessment=assessment,
                question_text=f"OS Question {i}",
                option_a="A", option_b="B", option_c="C", option_d="D",
                correct_answer="A",
                topic="Processes",
                difficulty="Medium"
            )

        self.client.force_login(self.student)
        res = self.client.post(reverse('api_match_assessment'), {
            'academic_type': 'college',
            'college_name': 'IIT Bombay',
            'degree': 'B.Tech',
            'academic_year': '3rd Year',
            'branch': 'Computer Science & Engineering',
            'subject': 'Operating Systems'
        }, content_type='application/json')

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['found'])
        self.assertEqual(res.data['assessment']['id'], assessment.id)
