from datetime import datetime

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from fusion.fusionlab_roles import get_active_role_for_user
from other_academic.models import Seminar, TAAssignment
from other_academic.notifications import create_notification
from other_academic.workflows.repositories import (
    AuditLogRepository,
    SeminarRepository,
    SupervisorRepository,
    TARepository,
)


class WorkflowServiceError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _role_of(user):
    return get_active_role_for_user(user)


def _department_of(user):
    profile = getattr(user, "profile", None)
    return (getattr(profile, "department", "") or "").strip()


def _department_hods_for(user):
    department = _department_of(user)
    queryset = User.objects.filter(is_active=True, profile__role="hod").select_related("profile").order_by("id")
    if department:
        scoped = queryset.filter(profile__department__iexact=department)
        if scoped.exists():
            return list(scoped)
    return list(queryset)


def _assert_role(user, allowed_roles):
    role = _role_of(user)
    if role not in allowed_roles:
        raise WorkflowServiceError("Insufficient permissions.", status_code=403)


def _parse_required_datetime(value, field_name):
    dt = parse_datetime(value) if isinstance(value, str) else value
    if not isinstance(dt, datetime):
        raise WorkflowServiceError(f"Invalid datetime for {field_name}. Use ISO format.")
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _parse_required_date(value, field_name):
    parsed = parse_date(value) if isinstance(value, str) else value
    if parsed is None:
        raise WorkflowServiceError(f"Invalid date for {field_name}. Use YYYY-MM-DD.")
    return parsed


def _serialize_seminar(seminar):
    return {
        "id": seminar.id,
        "student_id": seminar.student_id,
        "topic": seminar.topic,
        "status": seminar.status,
        "scheduled_start": seminar.scheduled_start.isoformat() if seminar.scheduled_start else None,
        "scheduled_end": seminar.scheduled_end.isoformat() if seminar.scheduled_end else None,
        "venue": seminar.venue,
        "panel_faculty_ids": list(seminar.panel_faculty.values_list("id", flat=True)),
    }


def _serialize_ta(assignment):
    return {
        "id": assignment.id,
        "student_id": assignment.student_id,
        "course_id": assignment.course_id,
        "faculty_id": assignment.faculty_id,
        "faculty_name": assignment.faculty.get_full_name() or assignment.faculty.username if assignment.faculty else "",
        "status": assignment.status,
        "start_date": assignment.start_date.isoformat(),
        "end_date": assignment.end_date.isoformat(),
    }


def _serialize_supervisor(assignment):
    return {
        "id": assignment.id,
        "student_id": assignment.student_id,
        "supervisor_id": assignment.supervisor_id,
        "is_primary": assignment.is_primary,
        "is_active": assignment.is_active,
        "started_at": assignment.started_at.isoformat() if assignment.started_at else None,
        "ended_at": assignment.ended_at.isoformat() if assignment.ended_at else None,
    }


class SeminarWorkflowService:
    TRANSITIONS = {
        Seminar.STATUS_REQUESTED: [Seminar.STATUS_SCHEDULED],
        Seminar.STATUS_SCHEDULED: [Seminar.STATUS_COMPLETED],
        Seminar.STATUS_COMPLETED: [Seminar.STATUS_EVALUATED],
        Seminar.STATUS_EVALUATED: [],
    }

    @staticmethod
    @transaction.atomic
    def request_seminar(actor, data):
        _assert_role(actor, ["student"])
        topic = (data.get("topic") or "").strip()
        if not topic:
            raise WorkflowServiceError("Topic is required.")
        abstract = (data.get("abstract") or "").strip()
        requested_slot_start = data.get("requested_slot_start")
        requested_slot_end = data.get("requested_slot_end")
        start_dt = _parse_required_datetime(requested_slot_start, "requested_slot_start") if requested_slot_start else None
        end_dt = _parse_required_datetime(requested_slot_end, "requested_slot_end") if requested_slot_end else None
        if start_dt and end_dt and start_dt >= end_dt:
            raise WorkflowServiceError("requested_slot_end must be after requested_slot_start.")

        seminar = SeminarRepository.create_request(
            student=actor,
            topic=topic,
            abstract=abstract,
            requested_slot_start=start_dt,
            requested_slot_end=end_dt,
        )
        AuditLogRepository.log(
            actor=actor,
            action="seminar_requested",
            entity_type="Seminar",
            entity_id=seminar.id,
            before_data={},
            after_data=_serialize_seminar(seminar),
        )
        return seminar

    @staticmethod
    @transaction.atomic
    def withdraw_seminar(actor, seminar_id):
        _assert_role(actor, ["student"])
        seminar = SeminarRepository.get_for_update(seminar_id)
        if seminar.student_id != actor.id:
            raise WorkflowServiceError("You can withdraw only your own seminar request.", status_code=403)
        if seminar.status != Seminar.STATUS_REQUESTED:
            raise WorkflowServiceError("Only seminar requests in REQUESTED state can be withdrawn.")

        before = _serialize_seminar(seminar)
        seminar_data = {
            "topic": seminar.topic,
            "student_id": seminar.student_id,
        }
        seminar.delete()
        AuditLogRepository.log(
            actor=actor,
            action="seminar_withdrawn",
            entity_type="Seminar",
            entity_id=seminar_id,
            before_data=before,
            after_data={},
        )
        return seminar_data

    @staticmethod
    @transaction.atomic
    def schedule_seminar(actor, seminar_id, data):
        _assert_role(actor, ["admin"])
        seminar = SeminarRepository.get_for_update(seminar_id)
        before = _serialize_seminar(seminar)

        if Seminar.STATUS_SCHEDULED not in SeminarWorkflowService.TRANSITIONS.get(seminar.status, []):
            raise WorkflowServiceError("Seminar can only be scheduled from REQUESTED state.")

        scheduled_start = _parse_required_datetime(data.get("scheduled_start"), "scheduled_start")
        scheduled_end = _parse_required_datetime(data.get("scheduled_end"), "scheduled_end")
        if scheduled_start >= scheduled_end:
            raise WorkflowServiceError("scheduled_end must be after scheduled_start.")

        venue = (data.get("venue") or "").strip()
        if not venue:
            raise WorkflowServiceError("Venue is required.")

        faculty_ids = data.get("panel_faculty_ids", [])
        if not isinstance(faculty_ids, list) or not faculty_ids:
            raise WorkflowServiceError("panel_faculty_ids must be a non-empty list.")

        faculty = list(User.objects.filter(id__in=faculty_ids))
        if len(faculty) != len(set(faculty_ids)):
            raise WorkflowServiceError("Invalid faculty selected in panel.")
        for member in faculty:
            member_role = _role_of(member)
            if member_role == "student":
                raise WorkflowServiceError("Panel faculty cannot include student accounts.")

        if SeminarRepository.venue_conflict_exists(venue, scheduled_start, scheduled_end, exclude_id=seminar.id):
            raise WorkflowServiceError("Venue conflict: another seminar is already scheduled in this slot.")
        if SeminarRepository.faculty_conflict_exists(faculty_ids, scheduled_start, scheduled_end, exclude_id=seminar.id):
            raise WorkflowServiceError("Faculty conflict: at least one panel member is unavailable in this slot.")

        seminar.status = Seminar.STATUS_SCHEDULED
        seminar.scheduled_start = scheduled_start
        seminar.scheduled_end = scheduled_end
        seminar.venue = venue
        seminar.scheduled_by = actor
        seminar.save()
        seminar.panel_faculty.set(faculty)

        create_notification(
            seminar.student,
            "Seminar scheduled",
            f"Your seminar '{seminar.topic}' is scheduled on {scheduled_start} at {venue}.",
        )
        for member in faculty:
            create_notification(
                member,
                "Seminar panel assignment",
                f"You were assigned to panel for seminar '{seminar.topic}' on {scheduled_start}.",
            )

        AuditLogRepository.log(
            actor=actor,
            action="seminar_scheduled",
            entity_type="Seminar",
            entity_id=seminar.id,
            before_data=before,
            after_data=_serialize_seminar(seminar),
            metadata={"panel_faculty_ids": faculty_ids},
        )
        return seminar

    @staticmethod
    @transaction.atomic
    def complete_seminar(actor, seminar_id):
        _assert_role(actor, ["admin"])
        seminar = SeminarRepository.get_for_update(seminar_id)
        before = _serialize_seminar(seminar)
        if Seminar.STATUS_COMPLETED not in SeminarWorkflowService.TRANSITIONS.get(seminar.status, []):
            raise WorkflowServiceError("Seminar can only be completed from SCHEDULED state.")
        seminar.status = Seminar.STATUS_COMPLETED
        seminar.completed_at = timezone.now()
        seminar.save(update_fields=["status", "completed_at", "updated_at"])
        AuditLogRepository.log(
            actor=actor,
            action="seminar_completed",
            entity_type="Seminar",
            entity_id=seminar.id,
            before_data=before,
            after_data=_serialize_seminar(seminar),
        )
        return seminar

    @staticmethod
    @transaction.atomic
    def evaluate_seminar(actor, seminar_id, notes=""):
        _assert_role(actor, ["admin"])
        seminar = SeminarRepository.get_for_update(seminar_id)
        before = _serialize_seminar(seminar)
        if Seminar.STATUS_EVALUATED not in SeminarWorkflowService.TRANSITIONS.get(seminar.status, []):
            raise WorkflowServiceError("Seminar can only be evaluated from COMPLETED state.")
        if not SupervisorRepository.student_has_active_primary(seminar.student):
            raise WorkflowServiceError("Supervisor must be assigned before seminar evaluation.")

        seminar.status = Seminar.STATUS_EVALUATED
        seminar.evaluated_at = timezone.now()
        seminar.evaluation_notes = notes or ""
        seminar.save(update_fields=["status", "evaluated_at", "evaluation_notes", "updated_at"])
        create_notification(
            seminar.student,
            "Seminar evaluated",
            f"Your seminar '{seminar.topic}' has been evaluated.",
        )
        AuditLogRepository.log(
            actor=actor,
            action="seminar_evaluated",
            entity_type="Seminar",
            entity_id=seminar.id,
            before_data=before,
            after_data=_serialize_seminar(seminar),
        )
        return seminar


class TAAssignmentService:
    @staticmethod
    @transaction.atomic
    def assign(actor, data):
        _assert_role(actor, ["admin"])
        student_id = data.get("student_id")
        course_id = data.get("course_id")
        start_date = _parse_required_date(data.get("start_date"), "start_date")
        end_date = _parse_required_date(data.get("end_date"), "end_date")
        requires_hod_approval = bool(data.get("requires_hod_approval", False))
        remarks = data.get("remarks", "")

        if not all([student_id, course_id, start_date, end_date]):
            raise WorkflowServiceError("student_id, course_id, start_date and end_date are required.")

        try:
            student = User.objects.get(id=student_id)
        except User.DoesNotExist:
            raise WorkflowServiceError("Invalid student_id.")
        if _role_of(student) != "student":
            raise WorkflowServiceError("TA student must be a student user.")
        if not getattr(getattr(student, "profile", None), "is_pg_student", False):
            raise WorkflowServiceError("Student must be a PG student for TA assignment.")

        try:
            course_id = int(course_id)
        except (TypeError, ValueError):
            raise WorkflowServiceError("Invalid course_id.")

        from other_academic.models import Course

        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            raise WorkflowServiceError("Course not found.")

        student_department = _department_of(student)
        if student_department and course.department and student_department.casefold() != course.department.strip().casefold():
            raise WorkflowServiceError("Course must belong to the student's department.")

        if start_date < timezone.localdate():
            raise WorkflowServiceError("start_date cannot be in the past.")

        if start_date > end_date:
            raise WorkflowServiceError("end_date must be on or after start_date.")

        if TARepository.assignment_overlap_exists(student, start_date, end_date):
            raise WorkflowServiceError("Student already has an overlapping TA assignment.")

        status_value = TAAssignment.STATUS_PENDING_APPROVAL if requires_hod_approval else TAAssignment.STATUS_ACTIVE
        assignment = TARepository.create_assignment(
            student=student,
            course=course,
            faculty=None,
            assigned_by=actor,
            status=status_value,
            start_date=start_date,
            end_date=end_date,
            remarks=remarks,
        )

        AuditLogRepository.log(
            actor=actor,
            action="ta_assigned",
            entity_type="TAAssignment",
            entity_id=assignment.id,
            before_data={},
            after_data=_serialize_ta(assignment),
            metadata={"requires_hod_approval": requires_hod_approval},
        )

        if requires_hod_approval:
            for hod in _department_hods_for(student):
                create_notification(
                    hod,
                    "TA assignment pending approval",
                    f"TA assignment #{assignment.id} for {student.username} requires HoD approval.",
                )
        else:
            create_notification(student, "TA assigned", f"You were assigned as TA for {course.course_code}.")
        return assignment

    @staticmethod
    @transaction.atomic
    def review_by_hod(actor, assignment_id, approve=True, remarks=""):
        _assert_role(actor, ["hod"])
        assignment = TARepository.get_for_update(assignment_id)
        before = _serialize_ta(assignment)
        if assignment.status != TAAssignment.STATUS_PENDING_APPROVAL:
            raise WorkflowServiceError("Only pending TA assignments can be reviewed.")
        actor_department = _department_of(actor)
        student_department = _department_of(assignment.student)
        if actor_department and student_department and actor_department.casefold() != student_department.casefold():
            raise WorkflowServiceError("You can review only TA assignments from your department.", status_code=403)

        assignment.status = TAAssignment.STATUS_ACTIVE if approve else TAAssignment.STATUS_REJECTED
        assignment.hod_reviewed_by = actor
        assignment.hod_reviewed_at = timezone.now()
        assignment.remarks = remarks or assignment.remarks
        assignment.save(update_fields=["status", "hod_reviewed_by", "hod_reviewed_at", "remarks", "updated_at"])

        create_notification(
            assignment.student,
            "TA assignment approved" if approve else "TA assignment rejected",
            f"Your TA assignment for {assignment.course.course_code} was {'approved' if approve else 'rejected'} by HoD.",
        )
        AuditLogRepository.log(
            actor=actor,
            action="ta_reviewed_by_hod",
            entity_type="TAAssignment",
            entity_id=assignment.id,
            before_data=before,
            after_data=_serialize_ta(assignment),
            metadata={"approve": approve},
        )
        return assignment


class SupervisorAssignmentService:
    DEFAULT_WORKLOAD_LIMIT = 8

    @staticmethod
    @transaction.atomic
    def assign_or_reassign_primary(actor, data):
        _assert_role(actor, ["admin"])
        student_id = data.get("student_id")
        supervisor_id = data.get("supervisor_id")
        reason = data.get("reason", "")
        workload_limit = int(data.get("workload_limit", SupervisorAssignmentService.DEFAULT_WORKLOAD_LIMIT))

        if not student_id or not supervisor_id:
            raise WorkflowServiceError("student_id and supervisor_id are required.")

        try:
            student = User.objects.get(id=student_id)
        except User.DoesNotExist:
            raise WorkflowServiceError("Student not found.")
        if _role_of(student) != "student":
            raise WorkflowServiceError("Supervisor can only be assigned to student users.")
        if not getattr(getattr(student, "profile", None), "is_pg_student", False):
            raise WorkflowServiceError("Supervisor assignment is only for PG students.")

        supervisor = SupervisorRepository.supervisor_exists_and_eligible(supervisor_id)
        if not supervisor:
            raise WorkflowServiceError("Invalid supervisor_id.")

        student_department = _department_of(student)
        supervisor_department = _department_of(supervisor)
        if student_department and supervisor_department and student_department.casefold() != supervisor_department.casefold():
            raise WorkflowServiceError("Supervisor must be a faculty member of the student's department.")

        current_load = SupervisorRepository.active_primary_count_for_supervisor(supervisor)
        if current_load >= workload_limit:
            raise WorkflowServiceError("Supervisor workload limit exceeded.")

        existing_primary = SupervisorRepository.active_primary_for_student(student)
        before = _serialize_supervisor(existing_primary) if existing_primary else {}

        if existing_primary and existing_primary.supervisor_id == supervisor.id:
            raise WorkflowServiceError("This supervisor is already assigned as primary.")

        if existing_primary:
            SupervisorRepository.deactivate_assignment(existing_primary, reason="Reassigned primary supervisor")

        assignment = SupervisorRepository.create_primary_assignment(
            student=student,
            supervisor=supervisor,
            assigned_by=actor,
            reason=reason,
        )

        create_notification(student, "Supervisor assigned", f"{supervisor.get_full_name() or supervisor.username} assigned as your supervisor.")
        create_notification(
            supervisor,
            "New supervisee assigned",
            f"{student.get_full_name() or student.username} assigned to you as supervisee.",
        )
        AuditLogRepository.log(
            actor=actor,
            action="supervisor_assigned",
            entity_type="SupervisorAssignment",
            entity_id=assignment.id,
            before_data=before,
            after_data=_serialize_supervisor(assignment),
            metadata={"reassignment": bool(existing_primary)},
        )
        return assignment
