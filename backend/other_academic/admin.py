from django.contrib import admin
from other_academic.models import (
    Leave,
    UserProfile,
    Course,
    Notification,
    NoDuesEntry,
    NoDuesRequest,
    BonafideRequest,
    AssistantshipApprover,
    Seminar,
    TAAssignment,
    SupervisorAssignment,
    WorkflowAuditLog,
)
from other_academic.notifications import create_notification

@admin.register(Leave)
class LeaveAdmin(admin.ModelAdmin):
    list_display = ('id', 'student_name', 'roll_no', 'leave_type', 'date_from', 'date_to', 'status', 'created_at')
    list_filter = ('status', 'leave_type', 'created_at', 'date_from')
    search_fields = ('student_name', 'roll_no', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'date_of_application')
    
    # Add actions for bulk approval/rejection
    actions = ['approve_leaves', 'reject_leaves']
    
    fieldsets = (
        ('Student Information', {
            'fields': ('user', 'student_name', 'roll_no')
        }),
        ('Leave Details', {
            'fields': ('leave_type', 'date_from', 'date_to', 'purpose', 'address', 'related_document')
        }),
        ('Contact Information', {
            'fields': ('mobile_number', 'parents_mobile', 'mobile_during_leave')
        }),
        ('Academic Information', {
            'fields': ('semester', 'academic_year', 'hod_credential')
        }),
        ('Approval', {
            'fields': ('status', 'hod_remarks'),
            'classes': ('wide',),
            'description': 'Update leave status here. Remarks are optional.'
        }),
        ('Timestamps', {
            'fields': ('date_of_application', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def approve_leaves(self, request, queryset):
        """Bulk approve selected leave requests"""
        approved_leaves = list(queryset)
        updated = queryset.update(status='approved')
        for leave in approved_leaves:
            create_notification(
                leave.user,
                "Leave request approved",
                f"Your {leave.leave_type} leave request from {leave.date_from} to {leave.date_to} was approved.",
            )
        self.message_user(request, f'{updated} leave request(s) approved successfully.')
    approve_leaves.short_description = 'Approve selected leave requests'
    
    def reject_leaves(self, request, queryset):
        """Bulk reject selected leave requests"""
        rejected_leaves = list(queryset)
        updated = queryset.update(status='rejected')
        for leave in rejected_leaves:
            create_notification(
                leave.user,
                "Leave request rejected",
                f"Your {leave.leave_type} leave request from {leave.date_from} to {leave.date_to} was rejected.",
            )
        self.message_user(request, f'{updated} leave request(s) rejected successfully.')
    reject_leaves.short_description = 'Reject selected leave requests'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'role', 'department', 'roll_no', 'is_pg_student', 'created_at')
    list_filter = ('role', 'department', 'created_at')
    search_fields = ('user__username', 'user__email', 'roll_no', 'department')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Role & Department', {
            'fields': ('role', 'department')
        }),
        ('Student Information', {
            'fields': ('roll_no', 'is_pg_student')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'course_code', 'course_name', 'semester', 'academic_year', 'credits', 'capacity', 'is_active')
    list_filter = ('is_active', 'semester', 'academic_year', 'department', 'created_at')
    search_fields = ('course_code', 'course_name', 'department')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Course Information', {
            'fields': ('course_code', 'course_name', 'description', 'credits')
        }),
        ('Academic Details', {
            'fields': ('semester', 'academic_year', 'department')
        }),
        ('Course Management', {
            'fields': ('capacity', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "verb", "unread", "deleted", "timestamp")
    list_filter = ("unread", "deleted", "timestamp")
    search_fields = ("user__username", "verb", "description")
    readonly_fields = ("timestamp",)


@admin.register(NoDuesEntry)
class NoDuesEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "category", "amount", "is_cleared", "updated_at")
    list_filter = ("is_cleared", "category", "updated_at")
    search_fields = ("student__username", "student__email", "category", "description")


@admin.register(AssistantshipApprover)
class AssistantshipApproverAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "role", "department", "email", "is_active", "updated_at")
    list_filter = ("role", "is_active", "department")
    search_fields = ("name", "email", "department")


@admin.register(Seminar)
class SeminarAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "topic", "status", "scheduled_start", "scheduled_end", "venue", "scheduled_by")
    list_filter = ("status", "venue", "scheduled_start")
    search_fields = ("student__username", "student__email", "topic", "venue")
    filter_horizontal = ("panel_faculty",)


@admin.register(TAAssignment)
class TAAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "course", "faculty", "status", "start_date", "end_date", "assigned_by")
    list_filter = ("status", "start_date", "end_date", "course__academic_year")
    search_fields = ("student__username", "course__course_code", "faculty__username")


@admin.register(SupervisorAssignment)
class SupervisorAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "supervisor", "is_primary", "is_active", "started_at", "ended_at")
    list_filter = ("is_primary", "is_active", "started_at")
    search_fields = ("student__username", "supervisor__username")


@admin.register(WorkflowAuditLog)
class WorkflowAuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "entity_type", "entity_id", "actor", "created_at")
    list_filter = ("action", "entity_type", "created_at")
    search_fields = ("action", "entity_type", "actor__username")
    readonly_fields = ("actor", "action", "entity_type", "entity_id", "before_data", "after_data", "metadata", "created_at")


@admin.register(NoDuesRequest)
class NoDuesRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "status", "total_due_snapshot", "requested_at", "reviewed_by", "clearance_file")
    list_filter = ("status", "requested_at", "reviewed_at")
    search_fields = ("student__username", "student__email", "remarks", "review_remarks")
    readonly_fields = ("requested_at", "clearance_uploaded_at")
    actions = ["approve_no_dues_requests", "reject_no_dues_requests"]

    def approve_no_dues_requests(self, request, queryset):
        from django.utils import timezone

        updated_count = 0
        for req in queryset.filter(status="pending"):
            req.status = "approved"
            req.reviewed_at = timezone.now()
            req.reviewed_by = request.user
            req.save()
            create_notification(
                req.student,
                "No dues request approved",
                "Your no-dues request has been approved.",
            )
            updated_count += 1
        self.message_user(request, f"{updated_count} no-dues request(s) approved successfully.")

    approve_no_dues_requests.short_description = "Approve selected no-dues requests"

    def reject_no_dues_requests(self, request, queryset):
        from django.utils import timezone

        updated_count = 0
        for req in queryset.filter(status="pending"):
            req.status = "rejected"
            req.reviewed_at = timezone.now()
            req.reviewed_by = request.user
            req.save()
            create_notification(
                req.student,
                "No dues request rejected",
                "Your no-dues request has been rejected.",
            )
            updated_count += 1
        self.message_user(request, f"{updated_count} no-dues request(s) rejected successfully.")

    reject_no_dues_requests.short_description = "Reject selected no-dues requests"


@admin.register(BonafideRequest)
class BonafideRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "certificate_type", "status", "requested_at", "reviewed_by", "certificate_sent_at")
    list_filter = ("status", "certificate_type", "requested_at", "reviewed_at")
    search_fields = ("student__username", "student__email", "purpose")
    readonly_fields = ("requested_at", "certificate_sent_at")
    actions = ["approve_bonafide_requests", "reject_bonafide_requests"]

    def approve_bonafide_requests(self, request, queryset):
        from django.utils import timezone

        updated_count = 0
        for req in queryset.filter(status="pending"):
            req.status = "approved"
            req.reviewed_at = timezone.now()
            req.reviewed_by = request.user
            req.save()
            create_notification(
                req.student,
                "Bonafide request approved",
                f"Your bonafide request for {req.get_certificate_type_display()} was approved.",
            )
            updated_count += 1
        self.message_user(request, f"{updated_count} bonafide request(s) approved successfully.")

    approve_bonafide_requests.short_description = "Approve selected bonafide requests"

    def reject_bonafide_requests(self, request, queryset):
        from django.utils import timezone

        updated_count = 0
        for req in queryset.filter(status="pending"):
            req.status = "rejected"
            req.reviewed_at = timezone.now()
            req.reviewed_by = request.user
            req.save()
            create_notification(
                req.student,
                "Bonafide request rejected",
                f"Your bonafide request for {req.get_certificate_type_display()} was rejected.",
            )
            updated_count += 1
        self.message_user(request, f"{updated_count} bonafide request(s) rejected successfully.")

    reject_bonafide_requests.short_description = "Reject selected bonafide requests"
