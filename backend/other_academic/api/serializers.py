import re

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers

from other_academic.models import Leave, UserProfile


DEPARTMENT_ALIASES = {
    "cse": {"cse", "computer science", "computer science engineering"},
    "ece": {"ece", "electronics", "electronics and communication engineering"},
    "me": {"me", "mechanical", "mechanical engineering"},
    "sm": {"sm", "smart manufacturing", "manufacturing"},
    "ns": {"ns", "natural sciences", "science"},
    "design": {"design"},
    "liberal arts": {"liberal arts", "humanities"},
}

PROGRAM_MAX_SEMESTERS = {
    "B": 8,
    "M": 4,
    "P": 10,
}

PHONE_FIELDS = {
    "mobile_number": "Mobile number",
    "parents_mobile": "Parents mobile number",
    "mobile_during_leave": "Mobile number during leave",
}

PHONE_PATTERN = re.compile(r"^\d{10}$")


def _normalize_department(value):
    text = (value or "").strip().casefold()
    if not text:
        return ""
    for canonical, aliases in DEPARTMENT_ALIASES.items():
        if text in aliases:
            return canonical
    return text


def _student_roll_value(user):
    profile = getattr(user, "profile", None)
    return (getattr(profile, "roll_no", "") or user.username or "").strip()


def _current_academic_year(today=None):
    today = today or timezone.localdate()
    start_year = today.year if today.month >= 7 else today.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _derive_student_semester(user, today=None):
    today = today or timezone.localdate()
    roll_no = _student_roll_value(user)
    match = re.match(r"^(?P<year>\d{2})(?P<program>[A-Za-z])", roll_no)
    if not match:
        return None

    admission_year = 2000 + int(match.group("year"))
    program_code = match.group("program").upper()
    academic_start_year = today.year if today.month >= 7 else today.year - 1
    semester = (academic_start_year - admission_year) * 2 + (1 if today.month >= 7 else 2)
    semester = max(1, semester)

    max_semester = PROGRAM_MAX_SEMESTERS.get(program_code)
    if max_semester:
        semester = min(semester, max_semester)
    return semester


def _find_hod_for_student(user):
    department = _normalize_department(getattr(getattr(user, "profile", None), "department", ""))
    hod_users = User.objects.filter(profile__role="hod").select_related("profile").order_by("username")
    for hod_user in hod_users:
        if _normalize_department(getattr(hod_user.profile, "department", "")) == department:
            return hod_user
    return hod_users.first()


def get_leave_form_defaults(user):
    hod_user = _find_hod_for_student(user)
    return {
        "student_name": user.get_full_name() or user.username,
        "roll_no": _student_roll_value(user),
        "semester": _derive_student_semester(user),
        "academic_year": _current_academic_year(),
        "hod_credential": hod_user.get_full_name() or hod_user.username if hod_user else "",
        "department": getattr(getattr(user, "profile", None), "department", ""),
    }


# =========================
# USER PROFILE SERIALIZERS
# =========================

class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'email', 'role', 'department', 'roll_no']


# =========================
# LEAVE SERIALIZERS
# =========================

class LeaveCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Leave
        exclude = ["status", "hod_remarks", "created_at", "updated_at", "user", "reviewed_at", "reviewed_by"]

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            raise serializers.ValidationError("Authentication is required to submit leave.")

        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")
        today = timezone.localdate()

        if date_from and date_from < today:
            raise serializers.ValidationError({"date_from": "Leave cannot be applied for a past date."})
        if date_from and date_to and date_to < date_from:
            raise serializers.ValidationError({"date_to": "date_to must be on or after date_from."})

        phone_errors = {}
        for field, label in PHONE_FIELDS.items():
            value = (attrs.get(field) or "").strip()
            if not PHONE_PATTERN.fullmatch(value):
                phone_errors[field] = f"{label}: Enter a valid 10 digit number."
        if phone_errors:
            raise serializers.ValidationError(phone_errors)

        overlap_exists = Leave.objects.filter(
            user=user,
            status__in=["pending", "approved"],
            date_from__lte=date_to,
            date_to__gte=date_from,
        ).exists()
        if overlap_exists:
            raise serializers.ValidationError("Leave dates overlap with an existing leave request.")

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        defaults = get_leave_form_defaults(request.user)
        validated_data["student_name"] = defaults["student_name"]
        validated_data["roll_no"] = defaults["roll_no"]
        validated_data["name"] = defaults["student_name"]
        validated_data["roll_number"] = defaults["roll_no"]
        validated_data["semester"] = defaults["semester"]
        validated_data["academic_year"] = defaults["academic_year"]
        validated_data["hod_credential"] = defaults["hod_credential"]
        validated_data["user"] = request.user
        return super().create(validated_data)


class LeaveOutputSerializer(serializers.ModelSerializer):
    user_profile = UserProfileSerializer(source='user.profile', read_only=True)

    class Meta:
        model = Leave
        fields = "__all__"


class LeaveUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Leave
        fields = ["id", "status", "hod_remarks"]
