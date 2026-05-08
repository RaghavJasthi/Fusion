from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from other_academic.models import UserProfile


class FusionAuthRoleTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_me_view_returns_multiple_roles_from_fusionlab_dump(self):
        user = User.objects.create_user(username="skjain", password="pass123")
        UserProfile.objects.create(user=user, role="acadadmin", department="CSE")
        self.client.force_authenticate(user)

        response = self.client.get("/api/auth/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data["designation_info"]),
            {"Assistant Professor", "Dean Academic", "acadadmin"},
        )
        self.assertEqual(response.data["last_selected_role"], "acadadmin")
        self.assertEqual(response.data["effective_role"], "acadadmin")

    def test_update_role_persists_selected_role_from_available_roles(self):
        user = User.objects.create_user(username="skjain", password="pass123")
        UserProfile.objects.create(user=user, role="acadadmin", department="CSE")
        self.client.force_authenticate(user)

        response = self.client.patch(
            "/api/update-role/",
            {"last_selected_role": "Dean Academic"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.last_selected_role, "Dean Academic")
        self.assertEqual(user.profile.role, "dean_academic")
