import re
from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User

def validate_strong_password(value):
    if len(value) < 6:
        raise serializers.ValidationError("Password must be at least 6 characters long.")
    if not re.search(r'[A-Za-z]', value):
        raise serializers.ValidationError("Password must contain at least one letter.")
    if not re.search(r'[0-9]', value):
        raise serializers.ValidationError("Password must contain at least one number.")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>\-_]', value):
        raise serializers.ValidationError("Password must contain at least one special character (e.g. !@#$%^&*).")
    return value

class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)

    def validate_email(self, value):
        normalized = value.strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("An account with this email address already exists.")
        return normalized

    def validate_password(self, value):
        return validate_strong_password(value)

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            role=validated_data['role']
        )

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        return validate_strong_password(value)

    def validate(self, attrs):
        email = attrs.get('email', '').strip().lower()
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')

        if new_password != confirm_password:
            raise serializers.ValidationError({'confirm_password': "Passwords do not match."})

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({'email': "No account found registered with this email address."})

        attrs['user'] = user
        return attrs

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)

    def validate(self, attrs):
        email = attrs.get('email', '').strip().lower()
        password = attrs.get('password')
        role = attrs.get('role')

        user = authenticate(email=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid email address or password.")

        if user.role != role:
            role_label = dict(User.ROLE_CHOICES).get(role, role)
            actual_label = user.get_role_display()
            raise serializers.ValidationError(
                f"Account role mismatch: This account is registered as '{actual_label}', not '{role_label}'."
            )

        if not user.is_active:
            raise serializers.ValidationError("This account has been deactivated.")

        attrs['user'] = user
        return attrs

class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'role', 'role_display', 'is_educator', 'is_student', 'date_joined']
