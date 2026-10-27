from django.urls import path
from . import views

urlpatterns = [
    # Web views
    path('educator/', views.educator_dashboard_view, name='educator_dashboard'),
    path('educator/school-form/', views.school_form_view, name='school_form'),
    path('educator/college-form/', views.college_form_view, name='college_form'),
    path('educator/review/<int:doc_id>/', views.educator_review_view, name='educator_review'),

    # REST APIs
    path('api/content/upload-and-generate/', views.UploadAndGenerateAPIView.as_view(), name='api_upload_generate'),
    path('api/content/drafts/<int:pk>/', views.QuestionDraftDetailAPIView.as_view(), name='api_draft_detail'),
    path('api/content/drafts/approve-bulk/', views.BulkApproveDraftsAPIView.as_view(), name='api_drafts_bulk_approve'),
]
