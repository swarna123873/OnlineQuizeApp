from rest_framework import serializers
from .models import SchoolAcademicContext, CollegeAcademicContext

class SchoolAcademicContextSerializer(serializers.ModelSerializer):
    educator_email = serializers.EmailField(source='educator.email', read_only=True)

    class Meta:
        model = SchoolAcademicContext
        fields = ['id', 'educator_email', 'school_name', 'board', 'state', 'standard', 'subject', 'created_at']

class CollegeAcademicContextSerializer(serializers.ModelSerializer):
    educator_email = serializers.EmailField(source='educator.email', read_only=True)

    class Meta:
        model = CollegeAcademicContext
        fields = ['id', 'educator_email', 'college_name', 'degree', 'academic_year', 'branch', 'classification', 'subject', 'created_at']
