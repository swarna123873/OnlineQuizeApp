from django.db import models
from django.conf import settings

class UploadedDocument(models.Model):
    educator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='uploaded_documents')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='notes_pdfs/%Y/%m/')
    extracted_text = models.TextField(blank=True, default='')
    total_pages = models.PositiveIntegerField(default=0)
    is_ocr_required = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} (by {self.educator.email})"


class QuestionDraft(models.Model):
    DIFFICULTY_CHOICES = [
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
    ]

    ANSWER_CHOICES = [
        ('A', 'Option A'),
        ('B', 'Option B'),
        ('C', 'Option C'),
        ('D', 'Option D'),
    ]

    document = models.ForeignKey(UploadedDocument, on_delete=models.CASCADE, null=True, blank=True, related_name='drafts')
    educator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='question_drafts')

    question_text = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    correct_answer = models.CharField(max_length=1, choices=ANSWER_CHOICES)
    explanation = models.TextField(blank=True, default='')
    topic = models.CharField(max_length=150, db_index=True)
    source_reference = models.CharField(max_length=255, blank=True, default='', help_text="e.g. Page 3, Section 2.1")

    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='Medium')
    provisional_difficulty = models.FloatField(default=0.0, help_text="IRT b parameter (provisional)")
    provisional_discrimination = models.FloatField(default=1.2, help_text="IRT a parameter (provisional)")

    is_approved = models.BooleanField(default=False, db_index=True)
    is_rejected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status_label = "Approved" if self.is_approved else ("Rejected" if self.is_rejected else "Draft")
        return f"[{status_label}] {self.topic} - {self.question_text[:50]}..."

    def assign_provisional_irt_parameters(self):
        settings_dict = getattr(settings, 'IRT_SETTINGS', {})
        mapping = {
            'Easy': settings_dict.get('PROVISIONAL_EASY_DIFF', -1.0),
            'Medium': settings_dict.get('PROVISIONAL_MEDIUM_DIFF', 0.0),
            'Hard': settings_dict.get('PROVISIONAL_HARD_DIFF', 1.0),
        }
        self.provisional_difficulty = mapping.get(self.difficulty, 0.0)
        self.provisional_discrimination = settings_dict.get('PROVISIONAL_DISCRIMINATION', 1.2)
