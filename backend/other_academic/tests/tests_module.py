from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from other_academic.models import (
    AssistantshipClaim,
    BonafideRequest,
    Leave,
    NoDuesEntry,
    NoDuesRequest,
    Notification,
    Seminar,
    UserProfile,
    WorkflowAuditLog,
)


class NoDuesRoleAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.student = User.objects.create_user(username="student_nd", password="pass123")
        UserProfile.objects.create(user=self.student, role="student", department="CSE", roll_no="23BCS999")

        self.librarian = User.objects.create_user(username="librarian_nd", password="pass123")
        UserProfile.objects.create(user=self.librarian, role="librarian", department="Library")

        self.hostel_warden = User.objects.create_user(username="warden_nd", password="pass123")
        UserProfile.objects.create(user=self.hostel_warden, role="hostel_warden", department="Hostel")

        self.mess_incharge = User.objects.create_user(username="mess_nd", password="pass123")
        UserProfile.objects.create(user=self.mess_incharge, role="mess_incharge", department="Mess")

        self.lab_incharge = User.objects.create_user(username="lab_nd", password="pass123")
        UserProfile.objects.create(user=self.lab_incharge, role="lab_incharge", department="Lab")

        self.acad_admin = User.objects.create_user(username="acad_nd", password="pass123")
        UserProfile.objects.create(user=self.acad_admin, role="acadadmin", department="Academic")

        self.request_obj = NoDuesRequest.objects.create(
            student=self.student,
            remarks="Need final clearance",
            domain_approvals={
                "mess_incharge": {"status": "pending", "actor": None, "remarks": "", "timestamp": None},
                "hostel_warden": {"status": "pending", "actor": None, "remarks": "", "timestamp": None},
                "librarian": {"status": "pending", "actor": None, "remarks": "", "timestamp": None},
                "lab_incharge": {"status": "pending", "actor": None, "remarks": "", "timestamp": None},
            },
        )
        NoDuesEntry.objects.create(
            student=self.student,
            category="Library",
            description="Pending library book return",
            amount="150.00",
            is_cleared=False,
        )
        NoDuesEntry.objects.create(
            student=self.student,
            category="Hostel",
            description="Hostel room handover due",
            amount="250.00",
            is_cleared=False,
        )
        NoDuesEntry.objects.create(
            student=self.student,
            category="Mess",
            description="Mess bill pending",
            amount="300.00",
            is_cleared=False,
        )
        NoDuesEntry.objects.create(
            student=self.student,
            category="Lab",
            description="Lab equipment clearance pending",
            amount="200.00",
            is_cleared=False,
        )

    def test_no_dues_review_list_is_available_to_librarian(self):
        self.client.force_authenticate(self.librarian)
        response = self.client.get("/otheracademic/api/no-dues/requests/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["visibility_scope"], "librarian")
        self.assertEqual(len(response.data["data"][0]["visible_entries"]), 1)
        self.assertEqual(response.data["data"][0]["visible_entries"][0]["category"], "Library")

    def test_no_dues_approve_is_available_to_hostel_warden(self):
        self.client.force_authenticate(self.hostel_warden)
        response = self.client.post(
            f"/otheracademic/api/no-dues/requests/{self.request_obj.id}/approve/",
            {"remarks": "Hostel clearance approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, "in_progress")
        self.assertEqual(self.request_obj.reviewed_by, self.hostel_warden)
        hostel_entry = NoDuesEntry.objects.get(student=self.student, category="Hostel")
        library_entry = NoDuesEntry.objects.get(student=self.student, category="Library")
        mess_entry = NoDuesEntry.objects.get(student=self.student, category="Mess")
        self.assertTrue(hostel_entry.is_cleared)
        self.assertFalse(library_entry.is_cleared)
        self.assertFalse(mess_entry.is_cleared)

    def test_domain_reviewer_can_reject_no_dues_request(self):
        self.client.force_authenticate(self.mess_incharge)
        response = self.client.post(
            f"/otheracademic/api/no-dues/requests/{self.request_obj.id}/reject/",
            {"remarks": "Pending mess dues"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, "rejected")
        self.assertEqual(self.request_obj.reviewed_by, self.mess_incharge)
        self.assertEqual(self.request_obj.domain_approvals["mess_incharge"]["status"], "rejected")

    def test_student_cannot_review_no_dues_requests(self):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            f"/otheracademic/api/no-dues/requests/{self.request_obj.id}/approve/",
            {"remarks": "Should not be allowed"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_role_cannot_see_unrelated_no_dues_entries(self):
        self.client.force_authenticate(self.hostel_warden)
        response = self.client.get("/otheracademic/api/no-dues/requests/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 1)
        visible_entries = response.data["data"][0]["visible_entries"]
        self.assertEqual(len(visible_entries), 1)
        self.assertEqual(visible_entries[0]["category"], "Hostel")

    def test_lab_incharge_can_review_no_dues_request(self):
        other_student = User.objects.create_user(username="student_nd2", password="pass123")
        UserProfile.objects.create(user=other_student, role="student", department="CSE")
        unrelated_request = NoDuesRequest.objects.create(
            student=other_student,
            remarks="Only library item",
            domain_approvals={
                "mess_incharge": {"status": "pending", "actor": None, "remarks": "", "timestamp": None},
                "hostel_warden": {"status": "pending", "actor": None, "remarks": "", "timestamp": None},
                "librarian": {"status": "pending", "actor": None, "remarks": "", "timestamp": None},
                "lab_incharge": {"status": "pending", "actor": None, "remarks": "", "timestamp": None},
            },
        )
        NoDuesEntry.objects.create(
            student=other_student,
            category="Lab",
            description="Lab clearance pending",
            amount="100.00",
            is_cleared=False,
        )

        self.client.force_authenticate(self.lab_incharge)
        response = self.client.post(
            f"/otheracademic/api/no-dues/requests/{unrelated_request.id}/approve/",
            {"remarks": "Lab cleared"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        unrelated_request.refresh_from_db()
        self.assertEqual(unrelated_request.domain_approvals["lab_incharge"]["status"], "approved")

    def test_librarian_can_create_no_dues_entry_for_student(self):
        self.client.force_authenticate(self.librarian)
        response = self.client.post(
            "/otheracademic/api/no-dues/entries/",
            {
                "student": self.student.username,
                "description": "Library fine pending",
                "amount": "450.00",
                "is_cleared": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        entry = NoDuesEntry.objects.filter(student=self.student, category__iexact="Library").order_by("-updated_at").first()
        self.assertIsNotNone(entry)
        self.assertEqual(str(entry.amount), "450.00")
        self.assertEqual(entry.description, "Library fine pending")

    def test_hostel_warden_fetches_only_hostel_entries_for_student(self):
        self.client.force_authenticate(self.hostel_warden)
        response = self.client.get(
            "/otheracademic/api/no-dues/entries/",
            {"student": self.student.username},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["default_category"], "Hostel")
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["category"], "Hostel")

    def test_mess_incharge_can_update_only_mess_entries(self):
        mess_entry = NoDuesEntry.objects.filter(student=self.student, category="Mess").first()
        self.client.force_authenticate(self.mess_incharge)
        response = self.client.post(
            "/otheracademic/api/no-dues/entries/",
            {
                "student": self.student.username,
                "entry_id": mess_entry.id,
                "description": "Mess dues cleared",
                "amount": "0.00",
                "is_cleared": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        mess_entry.refresh_from_db()
        self.assertTrue(mess_entry.is_cleared)
        self.assertEqual(str(mess_entry.amount), "0.00")

    def test_student_cannot_manage_no_dues_entries(self):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            "/otheracademic/api/no-dues/entries/",
            {
                "student": self.student.username,
                "category": "Library",
                "description": "Should fail",
                "amount": "10.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_acad_admin_can_finalize_no_dues_only_after_all_entries_cleared(self):
        self.client.force_authenticate(self.acad_admin)
        response = self.client.post(
            f"/otheracademic/api/no-dues/requests/{self.request_obj.id}/approve/",
            {"remarks": "Trying early finalization"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("mess, hostel, librarian, and lab approvals", response.data["error"])

        NoDuesEntry.objects.filter(student=self.student).update(is_cleared=True)
        self.request_obj.domain_approvals = {
            "mess_incharge": {"status": "approved", "actor": self.mess_incharge.username, "remarks": "", "timestamp": timezone.now().isoformat()},
            "hostel_warden": {"status": "approved", "actor": self.hostel_warden.username, "remarks": "", "timestamp": timezone.now().isoformat()},
            "librarian": {"status": "approved", "actor": self.librarian.username, "remarks": "", "timestamp": timezone.now().isoformat()},
            "lab_incharge": {"status": "approved", "actor": self.lab_incharge.username, "remarks": "", "timestamp": timezone.now().isoformat()},
        }
        self.request_obj.save(update_fields=["domain_approvals"])
        response = self.client.post(
            f"/otheracademic/api/no-dues/requests/{self.request_obj.id}/approve/",
            {"remarks": "All domains cleared"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, "approved")
        self.assertEqual(self.request_obj.reviewed_by, self.acad_admin)


class ConcernedAuthorityRoutingTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.student = User.objects.create_user(username="student_cse", password="pass123", first_name="CSE", last_name="Student")
        UserProfile.objects.create(user=self.student, role="student", department="CSE", roll_no="23BCS999")

        self.cse_hod = User.objects.create_user(username="hod_cse", password="pass123")
        UserProfile.objects.create(user=self.cse_hod, role="hod", department="CSE")

        self.ece_hod = User.objects.create_user(username="hod_ece", password="pass123")
        UserProfile.objects.create(user=self.ece_hod, role="hod", department="ECE")

        self.acad_admin = User.objects.create_user(username="acad_bon", password="pass123")
        UserProfile.objects.create(user=self.acad_admin, role="acadadmin", department="Academic")

    def test_leave_request_notifies_only_same_department_hod(self):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            "/otheracademic/api/leave-form-submit/",
            {
                "student_name": "CSE Student",
                "roll_no": "23BCS999",
                "date_from": "2026-04-22",
                "date_to": "2026-04-23",
                "leave_type": "medical",
                "address": "Campus Hostel",
                "purpose": "Medical rest",
                "hod_credential": "",
                "mobile_number": "9999999999",
                "parents_mobile": "8888888888",
                "mobile_during_leave": "9999999999",
                "semester": 6,
                "academic_year": "2026-27",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Notification.objects.filter(user=self.cse_hod, verb="Leave request pending review").exists())
        self.assertFalse(Notification.objects.filter(user=self.ece_hod, verb="Leave request pending review").exists())

    def test_bonafide_request_notifies_acad_admin_not_hod(self):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            "/otheracademic/api/bonafide/request/",
            {
                "certificate_type": "passport",
                "purpose": "Visa process",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(BonafideRequest.objects.count(), 1)
        self.assertTrue(Notification.objects.filter(user=self.acad_admin, verb="Bonafide request pending review").exists())
        self.assertFalse(Notification.objects.filter(user=self.cse_hod, verb="Bonafide request pending review").exists())
        self.assertFalse(Notification.objects.filter(user=self.ece_hod, verb="Bonafide request pending review").exists())

    def test_student_can_withdraw_pending_bonafide_request(self):
        bonafide = BonafideRequest.objects.create(
            student=self.student,
            certificate_type="passport",
            purpose="Visa",
        )
        self.client.force_authenticate(self.student)
        response = self.client.post(f"/otheracademic/api/bonafide/requests/{bonafide.id}/withdraw/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        bonafide.refresh_from_db()
        self.assertEqual(bonafide.status, "withdrawn")

    def test_non_student_cannot_submit_bonafide_request(self):
        self.client.force_authenticate(self.cse_hod)
        response = self.client.post(
            "/otheracademic/api/bonafide/request/",
            {
                "certificate_type": "passport",
                "purpose": "Role should be blocked",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Only students", response.data["error"])

    def test_non_hod_cannot_view_or_update_leave_requests(self):
        leave = Leave.objects.create(
            user=self.student,
            student_name="CSE Student",
            roll_no="23BCS999",
            date_from="2026-04-20",
            date_to="2026-04-21",
            leave_type="medical",
            address="Campus Hostel",
            purpose="Medical rest",
            mobile_number="9999999999",
            parents_mobile="8888888888",
            mobile_during_leave="9999999999",
            status="pending",
        )

        self.client.force_authenticate(self.acad_admin)
        fetch_response = self.client.get("/otheracademic/api/fetch-pending-leaves/")
        self.assertEqual(fetch_response.status_code, 403)
        self.assertIn("Only HoD", fetch_response.data["error"])

        update_response = self.client.post(
            "/otheracademic/api/update-leave-status/",
            {"approvedLeaves": [leave.id], "rejectedLeaves": []},
            format="json",
        )
        self.assertEqual(update_response.status_code, 403)
        self.assertIn("Only HoD", update_response.data["error"])

    def test_leave_defaults_are_derived_from_student_profile_and_department_hod(self):
        self.client.force_authenticate(self.student)
        response = self.client.get("/otheracademic/api/leave-form-defaults/")

        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertEqual(data["roll_no"], "23BCS999")
        self.assertEqual(data["hod_credential"], "hod_cse")
        self.assertEqual(data["academic_year"], "2025-26")
        self.assertEqual(data["semester"], 6)

    def test_leave_submission_rejects_past_dates(self):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            "/otheracademic/api/leave-form-submit/",
            {
                "student_name": "Tampered Name",
                "roll_no": "WRONG",
                "date_from": "2026-04-10",
                "date_to": "2026-04-11",
                "leave_type": "medical",
                "address": "Campus Hostel",
                "purpose": "Medical rest",
                "mobile_number": "9999999999",
                "parents_mobile": "8888888888",
                "mobile_during_leave": "9999999999",
                "semester": 1,
                "academic_year": "2024-25",
                "hod_credential": "wrong hod",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("past date", str(response.data).lower())

    def test_leave_submission_rejects_overlapping_leave_dates(self):
        Leave.objects.create(
            user=self.student,
            student_name="CSE Student",
            roll_no="23BCS999",
            date_from="2026-04-22",
            date_to="2026-04-24",
            leave_type="medical",
            address="Campus Hostel",
            purpose="Medical rest",
            mobile_number="9999999999",
            parents_mobile="8888888888",
            mobile_during_leave="9999999999",
            status="pending",
        )
        self.client.force_authenticate(self.student)
        response = self.client.post(
            "/otheracademic/api/leave-form-submit/",
            {
                "student_name": "Tampered Name",
                "roll_no": "WRONG",
                "date_from": "2026-04-23",
                "date_to": "2026-04-25",
                "leave_type": "medical",
                "address": "Campus Hostel",
                "purpose": "Medical rest",
                "mobile_number": "9999999999",
                "parents_mobile": "8888888888",
                "mobile_during_leave": "9999999999",
                "semester": 1,
                "academic_year": "2024-25",
                "hod_credential": "wrong hod",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("overlap", str(response.data).lower())

    def test_leave_submission_uses_derived_student_metadata(self):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            "/otheracademic/api/leave-form-submit/",
            {
                "student_name": "Tampered Name",
                "roll_no": "WRONG",
                "date_from": "2026-04-22",
                "date_to": "2026-04-23",
                "leave_type": "medical",
                "address": "Campus Hostel",
                "purpose": "Medical rest",
                "mobile_number": "9999999999",
                "parents_mobile": "8888888888",
                "mobile_during_leave": "9999999999",
                "semester": 1,
                "academic_year": "2024-25",
                "hod_credential": "wrong hod",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        leave = Leave.objects.get(id=response.data["data"]["id"])
        self.assertEqual(leave.student_name, "CSE Student")
        self.assertEqual(leave.roll_no, "23BCS999")
        self.assertEqual(leave.hod_credential, "hod_cse")
        self.assertEqual(leave.academic_year, "2025-26")
        self.assertEqual(leave.semester, 6)


class WorkflowHistoryTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.student = User.objects.create_user(
            username="history_student",
            password="pass123",
            first_name="History",
            last_name="Student",
        )
        UserProfile.objects.create(
            user=self.student,
            role="student",
            department="CSE",
            roll_no="23BCS777",
            is_pg_student=True,
        )

        self.hod = User.objects.create_user(username="history_hod", password="pass123", first_name="CSE", last_name="HoD")
        UserProfile.objects.create(user=self.hod, role="hod", department="CSE")

        self.acad_admin = User.objects.create_user(
            username="history_acad",
            password="pass123",
            first_name="Academic",
            last_name="Admin",
        )
        UserProfile.objects.create(user=self.acad_admin, role="acadadmin", department="Academic")

        self.supervisor = User.objects.create_user(
            username="history_supervisor",
            password="pass123",
            first_name="Thesis",
            last_name="Supervisor",
        )
        UserProfile.objects.create(user=self.supervisor, role="thesis_supervisor", department="CSE")

    def test_student_workflow_history_includes_requests_across_workflows(self):
        leave = Leave.objects.create(
            user=self.student,
            student_name="History Student",
            roll_no="23BCS777",
            date_from="2026-04-01",
            date_to="2026-04-03",
            leave_type="medical",
            address="Campus",
            purpose="Recovery",
            mobile_number="9999999999",
            parents_mobile="8888888888",
            mobile_during_leave="9999999999",
            status="approved",
            reviewed_by=self.hod,
            reviewed_at=timezone.now(),
            hod_remarks="Approved quickly",
        )
        bonafide = BonafideRequest.objects.create(
            student=self.student,
            certificate_type="scholarship",
            purpose="Scholarship renewal",
            status="approved",
            reviewed_by=self.acad_admin,
            reviewed_at=timezone.now(),
            review_remarks="Issued",
        )
        no_dues = NoDuesRequest.objects.create(
            student=self.student,
            remarks="Semester close",
            total_due_snapshot="0.00",
            status="approved",
            reviewed_by=self.acad_admin,
            reviewed_at=timezone.now(),
            review_remarks="All clear",
        )
        seminar = Seminar.objects.create(student=self.student, topic="History Seminar", status=Seminar.STATUS_REQUESTED)

        self.client.force_authenticate(self.student)
        response = self.client.get("/otheracademic/api/workflow-history/")

        self.assertEqual(response.status_code, 200)
        payload = response.data["data"]
        self.assertEqual(payload["decision_count"], 0)
        workflows = {item["workflow_type"] for item in payload["request_history"]}
        self.assertTrue({"leave", "bonafide", "no_dues", "seminar"}.issubset(workflows))
        leave_entry = next(item for item in payload["request_history"] if item["workflow_type"] == "leave" and item["entity_id"] == leave.id)
        self.assertEqual(leave_entry["actor_name"], "CSE HoD")
        bonafide_entry = next(
            item for item in payload["request_history"] if item["workflow_type"] == "bonafide" and item["entity_id"] == bonafide.id
        )
        self.assertEqual(bonafide_entry["status"], "approved")
        no_dues_entry = next(
            item for item in payload["request_history"] if item["workflow_type"] == "no_dues" and item["entity_id"] == no_dues.id
        )
        self.assertEqual(no_dues_entry["remarks"], "All clear")
        self.assertTrue(any(item["entity_id"] == seminar.id for item in payload["request_history"]))

    def test_hod_history_includes_leave_decisions(self):
        leave = Leave.objects.create(
            user=self.student,
            student_name="History Student",
            roll_no="23BCS777",
            date_from="2026-04-01",
            date_to="2026-04-03",
            leave_type="medical",
            address="Campus",
            purpose="Recovery",
            mobile_number="9999999999",
            parents_mobile="8888888888",
            mobile_during_leave="9999999999",
            status="approved",
            reviewed_by=self.hod,
            reviewed_at=timezone.now(),
            hod_remarks="Approved",
        )

        self.client.force_authenticate(self.hod)
        response = self.client.get("/otheracademic/api/workflow-history/")

        self.assertEqual(response.status_code, 200)
        payload = response.data["data"]
        workflows = {item["workflow_type"] for item in payload["decision_history"]}
        self.assertIn("leave", workflows)
        leave_entry = next(item for item in payload["decision_history"] if item["workflow_type"] == "leave" and item["entity_id"] == leave.id)
        self.assertEqual(leave_entry["student_roll_no"], "23BCS777")

    def test_supervisor_history_includes_assistantship_decisions(self):
        claim = AssistantshipClaim.objects.create(
            student=self.student,
            student_name="History Student",
            roll_no="23BCS777",
            discipline="CSE",
            date_from="2026-04-01",
            date_to="2026-04-30",
            bank_account_no="1234567890",
            applicability="Monthly",
            ta_supervisor="Department Admin",
            thesis_supervisor="Thesis Supervisor",
            hod="CSE HoD",
            date_applied="2026-04-30",
            thesis_status="approved",
        )
        WorkflowAuditLog.objects.create(
            actor=self.supervisor,
            action="assistantship_thesis_status_approved",
            entity_type="AssistantshipClaim",
            entity_id=claim.id,
            before_data={},
            after_data={
                "student_name": claim.student_name,
                "roll_no": claim.roll_no,
                "approvalStages": {"Supervisor": "Approved"},
            },
            metadata={"stage": "thesis_status", "decision": "approved"},
        )

        self.client.force_authenticate(self.supervisor)
        response = self.client.get("/otheracademic/api/workflow-history/")

        self.assertEqual(response.status_code, 200)
        payload = response.data["data"]
        assistantship_entry = next(
            item for item in payload["decision_history"] if item["workflow_type"] == "assistantship"
        )
        self.assertEqual(assistantship_entry["action_label"], "Approved")
        self.assertEqual(assistantship_entry["student_roll_no"], "23BCS777")
