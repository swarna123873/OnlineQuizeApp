from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from content.models import UploadedDocument, QuestionDraft
from assessments.models import Assessment, AssessmentQuestion

User = get_user_model()


class QuestionGenerationAndPublishingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.educator = User.objects.create_user(
            email="educator_q@test.com",
            password="StrongPassword123!",
            role="educator"
        )
        self.student = User.objects.create_user(
            email="student_q@test.com",
            password="StrongPassword123!",
            role="student"
        )

        self.doc = UploadedDocument.objects.create(
            educator=self.educator,
            title="Physics Chapter 4 - Thermodynamics",
            extracted_text="Sample text content for thermodynamics.",
            total_pages=5
        )

    def test_provisional_irt_parameter_assignment(self):
        """Test that provisional difficulty and discrimination are properly assigned."""
        draft_easy = QuestionDraft(
            document=self.doc,
            educator=self.educator,
            question_text="Easy Question",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_answer="A",
            topic="Thermodynamics",
            difficulty="Easy"
        )
        draft_easy.assign_provisional_irt_parameters()
        draft_easy.save()
        self.assertEqual(draft_easy.provisional_difficulty, -1.0)
        self.assertEqual(draft_easy.provisional_discrimination, 1.2)

        draft_hard = QuestionDraft(
            document=self.doc,
            educator=self.educator,
            question_text="Hard Question",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_answer="B",
            topic="Thermodynamics",
            difficulty="Hard"
        )
        draft_hard.assign_provisional_irt_parameters()
        draft_hard.save()
        self.assertEqual(draft_hard.provisional_difficulty, 1.0)
        self.assertEqual(draft_hard.provisional_discrimination, 1.2)

    def test_publishing_rejected_with_fewer_than_10_approved(self):
        """Assessments cannot be published with fewer than 10 approved questions."""
        self.client.force_login(self.educator)

        # Create only 5 approved drafts
        for i in range(5):
            d = QuestionDraft.objects.create(
                document=self.doc,
                educator=self.educator,
                question_text=f"Sample Question {i}",
                option_a="A", option_b="B", option_c="C", option_d="D",
                correct_answer="A",
                topic="Thermodynamics",
                difficulty="Medium",
                is_approved=True
            )
            d.assign_provisional_irt_parameters()
            d.save()

        response = self.client.post(reverse('api_publish_assessment'), {
            'document_id': self.doc.id,
            'academic_type': 'school'
        }, content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertIn("At least 10 approved questions are required", response.data['error'])
        self.assertEqual(Assessment.objects.count(), 0)

    def test_publishing_succeeds_with_10_approved_questions(self):
        """Assessment successfully publishes once 10 questions are approved."""
        self.client.force_login(self.educator)

        # Create 12 drafts (10 approved, 2 rejected)
        for i in range(10):
            d = QuestionDraft.objects.create(
                document=self.doc,
                educator=self.educator,
                question_text=f"Approved Question {i}",
                option_a="A", option_b="B", option_c="C", option_d="D",
                correct_answer="A",
                topic="Thermodynamics",
                difficulty="Medium",
                is_approved=True
            )
            d.assign_provisional_irt_parameters()
            d.save()

        # 2 rejected drafts
        for i in range(2):
            QuestionDraft.objects.create(
                document=self.doc,
                educator=self.educator,
                question_text=f"Rejected Question {i}",
                option_a="A", option_b="B", option_c="C", option_d="D",
                correct_answer="B",
                topic="Thermodynamics",
                difficulty="Hard",
                is_approved=False,
                is_rejected=True
            )

        response = self.client.post(reverse('api_publish_assessment'), {
            'document_id': self.doc.id,
            'academic_type': 'school'
        }, content_type='application/json')

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['questions_count'], 10)

        # Verify Assessment in DB
        assessment = Assessment.objects.first()
        self.assertTrue(assessment.is_published)
        self.assertEqual(assessment.questions.count(), 10)

        # Verify only approved questions are in the published assessment
        first_q = assessment.questions.first()
        self.assertIn("Approved Question", first_q.question_text)

    @patch('content.views.get_llm_provider')
    def test_multi_pdf_upload_and_mcq_generation(self, mock_get_llm):
        """Test uploading multiple PDFs together: all files extracted, combined chunks passed to LLM."""
        self.client.force_login(self.educator)

        mock_provider = MagicMock()
        mock_provider.generate_mcqs.return_value = [
            {
                'question_text': f'Sample MCQ {i} from multi-pdf content',
                'option_a': 'Option A text',
                'option_b': 'Option B text',
                'option_c': 'Option C text',
                'option_d': 'Option D text',
                'correct_answer': 'A',
                'explanation': 'Explanation for question',
                'topic': 'Physics',
                'difficulty': 'Medium',
                'source_reference': 'Doc 1 - Page 1'
            }
            for i in range(50)
        ]
        mock_get_llm.return_value = mock_provider

        try:
            import pymupdf as fitz
        except ImportError:
            import fitz

        # Create two real in-memory PDFs
        doc1 = fitz.open()
        p1 = doc1.new_page()
        p1.insert_text((50, 72), "First Law of Thermodynamics states that energy cannot be created or destroyed, only transformed from one form to another in an isolated system.")
        pdf1_bytes = doc1.tobytes()
        doc1.close()

        doc2 = fitz.open()
        p2 = doc2.new_page()
        p2.insert_text((50, 72), "Second Law of Thermodynamics states that the total entropy of an isolated system can never decrease over time and is constant if and only if all processes are reversible.")
        pdf2_bytes = doc2.tobytes()
        doc2.close()

        pdf1 = SimpleUploadedFile("thermo_part1.pdf", pdf1_bytes, content_type="application/pdf")
        pdf2 = SimpleUploadedFile("thermo_part2.pdf", pdf2_bytes, content_type="application/pdf")

        response = self.client.post(reverse('api_upload_generate'), {
            'academic_type': 'school',
            'school_name': 'Delhi Public School',
            'board': 'CBSE',
            'standard': 'Class 11',
            'subject': 'Physics',
            'assessment_title': 'Thermodynamics Comprehensive Test',
            'pdf_files': [pdf1, pdf2],
        })

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['documents_uploaded'], 2)
        self.assertEqual(response.data['pdfs_extracted'], 2)
        self.assertEqual(response.data['drafts_count'], 50)

        # Verify documents created in DB
        docs = UploadedDocument.objects.filter(educator=self.educator).exclude(id=self.doc.id)
        self.assertEqual(docs.count(), 2)
        primary = UploadedDocument.objects.get(id=response.data['document_id'])
        self.assertEqual(primary.title, 'Thermodynamics Comprehensive Test')
        self.assertEqual(primary.total_pages, 2)

    def test_multi_pdf_invalid_file_rejected(self):
        """Test that uploading non-PDF or empty list is rejected."""
        self.client.force_login(self.educator)

        not_a_pdf = SimpleUploadedFile("notes.txt", b"This is plain text, not a PDF", content_type="text/plain")

        response = self.client.post(reverse('api_upload_generate'), {
            'academic_type': 'school',
            'school_name': 'DPS',
            'board': 'CBSE',
            'standard': 'Class 10',
            'subject': 'Science',
            'assessment_title': 'Invalid File Test',
            'pdf_files': [not_a_pdf],
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)

