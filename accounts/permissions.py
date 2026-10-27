from rest_framework import permissions
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

class IsEducatorUser(permissions.BasePermission):
    """Allows access only to authenticated educators."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_educator)

class IsStudentUser(permissions.BasePermission):
    """Allows access only to authenticated students."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_student)

def educator_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Please log in to access this page.")
            return redirect('login')
        if not request.user.is_educator:
            messages.error(request, "Access restricted to Educators/School accounts.")
            return redirect('student_dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def student_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Please log in to access this page.")
            return redirect('login')
        if not request.user.is_student:
            messages.error(request, "Access restricted to Student accounts.")
            return redirect('educator_dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
