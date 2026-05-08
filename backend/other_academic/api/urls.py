# other_academic/api/urls.py
from django.urls import path
from .views import (
    LeaveFormDefaultsView, LeaveFormSubmitView, FetchPendingLeavesView, UpdateLeaveStatusView, GetLeaveRequestsView, WithdrawLeaveRequestView,
    WorkflowHistoryView,
    BonafideCertificateOptionsView,
    SubmitBonafideRequestView,
    GetBonafideRequestsView,
    WithdrawBonafideRequestView,
    ApproveBonafideRequestView,
    RejectBonafideRequestView,
    SendBonafideCertificateView,
    DownloadBonafideCertificateView,
    GetNoDuesSummaryView,
    NoDuesEntryManagementView,
    RequestNoDuesView,
    GetNoDuesRequestsView,
    ApproveNoDuesRequestView,
    RejectNoDuesRequestView,
    UploadNoDuesClearanceFileView,
    DownloadNoDuesClearanceFileView,
    AssistantshipFormSubmitView,
    DeptAdminFetchPendingAssistantshipRequests,
    DeptAdminUpdateAssistantshipStatus,
    HODFetchPendingAssistantshipRequests,
    HODUpdateAssistantshipStatus,
    AcadAdminFetchPendingAssistantshipRequests,
    AcadAdminUpdateAssistantshipStatus,
    TA_SupervisorUpdateAssistantshipStatus,
    Ths_SupervisorUpdateAssistantshipStatus,
    GetAssistantshipStatus,
    TA_SupervisorFetchPendingAssistantshipRequests,
    Ths_SupervisorFetchPendingAssistantshipRequests,
    DirectorFetchPendingAssistantshipRequests,
    DirectorUpdateAssistantshipStatus,
    DeanFetchPendingAssistantshipRequests,
    DeanUpdateAssistantshipStatus,
    ReviewAssistantshipClaimView,
    WithdrawAssistantshipClaimView,
    VerifyAssistantshipClaimView,
    AssistantshipApproversView,
    PGWorkflowOptionsView,
    SeminarRequestCreateView,
    SeminarWithdrawView,
    SeminarScheduleView,
    SeminarCompleteView,
    SeminarEvaluateView,
    SeminarListView,
    TAAssignmentCreateView,
    TAAssignmentHodReviewView,
    TAAssignmentListView,
    SupervisorAssignmentCreateView,
    SupervisorAssignmentListView,
)

urlpatterns = [
    # =========================
    # LEAVE MANAGEMENT URLs
    # =========================
    path('leave-form-submit/', LeaveFormSubmitView.as_view(), name='api-leave-form-submit'),
    path('leave-form-defaults/', LeaveFormDefaultsView.as_view(), name='api-leave-form-defaults'),
    path('fetch-pending-leaves/', FetchPendingLeavesView.as_view(), name='api-fetch-pending-leaves'),
    path('update-leave-status/', UpdateLeaveStatusView.as_view(), name='api-update-leave-status'),
    path('get-leave-requests/', GetLeaveRequestsView.as_view(), name='api-get-leave-requests'),
    path('leave-requests/<int:leave_id>/withdraw/', WithdrawLeaveRequestView.as_view(), name='api-withdraw-leave-request'),
    path('workflow-history/', WorkflowHistoryView.as_view(), name='api-workflow-history'),

    # =========================
    # BONAFIDE CERTIFICATE URLs
    # =========================
    path('bonafide/certificate-options/', BonafideCertificateOptionsView.as_view(), name='api-bonafide-certificate-options'),
    path('bonafide/request/', SubmitBonafideRequestView.as_view(), name='api-bonafide-request-submit'),
    path('bonafide/requests/', GetBonafideRequestsView.as_view(), name='api-bonafide-requests'),
    path('bonafide/requests/<int:request_id>/withdraw/', WithdrawBonafideRequestView.as_view(), name='api-bonafide-withdraw'),
    path('bonafide/requests/<int:request_id>/approve/', ApproveBonafideRequestView.as_view(), name='api-bonafide-approve'),
    path('bonafide/requests/<int:request_id>/reject/', RejectBonafideRequestView.as_view(), name='api-bonafide-reject'),
    path('bonafide/requests/<int:request_id>/send-certificate/', SendBonafideCertificateView.as_view(), name='api-bonafide-send-certificate'),
    path('bonafide/requests/<int:request_id>/download/', DownloadBonafideCertificateView.as_view(), name='api-bonafide-download-certificate'),

    # =========================
    # NO DUES URLs
    # =========================
    path('no-dues/summary/', GetNoDuesSummaryView.as_view(), name='api-no-dues-summary'),
    path('no-dues/entries/', NoDuesEntryManagementView.as_view(), name='api-no-dues-entry-management'),
    path('no-dues/request/', RequestNoDuesView.as_view(), name='api-no-dues-request'),
    path('no-dues/requests/', GetNoDuesRequestsView.as_view(), name='api-no-dues-requests'),
    path('no-dues/requests/<int:request_id>/approve/', ApproveNoDuesRequestView.as_view(), name='api-approve-no-dues-request'),
    path('no-dues/requests/<int:request_id>/reject/', RejectNoDuesRequestView.as_view(), name='api-reject-no-dues-request'),
    path('no-dues/requests/<int:request_id>/upload-file/', UploadNoDuesClearanceFileView.as_view(), name='api-upload-no-dues-file'),
    path('no-dues/requests/<int:request_id>/download-file/', DownloadNoDuesClearanceFileView.as_view(), name='api-download-no-dues-file'),

    # =========================
    # ASSISTANTSHIP URLs
    # =========================
    path('assistantship-form-submit/', AssistantshipFormSubmitView.as_view(), name='api-assistantship-submit'),
    path('assistantship/approvers/', AssistantshipApproversView.as_view(), name='api-assistantship-approvers'),
    path('deptadmin-pending-requests/', DeptAdminFetchPendingAssistantshipRequests.as_view(), name='api-deptadmin-pending-assistantship'),
    path('deptadmin-update-status/', DeptAdminUpdateAssistantshipStatus.as_view(), name='api-deptadmin-update-assistantship'),
    path('hod-pending-requests/', HODFetchPendingAssistantshipRequests.as_view(), name='api-hod-pending-assistantship'),
    path('hod-update-status/', HODUpdateAssistantshipStatus.as_view(), name='api-hod-update-assistantship'),
    path('acadadmin-pending-requests/', AcadAdminFetchPendingAssistantshipRequests.as_view(), name='api-acadadmin-pending-assistantship'),
    path('acadadmin-update-status/', AcadAdminUpdateAssistantshipStatus.as_view(), name='api-acadadmin-update-assistantship'),
    path('TA-supervisor-assistantship-update/', TA_SupervisorUpdateAssistantshipStatus.as_view(), name='api-ta-supervisor-update-assistantship'),
    path('Ths-supervisor-assistantship-update/', Ths_SupervisorUpdateAssistantshipStatus.as_view(), name='api-ths-supervisor-update-assistantship'),
    path('get_assistantship_status/', GetAssistantshipStatus.as_view(), name='api-get-assistantship-status'),
    path('TA-supervisor-pending-requests/', TA_SupervisorFetchPendingAssistantshipRequests.as_view(), name='api-ta-supervisor-pending-assistantship'),
    path('Ths-supervisor-pending-requests/', Ths_SupervisorFetchPendingAssistantshipRequests.as_view(), name='api-ths-supervisor-pending-assistantship'),
    path('director-pending-requests/', DirectorFetchPendingAssistantshipRequests.as_view(), name='api-director-pending-assistantship'),
    path('director-update-status/', DirectorUpdateAssistantshipStatus.as_view(), name='api-director-update-assistantship'),
    path('dean-pending-requests/', DeanFetchPendingAssistantshipRequests.as_view(), name='api-dean-pending-assistantship'),
    path('dean-update-status/', DeanUpdateAssistantshipStatus.as_view(), name='api-dean-update-assistantship'),
    path('assistantship/claims/<int:claim_id>/review/', ReviewAssistantshipClaimView.as_view(), name='api-assistantship-review-claim'),
    path('assistantship/claims/<int:claim_id>/withdraw/', WithdrawAssistantshipClaimView.as_view(), name='api-assistantship-withdraw-claim'),
    path('assistantship/claims/<int:claim_id>/verify/', VerifyAssistantshipClaimView.as_view(), name='api-assistantship-verify-claim'),

    # =========================
    # PG ACADEMIC WORKFLOW URLs
    # =========================
    path('pg-workflow/options/', PGWorkflowOptionsView.as_view(), name='api-pg-workflow-options'),
    path('pg-workflow/seminars/request/', SeminarRequestCreateView.as_view(), name='api-pg-seminar-request'),
    path('pg-workflow/seminars/', SeminarListView.as_view(), name='api-pg-seminar-list'),
    path('pg-workflow/seminars/<int:seminar_id>/withdraw/', SeminarWithdrawView.as_view(), name='api-pg-seminar-withdraw'),
    path('pg-workflow/seminars/<int:seminar_id>/schedule/', SeminarScheduleView.as_view(), name='api-pg-seminar-schedule'),
    path('pg-workflow/seminars/<int:seminar_id>/complete/', SeminarCompleteView.as_view(), name='api-pg-seminar-complete'),
    path('pg-workflow/seminars/<int:seminar_id>/evaluate/', SeminarEvaluateView.as_view(), name='api-pg-seminar-evaluate'),
    path('pg-workflow/ta-assignments/', TAAssignmentCreateView.as_view(), name='api-pg-ta-assignment-create'),
    path('pg-workflow/ta-assignments/list/', TAAssignmentListView.as_view(), name='api-pg-ta-assignment-list'),
    path('pg-workflow/ta-assignments/<int:assignment_id>/hod-review/', TAAssignmentHodReviewView.as_view(), name='api-pg-ta-assignment-hod-review'),
    path('pg-workflow/supervisor-assignments/', SupervisorAssignmentCreateView.as_view(), name='api-pg-supervisor-assignment-create'),
    path('pg-workflow/supervisor-assignments/list/', SupervisorAssignmentListView.as_view(), name='api-pg-supervisor-assignment-list'),
]
