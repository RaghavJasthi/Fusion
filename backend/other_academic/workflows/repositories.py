from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from other_academic.models import Seminar, SupervisorAssignment, TAAssignment, WorkflowAuditLog


class SeminarRepository:
    @staticmethod
    def create_request(student, topic, abstract="", requested_slot_start=None, requested_slot_end=None):
        return Seminar.objects.create(
            student=student,
            topic=topic,
            abstract=abstract,
            requested_slot_start=requested_slot_start,
            requested_slot_end=requested_slot_end,
        )

    @staticmethod
    def get_for_update(seminar_id):
        return Seminar.objects.select_for_update().get(id=seminar_id)

    @staticmethod
    def venue_conflict_exists(venue, scheduled_start, scheduled_end, exclude_id=None):
        queryset = Seminar.objects.filter(
            venue=venue,
            status__in=[Seminar.STATUS_SCHEDULED, Seminar.STATUS_COMPLETED, Seminar.STATUS_EVALUATED],
            scheduled_start__lt=scheduled_end,
            scheduled_end__gt=scheduled_start,
        )
        if exclude_id:
            queryset = queryset.exclude(id=exclude_id)
        return queryset.exists()

    @staticmethod
    def faculty_conflict_exists(faculty_ids, scheduled_start, scheduled_end, exclude_id=None):
        queryset = Seminar.objects.filter(
            status__in=[Seminar.STATUS_SCHEDULED, Seminar.STATUS_COMPLETED, Seminar.STATUS_EVALUATED],
            scheduled_start__lt=scheduled_end,
            scheduled_end__gt=scheduled_start,
            panel_faculty__id__in=faculty_ids,
        )
        if exclude_id:
            queryset = queryset.exclude(id=exclude_id)
        return queryset.exists()

    @staticmethod
    def list_for_user(user):
        profile = getattr(user, "profile", None)
        role = getattr(profile, "role", "")
        if role == "student":
            return Seminar.objects.filter(student=user).prefetch_related("panel_faculty").order_by("-created_at")
        return Seminar.objects.all().prefetch_related("panel_faculty").order_by("-created_at")


class TARepository:
    @staticmethod
    def assignment_overlap_exists(student, start_date, end_date):
        return TAAssignment.objects.filter(
            student=student,
            status__in=[TAAssignment.STATUS_ACTIVE, TAAssignment.STATUS_PENDING_APPROVAL],
            start_date__lte=end_date,
            end_date__gte=start_date,
        ).exists()

    @staticmethod
    def create_assignment(**kwargs):
        return TAAssignment.objects.create(**kwargs)

    @staticmethod
    def get_for_update(assignment_id):
        return TAAssignment.objects.select_for_update().get(id=assignment_id)

    @staticmethod
    def faculty_exists_and_eligible(faculty_id):
        try:
            user = User.objects.get(id=faculty_id)
        except User.DoesNotExist:
            return None
        profile = getattr(user, "profile", None)
        if not profile or profile.role == "student":
            return None
        return user

    @staticmethod
    def list_for_user(user):
        profile = getattr(user, "profile", None)
        role = getattr(profile, "role", "")
        if role == "student":
            return TAAssignment.objects.filter(student=user).select_related("course", "faculty").order_by("-created_at")
        return TAAssignment.objects.select_related("student", "course", "faculty").order_by("-created_at")


class SupervisorRepository:
    @staticmethod
    def active_primary_for_student(student):
        return SupervisorAssignment.objects.filter(student=student, is_primary=True, is_active=True).first()

    @staticmethod
    def active_primary_count_for_supervisor(supervisor):
        return SupervisorAssignment.objects.filter(
            supervisor=supervisor,
            is_primary=True,
            is_active=True,
        ).count()

    @staticmethod
    def deactivate_assignment(assignment, reason=""):
        assignment.is_active = False
        assignment.ended_at = timezone.now()
        if reason:
            assignment.reason = reason
        assignment.save(update_fields=["is_active", "ended_at", "reason", "updated_at"])
        return assignment

    @staticmethod
    def create_primary_assignment(student, supervisor, assigned_by, reason=""):
        return SupervisorAssignment.objects.create(
            student=student,
            supervisor=supervisor,
            assigned_by=assigned_by,
            is_primary=True,
            is_active=True,
            reason=reason,
        )

    @staticmethod
    def supervisor_exists_and_eligible(supervisor_id):
        try:
            user = User.objects.get(id=supervisor_id)
        except User.DoesNotExist:
            return None
        profile = getattr(user, "profile", None)
        if not profile or profile.role == "student":
            return None
        return user

    @staticmethod
    def student_has_active_primary(student):
        return SupervisorAssignment.objects.filter(student=student, is_primary=True, is_active=True).exists()

    @staticmethod
    def list_for_user(user):
        profile = getattr(user, "profile", None)
        role = getattr(profile, "role", "")
        if role == "student":
            return SupervisorAssignment.objects.filter(student=user).select_related("supervisor").order_by("-created_at")
        return SupervisorAssignment.objects.select_related("student", "supervisor").order_by("-created_at")


class AuditLogRepository:
    @staticmethod
    def log(actor, action, entity_type, entity_id, before_data=None, after_data=None, metadata=None):
        return WorkflowAuditLog.objects.create(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_data=before_data or {},
            after_data=after_data or {},
            metadata=metadata or {},
        )
