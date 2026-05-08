# services.py

from rest_framework.exceptions import ValidationError
from .selectors import (
    get_leave_by_id,
    get_pg_leave_by_id,
    get_bonafide_by_id,
    get_assistantship_claim_by_id,
    get_no_dues_by_student,
)
from .models import LeaveFormTable, LeavePG


# =========================
# UG LEAVE SERVICES
# =========================

def approve_leave_service(leave_id):
    leave = get_leave_by_id(leave_id)

    if not leave:
        raise ValidationError("Leave request not found")

    if leave.status != "Pending":
        raise ValidationError("Only pending leave can be approved")

    leave.status = "Approved"
    leave.save()

    return leave


def reject_leave_service(leave_id):
    leave = get_leave_by_id(leave_id)

    if not leave:
        raise ValidationError("Leave request not found")

    if leave.status != "Pending":
        raise ValidationError("Only pending leave can be rejected")

    leave.status = "Rejected"
    leave.save()

    return leave


# =========================
# PG LEAVE SERVICES
# =========================

def approve_pg_leave_service(leave_id):
    leave = get_pg_leave_by_id(leave_id)

    if not leave:
        raise ValidationError("PG Leave not found")

    if leave.status != "Pending":
        raise ValidationError("Only pending leave can be approved")

    leave.status = "Approved"
    leave.save()

    return leave


# =========================
# BONAFIDE SERVICES
# =========================

def approve_bonafide_service(record_id):
    bonafide = get_bonafide_by_id(record_id)

    if not bonafide:
        raise ValidationError("Bonafide request not found")

    bonafide.approve = True
    bonafide.reject = False
    bonafide.save()

    return bonafide


# =========================
# ASSISTANTSHIP SERVICES
# =========================

def approve_assistantship_service(record_id):
    claim = get_assistantship_claim_by_id(record_id)

    if not claim:
        raise ValidationError("Assistantship claim not found")

    claim.HOD_approved = True
    claim.HOD_rejected = False
    claim.save()

    return claim


# =========================
# NO DUES SERVICES
# =========================

def validate_no_dues_clearance(extra_info):
    no_dues = get_no_dues_by_student(extra_info)

    if not no_dues:
        raise ValidationError("No dues record not found")

    if not no_dues.library_clear:
        raise ValidationError("Library dues not cleared")

    return no_dues