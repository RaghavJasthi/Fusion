from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from fusion.fusionlab_roles import get_fusionlab_role_index, _role_sort_key
from other_academic.models import UserProfile


class Command(BaseCommand):
    help = "Import Other Academic role users from fusionlab.sql and create local login accounts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--default-password",
            default="fusion123",
            help="Password to assign to imported local users.",
        )
        parser.add_argument(
            "--include-students",
            action="store_true",
            help="Also import student-only users from fusionlab.sql.",
        )

    def handle(self, *args, **options):
        default_password = options["default_password"]
        include_students = options["include_students"]
        synced = 0

        for item in sorted(
            get_fusionlab_role_index().values(),
            key=lambda row: (_role_sort_key(row["module_roles"][0]) if row["module_roles"] else 999, row["username"]),
        ):
            if not item["module_roles"]:
                continue
            if not include_students and not any(role != "student" for role in item["module_roles"]):
                continue

            user = User.objects.filter(username=item["username"]).first()
            if not user:
                user = User(
                    id=int(item["user_id"]),
                    username=item["username"],
                )

            user.first_name = item.get("first_name", "")
            user.last_name = item.get("last_name", "")
            user.email = item.get("email", "")
            user.is_staff = any(role != "student" for role in item["module_roles"])
            user.is_active = True
            user.set_password(default_password)
            user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = item["module_roles"][0]
            profile.last_selected_role = item.get("last_selected_role") or item.get("available_designations", [item["module_roles"][0]])[0]
            profile.department = item.get("department", "")
            if item.get("user_type") == "student":
                profile.roll_no = item.get("extra_id", "")
            profile.is_pg_student = bool(profile.roll_no and len(profile.roll_no) > 2 and profile.roll_no[2].upper() in {"M", "P"})
            profile.save()

            synced += 1
            self.stdout.write(
                f"{user.username}: {', '.join(item.get('available_designations', item['module_roles']))}"
            )

        self.stdout.write(self.style.SUCCESS(f"Synced {synced} fusionlab users with module roles."))
