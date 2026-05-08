from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('hod', 'Head of Department'),
        ('admin', 'Admin'),
        ('acadadmin', 'Academic Admin'),
        ('ta_supervisor', 'TA Supervisor'),
        ('thesis_supervisor', 'Thesis Supervisor'),
        ('dean_academic', 'Dean Academic'),
        ('director', 'Director'),
        ('librarian', 'Librarian'),
        ('hostel_warden', 'Hostel Warden'),
        ('mess_incharge', 'Mess Incharge'),
        ('lab_incharge', 'Lab Incharge'),
        ('mess_warden', 'Mess Warden'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    last_selected_role = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=255, blank=True)
    roll_no = models.CharField(max_length=20, blank=True)
    is_pg_student = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    class Meta:
        ordering = ['-created_at']


class Leave(models.Model):
    LEAVE_TYPE_CHOICES = [
        ('medical', 'Medical Leave'),
        ('casual', 'Casual Leave'),
        ('earned', 'Earned Leave'),
        ('emergency', 'Emergency Leave'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]

    student_name = models.CharField(max_length=255)
    roll_no = models.CharField(max_length=20)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leaves', null=True, blank=True)
    date_from = models.DateField()
    date_to = models.DateField()
    leave_type = models.CharField(max_length=50, choices=LEAVE_TYPE_CHOICES)
    related_document = models.FileField(upload_to='leave_documents/', null=True, blank=True)
    address = models.TextField(blank=True)
    purpose = models.TextField()
    hod_credential = models.CharField(max_length=255, blank=True)
    date_of_application = models.DateField(auto_now_add=True)
    mobile_number = models.CharField(max_length=15)
    parents_mobile = models.CharField(max_length=15, blank=True)
    mobile_during_leave = models.CharField(max_length=15)
    semester = models.IntegerField(null=True, blank=True)
    academic_year = models.CharField(max_length=10, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    hod_remarks = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leave_requests_reviewed',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    roll_number = models.CharField(max_length=20, blank=True, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.student_name} - {self.leave_type} ({self.status})"

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(date_to__gte=models.F("date_from")),
                name="leave_date_to_on_or_after_date_from",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status", "date_from", "date_to"], name="leave_user_status_dates_idx"),
            models.Index(fields=["status", "created_at"], name="leave_status_created_idx"),
        ]

class Course(models.Model):
    """
    Course model to store course information
    """
    course_code = models.CharField(max_length=20, unique=True)
    course_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    credits = models.IntegerField()
    department = models.CharField(max_length=255)
    semester = models.IntegerField()
    academic_year = models.CharField(max_length=10)  # e.g., "2023-24"
    capacity = models.IntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.course_code} - {self.course_name}"

    class Meta:
        ordering = ['course_code']
        unique_together = [['course_code', 'semester', 'academic_year']]
        constraints = [
            models.CheckConstraint(condition=models.Q(credits__gt=0), name="course_credits_positive"),
            models.CheckConstraint(condition=models.Q(capacity__gt=0), name="course_capacity_positive"),
        ]


class BranchChangeRequest(models.Model):
    """
    Tracks student branch change requests
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='branch_change_requests')
    current_branch = models.CharField(max_length=100)
    requested_branch = models.CharField(max_length=100)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_date = models.DateTimeField(auto_now_add=True)
    reviewed_date = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='branch_change_requests_reviewed')
    admin_remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student.username} {self.current_branch}->{self.requested_branch} ({self.status})"

    class Meta:
        ordering = ['-requested_date']
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(current_branch=models.F("requested_branch")),
                name="branch_change_requested_branch_differs",
            ),
        ]
        indexes = [
            models.Index(fields=["student", "status"], name="branch_student_status_idx"),
        ]


class AssistantshipApprover(models.Model):
    ROLE_CHOICES = [
        ("hod", "HOD"),
        ("ta_supervisor", "TA Supervisor"),
        ("thesis_supervisor", "Thesis Supervisor"),
    ]

    name = models.CharField(max_length=255)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    department = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"

    class Meta:
        ordering = ["role", "name"]
        unique_together = [["name", "role"]]


class AssistantshipClaim(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assistantship_claims')
    student_name = models.CharField(max_length=255)
    roll_no = models.CharField(max_length=30)
    discipline = models.CharField(max_length=100)
    date_from = models.DateField()
    date_to = models.DateField()
    bank_account_no = models.CharField(max_length=40)
    signature = models.FileField(upload_to='assistantship_signatures/', null=True, blank=True)
    applicability = models.CharField(max_length=255)
    ta_supervisor = models.CharField(max_length=255)
    thesis_supervisor = models.CharField(max_length=255)
    hod = models.CharField(max_length=255)
    date_applied = models.DateField()

    ta_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    thesis_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    hod_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    acadadmin_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    dean_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    director_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    student_reviewed = models.BooleanField(default=False)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    student_withdrawn = models.BooleanField(default=False)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdraw_reason = models.TextField(blank=True)
    student_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)
    disbursed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assistantship_claims_disbursed",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.roll_no} assistantship claim"

    @property
    def overall_status(self):
        if self.student_withdrawn:
            return 'Withdrawn'
        statuses = [
            self.thesis_status,
            self.ta_status,
            self.hod_status,
            self.acadadmin_status,
        ]
        if 'rejected' in statuses:
            return 'Rejected'
        if all(stage == 'approved' for stage in statuses[:3]):
            if self.acadadmin_status == 'approved':
                if self.student_verified:
                    return 'Verified'
                return 'Disbursed'
            return 'Approved'
        return 'Pending'

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(date_to__gte=models.F("date_from")),
                name="assistantship_date_to_on_or_after_date_from",
            ),
        ]
        indexes = [
            models.Index(fields=["student", "created_at"], name="asst_student_created_idx"),
            models.Index(fields=["thesis_status", "ta_status", "hod_status", "acadadmin_status"], name="assistantship_stage_idx"),
        ]


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    verb = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    data = models.TextField(default="{}")
    unread = models.BooleanField(default=True)
    deleted = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}: {self.verb}"

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "unread", "deleted", "timestamp"], name="notification_user_state_idx"),
        ]


class NoDuesEntry(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="no_dues_entries")
    category = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_cleared = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student.username} - {self.category} ({'Cleared' if self.is_cleared else 'Due'})"

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gte=0), name="no_dues_amount_non_negative"),
        ]
        indexes = [
            models.Index(fields=["student", "category", "is_cleared"], name="no_dues_student_category_idx"),
        ]


class NoDuesRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="no_dues_requests")
    remarks = models.TextField(blank=True)
    total_due_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="no_dues_requests_reviewed",
    )
    review_remarks = models.TextField(blank=True)
    domain_approvals = models.JSONField(default=dict, blank=True)
    clearance_file = models.FileField(upload_to="no_dues_clearance_files/", null=True, blank=True)
    clearance_uploaded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.student.username} no-dues ({self.status})"

    class Meta:
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["student", "status", "requested_at"], name="no_dues_student_status_idx"),
            models.Index(fields=["status", "requested_at"], name="no_dues_status_requested_idx"),
        ]


class BonafideRequest(models.Model):
    CERTIFICATE_TYPE_CHOICES = [
        ("scholarship", "Scholarship"),
        ("internship", "Internship"),
        ("education_loan", "Education Loan"),
        ("passport", "Passport"),
        ("visa", "Visa"),
        ("hostel", "Hostel"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("withdrawn", "Withdrawn"),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bonafide_requests")
    certificate_type = models.CharField(max_length=50, choices=CERTIFICATE_TYPE_CHOICES)
    purpose = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bonafide_requests_reviewed",
    )
    review_remarks = models.TextField(blank=True)
    certificate_file = models.FileField(upload_to="bonafide_certificates/", null=True, blank=True)
    certificate_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.student.username} - {self.certificate_type} ({self.status})"

    class Meta:
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["student", "status", "requested_at"], name="bonafide_student_status_idx"),
            models.Index(fields=["status", "requested_at"], name="bonafide_status_requested_idx"),
        ]


class Seminar(models.Model):
    STATUS_REQUESTED = "requested"
    STATUS_SCHEDULED = "scheduled"
    STATUS_COMPLETED = "completed"
    STATUS_EVALUATED = "evaluated"
    STATUS_CHOICES = [
        (STATUS_REQUESTED, "Requested"),
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_EVALUATED, "Evaluated"),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="seminars")
    topic = models.CharField(max_length=255)
    abstract = models.TextField(blank=True)
    requested_slot_start = models.DateTimeField(null=True, blank=True)
    requested_slot_end = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_REQUESTED)
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    venue = models.CharField(max_length=255, blank=True)
    panel_faculty = models.ManyToManyField(User, blank=True, related_name="seminar_panels")
    scheduled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="seminars_scheduled"
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)
    evaluation_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student", "status", "created_at"], name="seminar_student_status_idx"),
            models.Index(fields=["status", "scheduled_start", "scheduled_end"], name="seminar_status_slot_idx"),
        ]

    def __str__(self):
        return f"Seminar#{self.id} {self.student.username} ({self.status})"


class TAAssignment(models.Model):
    STATUS_PENDING_APPROVAL = "pending_approval"
    STATUS_ACTIVE = "active"
    STATUS_REJECTED = "rejected"
    STATUS_WITHDRAWN = "withdrawn"
    STATUS_CHOICES = [
        (STATUS_PENDING_APPROVAL, "Pending Approval"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_WITHDRAWN, "Withdrawn"),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ta_assignments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="ta_assignments")
    faculty = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ta_students",
    )
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="ta_assignments_created")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    start_date = models.DateField()
    end_date = models.DateField()
    hod_reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="ta_assignments_reviewed"
    )
    hod_reviewed_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="ta_assignment_end_on_or_after_start",
            ),
        ]
        indexes = [
            models.Index(fields=["student", "status", "start_date", "end_date"], name="ta_student_status_dates_idx"),
            models.Index(fields=["course", "status"], name="ta_course_status_idx"),
        ]

    def __str__(self):
        return f"TA {self.student.username} -> {self.course.course_code} ({self.status})"


class SupervisorAssignment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="supervisor_assignments")
    supervisor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="supervisees")
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="supervisor_assignments_created"
    )
    is_primary = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student"],
                condition=models.Q(is_primary=True, is_active=True),
                name="one_active_primary_supervisor_per_student",
            ),
        ]
        indexes = [
            models.Index(fields=["student", "is_primary", "is_active"], name="supervisor_student_active_idx"),
            models.Index(fields=["supervisor", "is_primary", "is_active"], name="supervisor_load_idx"),
        ]

    def __str__(self):
        return f"{self.student.username} -> {self.supervisor.username} ({'active' if self.is_active else 'inactive'})"


class WorkflowAuditLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="workflow_audit_logs")
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.PositiveIntegerField()
    before_data = models.JSONField(default=dict, blank=True)
    after_data = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id", "created_at"], name="audit_entity_created_idx"),
            models.Index(fields=["actor", "created_at"], name="audit_actor_created_idx"),
        ]

    def __str__(self):
        return f"{self.action} on {self.entity_type}#{self.entity_id}"
