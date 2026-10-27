from django.urls import path
from . import views

urlpatterns = [
    path('api/academics/school/options/', views.SchoolDropdownOptionsAPIView.as_view(), name='api_school_options'),
    path('api/academics/college/options/', views.CollegeDropdownOptionsAPIView.as_view(), name='api_college_options'),
]
