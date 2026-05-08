"""Unified API views for other_academic."""

from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Sum
from django.http import FileResponse, Http404
from django.utils.dateparse import parse_date

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from fusion.fusionlab_roles import get_active_role_for_user, get_role_context_for_user
from other_academic.models import (
    AssistantshipClaim,
    AssistantshipApprover,
    Course,
    Leave,
    NoDuesEntry,
    NoDuesRequest,
    BonafideRequest,
    Seminar,
    SupervisorAssignment,
    TAAssignment,
    UserProfile,
    WorkflowAuditLog,
)
from other_academic.notifications import create_notification
from other_academic.workflows.repositories import AuditLogRepository
from other_academic.workflows.services import (
    SeminarWorkflowService,
    SupervisorAssignmentService,
    TAAssignmentService,
    WorkflowServiceError,
)
from .serializers import (
    LeaveCreateSerializer,
    LeaveOutputSerializer,
    get_leave_form_defaults,
)


NO_DUES_DOMAIN_REVIEWER_ROLES = {
    "librarian",
    "hostel_warden",
    "mess_incharge",
    "lab_incharge",
}

NO_DUES_REVIEWER_ROLES = NO_DUES_DOMAIN_REVIEWER_ROLES.union({"acadadmin"})

REQUIRED_NO_DUES_APPROVAL_ROLES = (
    "mess_incharge",
    "hostel_warden",
    "librarian",
    "lab_incharge",
)

NO_DUES_ROLE_CATEGORY_KEYWORDS = {
    "librarian": ("library", "librarian"),
    "hostel_warden": ("hostel", "warden"),
    "mess_incharge": ("mess", "canteen", "food"),
    "lab_incharge": ("lab", "laboratory"),
    "mess_warden": ("mess", "canteen", "food"),
}

NO_DUES_ROLE_DEFAULT_CATEGORY = {
    "librarian": "Library",
    "hostel_warden": "Hostel",
    "mess_incharge": "Mess",
    "lab_incharge": "Lab",
    "mess_warden": "Mess",
}

GLOBAL_BACKEND_ROLES = {"admin", "acadadmin", "dean_academic", "director"}


def _user_role(user):
    return get_active_role_for_user(user)


def _is_no_dues_reviewer(user):
    return _user_role(user) in NO_DUES_REVIEWER_ROLES


def _is_no_dues_finalizer(user):
    return _user_role(user) == "acadadmin"


def _is_bonafide_reviewer(user):
    return _user_role(user) == "acadadmin"


def _no_dues_scope_keywords(user):
    return NO_DUES_ROLE_CATEGORY_KEYWORDS.get(_user_role(user), ())


def _matches_no_dues_scope(category, keywords):
    category_value = (category or "").strip().casefold()
    return any(keyword in category_value for keyword in keywords)


def _scoped_no_dues_entries(student, user):
    entries = NoDuesEntry.objects.filter(student=student).order_by("-updated_at")
    keywords = _no_dues_scope_keywords(user)
    if not keywords:
        return entries
    return [entry for entry in entries if _matches_no_dues_scope(entry.category, keywords)]


def _serialize_no_dues_entries(entries):
    return [
        {
            "id": entry.id,
            "category": entry.category,
            "description": entry.description,
            "amount": str(entry.amount),
            "is_cleared": entry.is_cleared,
            "updated_at": entry.updated_at.isoformat(),
        }
        for entry in entries
    ]


def _default_no_dues_domain_approvals():
    return {
        role: {
            "status": "pending",
            "actor": None,
            "remarks": "",
            "timestamp": None,
        }
        for role in REQUIRED_NO_DUES_APPROVAL_ROLES
    }


def _normalized_no_dues_domain_approvals(req_obj):
    approvals = _default_no_dues_domain_approvals()
    for role, payload in (req_obj.domain_approvals or {}).items():
        if role not in approvals:
            continue
        approvals[role].update(payload or {})
    return approvals


def _all_no_dues_domains_approved(req_obj):
    approvals = _normalized_no_dues_domain_approvals(req_obj)
    return all(approvals[role]["status"] == "approved" for role in REQUIRED_NO_DUES_APPROVAL_ROLES)


def _can_review_no_dues_request(user, req_obj):
    role = _user_role(user)
    if _is_no_dues_finalizer(user):
        return True
    if role not in NO_DUES_REVIEWER_ROLES:
        return False
    if role in NO_DUES_DOMAIN_REVIEWER_ROLES:
        return True
    return False


def _belongs_to_user_department(subject_user, actor):
    subject_department = _profile_department(subject_user)
    actor_department = _profile_department(actor)
    return bool(subject_department and actor_department and subject_department.casefold() == actor_department.casefold())


def _department_scoped_queryset(queryset, actor, student_field="student"):
    role = _user_role(actor)
    if role in GLOBAL_BACKEND_ROLES:
        return queryset
    if role == "hod":
        lookup = f"{student_field}__profile__department__iexact"
        return queryset.filter(**{lookup: _profile_department(actor)})
    return queryset.none()


def _user_module_roles(user):
    context = get_role_context_for_user(user)
    roles = set(context.get("sql_person", {}).get("module_roles", []))
    profile = getattr(user, "profile", None)
    if profile and profile.role:
        roles.add(profile.role)
    return {role for role in roles if role}


def _role_users(role, department=""):
    department_value = (department or "").strip()
    matched = []
    for candidate in User.objects.filter(is_active=True).select_related("profile").order_by("id"):
        if role not in _user_module_roles(candidate):
            continue
        if department_value:
            candidate_department = _profile_department(candidate)
            if candidate_department.casefold() != department_value.casefold():
                continue
        matched.append(candidate)
    return matched


def _unique_users(users):
    seen = set()
    result = []
    for user in users:
        if not user or user.id in seen:
            continue
        seen.add(user.id)
        result.append(user)
    return result


def _department_authorities(student, roles=("hod",)):
    department = _profile_department(student)
    users = []
    for role in roles:
        scoped = _role_users(role, department=department) if department else []
        users.extend(scoped or _role_users(role))
    return _unique_users(users)


def _notify_users(users, verb, description):
    for user in _unique_users(users):
        create_notification(user, verb, description)


def _is_pg_student(user):
    return bool(getattr(getattr(user, "profile", None), "is_pg_student", False))


def _users_matching_identity(name, roles=None, department=""):
    target = (name or "").strip().casefold()
    if not target:
        return []

    department_value = (department or "").strip()
    matched = []
    for candidate in User.objects.filter(is_active=True).select_related("profile").order_by("id"):
        if roles:
            candidate_roles = _user_module_roles(candidate)
            if not any(role in candidate_roles for role in roles):
                continue
        if department_value:
            candidate_department = _profile_department(candidate)
            if candidate_department.casefold() != department_value.casefold():
                continue
        if target in _user_identity_values(candidate):
            matched.append(candidate)
    return matched


def _request_authority_users_for_no_dues(student):
    roles = {"acadadmin", "librarian", "hostel_warden", "mess_incharge", "lab_incharge"}
    users = []
    for role in sorted(roles):
        users.extend(_role_users(role))
    return _unique_users(users)


def _resolve_student_for_no_dues(actor, identifier):
    target = (identifier or "").strip()
    if not target:
        raise ValueError("student identifier is required.")

    queryset = User.objects.filter(is_active=True).select_related("profile").order_by("username")
    role = _user_role(actor)
    if role == "hod":
        queryset = queryset.filter(profile__department__iexact=_profile_department(actor))

    student = queryset.filter(Q(username__iexact=target) | Q(profile__roll_no__iexact=target)).first()
    if not student:
        raise ValueError("Student not found.")
    return student


def _can_manage_no_dues_entries(actor, student):
    if not _is_no_dues_reviewer(actor):
        return False
    role = _user_role(actor)
    if role == "hod":
        return _belongs_to_user_department(student, actor)
    return True


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return bool(value)


def _leave_payload(leave):
    return {
        "id": leave.id,
        "student": leave.user.username if leave.user else "",
        "student_name": leave.student_name,
        "roll_no": leave.roll_no,
        "leave_type": leave.leave_type,
        "date_from": leave.date_from.isoformat() if leave.date_from else None,
        "date_to": leave.date_to.isoformat() if leave.date_to else None,
        "status": leave.status,
        "hod_remarks": leave.hod_remarks,
        "reviewed_at": leave.reviewed_at.isoformat() if leave.reviewed_at else None,
        "reviewed_by": leave.reviewed_by.username if leave.reviewed_by else None,
    }


def _bonafide_payload(req):
    return {
        "id": req.id,
        "student": req.student.username,
        "certificate_type": req.certificate_type,
        "certificate_type_label": req.get_certificate_type_display(),
        "purpose": req.purpose,
        "status": req.status,
        "requested_at": req.requested_at.isoformat(),
        "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
        "reviewed_by": req.reviewed_by.username if req.reviewed_by else None,
        "review_remarks": req.review_remarks,
        "certificate_sent": bool(req.certificate_file),
        "certificate_sent_at": req.certificate_sent_at.isoformat() if req.certificate_sent_at else None,
        "certificate_download_url": f"/otheracademic/api/bonafide/requests/{req.id}/download/"
        if req.certificate_file and req.status == "approved"
        else None,
        "can_withdraw": req.status == "pending",
    }


def _assistantship_next_stage_users(claim, stage_field):
    department = _profile_department(claim.student)
    if stage_field == "thesis_status":
        users = _role_users("admin", department=department)
        return users or _role_users("admin")
    if stage_field == "ta_status":
        return _users_matching_identity(claim.hod, roles={"hod"}, department=department)
    if stage_field == "hod_status":
        users = _role_users("acadadmin", department=department)
        return users or _role_users("acadadmin")
    return []


def _assistantship_submission_authorities(claim):
    department = _profile_department(claim.student)
    return _users_matching_identity(claim.thesis_supervisor, roles={"thesis_supervisor"}, department=department)


def _assistantship_next_stage_label(stage_field):
    next_stage = ASSISTANTSHIP_NEXT_STAGE.get(stage_field)
    if not next_stage:
        return "next stage"
    return ASSISTANTSHIP_STAGE_CONFIG[next_stage]["label"]


HISTORY_REVIEWER_ROLES = {"hod", "acadadmin", "thesis_supervisor", "ta_supervisor", "admin"}


def _history_timestamp(value):
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _history_actor_name(user):
    if not user:
        return None
    return user.get_full_name() or user.username


def _build_history_item(
    *,
    category,
    workflow_type,
    workflow_label,
    entity_id,
    title,
    status_value,
    requested_at=None,
    updated_at=None,
    actor_name=None,
    action_label=None,
    remarks="",
    student=None,
    extra=None,
):
    payload = {
        "key": f"{category}-{workflow_type}-{entity_id}",
        "category": category,
        "workflow_type": workflow_type,
        "workflow_label": workflow_label,
        "entity_id": entity_id,
        "title": title,
        "status": status_value,
        "requested_at": _history_timestamp(requested_at),
        "updated_at": _history_timestamp(updated_at),
        "timestamp": _history_timestamp(updated_at or requested_at),
        "actor_name": actor_name,
        "action_label": action_label,
        "remarks": remarks or "",
        "student_name": _display_name(student) if student else None,
        "student_username": student.username if student else None,
        "student_roll_no": getattr(getattr(student, "profile", None), "roll_no", "") if student else "",
    }
    if extra:
        payload["extra"] = extra
    return payload


def _build_student_request_history(user):
    items = []

    for leave in Leave.objects.filter(user=user).select_related("reviewed_by").order_by("-created_at"):
        items.append(
            _build_history_item(
                category="request",
                workflow_type="leave",
                workflow_label="Leave",
                entity_id=leave.id,
                title=f"{leave.get_leave_type_display()} leave",
                status_value=leave.status,
                requested_at=leave.created_at,
                updated_at=leave.reviewed_at or leave.updated_at,
                actor_name=_history_actor_name(leave.reviewed_by),
                action_label="Reviewed" if leave.reviewed_by else None,
                remarks=leave.hod_remarks,
                student=user,
                extra={
                    "date_from": _to_iso(leave.date_from),
                    "date_to": _to_iso(leave.date_to),
                },
            )
        )

    for claim in AssistantshipClaim.objects.filter(student=user).order_by("-created_at"):
        items.append(
            _build_history_item(
                category="request",
                workflow_type="assistantship",
                workflow_label="Assistantship",
                entity_id=claim.id,
                title=f"Assistantship claim for {claim.date_from} to {claim.date_to}",
                status_value=claim.overall_status.lower(),
                requested_at=claim.created_at,
                updated_at=claim.updated_at,
                remarks=claim.withdraw_reason,
                student=user,
                extra={
                    "approval_stages": _claim_to_status_payload(claim)["approvalStages"],
                    "student_verified": claim.student_verified,
                    "student_withdrawn": claim.student_withdrawn,
                },
            )
        )

    for req in BonafideRequest.objects.filter(student=user).select_related("reviewed_by").order_by("-requested_at"):
        items.append(
            _build_history_item(
                category="request",
                workflow_type="bonafide",
                workflow_label="Bonafide",
                entity_id=req.id,
                title=req.get_certificate_type_display(),
                status_value=req.status,
                requested_at=req.requested_at,
                updated_at=req.reviewed_at or req.certificate_sent_at or req.requested_at,
                actor_name=_history_actor_name(req.reviewed_by),
                action_label="Reviewed" if req.reviewed_by else None,
                remarks=req.review_remarks,
                student=user,
            )
        )

    for req in NoDuesRequest.objects.filter(student=user).select_related("reviewed_by").order_by("-requested_at"):
        items.append(
            _build_history_item(
                category="request",
                workflow_type="no_dues",
                workflow_label="No Dues",
                entity_id=req.id,
                title="No-dues clearance request",
                status_value=req.status,
                requested_at=req.requested_at,
                updated_at=req.reviewed_at or req.clearance_uploaded_at or req.requested_at,
                actor_name=_history_actor_name(req.reviewed_by),
                action_label="Reviewed" if req.reviewed_by else None,
                remarks=req.review_remarks or req.remarks,
                student=user,
                extra={"total_due_snapshot": str(req.total_due_snapshot)},
            )
        )

    for seminar in Seminar.objects.filter(student=user).order_by("-created_at"):
        items.append(
            _build_history_item(
                category="request",
                workflow_type="seminar",
                workflow_label="Seminar",
                entity_id=seminar.id,
                title=seminar.topic,
                status_value=seminar.status,
                requested_at=seminar.created_at,
                updated_at=seminar.updated_at,
                actor_name=_history_actor_name(seminar.scheduled_by),
                action_label="Scheduled" if seminar.scheduled_by else None,
                remarks=seminar.evaluation_notes,
                student=user,
                extra={
                    "venue": seminar.venue,
                    "scheduled_start": _to_iso(seminar.scheduled_start),
                    "scheduled_end": _to_iso(seminar.scheduled_end),
                },
            )
        )

    return sorted(items, key=lambda item: item["timestamp"], reverse=True)


def _build_reviewer_decision_history(user):
    items = []

    for leave in Leave.objects.filter(reviewed_by=user, status__in=["approved", "rejected"]).select_related("user").order_by("-reviewed_at"):
        items.append(
            _build_history_item(
                category="decision",
                workflow_type="leave",
                workflow_label="Leave",
                entity_id=leave.id,
                title=f"{leave.get_leave_type_display()} leave",
                status_value=leave.status,
                requested_at=leave.created_at,
                updated_at=leave.reviewed_at,
                actor_name=_history_actor_name(user),
                action_label=leave.status.capitalize(),
                remarks=leave.hod_remarks,
                student=leave.user,
            )
        )

    for req in BonafideRequest.objects.filter(reviewed_by=user, status__in=["approved", "rejected"]).select_related("student").order_by("-reviewed_at"):
        items.append(
            _build_history_item(
                category="decision",
                workflow_type="bonafide",
                workflow_label="Bonafide",
                entity_id=req.id,
                title=req.get_certificate_type_display(),
                status_value=req.status,
                requested_at=req.requested_at,
                updated_at=req.reviewed_at,
                actor_name=_history_actor_name(user),
                action_label=req.status.capitalize(),
                remarks=req.review_remarks,
                student=req.student,
            )
        )

    for req in NoDuesRequest.objects.filter(reviewed_by=user, status__in=["in_progress", "approved", "rejected"]).select_related("student").order_by("-reviewed_at"):
        items.append(
            _build_history_item(
                category="decision",
                workflow_type="no_dues",
                workflow_label="No Dues",
                entity_id=req.id,
                title="No-dues clearance request",
                status_value=req.status,
                requested_at=req.requested_at,
                updated_at=req.reviewed_at,
                actor_name=_history_actor_name(user),
                action_label="Verified" if req.status == "in_progress" else req.status.capitalize(),
                remarks=req.review_remarks,
                student=req.student,
            )
        )

    for assignment in TAAssignment.objects.filter(hod_reviewed_by=user).exclude(hod_reviewed_at__isnull=True).select_related("student", "course").order_by("-hod_reviewed_at"):
        action_label = "Approved" if assignment.status == TAAssignment.STATUS_ACTIVE else "Rejected"
        items.append(
            _build_history_item(
                category="decision",
                workflow_type="ta_assignment",
                workflow_label="TA Assignment",
                entity_id=assignment.id,
                title=assignment.course.course_code,
                status_value=assignment.status,
                requested_at=assignment.created_at,
                updated_at=assignment.hod_reviewed_at,
                actor_name=_history_actor_name(user),
                action_label=action_label,
                remarks=assignment.remarks,
                student=assignment.student,
            )
        )

    audit_logs = WorkflowAuditLog.objects.filter(
        actor=user,
        entity_type="AssistantshipClaim",
        metadata__stage__isnull=False,
    ).order_by("-created_at")
    for log in audit_logs:
        decision = (log.metadata or {}).get("decision")
        if decision not in {"approved", "rejected"}:
            continue
        after_data = log.after_data or {}
        student_name = after_data.get("student_name") or ""
        student_roll_no = after_data.get("roll_no") or ""
        items.append(
            {
                "key": f"decision-assistantship-{log.id}",
                "category": "decision",
                "workflow_type": "assistantship",
                "workflow_label": "Assistantship",
                "entity_id": log.entity_id,
                "title": f"Assistantship claim #{log.entity_id}",
                "status": decision,
                "requested_at": "",
                "updated_at": _history_timestamp(log.created_at),
                "timestamp": _history_timestamp(log.created_at),
                "actor_name": _history_actor_name(user),
                "action_label": decision.capitalize(),
                "remarks": ASSISTANTSHIP_STAGE_CONFIG.get((log.metadata or {}).get("stage"), {}).get("label", ""),
                "student_name": student_name,
                "student_username": after_data.get("student_username"),
                "student_roll_no": student_roll_no,
                "extra": {
                    "stage": ASSISTANTSHIP_STAGE_CONFIG.get((log.metadata or {}).get("stage"), {}).get("label", ""),
                    "approval_stages": after_data.get("approvalStages", {}),
                },
            }
        )

    return sorted(items, key=lambda item: item["timestamp"], reverse=True)


# ============================================================================
# LEAVE MANAGEMENT
# ============================================================================


class LeaveFormSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data.copy()
        serializer = LeaveCreateSerializer(data=data, context={"request": request})
        if serializer.is_valid():
            leave = serializer.save()
            authorities = _department_authorities(request.user, roles=("hod",))
            _notify_users(
                authorities,
                "Leave request pending review",
                (
                    f"{request.user.get_full_name() or request.user.username} submitted a "
                    f"{leave.leave_type} leave request for {leave.date_from} to {leave.date_to}."
                ),
            )
            return Response(
                {"message": "Leave application submitted successfully", "data": LeaveOutputSerializer(leave).data},
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LeaveFormDefaultsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "message": "Leave defaults fetched successfully",
                "data": get_leave_form_defaults(request.user),
            },
            status=status.HTTP_200_OK,
        )


class FetchPendingLeavesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            role = _user_role(request.user)
            if role != "hod":
                return Response({"error": "Only HoD can view pending leave requests"}, status=status.HTTP_403_FORBIDDEN)
        except UserProfile.DoesNotExist:
            return Response({"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND)

        pending_leaves = Leave.objects.filter(status="pending").select_related("user", "user__profile", "reviewed_by")
        if role == "hod":
            pending_leaves = pending_leaves.filter(user__profile__department__iexact=_profile_department(request.user))
        pending_leaves = pending_leaves.order_by("-created_at")
        serializer = LeaveOutputSerializer(pending_leaves, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UpdateLeaveStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        try:
            role = _user_role(request.user)
            if role != "hod":
                return Response({"error": "Only HoD can approve or reject leave requests"}, status=status.HTTP_403_FORBIDDEN)
        except UserProfile.DoesNotExist:
            return Response({"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND)

        approved_ids = request.data.get("approvedLeaves", [])
        rejected_ids = request.data.get("rejectedLeaves", [])
        remarks = request.data.get("remarks", "")

        if not isinstance(approved_ids, list) or not isinstance(rejected_ids, list):
            return Response(
                {"error": "approvedLeaves and rejectedLeaves must be arrays."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            approved_ids = [int(leave_id) for leave_id in approved_ids]
            rejected_ids = [int(leave_id) for leave_id in rejected_ids]
        except (TypeError, ValueError):
            return Response({"error": "Leave IDs must be integers."}, status=status.HTTP_400_BAD_REQUEST)

        duplicate_ids = sorted(set(approved_ids).intersection(rejected_ids))
        if duplicate_ids:
            return Response(
                {"error": f"Leave IDs cannot be both approved and rejected: {duplicate_ids}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        decision_map = {leave_id: "approved" for leave_id in approved_ids}
        decision_map.update({leave_id: "rejected" for leave_id in rejected_ids})
        if not decision_map:
            return Response(
                {"error": "At least one leave request must be approved or rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if role == "hod":
            scoped_ids = set(
                Leave.objects.filter(user__profile__department__iexact=_profile_department(request.user)).values_list("id", flat=True)
            )
            requested_ids = set(decision_map)
            if not requested_ids.issubset(scoped_ids):
                return Response({"error": "You can update only leave requests from your department."}, status=status.HTTP_403_FORBIDDEN)

        leaves = {
            leave.id: leave
            for leave in Leave.objects.select_for_update()
            .select_related("user", "user__profile", "reviewed_by")
            .filter(id__in=decision_map.keys())
        }
        missing_ids = sorted(set(decision_map) - set(leaves))
        if missing_ids:
            return Response({"error": f"Invalid leave IDs: {missing_ids}"}, status=status.HTTP_400_BAD_REQUEST)

        non_pending = sorted(leave.id for leave in leaves.values() if leave.status != "pending")
        if non_pending:
            return Response(
                {"error": f"Only pending leave requests can be updated. Non-pending IDs: {non_pending}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        for leave_id, decision in decision_map.items():
            leave = leaves[leave_id]
            before = _leave_payload(leave)
            leave.status = decision
            leave.reviewed_by = request.user
            leave.reviewed_at = now
            leave.hod_remarks = remarks if remarks else ""
            leave.save(update_fields=["status", "reviewed_by", "reviewed_at", "hod_remarks", "updated_at"])
            if leave.user_id:
                create_notification(
                    leave.user,
                    f"Leave request {decision}",
                    f"Your {leave.leave_type} leave request from {leave.date_from} to {leave.date_to} was {decision}.",
                )
            AuditLogRepository.log(
                request.user,
                f"leave_{decision}",
                "Leave",
                leave.id,
                before_data=before,
                after_data=_leave_payload(leave),
            )

        return Response({"message": "Leave statuses updated successfully"}, status=status.HTTP_200_OK)


class GetLeaveRequestsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        leaves = Leave.objects.filter(user=request.user).select_related("user", "user__profile", "reviewed_by")
        serializer = LeaveOutputSerializer(leaves, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class WithdrawLeaveRequestView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, leave_id):
        leave_request = get_object_or_404(
            Leave.objects.select_for_update().select_related("user", "reviewed_by"),
            id=leave_id,
            user=request.user,
        )
        if leave_request.status != "pending":
            return Response(
                {"error": f"Only pending leave requests can be withdrawn. Current status: {leave_request.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        before = _leave_payload(leave_request)
        leave_request.status = "withdrawn"
        leave_request.reviewed_by = request.user
        leave_request.reviewed_at = timezone.now()
        leave_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
        AuditLogRepository.log(
            request.user,
            "leave_withdrawn",
            "Leave",
            leave_request.id,
            before_data=before,
            after_data=_leave_payload(leave_request),
        )

        create_notification(
            request.user,
            "Leave request withdrawn",
            f"Your leave request from {leave_request.date_from} to {leave_request.date_to} was withdrawn.",
        )
        return Response({"message": "Leave request withdrawn successfully."}, status=status.HTTP_200_OK)


class WorkflowHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = _user_role(request.user)
        request_history = _build_student_request_history(request.user) if role == "student" else []
        decision_history = _build_reviewer_decision_history(request.user) if role in HISTORY_REVIEWER_ROLES else []

        return Response(
            {
                "message": "Workflow history fetched successfully",
                "data": {
                    "role": role,
                    "request_history": request_history,
                    "decision_history": decision_history,
                    "request_count": len(request_history),
                    "decision_count": len(decision_history),
                },
            },
            status=status.HTTP_200_OK,
        )


# ============================================================================
# BONAFIDE CERTIFICATE MANAGEMENT
# ============================================================================


class BonafideCertificateOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        options = [{"value": value, "label": label} for value, label in BonafideRequest.CERTIFICATE_TYPE_CHOICES]
        return Response({"data": options}, status=status.HTTP_200_OK)


class SubmitBonafideRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if _user_role(request.user) != "student":
            return Response({"error": "Only students can submit bonafide requests."}, status=status.HTTP_403_FORBIDDEN)

        certificate_type = request.data.get("certificate_type")
        purpose = request.data.get("purpose", "").strip()

        valid_types = {value for value, _ in BonafideRequest.CERTIFICATE_TYPE_CHOICES}
        if certificate_type not in valid_types:
            return Response({"error": "Invalid certificate_type"}, status=status.HTTP_400_BAD_REQUEST)
        if not purpose:
            return Response({"error": "purpose is required"}, status=status.HTTP_400_BAD_REQUEST)
        if BonafideRequest.objects.filter(student=request.user, status="pending").exists():
            return Response(
                {"error": "You already have a pending bonafide request."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bonafide = BonafideRequest.objects.create(
            student=request.user,
            certificate_type=certificate_type,
            purpose=purpose,
        )
        AuditLogRepository.log(
            request.user,
            "bonafide_submitted",
            "BonafideRequest",
            bonafide.id,
            after_data=_bonafide_payload(bonafide),
        )

        create_notification(
            request.user,
            "Bonafide request submitted",
            f"Your bonafide certificate request for {bonafide.get_certificate_type_display()} was submitted.",
        )
        _notify_users(
            _role_users("acadadmin"),
            "Bonafide request pending review",
            (
                f"{request.user.get_full_name() or request.user.username} submitted a bonafide "
                f"request for {bonafide.get_certificate_type_display()}."
            ),
        )

        return Response(
            {
                "message": "Bonafide request submitted successfully",
                "data": {
                    "id": bonafide.id,
                    "certificate_type": bonafide.certificate_type,
                    "certificate_type_label": bonafide.get_certificate_type_display(),
                    "purpose": bonafide.purpose,
                    "status": bonafide.status,
                    "requested_at": bonafide.requested_at.isoformat(),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class GetBonafideRequestsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        status_filter = request.query_params.get("status", "all")
        is_reviewer = _is_bonafide_reviewer(request.user)
        if not is_reviewer and _user_role(request.user) != "student":
            return Response({"error": "Only students and Academic Admin can access bonafide requests."}, status=status.HTTP_403_FORBIDDEN)

        queryset = (
            BonafideRequest.objects.select_related("student", "reviewed_by").all()
            if is_reviewer
            else BonafideRequest.objects.select_related("student", "reviewed_by").filter(student=request.user)
        )
        if status_filter != "all":
            queryset = queryset.filter(status=status_filter)
        data = [_bonafide_payload(req) for req in queryset.order_by("-requested_at")]
        return Response({"message": "Bonafide requests fetched successfully", "data": data}, status=status.HTTP_200_OK)


class WithdrawBonafideRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        if _user_role(request.user) != "student":
            return Response({"error": "Only students can withdraw bonafide requests."}, status=status.HTTP_403_FORBIDDEN)

        req_obj = get_object_or_404(BonafideRequest, id=request_id, student=request.user)
        if req_obj.status != "pending":
            return Response(
                {"error": f"Only pending bonafide requests can be withdrawn. Current status: {req_obj.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        before = _bonafide_payload(req_obj)
        req_obj.status = "withdrawn"
        req_obj.reviewed_at = timezone.now()
        req_obj.reviewed_by = request.user
        req_obj.review_remarks = request.data.get("remarks", "Withdrawn by student")
        req_obj.save(update_fields=["status", "reviewed_at", "reviewed_by", "review_remarks"])
        AuditLogRepository.log(
            request.user,
            "bonafide_withdrawn",
            "BonafideRequest",
            req_obj.id,
            before_data=before,
            after_data=_bonafide_payload(req_obj),
        )
        create_notification(
            request.user,
            "Bonafide request withdrawn",
            f"Your bonafide request for {req_obj.get_certificate_type_display()} was withdrawn.",
        )
        return Response({"message": "Bonafide request withdrawn successfully"}, status=status.HTTP_200_OK)


class ApproveBonafideRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        if not _is_bonafide_reviewer(request.user):
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)

        req_obj = get_object_or_404(BonafideRequest, id=request_id)
        if req_obj.status != "pending":
            return Response({"error": f"Request is already {req_obj.status}"}, status=status.HTTP_400_BAD_REQUEST)

        before = _bonafide_payload(req_obj)
        req_obj.status = "approved"
        req_obj.reviewed_at = timezone.now()
        req_obj.reviewed_by = request.user
        req_obj.review_remarks = request.data.get("remarks", "")
        req_obj.save()
        AuditLogRepository.log(
            request.user,
            "bonafide_approved",
            "BonafideRequest",
            req_obj.id,
            before_data=before,
            after_data=_bonafide_payload(req_obj),
        )

        create_notification(
            req_obj.student,
            "Bonafide request approved",
            f"Your bonafide request for {req_obj.get_certificate_type_display()} was approved.",
        )
        return Response({"message": "Bonafide request approved successfully"}, status=status.HTTP_200_OK)


class RejectBonafideRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        if not _is_bonafide_reviewer(request.user):
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)

        req_obj = get_object_or_404(BonafideRequest, id=request_id)
        if req_obj.status != "pending":
            return Response({"error": f"Request is already {req_obj.status}"}, status=status.HTTP_400_BAD_REQUEST)

        before = _bonafide_payload(req_obj)
        req_obj.status = "rejected"
        req_obj.reviewed_at = timezone.now()
        req_obj.reviewed_by = request.user
        req_obj.review_remarks = request.data.get("remarks", "")
        req_obj.save()
        AuditLogRepository.log(
            request.user,
            "bonafide_rejected",
            "BonafideRequest",
            req_obj.id,
            before_data=before,
            after_data=_bonafide_payload(req_obj),
        )

        create_notification(
            req_obj.student,
            "Bonafide request rejected",
            f"Your bonafide request for {req_obj.get_certificate_type_display()} was rejected.",
        )
        return Response({"message": "Bonafide request rejected successfully"}, status=status.HTTP_200_OK)


class SendBonafideCertificateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        if not _is_bonafide_reviewer(request.user):
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)

        req_obj = get_object_or_404(BonafideRequest, id=request_id)
        if req_obj.status != "approved":
            return Response({"error": "Certificate can be issued only after bonafide approval."}, status=status.HTTP_400_BAD_REQUEST)
        certificate_file = request.FILES.get("certificate_file")
        if not certificate_file:
            return Response({"error": "certificate_file is required"}, status=status.HTTP_400_BAD_REQUEST)

        before = _bonafide_payload(req_obj)
        req_obj.certificate_file = certificate_file
        req_obj.certificate_sent_at = timezone.now()
        req_obj.reviewed_at = timezone.now()
        req_obj.reviewed_by = request.user
        req_obj.save()
        AuditLogRepository.log(
            request.user,
            "bonafide_certificate_sent",
            "BonafideRequest",
            req_obj.id,
            before_data=before,
            after_data=_bonafide_payload(req_obj),
        )

        create_notification(
            req_obj.student,
            "Bonafide certificate issued",
            f"Your bonafide certificate for {req_obj.get_certificate_type_display()} is ready to download.",
        )
        return Response({"message": "Certificate uploaded and sent successfully"}, status=status.HTTP_200_OK)


class DownloadBonafideCertificateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, request_id):
        req_obj = get_object_or_404(BonafideRequest, id=request_id)
        role = _user_role(request.user)
        is_admin = _is_bonafide_reviewer(request.user)
        if not is_admin and req_obj.student_id != request.user.id:
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)
        if req_obj.status != "approved":
            return Response({"error": "Bonafide request is not approved yet."}, status=status.HTTP_400_BAD_REQUEST)
        if not req_obj.certificate_file:
            return Response({"error": "Certificate not available yet"}, status=status.HTTP_404_NOT_FOUND)

        try:
            return FileResponse(
                req_obj.certificate_file.open("rb"),
                as_attachment=True,
                filename=req_obj.certificate_file.name.split("/")[-1],
            )
        except FileNotFoundError as exc:
            raise Http404("Certificate file not found") from exc


# ============================================================================
# NO DUES MANAGEMENT
# ============================================================================


class GetNoDuesSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        entries = NoDuesEntry.objects.filter(student=request.user).order_by("-updated_at")
        outstanding_entries = entries.filter(is_cleared=False)
        total_due = outstanding_entries.aggregate(total=Sum("amount")).get("total") or 0
        latest_request = NoDuesRequest.objects.filter(student=request.user).first()

        data = [
            {
                "id": entry.id,
                "category": entry.category,
                "description": entry.description,
                "amount": str(entry.amount),
                "is_cleared": entry.is_cleared,
            }
            for entry in entries
        ]

        return Response(
            {
                "message": "No dues summary fetched successfully",
                "data": data,
                "total_due": str(total_due),
                "outstanding_count": outstanding_entries.count(),
                "latest_request_status": latest_request.status if latest_request else None,
            },
            status=status.HTTP_200_OK,
        )


class NoDuesEntryManagementView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_no_dues_reviewer(request.user):
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)

        try:
            student = _resolve_student_for_no_dues(request.user, request.query_params.get("student"))
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not _can_manage_no_dues_entries(request.user, student):
            return Response({"error": "You can manage no-dues entries only for allowed students."}, status=status.HTTP_403_FORBIDDEN)

        entries = _scoped_no_dues_entries(student, request.user)
        return Response(
            {
                "message": "No dues entries fetched successfully",
                "student": {
                    "username": student.username,
                    "roll_no": getattr(getattr(student, "profile", None), "roll_no", ""),
                    "department": _profile_department(student),
                    "name": _display_name(student),
                },
                "role_scope": _user_role(request.user),
                "default_category": NO_DUES_ROLE_DEFAULT_CATEGORY.get(_user_role(request.user), ""),
                "data": _serialize_no_dues_entries(entries),
            },
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def post(self, request):
        if not _is_no_dues_reviewer(request.user):
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)

        try:
            student = _resolve_student_for_no_dues(request.user, request.data.get("student"))
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not _can_manage_no_dues_entries(request.user, student):
            return Response({"error": "You can manage no-dues entries only for allowed students."}, status=status.HTTP_403_FORBIDDEN)

        role = _user_role(request.user)
        scoped_category = NO_DUES_ROLE_DEFAULT_CATEGORY.get(role, "")
        category = (request.data.get("category") or "").strip()
        if scoped_category:
            category = scoped_category
        if not category:
            return Response({"error": "category is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(str(request.data.get("amount", "0")))
        except (InvalidOperation, TypeError, ValueError):
            return Response({"error": "amount must be a valid number."}, status=status.HTTP_400_BAD_REQUEST)
        if amount < 0:
            return Response({"error": "amount cannot be negative."}, status=status.HTTP_400_BAD_REQUEST)

        description = (request.data.get("description") or "").strip()
        is_cleared = _coerce_bool(request.data.get("is_cleared", False))
        entry_id = request.data.get("entry_id")

        if role not in GLOBAL_BACKEND_ROLES.union({"hod"}) and not _matches_no_dues_scope(category, _no_dues_scope_keywords(request.user)):
            return Response({"error": "You can manage only entries in your assigned no-dues domain."}, status=status.HTTP_403_FORBIDDEN)

        entry = None
        if entry_id:
            entry = get_object_or_404(NoDuesEntry.objects.select_for_update(), id=entry_id, student=student)
            if role not in GLOBAL_BACKEND_ROLES.union({"hod"}) and not _matches_no_dues_scope(entry.category, _no_dues_scope_keywords(request.user)):
                return Response({"error": "You can update only entries in your assigned no-dues domain."}, status=status.HTTP_403_FORBIDDEN)
        elif scoped_category:
            entry = (
                NoDuesEntry.objects.select_for_update().filter(student=student, category__iexact=scoped_category)
                .order_by("-updated_at")
                .first()
            )

        created = False
        if entry is None:
            entry = NoDuesEntry(student=student)
            created = True

        entry.category = category
        entry.description = description
        entry.amount = amount
        entry.is_cleared = is_cleared
        entry.save()

        create_notification(
            student,
            "No dues entry updated",
            f"{category} no-dues entry was {'created' if created else 'updated'} for your account.",
        )

        return Response(
            {
                "message": f"No dues entry {'created' if created else 'updated'} successfully",
                "data": _serialize_no_dues_entries([entry])[0],
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class RequestNoDuesView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        pending_exists = NoDuesRequest.objects.select_for_update().filter(student=request.user, status__in=["pending", "in_progress"]).exists()
        if pending_exists:
            return Response(
                {"error": "You already have an active no-dues request."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_due = (
            NoDuesEntry.objects.filter(student=request.user, is_cleared=False).aggregate(total=Sum("amount")).get("total") or 0
        )
        request_obj = NoDuesRequest.objects.create(
            student=request.user,
            remarks=request.data.get("remarks", ""),
            total_due_snapshot=total_due,
            status="pending",
            domain_approvals=_default_no_dues_domain_approvals(),
        )
        create_notification(
            request.user,
            "No dues request submitted",
            f"Your no-dues request has been submitted with total due snapshot: {total_due}.",
        )
        _notify_users(
            _request_authority_users_for_no_dues(request.user),
            "No dues request pending review",
            (
                f"{request.user.get_full_name() or request.user.username} submitted a no-dues request "
                f"with total outstanding amount {total_due}."
            ),
        )

        return Response(
            {
                "message": "No dues request submitted successfully",
                "data": {
                    "id": request_obj.id,
                    "status": request_obj.status,
                    "total_due_snapshot": str(request_obj.total_due_snapshot),
                    "requested_at": request_obj.requested_at.isoformat(),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class GetNoDuesRequestsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        status_filter = request.query_params.get("status", "all")
        is_reviewer = _is_no_dues_reviewer(request.user)
        role = _user_role(request.user)

        queryset = (
            NoDuesRequest.objects.select_related("student", "student__profile", "reviewed_by").all()
            if is_reviewer
            else NoDuesRequest.objects.select_related("student", "student__profile", "reviewed_by").filter(student=request.user)
        )
        if role == "hod":
            queryset = queryset.filter(student__profile__department__iexact=_profile_department(request.user))
        if status_filter != "all":
            queryset = queryset.filter(status=status_filter)

        data = []
        for req in queryset.order_by("-requested_at"):
            scoped_entries = _scoped_no_dues_entries(req.student, request.user) if is_reviewer else list(
                NoDuesEntry.objects.filter(student=req.student).order_by("-updated_at")
            )

            payload = {
                "id": req.id,
                "student": req.student.username,
                "status": req.status,
                "remarks": req.remarks,
                "review_remarks": req.review_remarks,
                "total_due_snapshot": str(req.total_due_snapshot),
                "requested_at": req.requested_at.isoformat(),
                "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
                "reviewed_by": req.reviewed_by.username if req.reviewed_by else None,
                "has_clearance_file": bool(req.clearance_file),
                "clearance_file_name": req.clearance_file.name.split("/")[-1] if req.clearance_file else None,
                "domain_approvals": _normalized_no_dues_domain_approvals(req),
                "all_domain_approvals_complete": _all_no_dues_domains_approved(req),
                "visible_entries": [
                    {
                        "id": entry.id,
                        "category": entry.category,
                        "description": entry.description,
                        "amount": str(entry.amount),
                        "is_cleared": entry.is_cleared,
                    }
                    for entry in scoped_entries
                ],
            }
            if is_reviewer and role in NO_DUES_ROLE_CATEGORY_KEYWORDS:
                payload["visibility_scope"] = role
            data.append(payload)

        return Response({"message": "No dues requests fetched successfully", "data": data}, status=status.HTTP_200_OK)


class ApproveNoDuesRequestView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, request_id):
        if not _is_no_dues_reviewer(request.user):
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)

        req_obj = get_object_or_404(
            NoDuesRequest.objects.select_for_update().select_related("student", "student__profile", "reviewed_by"),
            id=request_id,
        )
        if not _can_review_no_dues_request(request.user, req_obj):
            return Response({"error": "You can review only no-dues requests related to your assigned domain."}, status=status.HTTP_403_FORBIDDEN)
        if req_obj.status not in {"pending", "in_progress"}:
            return Response({"error": f"Request is already {req_obj.status}"}, status=status.HTTP_400_BAD_REQUEST)

        before_status = req_obj.status
        role = _user_role(request.user)
        if _is_no_dues_finalizer(request.user):
            if not _all_no_dues_domains_approved(req_obj):
                return Response(
                    {"error": "Academic Admin can finalize only after mess, hostel, librarian, and lab approvals are completed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            outstanding_exists = NoDuesEntry.objects.select_for_update().filter(student=req_obj.student, is_cleared=False).exists()
            if outstanding_exists:
                return Response(
                    {"error": "No-dues request can be finalized only after all outstanding entries are cleared."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            req_obj.status = "approved"
            req_obj.reviewed_at = timezone.now()
            req_obj.reviewed_by = request.user
            req_obj.review_remarks = request.data.get("remarks", "")
            req_obj.save()

            create_notification(
                req_obj.student,
                "No dues request approved",
                "Your no-dues request has been finalized and approved.",
            )
            return Response({"message": "No dues request finalized successfully"}, status=status.HTTP_200_OK)

        approvals = _normalized_no_dues_domain_approvals(req_obj)
        if approvals[role]["status"] == "approved":
            return Response({"error": "Your domain has already approved this request."}, status=status.HTTP_400_BAD_REQUEST)
        if approvals[role]["status"] == "rejected":
            return Response({"error": "Your domain has already rejected this request."}, status=status.HTTP_400_BAD_REQUEST)

        scoped_entries = list(_scoped_no_dues_entries(req_obj.student, request.user))
        for entry in scoped_entries:
            if not entry.is_cleared:
                entry.is_cleared = True
                entry.save(update_fields=["is_cleared", "updated_at"])

        approvals[role] = {
            "status": "approved",
            "actor": request.user.username,
            "remarks": request.data.get("remarks", f"{role} approval recorded"),
            "timestamp": timezone.now().isoformat(),
        }
        req_obj.status = "in_progress"
        req_obj.reviewed_at = timezone.now()
        req_obj.reviewed_by = request.user
        req_obj.review_remarks = request.data.get("remarks", f"{role} approval recorded")
        req_obj.domain_approvals = approvals
        req_obj.save(update_fields=["status", "reviewed_at", "reviewed_by", "review_remarks", "domain_approvals"])

        create_notification(
            req_obj.student,
            "No dues verification updated",
            f"{role.replace('_', ' ').title()} approval was recorded for your no-dues request.",
        )

        if before_status != "in_progress":
            _notify_users(
                _role_users("acadadmin"),
                "No dues request in progress",
                f"No-dues request #{req_obj.id} for {req_obj.student.username} has started domain verification.",
            )

        return Response({"message": "No dues verification recorded successfully"}, status=status.HTTP_200_OK)


class RejectNoDuesRequestView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, request_id):
        if not _is_no_dues_reviewer(request.user):
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)

        req_obj = get_object_or_404(
            NoDuesRequest.objects.select_for_update().select_related("student", "student__profile", "reviewed_by"),
            id=request_id,
        )
        if not _can_review_no_dues_request(request.user, req_obj):
            return Response({"error": "You can review only no-dues requests related to your assigned domain."}, status=status.HTTP_403_FORBIDDEN)
        if req_obj.status not in {"pending", "in_progress"}:
            return Response({"error": f"Request is already {req_obj.status}"}, status=status.HTTP_400_BAD_REQUEST)

        role = _user_role(request.user)
        approvals = _normalized_no_dues_domain_approvals(req_obj)
        if role in NO_DUES_DOMAIN_REVIEWER_ROLES:
            approvals[role] = {
                "status": "rejected",
                "actor": request.user.username,
                "remarks": request.data.get("remarks", f"{role} rejection recorded"),
                "timestamp": timezone.now().isoformat(),
            }
            req_obj.domain_approvals = approvals
        req_obj.status = "rejected"
        req_obj.reviewed_at = timezone.now()
        req_obj.reviewed_by = request.user
        req_obj.review_remarks = request.data.get("remarks", "")
        req_obj.save()

        create_notification(
            req_obj.student,
            "No dues request rejected",
            f"Your no-dues request was rejected by {role.replace('_', ' ').title()}.",
        )

        return Response({"message": "No dues request rejected successfully"}, status=status.HTTP_200_OK)


class UploadNoDuesClearanceFileView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        if not _is_no_dues_finalizer(request.user):
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)

        req_obj = get_object_or_404(NoDuesRequest, id=request_id)
        if req_obj.status != "approved":
            return Response(
                {"error": "Clearance file can be uploaded only after final approval."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        clearance_file = request.FILES.get("clearance_file")
        if not clearance_file:
            return Response({"error": "clearance_file is required."}, status=status.HTTP_400_BAD_REQUEST)

        req_obj.clearance_file = clearance_file
        req_obj.clearance_uploaded_at = timezone.now()
        req_obj.reviewed_by = request.user
        if not req_obj.reviewed_at:
            req_obj.reviewed_at = timezone.now()
        req_obj.save()

        create_notification(
            req_obj.student,
            "No dues clearance file uploaded",
            "Your approved no-dues clearance file is ready for download.",
        )

        return Response({"message": "No dues clearance file uploaded successfully"}, status=status.HTTP_200_OK)


class DownloadNoDuesClearanceFileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, request_id):
        req_obj = get_object_or_404(NoDuesRequest, id=request_id)
        is_admin = _is_no_dues_reviewer(request.user)
        if not is_admin and req_obj.student_id != request.user.id:
            return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)
        if is_admin and not (_is_no_dues_finalizer(request.user) or _can_review_no_dues_request(request.user, req_obj)):
            return Response({"error": "You can access only no-dues files related to your assigned domain."}, status=status.HTTP_403_FORBIDDEN)
        if req_obj.status != "approved":
            return Response({"error": "No dues request is not finalized yet."}, status=status.HTTP_400_BAD_REQUEST)
        if not req_obj.clearance_file:
            return Response({"error": "Clearance file not available yet."}, status=status.HTTP_404_NOT_FOUND)

        try:
            return FileResponse(
                req_obj.clearance_file.open("rb"),
                as_attachment=True,
                filename=req_obj.clearance_file.name.split("/")[-1],
            )
        except FileNotFoundError as exc:
            raise Http404("Clearance file not found") from exc


# ============================================================================
# ASSISTANTSHIP MANAGEMENT
# ============================================================================


ASSISTANTSHIP_STAGE_CONFIG = {
    "thesis_status": {
        "label": "Supervisor",
        "role_names": ["thesis_supervisor"],
        "claim_field": "thesis_supervisor",
        "prerequisites": [],
    },
    "ta_status": {
        "label": "Department Admin",
        "role_names": ["admin"],
        "claim_field": None,
        "prerequisites": [("thesis_status", "approved")],
    },
    "hod_status": {
        "label": "HoD",
        "role_names": ["hod"],
        "claim_field": None,
        "prerequisites": [("ta_status", "approved")],
    },
    "acadadmin_status": {
        "label": "Stipend Disbursement",
        "role_names": ["acadadmin"],
        "claim_field": None,
        "prerequisites": [("hod_status", "approved")],
    },
}

ASSISTANTSHIP_NEXT_STAGE = {
    "thesis_status": "ta_status",
    "ta_status": "hod_status",
    "hod_status": "acadadmin_status",
}


def _profile_department(user):
    return (getattr(getattr(user, "profile", None), "department", "") or "").strip()


def _user_role(user):
    return get_active_role_for_user(user)


def _user_identity_values(user):
    values = {
        (user.get_full_name() or "").strip(),
        (user.username or "").strip(),
        (user.email or "").strip(),
    }
    return {value.casefold() for value in values if value}


def _display_name(user):
    return user.get_full_name() or user.username


def _active_ta_assignment_for(student):
    return (
        TAAssignment.objects.filter(
            student=student,
            status=TAAssignment.STATUS_ACTIVE,
        )
        .select_related("faculty", "course")
        .order_by("-created_at")
        .first()
    )


def _active_supervisor_assignment_for(student):
    return (
        SupervisorAssignment.objects.filter(
            student=student,
            is_primary=True,
            is_active=True,
        )
        .select_related("supervisor")
        .order_by("-created_at")
        .first()
    )


def _find_approver(name, role, department=""):
    filters = {
        "is_active": True,
        "role": role,
        "name__iexact": (name or "").strip(),
    }
    queryset = AssistantshipApprover.objects.filter(**filters)
    if department:
        queryset = queryset.filter(department__iexact=department)
    return queryset.first()


def _allowed_hod_queryset_for(user):
    queryset = AssistantshipApprover.objects.filter(is_active=True, role="hod").order_by("name")
    department = _profile_department(user)
    if department:
        scoped = queryset.filter(department__iexact=department)
        if scoped.exists():
            return scoped
    return queryset


def _allowed_hod_users_for(user):
    department = _profile_department(user)
    queryset = User.objects.filter(is_active=True, profile__role="hod").select_related("profile").order_by("username")
    if department:
        scoped = queryset.filter(profile__department__iexact=department)
        if scoped.exists():
            return list(scoped)
    return list(queryset)


def _log_assistantship_event(actor, action, claim, before_data=None, metadata=None):
    AuditLogRepository.log(
        actor=actor,
        action=action,
        entity_type="AssistantshipClaim",
        entity_id=claim.id,
        before_data=before_data or {},
        after_data=_claim_to_status_payload(claim),
        metadata=metadata or {},
    )


def _stage_actor_matches_claim(actor, claim, field_name):
    config = ASSISTANTSHIP_STAGE_CONFIG[field_name]
    claim_field = config.get("claim_field")
    if not claim_field:
        return True
    assigned_value = getattr(claim, claim_field, "")
    if not assigned_value:
        return False
    return assigned_value.strip().casefold() in _user_identity_values(actor)


def _assert_stage_access(actor, claim, field_name):
    if actor.is_superuser:
        return None

    config = ASSISTANTSHIP_STAGE_CONFIG[field_name]
    role = _user_role(actor)
    if role not in config["role_names"]:
        if role in {"admin", "hod", "ta_supervisor", "thesis_supervisor", "acadadmin", "dean_academic", "director"}:
            return f"This claim is not assigned to you for {config['label']} review."
        return f"Only {config['label']} authority can act on this stage."
    if not _stage_actor_matches_claim(actor, claim, field_name):
        return f"This claim is not assigned to you for {config['label']} review."
    return None


def _validate_stage_transition(claim, field_name):
    if claim.student_withdrawn:
        return "Withdrawn claims cannot be processed."
    if claim.student_verified:
        return "Verified claims cannot be modified."
    current_value = getattr(claim, field_name)
    if current_value != "pending":
        return f"{ASSISTANTSHIP_STAGE_CONFIG[field_name]['label']} stage has already been decided."
    for prerequisite_field, expected_value in ASSISTANTSHIP_STAGE_CONFIG[field_name]["prerequisites"]:
        actual_value = getattr(claim, prerequisite_field)
        if actual_value != expected_value:
            prerequisite_label = ASSISTANTSHIP_STAGE_CONFIG[prerequisite_field]["label"]
            return f"{prerequisite_label} must be {expected_value} before {ASSISTANTSHIP_STAGE_CONFIG[field_name]['label']} review."
    return None


class AssistantshipApproversView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if request.user.is_authenticated and _user_role(request.user) == "student" and not _is_pg_student(request.user):
            return Response(
                {"error": "Assistantship is available only for PG students."},
                status=status.HTTP_403_FORBIDDEN,
            )
        approvers = AssistantshipApprover.objects.filter(is_active=True).order_by("name")

        def _serialize(role):
            role_data = approvers.filter(role=role)
            return [
                {
                    "id": approver.id,
                    "name": approver.name,
                    "department": approver.department,
                    "email": approver.email,
                }
                for approver in role_data
            ]

        if request.user.is_authenticated:
            ta_assignment = _active_ta_assignment_for(request.user)
            supervisor_assignment = _active_supervisor_assignment_for(request.user)
            hod_users = _allowed_hod_users_for(request.user)
            return Response(
                {
                    "hods": [
                        {
                            "id": hod_user.id,
                            "name": _display_name(hod_user),
                            "department": _profile_department(hod_user),
                            "email": hod_user.email,
                        }
                        for hod_user in hod_users
                    ],
                    "ta_supervisors": [
                        {
                            "id": ta_assignment.assigned_by_id,
                            "name": "Department Admin",
                            "department": _profile_department(request.user),
                            "email": "",
                        }
                    ]
                    if ta_assignment
                    else [],
                    "thesis_supervisors": [
                        {
                            "id": supervisor_assignment.supervisor_id,
                            "name": _display_name(supervisor_assignment.supervisor),
                            "department": _profile_department(supervisor_assignment.supervisor),
                            "email": supervisor_assignment.supervisor.email,
                        }
                    ]
                    if supervisor_assignment
                    else [],
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "hods": _serialize("hod"),
                "ta_supervisors": _serialize("ta_supervisor"),
                "thesis_supervisors": _serialize("thesis_supervisor"),
            },
            status=status.HTTP_200_OK,
        )


def _stage_label(value):
    return value.capitalize() if value else "Pending"


def _to_iso(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _claim_to_status_payload(claim):
    can_withdraw = (not claim.student_withdrawn) and claim.overall_status == "Pending"
    can_verify = (not claim.student_verified) and claim.overall_status == "Approved"
    return {
        "id": claim.id,
        "roll_no": claim.roll_no,
        "student_name": claim.student_name,
        "discipline": claim.discipline,
        "dateFrom": _to_iso(claim.date_from),
        "dateTo": _to_iso(claim.date_to),
        "ta_supervisor": claim.ta_supervisor,
        "thesis_supervisor": claim.thesis_supervisor,
        "hod": claim.hod,
        "dateApplied": _to_iso(claim.date_applied),
        "approvalStages": {
            "Supervisor": _stage_label(claim.thesis_status),
            "Department_Admin": _stage_label(claim.ta_status),
            "HOD": _stage_label(claim.hod_status),
            "Academic_Admin": _stage_label(claim.acadadmin_status),
        },
        "status": claim.overall_status,
        "disbursedAt": _to_iso(claim.disbursed_at),
        "disbursedBy": claim.disbursed_by.username if claim.disbursed_by else None,
        "studentReviewed": claim.student_reviewed,
        "reviewedAt": _to_iso(claim.reviewed_at),
        "studentWithdrawn": claim.student_withdrawn,
        "withdrawnAt": _to_iso(claim.withdrawn_at),
        "withdrawReason": claim.withdraw_reason,
        "studentVerified": claim.student_verified,
        "verifiedAt": _to_iso(claim.verified_at),
        "canWithdraw": can_withdraw,
        "canVerify": (not claim.student_verified) and claim.acadadmin_status == "approved",
    }


class AssistantshipFormSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.POST
        required_fields = [
            "discipline",
            "date_from",
            "date_to",
            "bank_account_no",
            "applicability",
            "thesis_supervisor",
            "hod",
        ]
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            return Response(
                {"error": f"Missing required fields: {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = getattr(request.user, "profile", None)
        if not getattr(profile, "is_pg_student", False):
            return Response(
                {"error": "Only PG students can submit assistantship claims."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        supervisor_assignment = _active_supervisor_assignment_for(request.user)
        if not supervisor_assignment:
            return Response(
                {"error": "Assistantship claims cannot be submitted without an assigned thesis supervisor."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        thesis_supervisor_name = _display_name(supervisor_assignment.supervisor)
        submitted_thesis_supervisor = (data.get("thesis_supervisor") or "").strip()
        submitted_hod = (data.get("hod") or "").strip()

        if submitted_thesis_supervisor.casefold() != thesis_supervisor_name.casefold():
            return Response(
                {"error": "Selected thesis supervisor does not match the active department-assigned supervisor."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        student_department = _profile_department(request.user)
        hod_candidates = _allowed_hod_users_for(request.user)
        selected_hod_user = next(
            (
                hod_user
                for hod_user in hod_candidates
                if submitted_hod.casefold() in _user_identity_values(hod_user)
            ),
            None,
        )
        if not selected_hod_user:
            return Response(
                {"error": "Selected HoD does not match the student's department HoD assignment."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        roll_no = getattr(profile, "roll_no", "") or request.user.username
        student_name = request.user.get_full_name() or request.user.username

        date_from = parse_date(data.get("date_from", ""))
        date_to = parse_date(data.get("date_to", ""))
        date_applied = parse_date(data.get("date_applied", "")) if data.get("date_applied") else date.today()
        if not date_from or not date_to:
            return Response(
                {"error": "date_from and date_to must use YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if date_to < date_from:
            return Response(
                {"error": "date_to must be on or after date_from."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if date_applied and date_applied < date_from:
            return Response(
                {"error": "date_applied cannot be before date_from."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            claim = AssistantshipClaim.objects.create(
                student=request.user,
                student_name=student_name,
                roll_no=roll_no,
                discipline=data.get("discipline"),
                date_from=date_from,
                date_to=date_to,
                bank_account_no=data.get("bank_account_no"),
                signature=request.FILES.get("signature"),
                applicability=data.get("applicability"),
                ta_supervisor="Department Admin",
                thesis_supervisor=thesis_supervisor_name,
                hod=_display_name(selected_hod_user),
                date_applied=date_applied,
                dean_status="approved",
                director_status="approved",
            )
            _log_assistantship_event(
                request.user,
                "assistantship_claim_submitted",
                claim,
                metadata={
                    "supervisor_assignment_id": supervisor_assignment.id,
                    "hod_user_id": selected_hod_user.id,
                },
            )
            _notify_users(
                _assistantship_submission_authorities(claim),
                "Assistantship claim pending supervisor review",
                f"Assistantship claim #{claim.id} from {claim.student_name} is awaiting your review.",
            )
            return Response(
                {"message": "Form submitted successfully.", "data": _claim_to_status_payload(claim)},
                status=status.HTTP_201_CREATED,
            )
        except Exception as exc:
            return Response(
                {"error": "Failed to submit assistantship form.", "details": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class GetAssistantshipStatus(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if _user_role(request.user) == "student" and not _is_pg_student(request.user):
            return Response(
                {"error": "Assistantship is available only for PG students."},
                status=status.HTTP_403_FORBIDDEN,
            )
        roll_no = request.data.get("roll_no")
        queryset = AssistantshipClaim.objects.filter(student=request.user)
        if roll_no:
            queryset = queryset.filter(roll_no=roll_no)
        payload = [_claim_to_status_payload(claim) for claim in queryset.order_by("-created_at")]
        return Response(payload, status=status.HTTP_200_OK)


class ReviewAssistantshipClaimView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, claim_id):
        if _user_role(request.user) == "student" and not _is_pg_student(request.user):
            return Response(
                {"error": "Assistantship is available only for PG students."},
                status=status.HTTP_403_FORBIDDEN,
            )
        claim = get_object_or_404(AssistantshipClaim, id=claim_id, student=request.user)
        if claim.student_reviewed:
            return Response({"error": "Claim is already marked as reviewed."}, status=status.HTTP_400_BAD_REQUEST)
        before = _claim_to_status_payload(claim)
        claim.student_reviewed = True
        claim.reviewed_at = timezone.now()
        claim.save(update_fields=["student_reviewed", "reviewed_at", "updated_at"])
        _log_assistantship_event(request.user, "assistantship_claim_reviewed", claim, before_data=before)

        create_notification(
            request.user,
            "Assistantship claim reviewed",
            f"You reviewed assistantship claim #{claim.id}.",
        )

        return Response(
            {"message": "Assistantship claim marked as reviewed", "data": _claim_to_status_payload(claim)},
            status=status.HTTP_200_OK,
        )


class WithdrawAssistantshipClaimView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, claim_id):
        if _user_role(request.user) == "student" and not _is_pg_student(request.user):
            return Response(
                {"error": "Assistantship is available only for PG students."},
                status=status.HTTP_403_FORBIDDEN,
            )
        claim = get_object_or_404(AssistantshipClaim, id=claim_id, student=request.user)
        if claim.student_withdrawn:
            return Response({"error": "Claim is already withdrawn."}, status=status.HTTP_400_BAD_REQUEST)

        if claim.overall_status in ["Approved", "Rejected", "Verified"]:
            return Response(
                {"error": "Only pending claims can be withdrawn."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        before = _claim_to_status_payload(claim)
        claim.student_withdrawn = True
        claim.withdrawn_at = timezone.now()
        claim.withdraw_reason = request.data.get("reason", "")
        claim.save(update_fields=["student_withdrawn", "withdrawn_at", "withdraw_reason", "updated_at"])
        _log_assistantship_event(request.user, "assistantship_claim_withdrawn", claim, before_data=before)

        create_notification(
            request.user,
            "Assistantship claim withdrawn",
            f"You withdrew assistantship claim #{claim.id}.",
        )

        return Response(
            {"message": "Assistantship claim withdrawn successfully", "data": _claim_to_status_payload(claim)},
            status=status.HTTP_200_OK,
        )


class VerifyAssistantshipClaimView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, claim_id):
        if _user_role(request.user) == "student" and not _is_pg_student(request.user):
            return Response(
                {"error": "Assistantship is available only for PG students."},
                status=status.HTTP_403_FORBIDDEN,
            )
        claim = get_object_or_404(AssistantshipClaim, id=claim_id, student=request.user)
        if claim.student_withdrawn:
            return Response({"error": "Withdrawn claims cannot be verified."}, status=status.HTTP_400_BAD_REQUEST)

        if claim.acadadmin_status != "approved":
            return Response(
                {"error": "Only disbursed claims can be verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        before = _claim_to_status_payload(claim)
        claim.student_verified = True
        claim.verified_at = timezone.now()
        claim.save(update_fields=["student_verified", "verified_at", "updated_at"])
        _log_assistantship_event(request.user, "assistantship_claim_verified", claim, before_data=before)

        create_notification(
            request.user,
            "Assistantship claim verified",
            f"You verified assistantship claim #{claim.id}.",
        )

        return Response(
            {"message": "Assistantship claim verified successfully", "data": _claim_to_status_payload(claim)},
            status=status.HTTP_200_OK,
        )


class _PendingStageFetchView(APIView):
    permission_classes = [IsAuthenticated]
    filters = {}
    field_name = None

    def get(self, request):
        claims = AssistantshipClaim.objects.filter(student_withdrawn=False, **self.filters).order_by("-created_at")
        payload = []
        for claim in claims:
            access_error = _assert_stage_access(request.user, claim, self.field_name)
            if access_error is None:
                payload.append(_claim_to_status_payload(claim))
        return Response(payload, status=status.HTTP_200_OK)


class _StageUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    field_name = None

    @transaction.atomic
    def post(self, request):
        approved_ids = request.data.get("approvedRequests", [])
        rejected_ids = request.data.get("rejectedRequests", [])
        if not isinstance(approved_ids, list) or not isinstance(rejected_ids, list):
            return Response(
                {"error": "approvedRequests and rejectedRequests must be arrays."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not self.field_name:
            return Response({"error": "Stage field not configured."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        duplicate_ids = set(approved_ids).intersection(rejected_ids)
        if duplicate_ids:
            return Response(
                {"error": f"Claim IDs cannot be both approved and rejected: {sorted(duplicate_ids)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        decision_map = {claim_id: "approved" for claim_id in approved_ids}
        decision_map.update({claim_id: "rejected" for claim_id in rejected_ids})
        if not decision_map:
            return Response(
                {"error": "At least one claim must be approved or rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        claims = {
            claim.id: claim
            for claim in AssistantshipClaim.objects.select_for_update().filter(id__in=decision_map.keys())
        }
        missing_ids = sorted(set(decision_map.keys()) - set(claims.keys()))
        if missing_ids:
            return Response(
                {"error": f"Invalid claim IDs: {missing_ids}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validation_errors = []
        for claim_id, decision in decision_map.items():
            claim = claims[claim_id]
            access_error = _assert_stage_access(request.user, claim, self.field_name)
            if access_error:
                validation_errors.append({"claim_id": claim_id, "error": access_error})
                continue
            transition_error = _validate_stage_transition(claim, self.field_name)
            if transition_error:
                validation_errors.append({"claim_id": claim_id, "error": transition_error})
                continue
            if decision not in {"approved", "rejected"}:
                validation_errors.append({"claim_id": claim_id, "error": "Invalid decision."})

        if validation_errors:
            return Response(
                {"error": "One or more claims failed validation.", "details": validation_errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        approved_count = 0
        rejected_count = 0
        stage_label = ASSISTANTSHIP_STAGE_CONFIG[self.field_name]["label"]
        for claim_id, decision in decision_map.items():
            claim = claims[claim_id]
            before = _claim_to_status_payload(claim)
            setattr(claim, self.field_name, decision)
            update_fields = [self.field_name, "updated_at"]
            if self.field_name == "acadadmin_status" and decision == "approved":
                claim.disbursed_at = timezone.now()
                claim.disbursed_by = request.user
                update_fields.extend(["disbursed_at", "disbursed_by"])
            claim.save(update_fields=update_fields)
            if decision == "approved":
                approved_count += 1
            else:
                rejected_count += 1
            stage_outcome = "stipend disbursed" if self.field_name == "acadadmin_status" and decision == "approved" else decision
            create_notification(
                claim.student,
                f"Assistantship {stage_label} {decision}",
                f"Your assistantship request was {stage_outcome} at {stage_label} stage.",
            )
            if decision == "approved":
                next_users = _assistantship_next_stage_users(claim, self.field_name)
                if next_users:
                    _notify_users(
                        next_users,
                        f"Assistantship claim pending {_assistantship_next_stage_label(self.field_name)} review",
                        f"Assistantship claim #{claim.id} from {claim.student_name} is awaiting your review.",
                    )
            _log_assistantship_event(
                request.user,
                f"assistantship_{self.field_name}_{decision}",
                claim,
                before_data=before,
                metadata={"stage": self.field_name, "decision": decision},
            )

        return Response(
            {
                "message": "Assistantship statuses updated successfully",
                "approved": approved_count,
                "rejected": rejected_count,
            },
            status=status.HTTP_200_OK,
        )


class TA_SupervisorFetchPendingAssistantshipRequests(_PendingStageFetchView):
    field_name = "ta_status"
    filters = {"id__in": []}


class TA_SupervisorUpdateAssistantshipStatus(_StageUpdateView):
    field_name = "ta_status"


class DeptAdminFetchPendingAssistantshipRequests(_PendingStageFetchView):
    field_name = "ta_status"
    filters = {"thesis_status": "approved", "ta_status": "pending"}


class DeptAdminUpdateAssistantshipStatus(_StageUpdateView):
    field_name = "ta_status"


class Ths_SupervisorFetchPendingAssistantshipRequests(_PendingStageFetchView):
    field_name = "thesis_status"
    filters = {"thesis_status": "pending"}


class Ths_SupervisorUpdateAssistantshipStatus(_StageUpdateView):
    field_name = "thesis_status"


class HODFetchPendingAssistantshipRequests(_PendingStageFetchView):
    field_name = "hod_status"
    filters = {"ta_status": "approved", "hod_status": "pending"}


class HODUpdateAssistantshipStatus(_StageUpdateView):
    field_name = "hod_status"


class AcadAdminFetchPendingAssistantshipRequests(_PendingStageFetchView):
    field_name = "acadadmin_status"
    filters = {"hod_status": "approved", "acadadmin_status": "pending"}


class AcadAdminUpdateAssistantshipStatus(_StageUpdateView):
    field_name = "acadadmin_status"


class DeanFetchPendingAssistantshipRequests(_PendingStageFetchView):
    field_name = "dean_status"
    filters = {"acadadmin_status": "approved", "dean_status": "pending"}


class DeanUpdateAssistantshipStatus(_StageUpdateView):
    field_name = "dean_status"


class DirectorFetchPendingAssistantshipRequests(_PendingStageFetchView):
    field_name = "director_status"
    filters = {"dean_status": "approved", "director_status": "pending"}


class DirectorUpdateAssistantshipStatus(_StageUpdateView):
    field_name = "director_status"


# ============================================================================
# PG ACADEMIC WORKFLOW
# ============================================================================


def _seminar_payload(seminar):
    ta_assignment = (
        TAAssignment.objects.filter(
            student_id=seminar.student_id,
            status=TAAssignment.STATUS_ACTIVE,
            created_at__gte=seminar.created_at,
        )
        .select_related("course", "faculty")
        .order_by("-created_at")
        .first()
    )
    supervisor_assignment = (
        SupervisorAssignment.objects.filter(
            student_id=seminar.student_id,
            is_primary=True,
            is_active=True,
            created_at__gte=seminar.created_at,
        )
        .select_related("supervisor")
        .order_by("-created_at")
        .first()
    )

    return {
        "id": seminar.id,
        "student_id": seminar.student_id,
        "student_name": seminar.student.get_full_name() or seminar.student.username,
        "topic": seminar.topic,
        "abstract": seminar.abstract,
        "status": seminar.status,
        "requested_slot_start": seminar.requested_slot_start,
        "requested_slot_end": seminar.requested_slot_end,
        "scheduled_start": seminar.scheduled_start,
        "scheduled_end": seminar.scheduled_end,
        "venue": seminar.venue,
        "panel_faculty": [
            {"id": user.id, "name": user.get_full_name() or user.username}
            for user in seminar.panel_faculty.all()
        ],
        "assigned_ta": {
            "id": ta_assignment.id,
            "faculty_id": ta_assignment.faculty_id,
            "faculty_name": ta_assignment.faculty.get_full_name() or ta_assignment.faculty.username if ta_assignment.faculty else "",
            "course_id": ta_assignment.course_id,
            "course_code": ta_assignment.course.course_code,
        }
        if ta_assignment
        else None,
        "assigned_supervisor": {
            "id": supervisor_assignment.id,
            "supervisor_id": supervisor_assignment.supervisor_id,
            "supervisor_name": supervisor_assignment.supervisor.get_full_name()
            or supervisor_assignment.supervisor.username,
        }
        if supervisor_assignment
        else None,
        "completed_at": seminar.completed_at,
        "evaluated_at": seminar.evaluated_at,
        "evaluation_notes": seminar.evaluation_notes,
    }


def _ta_payload(assignment):
    return {
        "id": assignment.id,
        "student_id": assignment.student_id,
        "student_name": assignment.student.get_full_name() or assignment.student.username,
        "course_id": assignment.course_id,
        "course_code": assignment.course.course_code,
        "faculty_id": assignment.faculty_id,
        "faculty_name": assignment.faculty.get_full_name() or assignment.faculty.username if assignment.faculty else "",
        "status": assignment.status,
        "start_date": assignment.start_date,
        "end_date": assignment.end_date,
        "remarks": assignment.remarks,
    }


def _supervisor_payload(assignment):
    return {
        "id": assignment.id,
        "student_id": assignment.student_id,
        "student_username": assignment.student.username,
        "student_name": assignment.student.get_full_name() or assignment.student.username,
        "student_roll_no": getattr(getattr(assignment.student, "profile", None), "roll_no", ""),
        "supervisor_id": assignment.supervisor_id,
        "supervisor_username": assignment.supervisor.username,
        "supervisor_name": assignment.supervisor.get_full_name() or assignment.supervisor.username,
        "assigned_by": _display_name(assignment.assigned_by) if assignment.assigned_by else "",
        "assigned_by_username": assignment.assigned_by.username if assignment.assigned_by else "",
        "is_primary": assignment.is_primary,
        "is_active": assignment.is_active,
        "started_at": assignment.started_at.isoformat() if assignment.started_at else None,
        "ended_at": assignment.ended_at.isoformat() if assignment.ended_at else None,
        "reason": assignment.reason,
    }


def _workflow_user_payload(user):
    active_ta = (
        TAAssignment.objects.filter(
            student=user,
            status__in=[TAAssignment.STATUS_ACTIVE, TAAssignment.STATUS_PENDING_APPROVAL],
        )
        .select_related("course", "faculty")
        .order_by("-created_at")
        .first()
    )
    active_supervisor = (
        SupervisorAssignment.objects.filter(student=user, is_primary=True, is_active=True)
        .select_related("supervisor")
        .order_by("-created_at")
        .first()
    )
    return {
        "id": user.id,
        "username": user.username,
        "name": _display_name(user),
        "email": user.email,
        "department": _profile_department(user),
        "role": _user_role(user),
        "roll_no": getattr(getattr(user, "profile", None), "roll_no", ""),
        "is_pg_student": bool(getattr(getattr(user, "profile", None), "is_pg_student", False)),
        "active_ta_assignment": (
            {
                "id": active_ta.id,
                "course_code": active_ta.course.course_code,
                "course_name": active_ta.course.course_name,
                "faculty_name": _display_name(active_ta.faculty) if active_ta.faculty else "",
                "faculty_username": active_ta.faculty.username if active_ta.faculty else "",
                "status": active_ta.status,
                "start_date": active_ta.start_date.isoformat(),
                "end_date": active_ta.end_date.isoformat(),
            }
            if active_ta
            else None
        ),
        "active_supervisor_assignment": (
            {
                "id": active_supervisor.id,
                "supervisor_name": _display_name(active_supervisor.supervisor),
                "supervisor_username": active_supervisor.supervisor.username,
                "started_at": active_supervisor.started_at.isoformat() if active_supervisor.started_at else None,
            }
            if active_supervisor
            else None
        ),
    }


def _workflow_course_payload(course):
    return {
        "id": course.id,
        "course_code": course.course_code,
        "course_name": course.course_name,
        "department": course.department,
        "semester": course.semester,
        "academic_year": course.academic_year,
    }


class PGWorkflowOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = _user_role(request.user)
        allowed_roles = GLOBAL_BACKEND_ROLES | {"hod"}
        if role not in allowed_roles:
            return Response(
                {"error": "Only workflow authorities can access seminar admin options."},
                status=status.HTTP_403_FORBIDDEN,
            )

        department = _profile_department(request.user)

        seminar_student_ids = Seminar.objects.order_by("-created_at").values_list("student_id", flat=True).distinct()
        seminar_students = User.objects.filter(
            id__in=seminar_student_ids,
            is_active=True,
            profile__role="student",
            profile__is_pg_student=True,
        ).select_related("profile").order_by("username")
        pg_students = User.objects.filter(
            is_active=True,
            profile__role="student",
            profile__is_pg_student=True,
        ).select_related("profile").order_by("username")
        courses = Course.objects.filter(is_active=True).order_by("course_code")

        if role == "hod" and department:
            seminar_students = seminar_students.filter(profile__department__iexact=department)
            pg_students = pg_students.filter(profile__department__iexact=department)
            courses = courses.filter(department__iexact=department)

        faculty_users = []
        for candidate in User.objects.filter(is_active=True).select_related("profile").order_by("username"):
            if _user_role(candidate) == "student":
                continue
            if role == "hod" and department and _profile_department(candidate).casefold() != department.casefold():
                continue
            faculty_users.append(candidate)

        return Response(
            {
                "students": [_workflow_user_payload(student) for student in seminar_students],
                "pg_students": [_workflow_user_payload(student) for student in pg_students],
                "faculty": [_workflow_user_payload(user) for user in faculty_users],
                "courses": [_workflow_course_payload(course) for course in courses],
            },
            status=status.HTTP_200_OK,
        )


class SeminarRequestCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if _user_role(request.user) == "student" and not _is_pg_student(request.user):
            return Response(
                {"error": "Seminar is available only for PG students."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            seminar = SeminarWorkflowService.request_seminar(request.user, request.data)
            _notify_users(
                _department_authorities(request.user, roles=("hod", "admin")),
                "Seminar request pending scheduling",
                f"{request.user.get_full_name() or request.user.username} submitted seminar topic '{seminar.topic}'.",
            )
            return Response(
                {"message": "Seminar requested successfully.", "data": _seminar_payload(seminar)},
                status=status.HTTP_201_CREATED,
            )
        except WorkflowServiceError as exc:
            return Response({"error": exc.message}, status=exc.status_code)


class SeminarWithdrawView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, seminar_id):
        try:
            seminar_data = SeminarWorkflowService.withdraw_seminar(request.user, seminar_id)
            return Response(
                {
                    "message": "Seminar request withdrawn successfully.",
                    "data": seminar_data,
                },
                status=status.HTTP_200_OK,
            )
        except WorkflowServiceError as exc:
            return Response({"error": exc.message}, status=exc.status_code)


class SeminarScheduleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, seminar_id):
        try:
            seminar = SeminarWorkflowService.schedule_seminar(request.user, seminar_id, request.data)
            return Response(
                {"message": "Seminar scheduled successfully.", "data": _seminar_payload(seminar)},
                status=status.HTTP_200_OK,
            )
        except WorkflowServiceError as exc:
            return Response({"error": exc.message}, status=exc.status_code)


class SeminarCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, seminar_id):
        try:
            seminar = SeminarWorkflowService.complete_seminar(request.user, seminar_id)
            return Response(
                {"message": "Seminar marked as completed.", "data": _seminar_payload(seminar)},
                status=status.HTTP_200_OK,
            )
        except WorkflowServiceError as exc:
            return Response({"error": exc.message}, status=exc.status_code)


class SeminarEvaluateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, seminar_id):
        try:
            seminar = SeminarWorkflowService.evaluate_seminar(
                request.user,
                seminar_id,
                notes=request.data.get("evaluation_notes", ""),
            )
            return Response(
                {"message": "Seminar evaluated successfully.", "data": _seminar_payload(seminar)},
                status=status.HTTP_200_OK,
            )
        except WorkflowServiceError as exc:
            return Response({"error": exc.message}, status=exc.status_code)


class SeminarListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Seminar.objects.none()
        role = _user_role(request.user)
        if role == "student":
            if not _is_pg_student(request.user):
                return Response(
                    {"error": "Seminar is available only for PG students."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            queryset = Seminar.objects.filter(student=request.user).prefetch_related("panel_faculty").order_by("-created_at")
        elif role in GLOBAL_BACKEND_ROLES:
            queryset = Seminar.objects.all().prefetch_related("panel_faculty").order_by("-created_at")
        elif role == "hod":
            queryset = Seminar.objects.filter(student__profile__department__iexact=_profile_department(request.user)).prefetch_related("panel_faculty").order_by("-created_at")
        elif role == "ta_supervisor":
            student_ids = TAAssignment.objects.filter(faculty=request.user).values_list("student_id", flat=True)
            queryset = Seminar.objects.filter(student_id__in=student_ids).prefetch_related("panel_faculty").order_by("-created_at")
        elif role == "thesis_supervisor":
            student_ids = SupervisorAssignment.objects.filter(supervisor=request.user, is_primary=True, is_active=True).values_list("student_id", flat=True)
            queryset = Seminar.objects.filter(student_id__in=student_ids).prefetch_related("panel_faculty").order_by("-created_at")
        data = [_seminar_payload(item) for item in queryset]
        return Response({"count": len(data), "data": data}, status=status.HTTP_200_OK)


class TAAssignmentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            assignment = TAAssignmentService.assign(request.user, request.data)
            return Response(
                {"message": "TA assignment created.", "data": _ta_payload(assignment)},
                status=status.HTTP_201_CREATED,
            )
        except WorkflowServiceError as exc:
            return Response({"error": exc.message}, status=exc.status_code)


class TAAssignmentHodReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        try:
            approve = bool(request.data.get("approve", False))
            assignment = TAAssignmentService.review_by_hod(
                request.user,
                assignment_id,
                approve=approve,
                remarks=request.data.get("remarks", ""),
            )
            return Response(
                {"message": "TA assignment review completed.", "data": _ta_payload(assignment)},
                status=status.HTTP_200_OK,
            )
        except WorkflowServiceError as exc:
            return Response({"error": exc.message}, status=exc.status_code)


class TAAssignmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = _user_role(request.user)
        if role == "student":
            queryset = TAAssignment.objects.filter(student=request.user).select_related("student", "course", "faculty").order_by("-created_at")
        elif role in GLOBAL_BACKEND_ROLES:
            queryset = TAAssignment.objects.select_related("student", "course", "faculty").order_by("-created_at")
        elif role == "hod":
            queryset = TAAssignment.objects.filter(student__profile__department__iexact=_profile_department(request.user)).select_related("student", "course", "faculty").order_by("-created_at")
        else:
            queryset = TAAssignment.objects.filter(faculty=request.user).select_related("student", "course", "faculty").order_by("-created_at")
        data = [_ta_payload(item) for item in queryset]
        return Response({"count": len(data), "data": data}, status=status.HTTP_200_OK)


class SupervisorAssignmentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            assignment = SupervisorAssignmentService.assign_or_reassign_primary(request.user, request.data)
            return Response(
                {"message": "Supervisor assignment completed.", "data": _supervisor_payload(assignment)},
                status=status.HTTP_201_CREATED,
            )
        except WorkflowServiceError as exc:
            return Response({"error": exc.message}, status=exc.status_code)


class SupervisorAssignmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = _user_role(request.user)
        student_id = request.query_params.get("student_id")
        if role == "student":
            queryset = SupervisorAssignment.objects.filter(student=request.user).select_related("student", "supervisor")
        elif role in GLOBAL_BACKEND_ROLES:
            queryset = SupervisorAssignment.objects.select_related("student", "supervisor")
        elif role == "hod":
            queryset = SupervisorAssignment.objects.filter(student__profile__department__iexact=_profile_department(request.user)).select_related("student", "supervisor")
        else:
            queryset = SupervisorAssignment.objects.filter(supervisor=request.user).select_related("student", "supervisor")
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        data = [_supervisor_payload(item) for item in queryset.order_by("-created_at")]
        return Response({"count": len(data), "data": data}, status=status.HTTP_200_OK)
