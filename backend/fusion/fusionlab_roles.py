from functools import lru_cache
from pathlib import Path
import re

from django.conf import settings


MODULE_ROLE_ORDER = [
    "director",
    "dean_academic",
    "acadadmin",
    "hod",
    "admin",
    "librarian",
    "hostel_warden",
    "mess_incharge",
    "lab_incharge",
    "mess_warden",
    "ta_supervisor",
    "thesis_supervisor",
    "student",
]

RAW_ROLE_ORDER = [
    "Director",
    "Dean Academic",
    "acadadmin",
    "dracad",
    "dept_admin",
    "deptadmin_cse",
    "deptadmin_ece",
    "deptadmin_me",
    "deptadmin_sm",
    "deptadmin_design",
    "deptadmin_ns",
    "deptadmin_liberalarts",
    "HOD (CSE)",
    "HOD (ECE)",
    "HOD (ME)",
    "HOD (NS)",
    "HOD (Design)",
    "HOD (Liberal Arts)",
    "mess_manager",
    "mess_warden",
    "student",
]

ROLE_MODULES = {
    "student": {"home": True, "other_academics": True},
    "hod": {"home": True, "other_academics": True},
    "admin": {"home": True, "other_academics": True},
    "acadadmin": {"home": True, "other_academics": True},
    "ta_supervisor": {"home": True, "other_academics": True},
    "thesis_supervisor": {"home": True, "other_academics": True},
    "dean_academic": {"home": True, "other_academics": True},
    "director": {"home": True, "other_academics": True},
    "librarian": {"home": True, "other_academics": True},
    "hostel_warden": {"home": True, "other_academics": True},
    "mess_incharge": {"home": True, "other_academics": True},
    "lab_incharge": {"home": True, "other_academics": True},
    "mess_warden": {"home": True, "other_academics": True},
}

DEPARTMENT_ALIASES = {
    "computer science and engineering": "CSE",
    "cse": "CSE",
    "electronics and communication engineering": "ECE",
    "ece": "ECE",
    "mechanical engineering": "ME",
    "me": "ME",
    "smart manufacturing": "SM",
    "sm": "SM",
    "design": "Design",
    "bachelor's of design": "Design",
    "natural science": "NS",
    "liberal arts": "Liberal Arts",
    "library": "Library",
    "security and central mess": "Mess",
    "mess committee": "Mess",
}

DEPTADMIN_TO_DEPARTMENT = {
    "deptadmin_cse": "CSE",
    "deptadmin_ece": "ECE",
    "deptadmin_me": "ME",
    "deptadmin_sm": "SM",
    "deptadmin_design": "Design",
    "deptadmin_ns": "NS",
    "deptadmin_liberalarts": "Liberal Arts",
    "dept_admin": "CSE",
}


def _normalize(value):
    return (value or "").strip()


def _casefold(value):
    return _normalize(value).casefold()


def _role_sort_key(role):
    try:
        return MODULE_ROLE_ORDER.index(role)
    except ValueError:
        return len(MODULE_ROLE_ORDER)


def _sort_roles(roles):
    return sorted(set(filter(None, roles)), key=_role_sort_key)


def _raw_role_sort_key(role):
    try:
        return RAW_ROLE_ORDER.index(role)
    except ValueError:
        return len(RAW_ROLE_ORDER)


def _sort_raw_roles(roles):
    return sorted(set(filter(None, roles)), key=_raw_role_sort_key)


def _sql_path():
    return Path(settings.BASE_DIR) / "fusionlab.sql"


def _extract_copy_blocks():
    signatures = {
        "auth_user": "COPY public.auth_user (id, password, last_login, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined) FROM stdin;",
        "globals_designation": "COPY public.globals_designation (id, name, full_name, type, basic, category) FROM stdin;",
        "globals_extrainfo": "COPY public.globals_extrainfo (id, title, sex, date_of_birth, user_status, address, phone_no, user_type, profile_picture, about_me, date_modified, department_id, user_id, last_selected_role) FROM stdin;",
        "globals_holdsdesignation": "COPY public.globals_holdsdesignation (id, held_at, designation_id, user_id, working_id) FROM stdin;",
        "globals_departmentinfo": "COPY public.globals_departmentinfo (id, name) FROM stdin;",
    }
    blocks = {key: [] for key in signatures}
    current_key = None

    with _sql_path().open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if current_key:
                if line == r"\.":
                    current_key = None
                elif line:
                    blocks[current_key].append(line.split("\t"))
                continue

            for key, signature in signatures.items():
                if line == signature:
                    current_key = key
                    break

    return blocks


def _normalize_department(value):
    normalized = DEPARTMENT_ALIASES.get(_casefold(value))
    return normalized or _normalize(value)


def map_designation_to_module_roles(name, full_name="", department_name=""):
    raw_name = _normalize(name)
    folded_name = raw_name.casefold()
    folded_full_name = _casefold(full_name)
    folded_department = _casefold(department_name)

    roles = []
    if raw_name == "student":
        roles.append("student")
    if raw_name.startswith("HOD ("):
        roles.append("hod")
    if raw_name in {"dept_admin", "academic_user"} or raw_name.startswith("deptadmin_"):
        roles.append("admin")
    if raw_name in {"acadadmin", "studentacadadmin", "dracad"}:
        roles.append("acadadmin")
    if raw_name == "Dean Academic":
        roles.append("dean_academic")
    if raw_name == "Director":
        roles.append("director")
    if raw_name == "mess_manager":
        roles.append("mess_incharge")
    if "lab" in folded_name or "lab" in folded_full_name or folded_department == "lab":
        roles.append("lab_incharge")
    if raw_name == "mess_warden":
        roles.append("mess_warden")
    if folded_name.endswith("warden") or raw_name == "Hostel_admin":
        roles.append("hostel_warden")
    if "librar" in folded_name or "librar" in folded_full_name or folded_department == "library":
        roles.append("librarian")
    return _sort_roles(roles)


def map_selected_role_to_module_role(selected_role, fallback_roles=None):
    raw_role = _normalize(selected_role)
    fallback_roles = fallback_roles or []
    if raw_role in MODULE_ROLE_ORDER:
        return raw_role
    mapped = map_designation_to_module_roles(raw_role)
    if mapped:
        return mapped[0]
    if fallback_roles:
        return _sort_roles(fallback_roles)[0]
    return "admin" if raw_role else "student"


def _derive_department(designation_names, fallback_department=""):
    for designation_name in designation_names:
        if designation_name.startswith("HOD (") and designation_name.endswith(")"):
            return designation_name[5:-1].strip()
        if designation_name in DEPTADMIN_TO_DEPARTMENT:
            return DEPTADMIN_TO_DEPARTMENT[designation_name]
        if designation_name == "mess_manager":
            return "Mess"
        if "lab" in designation_name.casefold():
            return "Lab"
        if designation_name == "mess_warden":
            return "Mess"
        if designation_name.endswith("warden") or designation_name == "Hostel_admin":
            return "Hostel"
        if "librar" in designation_name.casefold():
            return "Library"
    return _normalize_department(fallback_department)


def _map_selected_role(raw_role_name, designation_lookup, fallback_roles):
    raw_role = _normalize(raw_role_name)
    if not raw_role:
        return ""
    if raw_role in fallback_roles:
        return raw_role

    designation = designation_lookup.get(raw_role)
    if designation:
        mapped = map_designation_to_module_roles(
            designation["name"],
            designation.get("full_name", ""),
            designation.get("department_name", ""),
        )
        if mapped:
            return mapped[0]
    return ""


@lru_cache(maxsize=1)
def get_fusionlab_role_index():
    if not _sql_path().exists():
        return {}

    blocks = _extract_copy_blocks()
    departments = {row[0]: row[1] for row in blocks["globals_departmentinfo"]}

    designations = {}
    for row in blocks["globals_designation"]:
        department_name = departments.get(row[2], "")
        designations[row[0]] = {
            "id": row[0],
            "name": row[1],
            "full_name": row[2],
            "type": row[3],
            "basic": row[4] == "t",
            "category": row[5],
            "department_name": department_name,
        }

    auth_users = {
        row[0]: {
            "id": row[0],
            "password": row[1],
            "username": row[4],
            "first_name": row[5],
            "last_name": row[6],
            "email": row[7],
            "is_staff": row[8] == "t",
            "is_active": row[9] == "t",
        }
        for row in blocks["auth_user"]
    }

    extrainfo = {
        row[12]: {
            "extra_id": row[0],
            "title": row[1],
            "sex": row[2],
            "department_name": departments.get(row[11], ""),
            "user_type": row[7],
            "last_selected_role": row[13],
        }
        for row in blocks["globals_extrainfo"]
    }

    designation_names_by_user = {}
    for row in blocks["globals_holdsdesignation"]:
        designation = designations.get(row[2])
        if not designation:
            continue
        designation_names_by_user.setdefault(row[3], []).append(designation["name"])

    users = {}
    for user_id, user_info in auth_users.items():
        raw_designations = designation_names_by_user.get(user_id, [])
        extra_info = extrainfo.get(user_id, {})
        mapped_roles = []
        for designation_name in raw_designations:
            designation = next(
                (item for item in designations.values() if item["name"] == designation_name),
                None,
            )
            mapped_roles.extend(
                map_designation_to_module_roles(
                    designation_name,
                    designation.get("full_name", "") if designation else "",
                    extra_info.get("department_name", ""),
                )
            )
        mapped_roles = _sort_roles(mapped_roles)
        if extra_info.get("user_type") == "student":
            mapped_roles = _sort_roles(mapped_roles + ["student"])
        derived_department = _derive_department(raw_designations, extra_info.get("department_name", ""))
        active_role = _map_selected_role(
            extra_info.get("last_selected_role", ""),
            {item["name"]: item for item in designations.values()},
            mapped_roles,
        )
        available_designations = _sort_raw_roles(raw_designations)
        if extra_info.get("user_type") == "student" or "student" in mapped_roles:
            available_designations = _sort_raw_roles(available_designations + ["student"])
        if not available_designations:
            available_designations = _sort_raw_roles(mapped_roles)
        if not active_role and available_designations:
            active_role = available_designations[0]
        users[user_info["username"]] = {
            "user_id": user_id,
            "username": user_info["username"],
            "first_name": user_info["first_name"],
            "last_name": user_info["last_name"],
            "email": user_info["email"],
            "password_hash": user_info["password"],
            "is_staff": user_info["is_staff"],
            "is_active": user_info["is_active"],
            "extra_id": extra_info.get("extra_id", ""),
            "user_type": extra_info.get("user_type", ""),
            "department": derived_department,
            "raw_designations": sorted(set(raw_designations)),
            "available_designations": available_designations,
            "module_roles": mapped_roles,
            "last_selected_role": active_role,
        }
    return users


def get_sql_person_for_username(username):
    return get_fusionlab_role_index().get(username)


def get_role_context_for_user(user):
    from other_academic.models import UserProfile

    sql_person = get_sql_person_for_username(user.username) or {}
    profile = getattr(user, "profile", None)

    available_roles = []
    available_roles.extend(sql_person.get("available_designations", []))
    if profile and profile.last_selected_role:
        available_roles.append(profile.last_selected_role)
    if profile and profile.role and not sql_person:
        available_roles.append(profile.role)
    if not available_roles:
        available_roles.append("admin" if user.is_staff else "student")
    available_roles = _sort_raw_roles(available_roles)

    active_designation = ""
    if profile and profile.last_selected_role in available_roles:
        active_designation = profile.last_selected_role
    elif sql_person.get("last_selected_role") in available_roles:
        active_designation = sql_person["last_selected_role"]
    elif profile and profile.role in available_roles:
        active_designation = profile.role
    else:
        active_designation = available_roles[0]

    effective_module_role = map_selected_role_to_module_role(
        active_designation,
        sql_person.get("module_roles", []) + ([profile.role] if profile and profile.role else []),
    )

    roll_no = ""
    if profile and profile.roll_no:
        roll_no = profile.roll_no
    elif sql_person.get("user_type") == "student":
        roll_no = sql_person.get("extra_id", "")

    department = ""
    if profile and profile.department:
        department = profile.department
    else:
        department = sql_person.get("department", "")

    name = user.get_full_name().strip()
    if not name:
        name = f"{sql_person.get('first_name', '')} {sql_person.get('last_name', '')}".strip()
    if not name:
        name = user.username

    return {
        "name": name,
        "roll_no": roll_no,
        "available_roles": available_roles,
        "active_role": active_designation,
        "effective_module_role": effective_module_role,
        "department": department,
        "sql_person": sql_person,
    }


def get_active_role_for_user(user):
    return get_role_context_for_user(user)["effective_module_role"]


def get_accessible_modules_for_roles(roles):
    return {
        role: ROLE_MODULES.get(role, {"home": True, "other_academics": True})
        for role in roles
    }


def sync_user_profile_from_role_context(user, context=None):
    from other_academic.models import UserProfile

    context = context or get_role_context_for_user(user)
    profile, _ = UserProfile.objects.get_or_create(user=user)

    if context["effective_module_role"]:
        profile.role = context["effective_module_role"]
    if context["active_role"]:
        profile.last_selected_role = context["active_role"]
    if context["department"]:
        profile.department = context["department"]
    if context["roll_no"] and not profile.roll_no:
        profile.roll_no = context["roll_no"]
    if profile.roll_no and re.match(r"^\d{2}[A-Z]", profile.roll_no):
        profile.is_pg_student = bool(len(profile.roll_no) > 2 and profile.roll_no[2].upper() in {"M", "P"})
    profile.save()
    return profile
