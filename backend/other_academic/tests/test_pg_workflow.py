from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.db.models import F
from django.utils import timezone
from rest_framework.test import APIClient

from other_academic.models import (
    AssistantshipClaim,
    Course,
    Notification,
    Seminar,
    SupervisorAssignment,
    TAAssignment,
    UserProfile,
    WorkflowAuditLog,
)


class PGWorkflowAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.future_start = date.today() + timedelta(days=5)
        self.future_end = self.future_start + timedelta(days=30)
        self.future_overlap_start = self.future_start + timedelta(days=10)
        self.future_overlap_end = self.future_end + timedelta(days=10)

        self.student = User.objects.create_user(username="pgstudent", password="pass123")
        UserProfile.objects.create(
            user=self.student,
            role="student",
            roll_no="23MCS001",
            is_pg_student=True,
            department="CSE",
        )

        self.student2 = User.objects.create_user(username="pgstudent2", password="pass123")
        UserProfile.objects.create(
            user=self.student2,
            role="student",
            roll_no="23MCS002",
            is_pg_student=True,
            department="CSE",
        )

        self.ug_student = User.objects.create_user(username="ugstudent", password="pass123")
        UserProfile.objects.create(
            user=self.ug_student,
            role="student",
            roll_no="23BCS001",
            is_pg_student=False,
            department="CSE",
        )

        self.dept_admin = User.objects.create_user(username="deptadmin", password="pass123")
        UserProfile.objects.create(user=self.dept_admin, role="admin", department="CSE")

        self.hod = User.objects.create_user(username="hoduser", password="pass123")
        UserProfile.objects.create(user=self.hod, role="hod", department="CSE")

        self.acad_admin = User.objects.create_user(username="acadadminuser", password="pass123")
        UserProfile.objects.create(user=self.acad_admin, role="acadadmin", department="CSE")

        self.faculty = User.objects.create_user(username="faculty1", password="pass123")
        UserProfile.objects.create(user=self.faculty, role="admin", department="CSE")

        self.faculty2 = User.objects.create_user(username="faculty2", password="pass123")
        UserProfile.objects.create(user=self.faculty2, role="thesis_supervisor", department="CSE")

        self.out_of_department_faculty = User.objects.create_user(username="ecefaculty", password="pass123")
        UserProfile.objects.create(user=self.out_of_department_faculty, role="admin", department="ECE")

        self.ece_hod = User.objects.create_user(username="hod_ece", password="pass123")
        UserProfile.objects.create(user=self.ece_hod, role="hod", department="ECE")

        self.course = Course.objects.create(
            course_code="CSE701",
            course_name="Advanced Algorithms",
            description="PG course",
            credits=4,
            department="CSE",
            semester=6,
            academic_year="2025-26",
            capacity=100,
            is_active=True,
        )

    def _assistantship_payload(self, **overrides):
        payload = {
            "discipline": "CSE",
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
            "bank_account_no": "123456789012",
            "signature": SimpleUploadedFile("sig.jpg", b"binarydata", content_type="image/jpeg"),
            "applicability": "Monthly claim",
            "thesis_supervisor": self.faculty2.username,
            "hod": self.hod.username,
            "date_applied": "2026-04-30",
        }
        payload.update(overrides)
        return payload

    def test_seminar_workflow_no_skipping_states(self):
        self.client.force_authenticate(self.student)
        request_resp = self.client.post(
            "/otheracademic/api/pg-workflow/seminars/request/",
            {
                "topic": "Distributed ML",
                "abstract": "Seminar abstract",
            },
            format="json",
        )
        self.assertEqual(request_resp.status_code, 201)
        seminar_id = request_resp.data["data"]["id"]

        self.client.force_authenticate(self.dept_admin)
        evaluate_resp = self.client.post(
            f"/otheracademic/api/pg-workflow/seminars/{seminar_id}/evaluate/",
            {"evaluation_notes": "Cannot evaluate yet"},
            format="json",
        )
        self.assertEqual(evaluate_resp.status_code, 400)
        self.assertIn("COMPLETED", evaluate_resp.data["error"])

    def test_seminar_schedule_conflict_detection(self):
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=1)

        seminar_existing = Seminar.objects.create(
            student=self.student,
            topic="Existing Seminar",
            status=Seminar.STATUS_SCHEDULED,
            scheduled_start=start,
            scheduled_end=end,
            venue="LH-101",
            scheduled_by=self.dept_admin,
        )
        seminar_existing.panel_faculty.set([self.faculty])

        self.client.force_authenticate(self.student2)
        create_resp = self.client.post(
            "/otheracademic/api/pg-workflow/seminars/request/",
            {"topic": "New Seminar"},
            format="json",
        )
        seminar_id = create_resp.data["data"]["id"]

        self.client.force_authenticate(self.dept_admin)
        schedule_resp = self.client.post(
            f"/otheracademic/api/pg-workflow/seminars/{seminar_id}/schedule/",
            {
                "scheduled_start": start.isoformat(),
                "scheduled_end": end.isoformat(),
                "venue": "LH-101",
                "panel_faculty_ids": [self.faculty.id],
            },
            format="json",
        )
        self.assertEqual(schedule_resp.status_code, 400)
        self.assertIn("Venue conflict", schedule_resp.data["error"])

    def test_student_can_withdraw_requested_seminar(self):
        self.client.force_authenticate(self.student)
        create_resp = self.client.post(
            "/otheracademic/api/pg-workflow/seminars/request/",
            {"topic": "Withdrawable Seminar"},
            format="json",
        )
        seminar_id = create_resp.data["data"]["id"]

        withdraw_resp = self.client.post(
            f"/otheracademic/api/pg-workflow/seminars/{seminar_id}/withdraw/",
            {},
            format="json",
        )

        self.assertEqual(withdraw_resp.status_code, 200)
        self.assertFalse(Seminar.objects.filter(id=seminar_id).exists())
        self.assertTrue(
            WorkflowAuditLog.objects.filter(
                action="seminar_withdrawn",
                entity_type="Seminar",
                entity_id=seminar_id,
            ).exists()
        )

    def test_student_cannot_withdraw_scheduled_seminar(self):
        seminar = Seminar.objects.create(student=self.student, topic="Scheduled Seminar", status=Seminar.STATUS_SCHEDULED)
        self.client.force_authenticate(self.student)

        withdraw_resp = self.client.post(
            f"/otheracademic/api/pg-workflow/seminars/{seminar.id}/withdraw/",
            {},
            format="json",
        )

        self.assertEqual(withdraw_resp.status_code, 400)
        self.assertIn("REQUESTED", withdraw_resp.data["error"])
        self.assertTrue(Seminar.objects.filter(id=seminar.id).exists())

    def test_ta_assignment_requires_pg_student(self):
        self.client.force_authenticate(self.dept_admin)
        resp = self.client.post(
            "/otheracademic/api/pg-workflow/ta-assignments/",
            {
                "student_id": self.ug_student.id,
                "course_id": self.course.id,
                "start_date": self.future_start.isoformat(),
                "end_date": self.future_end.isoformat(),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("PG student", resp.data["error"])

    def test_ug_student_cannot_access_assistantship_endpoints(self):
        self.client.force_authenticate(self.ug_student)

        approvers_response = self.client.get("/otheracademic/api/assistantship/approvers/")
        self.assertEqual(approvers_response.status_code, 403)
        self.assertIn("PG students", approvers_response.data["error"])

        status_response = self.client.post(
            "/otheracademic/api/get_assistantship_status/",
            {},
            format="json",
        )
        self.assertEqual(status_response.status_code, 403)
        self.assertIn("PG students", status_response.data["error"])

    def test_ug_student_cannot_access_seminar_endpoints(self):
        self.client.force_authenticate(self.ug_student)

        list_response = self.client.get("/otheracademic/api/pg-workflow/seminars/")
        self.assertEqual(list_response.status_code, 403)
        self.assertIn("PG students", list_response.data["error"])

        create_response = self.client.post(
            "/otheracademic/api/pg-workflow/seminars/request/",
            {"topic": "UG Seminar Attempt"},
            format="json",
        )
        self.assertEqual(create_response.status_code, 403)
        self.assertIn("PG students", create_response.data["error"])

    def test_ta_assignment_overlap_validation(self):
        TAAssignment.objects.create(
            student=self.student,
            course=self.course,
            faculty=self.faculty,
            assigned_by=self.dept_admin,
            status=TAAssignment.STATUS_ACTIVE,
            start_date=self.future_start,
            end_date=self.future_end,
        )
        self.client.force_authenticate(self.dept_admin)
        resp = self.client.post(
            "/otheracademic/api/pg-workflow/ta-assignments/",
            {
                "student_id": self.student.id,
                "course_id": self.course.id,
                "start_date": self.future_overlap_start.isoformat(),
                "end_date": self.future_overlap_end.isoformat(),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("overlapping", resp.data["error"])

    def test_ta_assignment_rejects_past_start_date(self):
        self.client.force_authenticate(self.dept_admin)
        resp = self.client.post(
            "/otheracademic/api/pg-workflow/ta-assignments/",
            {
                "student_id": self.student.id,
                "course_id": self.course.id,
                "start_date": (date.today() - timedelta(days=1)).isoformat(),
                "end_date": self.future_end.isoformat(),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("past", resp.data["error"])

    def test_supervisor_reassignment_keeps_single_active_primary(self):
        self.client.force_authenticate(self.dept_admin)
        first = self.client.post(
            "/otheracademic/api/pg-workflow/supervisor-assignments/",
            {
                "student_id": self.student.id,
                "supervisor_id": self.faculty.id,
                "reason": "Initial allocation",
            },
            format="json",
        )
        self.assertEqual(first.status_code, 201)

        second = self.client.post(
            "/otheracademic/api/pg-workflow/supervisor-assignments/",
            {
                "student_id": self.student.id,
                "supervisor_id": self.faculty2.id,
                "reason": "Reassigned for domain fit",
            },
            format="json",
        )
        self.assertEqual(second.status_code, 201)
        self.assertEqual(
            SupervisorAssignment.objects.filter(student=self.student, is_primary=True, is_active=True).count(),
            1,
        )
        self.assertEqual(
            SupervisorAssignment.objects.filter(student=self.student, is_primary=True).count(),
            2,
        )

    def test_supervisor_assignment_list_can_be_filtered_and_shows_assignment_metadata(self):
        assignment = SupervisorAssignment.objects.create(
            student=self.student,
            supervisor=self.faculty2,
            assigned_by=self.dept_admin,
            is_primary=True,
            is_active=True,
            reason="Initial PhD allocation",
        )
        SupervisorAssignment.objects.create(
            student=self.student2,
            supervisor=self.faculty,
            assigned_by=self.dept_admin,
            is_primary=True,
            is_active=True,
            reason="Other student allocation",
        )

        self.client.force_authenticate(self.dept_admin)
        response = self.client.get(
            "/otheracademic/api/pg-workflow/supervisor-assignments/list/",
            {"student_id": self.student.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        payload = response.data["data"][0]
        self.assertEqual(payload["id"], assignment.id)
        self.assertEqual(payload["student_username"], self.student.username)
        self.assertEqual(payload["student_roll_no"], self.student.profile.roll_no)
        self.assertEqual(payload["supervisor_username"], self.faculty2.username)
        self.assertEqual(payload["assigned_by_username"], self.dept_admin.username)
        self.assertEqual(payload["reason"], "Initial PhD allocation")
        self.assertIsNotNone(payload["started_at"])

    def test_workflow_options_only_include_students_with_seminar_requests(self):
        Seminar.objects.create(student=self.student, topic="Applied Seminar")
        TAAssignment.objects.create(
            student=self.student2,
            course=self.course,
            faculty=None,
            assigned_by=self.dept_admin,
            status=TAAssignment.STATUS_ACTIVE,
            start_date=self.future_start,
            end_date=self.future_end,
        )
        SupervisorAssignment.objects.create(
            student=self.student2,
            supervisor=self.faculty2,
            assigned_by=self.dept_admin,
            is_primary=True,
            is_active=True,
            reason="Initial PhD allocation",
        )

        self.client.force_authenticate(self.dept_admin)
        response = self.client.get("/otheracademic/api/pg-workflow/options/")

        self.assertEqual(response.status_code, 200)
        returned_usernames = [item["username"] for item in response.data["students"]]
        assignment_usernames = [item["username"] for item in response.data["pg_students"]]
        self.assertIn(self.student.username, returned_usernames)
        self.assertNotIn(self.student2.username, returned_usernames)
        self.assertIn(self.student.username, assignment_usernames)
        self.assertIn(self.student2.username, assignment_usernames)

        student2_payload = next(item for item in response.data["pg_students"] if item["username"] == self.student2.username)
        self.assertEqual(student2_payload["active_ta_assignment"]["course_code"], self.course.course_code)
        self.assertEqual(student2_payload["active_ta_assignment"]["faculty_username"], "")
        self.assertEqual(
            student2_payload["active_supervisor_assignment"]["supervisor_username"],
            self.faculty2.username,
        )

    def test_rbac_and_audit_notification(self):
        self.client.force_authenticate(self.student)
        denied = self.client.post(
            "/otheracademic/api/pg-workflow/ta-assignments/",
            {
                "student_id": self.student.id,
                "course_id": self.course.id,
                "start_date": self.future_start.isoformat(),
                "end_date": self.future_end.isoformat(),
            },
            format="json",
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.dept_admin)
        ok = self.client.post(
            "/otheracademic/api/pg-workflow/ta-assignments/",
            {
                "student_id": self.student.id,
                "course_id": self.course.id,
                "start_date": self.future_start.isoformat(),
                "end_date": self.future_end.isoformat(),
                "requires_hod_approval": False,
            },
            format="json",
        )
        self.assertEqual(ok.status_code, 201)
        self.assertTrue(Notification.objects.filter(user=self.student, verb="TA assigned").exists())
        self.assertTrue(WorkflowAuditLog.objects.filter(entity_type="TAAssignment").exists())

    def test_ta_assignment_pending_approval_notifies_only_student_department_hod(self):
        self.client.force_authenticate(self.dept_admin)
        response = self.client.post(
            "/otheracademic/api/pg-workflow/ta-assignments/",
            {
                "student_id": self.student.id,
                "course_id": self.course.id,
                "start_date": self.future_start.isoformat(),
                "end_date": self.future_end.isoformat(),
                "requires_hod_approval": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Notification.objects.filter(user=self.hod, verb="TA assignment pending approval").exists())
        self.assertFalse(Notification.objects.filter(user=self.ece_hod, verb="TA assignment pending approval").exists())

    def test_seminar_list_includes_assigned_ta_and_supervisor(self):
        seminar = Seminar.objects.create(
            student=self.student,
            topic="Seminar With Assignments",
            abstract="Checks assignment visibility",
        )
        TAAssignment.objects.create(
            student=self.student,
            course=self.course,
            faculty=None,
            assigned_by=self.dept_admin,
            status=TAAssignment.STATUS_ACTIVE,
            start_date=self.future_start,
            end_date=self.future_end,
        )
        SupervisorAssignment.objects.create(
            student=self.student,
            supervisor=self.faculty2,
            assigned_by=self.dept_admin,
            is_primary=True,
            is_active=True,
            reason="Research alignment",
        )

        self.client.force_authenticate(self.student)
        response = self.client.get("/otheracademic/api/pg-workflow/seminars/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        seminar_data = response.data["data"][0]
        self.assertEqual(seminar_data["id"], seminar.id)
        self.assertEqual(seminar_data["assigned_ta"]["course_code"], self.course.course_code)
        self.assertEqual(
            seminar_data["assigned_supervisor"]["supervisor_name"],
            self.faculty2.username,
        )

    def test_new_seminar_hides_old_student_assignments_until_reassigned(self):
        old_ta = TAAssignment.objects.create(
            student=self.student,
            course=self.course,
            faculty=None,
            assigned_by=self.dept_admin,
            status=TAAssignment.STATUS_ACTIVE,
            start_date=self.future_start,
            end_date=self.future_end,
        )
        old_supervisor = SupervisorAssignment.objects.create(
            student=self.student,
            supervisor=self.faculty2,
            assigned_by=self.dept_admin,
            is_primary=True,
            is_active=True,
            reason="Earlier seminar cycle",
        )
        TAAssignment.objects.filter(id=old_ta.id).update(created_at=F("created_at") - timedelta(days=2))
        SupervisorAssignment.objects.filter(id=old_supervisor.id).update(
            created_at=F("created_at") - timedelta(days=2)
        )

        seminar = Seminar.objects.create(
            student=self.student,
            topic="Fresh Seminar Request",
            abstract="Should start with blank assignees",
        )

        self.client.force_authenticate(self.student)
        response = self.client.get("/otheracademic/api/pg-workflow/seminars/")

        self.assertEqual(response.status_code, 200)
        seminar_data = next(item for item in response.data["data"] if item["id"] == seminar.id)
        self.assertIsNone(seminar_data["assigned_ta"])
        self.assertIsNone(seminar_data["assigned_supervisor"])

    def test_supervisor_assignment_rejects_cross_department_faculty(self):
        self.client.force_authenticate(self.dept_admin)
        response = self.client.post(
            "/otheracademic/api/pg-workflow/supervisor-assignments/",
            {
                "student_id": self.student.id,
                "supervisor_id": self.out_of_department_faculty.id,
                "reason": "Should fail",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("department", response.data["error"])

    def test_ta_assignment_rejects_cross_department_course(self):
        ece_course = Course.objects.create(
            course_code="ECE701",
            course_name="Advanced Circuits",
            description="PG course",
            credits=4,
            department="ECE",
            semester=6,
            academic_year="2025-26",
            capacity=100,
            is_active=True,
        )
        self.client.force_authenticate(self.dept_admin)
        response = self.client.post(
            "/otheracademic/api/pg-workflow/ta-assignments/",
            {
                "student_id": self.student.id,
                "course_id": ece_course.id,
                "start_date": self.future_start.isoformat(),
                "end_date": self.future_end.isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("department", response.data["error"])

    def test_assistantship_claim_requires_department_assigned_supervisors(self):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            "/otheracademic/api/assistantship-form-submit/",
            self._assistantship_payload(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("assigned thesis supervisor", response.data["error"])

    def test_assistantship_claim_submission_and_audit_uses_active_assignments(self):
        TAAssignment.objects.create(
            student=self.student,
            course=self.course,
            faculty=None,
            assigned_by=self.dept_admin,
            status=TAAssignment.STATUS_ACTIVE,
            start_date=self.future_start,
            end_date=self.future_end,
        )
        SupervisorAssignment.objects.create(
            student=self.student,
            supervisor=self.faculty2,
            assigned_by=self.dept_admin,
            is_primary=True,
            is_active=True,
            reason="Research fit",
        )

        self.client.force_authenticate(self.student)
        response = self.client.post(
            "/otheracademic/api/assistantship-form-submit/",
            self._assistantship_payload(),
        )

        self.assertEqual(response.status_code, 201)
        claim = AssistantshipClaim.objects.get(student=self.student)
        self.assertEqual(claim.thesis_supervisor, self.faculty2.username)
        self.assertEqual(claim.ta_status, "pending")
        self.assertEqual(claim.thesis_status, "pending")
        self.assertEqual(claim.dean_status, "approved")
        self.assertEqual(claim.director_status, "approved")
        self.assertTrue(
            WorkflowAuditLog.objects.filter(
                entity_type="AssistantshipClaim",
                entity_id=claim.id,
                action="assistantship_claim_submitted",
            ).exists()
        )

    def test_assistantship_claim_rejects_spoofed_supervisor_names(self):
        TAAssignment.objects.create(
            student=self.student,
            course=self.course,
            faculty=None,
            assigned_by=self.dept_admin,
            status=TAAssignment.STATUS_ACTIVE,
            start_date=self.future_start,
            end_date=self.future_end,
        )
        SupervisorAssignment.objects.create(
            student=self.student,
            supervisor=self.faculty2,
            assigned_by=self.dept_admin,
            is_primary=True,
            is_active=True,
        )

        self.client.force_authenticate(self.student)
        response = self.client.post(
            "/otheracademic/api/assistantship-form-submit/",
            self._assistantship_payload(thesis_supervisor="someone-else"),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("does not match", response.data["error"])

    def test_assistantship_stage_update_enforces_assignment_and_sequence(self):
        claim = AssistantshipClaim.objects.create(
            student=self.student,
            student_name="PG Student",
            roll_no="23MCS001",
            discipline="CSE",
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 30),
            bank_account_no="123456789012",
            applicability="Monthly claim",
            ta_supervisor="Department Admin",
            thesis_supervisor=self.faculty2.username,
            hod=self.hod.username,
            date_applied=date(2026, 4, 30),
            ta_status="pending",
        )

        self.client.force_authenticate(self.acad_admin)
        premature = self.client.post(
            "/otheracademic/api/acadadmin-update-status/",
            {"approvedRequests": [claim.id], "rejectedRequests": []},
            format="json",
        )
        self.assertEqual(premature.status_code, 400)
        self.assertIn("HoD must be approved", str(premature.data))

        self.client.force_authenticate(self.hod)
        unauthorized = self.client.post(
            "/otheracademic/api/TA-supervisor-assistantship-update/",
            {"approvedRequests": [claim.id], "rejectedRequests": []},
            format="json",
        )
        self.assertEqual(unauthorized.status_code, 400)
        self.assertIn("not assigned", str(unauthorized.data))

        self.client.force_authenticate(self.faculty2)
        approve_supervisor = self.client.post(
            "/otheracademic/api/Ths-supervisor-assistantship-update/",
            {"approvedRequests": [claim.id], "rejectedRequests": []},
            format="json",
        )
        self.assertEqual(approve_supervisor.status_code, 200)

        self.client.force_authenticate(self.dept_admin)
        approve_deptadmin = self.client.post(
            "/otheracademic/api/deptadmin-update-status/",
            {"approvedRequests": [claim.id], "rejectedRequests": []},
            format="json",
        )
        self.assertEqual(approve_deptadmin.status_code, 200)

        self.client.force_authenticate(self.hod)
        approve_hod = self.client.post(
            "/otheracademic/api/hod-update-status/",
            {"approvedRequests": [claim.id], "rejectedRequests": []},
            format="json",
        )
        self.assertEqual(approve_hod.status_code, 200)

        self.client.force_authenticate(self.acad_admin)
        approve_acadadmin = self.client.post(
            "/otheracademic/api/acadadmin-update-status/",
            {"approvedRequests": [claim.id], "rejectedRequests": []},
            format="json",
        )
        self.assertEqual(approve_acadadmin.status_code, 200)
        claim.refresh_from_db()
        self.assertEqual(claim.thesis_status, "approved")
        self.assertEqual(claim.hod_status, "approved")
        self.assertEqual(claim.acadadmin_status, "approved")
        self.assertIsNotNone(claim.disbursed_at)
        self.assertEqual(claim.disbursed_by, self.acad_admin)
        self.assertEqual(claim.overall_status, "Disbursed")
        self.assertTrue(
            WorkflowAuditLog.objects.filter(
                entity_type="AssistantshipClaim",
                entity_id=claim.id,
                action="assistantship_acadadmin_status_approved",
            ).exists()
        )
