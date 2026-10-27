from django.db import models
from django.conf import settings

class SchoolAcademicContext(models.Model):
    BOARD_CHOICES = [
        ('CBSE', 'Central Board of Secondary Education (CBSE)'),
        ('ICSE', 'Indian Certificate of Secondary Education (ICSE)'),
        ('State Board', 'State Board'),
    ]

    educator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='school_academic_contexts')
    school_name = models.CharField(max_length=255, db_index=True)
    board = models.CharField(max_length=50, choices=BOARD_CHOICES)
    state = models.CharField(max_length=100, blank=True, default='')
    standard = models.CharField(max_length=50, db_index=True, help_text="e.g. Class 10, Class 12")
    subject = models.CharField(max_length=150, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['school_name', 'standard', 'subject']
        indexes = [
            models.Index(fields=['school_name', 'board', 'standard', 'subject']),
        ]

    def __str__(self):
        state_str = f" ({self.state})" if self.state else ""
        return f"{self.school_name} | {self.board}{state_str} | {self.standard} | {self.subject}"


class CollegeAcademicContext(models.Model):
    CLASSIFICATION_CHOICES = [
        ('Core', 'Core Subject'),
        ('Elective', 'Elective Subject'),
    ]

    educator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='college_academic_contexts')
    college_name = models.CharField(max_length=255, db_index=True)
    degree = models.CharField(max_length=150, db_index=True, help_text="e.g. B.Tech, B.Sc, MCA")
    academic_year = models.CharField(max_length=50, help_text="e.g. 1st Year, 2nd Year, 3rd Year, 4th Year")
    branch = models.CharField(max_length=150, help_text="e.g. Computer Science, Mechanical")
    classification = models.CharField(max_length=50, choices=CLASSIFICATION_CHOICES)
    subject = models.CharField(max_length=150, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['college_name', 'degree', 'academic_year', 'subject']
        indexes = [
            models.Index(fields=['college_name', 'degree', 'academic_year', 'branch', 'classification', 'subject']),
        ]

    def __str__(self):
        return f"{self.college_name} | {self.degree} ({self.academic_year}) | {self.branch} | {self.subject} [{self.classification}]"
