from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User

from other_academic.models import UserProfile, Notification
from .fusionlab_roles import (
    get_accessible_modules_for_roles,
    get_role_context_for_user,
    map_selected_role_to_module_role,
    sync_user_profile_from_role_context,
)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "Username and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(username=username, password=password)
        if not user:
            return Response(
                {"error": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key}, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        context = get_role_context_for_user(user)
        sync_user_profile_from_role_context(user, context)

        return Response(
            {
                "name": context["name"],
                "roll_no": context["roll_no"],
                "is_pg_student": getattr(getattr(user, "profile", None), "is_pg_student", False),
                "designation_info": context["available_roles"],
                "last_selected_role": context["active_role"],
                "effective_role": context["effective_module_role"],
                "accessible_modules": get_accessible_modules_for_roles(context["available_roles"]),
                "person_details": {
                    "department": context["department"],
                    "raw_designations": context["sql_person"].get("raw_designations", []),
                    "source": "fusionlab.sql" if context["sql_person"] else "local_profile",
                },
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if hasattr(request.user, "auth_token"):
            request.user.auth_token.delete()
        return Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)


class UpdateRoleView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        new_role = request.data.get("last_selected_role")
        context = get_role_context_for_user(request.user)
        available_roles = context["available_roles"]

        if not new_role:
            return Response(
                {"error": "last_selected_role is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_role not in available_roles:
            return Response(
                {"error": f"Role '{new_role}' is not available for this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = sync_user_profile_from_role_context(request.user, context)
        profile.last_selected_role = new_role
        profile.role = map_selected_role_to_module_role(new_role, context["sql_person"].get("module_roles", []))
        profile.save(update_fields=["last_selected_role", "role"])

        return Response(
            {"message": "Role updated successfully.", "last_selected_role": new_role},
            status=status.HTTP_200_OK,
        )


def _build_profile_payload(user):
    context = get_role_context_for_user(user)
    profile = sync_user_profile_from_role_context(user, context)

    return {
        "current": [
            {
                "user": {
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "username": user.username,
                    "email": user.email,
                }
            }
        ],
        "profile": {
            "department": {"name": getattr(profile, "department", "")},
            "roll_no": getattr(profile, "roll_no", ""),
            "role": context["active_role"],
        },
        "semester_no": None,
        "skills": [],
        "education": [],
        "course": [],
        "experience": [],
        "project": [],
        "achievement": [],
    }


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_build_profile_payload(request.user), status=status.HTTP_200_OK)


class ProfileByUsernameView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, username):
        user = User.objects.filter(username=username).first()
        if not user:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(_build_profile_payload(user), status=status.HTTP_200_OK)


class ProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        # Keep compatibility with legacy payload shape while persisting supported fields.
        payload = request.data.get("profilesubmit", {}) if isinstance(request.data, dict) else {}
        profile, _ = UserProfile.objects.get_or_create(user=request.user)

        # These fields exist in current UserProfile model.
        department = payload.get("department")
        roll_no = payload.get("roll_no")
        if isinstance(department, str):
            profile.department = department
        if isinstance(roll_no, str):
            profile.roll_no = roll_no
        profile.save()

        return Response(
            {"message": "Profile updated successfully.", "data": _build_profile_payload(request.user)},
            status=status.HTTP_200_OK,
        )


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = Notification.objects.filter(user=request.user, deleted=False).order_by("-timestamp")
        payload = [
            {
                "id": item.id,
                "verb": item.verb,
                "description": item.description,
                "data": item.data,
                "unread": item.unread,
                "deleted": item.deleted,
                "timestamp": item.timestamp.isoformat(),
            }
            for item in items
        ]
        return Response({"notifications": payload}, status=status.HTTP_200_OK)


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        notif_id = request.data.get("id")
        notification = Notification.objects.filter(id=notif_id, user=request.user, deleted=False).first()
        if not notification:
            return Response({"error": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)
        notification.unread = False
        notification.save(update_fields=["unread"])
        return Response({"message": "Notification marked as read."}, status=status.HTTP_200_OK)


class NotificationUnreadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        notif_id = request.data.get("id")
        notification = Notification.objects.filter(id=notif_id, user=request.user, deleted=False).first()
        if not notification:
            return Response({"error": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)
        notification.unread = True
        notification.save(update_fields=["unread"])
        return Response({"message": "Notification marked as unread."}, status=status.HTTP_200_OK)


class NotificationDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        notif_id = request.data.get("id")
        notification = Notification.objects.filter(id=notif_id, user=request.user, deleted=False).first()
        if not notification:
            return Response({"error": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)
        notification.deleted = True
        notification.save(update_fields=["deleted"])
        return Response({"message": "Notification deleted."}, status=status.HTTP_200_OK)
