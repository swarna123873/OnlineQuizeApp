from django.urls import path
from . import views

urlpatterns = [
    # Web views
    path('', views.landing_view, name='landing'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('logout/', views.logout_view, name='logout'),

    # REST APIs
    path('api/accounts/register/', views.RegisterAPIView.as_view(), name='api_register'),
    path('api/accounts/login/', views.LoginAPIView.as_view(), name='api_login'),
    path('api/accounts/forgot-password/', views.ForgotPasswordAPIView.as_view(), name='api_forgot_password'),
    path('api/accounts/logout/', views.LogoutAPIView.as_view(), name='api_logout'),
    path('api/accounts/me/', views.CurrentUserAPIView.as_view(), name='api_current_user'),
]
