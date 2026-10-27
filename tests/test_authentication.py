from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.educator_email = "teacher@school.edu"
        self.student_email = "student@school.edu"
        self.strong_password = "Secur3P@ssword!"
        self.weak_password = "simplepassword"  # No numbers or special characters

    def test_registration_educator_redirects_to_login_without_autologin(self):
        """Test registration redirects to login page with success message, requiring explicit login."""
        response = self.client.post(reverse('register'), {
            'role': 'educator',
            'email': self.educator_email,
            'password': self.strong_password
        }, follow=False)

        # Must redirect to login page, NOT to educator_dashboard
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))

        # Verify user is created in database
        self.assertTrue(User.objects.filter(email=self.educator_email).exists())
        user = User.objects.get(email=self.educator_email)
        self.assertTrue(user.is_educator)

        # Verify user is NOT automatically authenticated in the session
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_registration_student_redirects_to_login(self):
        """Test student registration redirects to login page."""
        response = self.client.post(reverse('register'), {
            'role': 'student',
            'email': self.student_email,
            'password': self.strong_password
        }, follow=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))
        self.assertTrue(User.objects.filter(email=self.student_email).exists())

    def test_registration_weak_password_rejected(self):
        """Test password complexity rule: requires letters, numbers, and special characters."""
        # Test password without numbers/special chars
        response = self.client.post(reverse('register'), {
            'role': 'educator',
            'email': 'weakpass@test.com',
            'password': self.weak_password
        })
        self.assertFalse(User.objects.filter(email='weakpass@test.com').exists())

        # Test password shorter than 6 characters
        response = self.client.post(reverse('register'), {
            'role': 'educator',
            'email': 'shortpass@test.com',
            'password': 'a1!'
        })
        self.assertFalse(User.objects.filter(email='shortpass@test.com').exists())

    def test_dashboard_requires_login(self):
        """Dashboard access can happen only through successful login."""
        # Trying to access educator dashboard without login redirects to login
        response = self.client.get(reverse('educator_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(reverse('login') in response.url)

        # Trying to access student dashboard without login redirects to login
        response = self.client.get(reverse('student_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(reverse('login') in response.url)

    def test_login_success(self):
        """Test valid login gives access to educator dashboard."""
        User.objects.create_user(email=self.educator_email, password=self.strong_password, role='educator')
        response = self.client.post(reverse('login'), {
            'role': 'educator',
            'email': self.educator_email,
            'password': self.strong_password
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('educator_dashboard'))

    def test_login_role_mismatch_prevented(self):
        """Test that student cannot log in under the educator role."""
        User.objects.create_user(email=self.student_email, password=self.strong_password, role='student')
        response = self.client.post(reverse('login'), {
            'role': 'educator',
            'email': self.student_email,
            'password': self.strong_password
        }, follow=True)
        self.assertFalse(response.context['user'].is_authenticated)

    def test_forgot_password_success(self):
        """Test forgot password allows resetting password with new strong password."""
        user = User.objects.create_user(email=self.educator_email, password=self.strong_password, role='educator')
        new_strong_pass = "N3wBrandSecur3#Pass"

        response = self.client.post(reverse('forgot_password'), {
            'email': self.educator_email,
            'new_password': new_strong_pass,
            'confirm_password': new_strong_pass
        }, follow=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('login'))

        # Check user can now log in with the new password
        user.refresh_from_db()
        self.assertTrue(user.check_password(new_strong_pass))

    def test_forgot_password_mismatch_rejected(self):
        """Test that mismatched new and confirm passwords are rejected."""
        User.objects.create_user(email=self.educator_email, password=self.strong_password, role='educator')
        response = self.client.post(reverse('forgot_password'), {
            'email': self.educator_email,
            'new_password': 'NewP@ssword123',
            'confirm_password': 'DifferentP@ssword456'
        })
        user = User.objects.get(email=self.educator_email)
        self.assertTrue(user.check_password(self.strong_password))
