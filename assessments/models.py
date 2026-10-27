from django.db import models
from django.conf import settings
from academics.models import SchoolAcademicContext, CollegeAcademicContext

class Assessment(models.Model):
    ACADEMIC_TYPE_CHOICES = [
        ('school', 'School Assessment'),
        ('college', 'College Assessment'),
    ]

    educator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assessments')
    academic_type = models.CharField(max_length=20, choices=ACADEMIC_TYPE_CHOICES)
    school_context = models.ForeignKey(SchoolAcademicContext, on_delete=models.SET_NULL, null=True, blank=True, related_name='assessments')
    college_context = models.ForeignKey(CollegeAcademicContext, on_delete=models.SET_NULL, null=True, blank=True, related_name='assessments')

    title = models.CharField(max_length=255)
    subject = models.CharField(max_length=150, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status_str = "Published" if self.is_published else "Draft"
        return f"[{status_str}] {self.title} ({self.subject})"

    @property
    def question_count(self):
        return self.questions.count()


class AssessmentQuestion(models.Model):
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

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    correct_answer = models.CharField(max_length=1, choices=ANSWER_CHOICES)
    explanation = models.TextField(blank=True, default='')
    topic = models.CharField(max_length=150, db_index=True)
    source_reference = models.CharField(max_length=255, blank=True, default='')

    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='Medium')
    discrimination_a = models.FloatField(default=1.2, help_text="IRT 2PL discrimination parameter (a > 0)")
    difficulty_b = models.FloatField(default=0.0, help_text="IRT 2PL difficulty parameter (b)")
    is_calibrated = models.BooleanField(default=False, help_text="False = provisional parameter; True = calibrated")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.topic} (b={self.difficulty_b}, a={self.discrimination_a}): {self.question_text[:40]}..."


class AssessmentAttempt(models.Model):
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('terminated', 'Terminated Due to Integrity Warnings'),
    ]

    ADAPTIVE_MODE_CHOICES = [
        ('IRT_ONLY', 'IRT-Only Mode'),
        ('IRT_XGBOOST', 'Combined IRT + XGBoost Mode'),
    ]

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assessment_attempts')
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='attempts')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='in_progress')
    adaptive_mode = models.CharField(max_length=30, choices=ADAPTIVE_MODE_CHOICES, default='IRT_ONLY')
    model_version = models.CharField(max_length=50, default='IRT-2PL-MAP-v1')

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    raw_score = models.IntegerField(null=True, blank=True, help_text="Sum of correct responses (0 to 10)")
    accuracy = models.FloatField(null=True, blank=True, help_text="Accuracy percentage (0 to 100)")
    final_theta = models.FloatField(null=True, blank=True, help_text="Estimated latent ability theta")
    final_se = models.FloatField(null=True, blank=True, help_text="Standard error of theta estimate")

    class Meta:
        ordering = ['-started_at']

    @property
    def duration_seconds(self):
        if self.completed_at and self.started_at:
            delta = (self.completed_at - self.started_at).total_seconds()
            return max(1, int(delta))
        return None

    @property
    def duration_formatted(self):
        secs = self.duration_seconds
        if secs is None:
            return "N/A"
        mins = int(secs // 60)
        rem_secs = int(secs % 60)
        if mins > 0:
            return f"{mins}m {rem_secs:02d}s"
        return f"{rem_secs}s"

    @property
    def incorrect_count(self):
        if self.raw_score is not None:
            return max(0, 10 - self.raw_score)
        return 0

    def __str__(self):
        return f"Attempt #{self.id} by {self.student.email} on {self.assessment.title} [{self.status}]"


class StudentResponse(models.Model):
    attempt = models.ForeignKey(AssessmentAttempt, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(AssessmentQuestion, on_delete=models.CASCADE, related_name='student_responses')
    question_sequence = models.PositiveIntegerField(help_text="Order in which question was presented (1 to 10)")
    selected_option = models.CharField(max_length=1)
    is_correct = models.BooleanField(db_index=True)

    theta_before = models.FloatField(help_text="Ability estimate before this response")
    theta_after = models.FloatField(help_text="Updated ability estimate after this response")
    se_after = models.FloatField(help_text="Updated standard error after this response")
    irt_information = models.FloatField(default=0.0, help_text="Fisher Item Information value calculated for this item")
    xgboost_predicted_prob = models.FloatField(null=True, blank=True, help_text="Predicted probability from XGBoost if available")

    responded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('attempt', 'question_sequence')
        ordering = ['question_sequence']

    def __str__(self):
        result = "Correct" if self.is_correct else "Incorrect"
        return f"Attempt #{self.attempt_id} - Q{self.question_sequence} ({result})"


class IntegrityEvent(models.Model):
    EVENT_CHOICES = [
        ('fullscreen_exit', 'Exited Fullscreen Mode'),
        ('tab_switch', 'Switched Browser Tab / Window Focus Lost'),
        ('clipboard_attempt', 'Attempted Copy / Paste Action'),
    ]

    attempt = models.ForeignKey(AssessmentAttempt, on_delete=models.CASCADE, related_name='integrity_events')
    event_type = models.CharField(max_length=50, choices=EVENT_CHOICES)
    warning_number = models.PositiveIntegerField(default=1)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attempt #{self.attempt_id} Warning #{self.warning_number}: {self.get_event_type_display()}"
