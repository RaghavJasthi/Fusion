# selectors.py

from .models import (
    LeaveFormTable,
    LeavePG,
    LeavePGUpdTable,
    GraduateSeminarFormTable,
    BonafideFormTableUpdated,
    AssistantshipClaimFormStatusUpd,
    NoDues,
)


# =========================
# LEAVE (UG)
# =========================

def get_leave_by_id(leave_id):
    return LeaveFormTable.objects.filter(id=leave_id).first()


def list_leaves_by_student(extra_info):
    return LeaveFormTable.objects.filter(roll_no=extra_info)


def list_all_leaves():
    return LeaveFormTable.objects.all()


# =========================
# LEAVE (PG)
# =========================

def get_pg_leave_by_id(leave_id):
    return LeavePG.objects.filter(id=leave_id).first()


def list_pg_leaves_by_student(extra_info):
    return LeavePG.objects.filter(roll_no=extra_info)


def list_all_pg_leaves():
    return LeavePG.objects.all()


# =========================
# PG LEAVE UPDATE TABLE
# =========================

def get_pg_leave_update_by_id(record_id):
    return LeavePGUpdTable.objects.filter(id=record_id).first()


def list_pg_leave_updates_by_student(extra_info):
    return LeavePGUpdTable.objects.filter(roll_no=extra_info)


# =========================
# GRADUATE SEMINAR
# =========================

def get_seminar_by_id(seminar_id):
    return GraduateSeminarFormTable.objects.filter(id=seminar_id).first()


def list_seminars_by_roll(roll_no):
    return GraduateSeminarFormTable.objects.filter(roll_no=roll_no)


def list_all_seminars():
    return GraduateSeminarFormTable.objects.all()


# =========================
# BONAFIDE
# =========================

def get_bonafide_by_id(record_id):
    return BonafideFormTableUpdated.objects.filter(id=record_id).first()


def list_bonafides_by_student(extra_info):
    return BonafideFormTableUpdated.objects.filter(roll_nos=extra_info)


def list_all_bonafides():
    return BonafideFormTableUpdated.objects.all()


# =========================
# ASSISTANTSHIP CLAIM
# =========================

def get_assistantship_claim_by_id(record_id):
    return AssistantshipClaimFormStatusUpd.objects.filter(id=record_id).first()


def list_assistantship_by_student(extra_info):
    return AssistantshipClaimFormStatusUpd.objects.filter(roll_no=extra_info)


def list_all_assistantship_claims():
    return AssistantshipClaimFormStatusUpd.objects.all()


# =========================
# NO DUES
# =========================

def get_no_dues_by_id(record_id):
    return NoDues.objects.filter(id=record_id).first()


def get_no_dues_by_student(extra_info):
    return NoDues.objects.filter(roll_no=extra_info).first()


def list_all_no_dues():
    return NoDues.objects.all()