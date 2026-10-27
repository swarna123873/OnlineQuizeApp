from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer, ForgotPasswordSerializer
from .models import User

def landing_view(request):
    if request.user.is_authenticated:
        if request.user.is_educator:
            return redirect('educator_dashboard')
        return redirect('student_dashboard')
    return render(request, 'landing.html')

@ensure_csrf_cookie
def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_educator:
            return redirect('educator_dashboard')
        return redirect('student_dashboard')

    if request.method == 'POST':
        role = request.POST.get('role', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        serializer = LoginSerializer(data={'role': role, 'email': email, 'password': password})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            messages.success(request, f"Welcome back, {user.email}!")
            if user.is_educator:
                return redirect('educator_dashboard')
            return redirect('student_dashboard')
        else:
            for field_errors in serializer.errors.values():
                for err in field_errors:
                    messages.error(request, str(err))

    return render(request, 'login.html')

@ensure_csrf_cookie
def register_view(request):
    if request.user.is_authenticated:
        if request.user.is_educator:
            return redirect('educator_dashboard')
        return redirect('student_dashboard')

    if request.method == 'POST':
        role = request.POST.get('role', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        serializer = RegisterSerializer(data={'role': role, 'email': email, 'password': password})
        if serializer.is_valid():
            user = serializer.save()
            messages.success(request, "Registered successfully! Please log in with your credentials to access your dashboard.")
            return redirect('login')
        else:
            for field_errors in serializer.errors.values():
                for err in field_errors:
                    messages.error(request, str(err))

    return render(request, 'register.html')

@ensure_csrf_cookie
def forgot_password_view(request):
    if request.user.is_authenticated:
        if request.user.is_educator:
            return redirect('educator_dashboard')
        return redirect('student_dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        serializer = ForgotPasswordSerializer(data={
            'email': email,
            'new_password': new_password,
            'confirm_password': confirm_password
        })
        if serializer.is_valid():
            serializer.save()
            messages.success(request, "Password reset successfully! Please log in with your new password.")
            return redirect('login')
        else:
            for field_errors in serializer.errors.values():
                for err in field_errors:
                    messages.error(request, str(err))

    return render(request, 'forgot_password.html')

def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('landing')

# REST API Endpoints
class RegisterAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'success': True,
                'message': 'Registered successfully! Please log in to access your dashboard.',
                'redirect_url': '/login/',
                'user': UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class ForgotPasswordAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': 'Password reset successfully! Please log in with your new password.',
                'redirect_url': '/login/'
            }, status=status.HTTP_200_OK)
        return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class LoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            redirect_url = '/educator/' if user.is_educator else '/student/'
            return Response({
                'success': True,
                'message': 'Login successful.',
                'redirect_url': redirect_url,
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

class LogoutAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({'success': True, 'message': 'Logged out successfully.'})

class CurrentUserAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
