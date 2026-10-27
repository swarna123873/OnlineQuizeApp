from django.urls import path
from . import views

urlpatterns = [
    # Student Web Views
    path('student/', views.student_dashboard_view, name='student_dashboard'),
    path('student/school-zone/', views.student_school_zone_view, name='student_school_zone'),
    path('student/college-zone/', views.student_college_zone_view, name='student_college_zone'),
    path('student/assessment/<int:assessment_id>/instructions/', views.assessment_instructions_view, name='student_assessment_instructions'),
    path('student/assessment/<int:attempt_id>/test/', views.assessment_exam_view, name='student_assessment_exam'),
    path('student/assessment/<int:attempt_id>/completed/', views.assessment_completed_view, name='student_assessment_completed'),
    path('student/assessment/<int:attempt_id>/terminated/', views.assessment_terminated_view, name='student_assessment_terminated'),

    # REST APIs
    path('api/assessments/publish/', views.PublishAssessmentAPIView.as_view(), name='api_publish_assessment'),
    path('api/assessments/match/', views.MatchAssessmentAPIView.as_view(), name='api_match_assessment'),
    path('api/assessments/start-attempt/', views.StartAssessmentAPIView.as_view(), name='api_start_assessment'),
    path('api/assessments/integrity-warning/', views.IntegrityWarningAPIView.as_view(), name='api_integrity_warning'),
    path('api/assessments/submit-response/', views.SubmitResponseAPIView.as_view(), name='api_submit_response'),
]


