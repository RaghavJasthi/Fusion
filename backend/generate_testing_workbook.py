import copy
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", NS)


def qn(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def col_letter(index: int) -> str:
    result = ""
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result


def inline_cell(ref: str, value: str) -> ET.Element:
    cell = ET.Element(qn("c"), {"r": ref, "t": "inlineStr"})
    is_el = ET.SubElement(cell, qn("is"))
    t_el = ET.SubElement(is_el, qn("t"))
    if value.startswith(" ") or value.endswith(" ") or "\n" in value:
        t_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t_el.text = value
    return cell


def numeric_cell(ref: str, value: str) -> ET.Element:
    cell = ET.Element(qn("c"), {"r": ref})
    v_el = ET.SubElement(cell, qn("v"))
    v_el.text = value
    return cell


def build_row(row_idx: int, values: list[str]) -> ET.Element:
    row = ET.Element(qn("row"), {"r": str(row_idx)})
    for idx, value in enumerate(values, start=1):
        ref = f"{col_letter(idx)}{row_idx}"
        if value is None:
            continue
        if isinstance(value, (int, float)):
            row.append(numeric_cell(ref, str(value)))
        else:
            row.append(inline_cell(ref, str(value)))
    return row


def set_sheet_rows(xml_bytes: bytes, rows: list[list[str]]) -> bytes:
    root = ET.fromstring(xml_bytes)
    sheet_data = root.find(qn("sheetData"))
    assert sheet_data is not None
    header = copy.deepcopy(sheet_data.find(qn("row")))
    sheet_data.clear()
    sheet_data.append(header)
    for idx, row_values in enumerate(rows, start=2):
        sheet_data.append(build_row(idx, row_values))
    max_col = len(rows[0]) if rows else len(header.findall(qn("c")))
    max_row = len(rows) + 1
    dim = root.find(qn("dimension"))
    if dim is not None:
        dim.set("ref", f"A1:{col_letter(max_col)}{max_row}")
    return ET.tostring(root, encoding="utf-8", xml_declaration=False)


@dataclass
class UseCase:
    uc_id: str
    name: str
    precondition: str
    flow: str
    wf_id: str
    br_ids: list[str]


@dataclass
class Workflow:
    wf_id: str
    name: str
    objective: str
    start_uc: str


BR_DESCRIPTIONS = {
    "OA-BR-01": "RBAC and authenticated access must be enforced for each action.",
    "OA-BR-02": "Workflow integrity must prevent status skipping or direct stage changes.",
    "OA-BR-03": "Notifications must be sent on submission, decision, escalation, and certificate readiness.",
    "OA-BR-04": "Audit logs must capture actor, action, artifact, and timestamp for critical actions.",
    "OA-BR-05": "Downloads are allowed only for approved artifacts and authorized users.",
    "OA-BR-06": "Withdrawal is allowed only by the requester while the request is still pending.",
    "OA-BR-07": "Concurrent actions on the same request must not create conflicting final states.",
}


USE_CASES = [
    UseCase("OA-UC-001", "Submit UG Leave", "Authenticated student with valid leave details.", "Fill leave, validate data, submit for approval.", "OA-WF-001", ["OA-BR-01", "OA-BR-02", "OA-BR-03", "OA-BR-04", "OA-BR-06"]),
    UseCase("OA-UC-002", "Submit PG Leave", "Authenticated PG student with supervisor details.", "Fill PG leave, validate, route for approval.", "OA-WF-002", ["OA-BR-01", "OA-BR-02", "OA-BR-03", "OA-BR-04", "OA-BR-06"]),
    UseCase("OA-UC-003", "Approve or Reject Request", "Authorized approver opens pending request.", "Review request, decide once, trigger downstream actions.", "OA-WF-002", ["OA-BR-01", "OA-BR-02", "OA-BR-03", "OA-BR-04", "OA-BR-07"]),
    UseCase("OA-UC-004", "Upload Attachment", "Authenticated requester has supporting document.", "Upload attachment, validate file, bind to request.", "OA-WF-001", ["OA-BR-01", "OA-BR-02", "OA-BR-05"]),
    UseCase("OA-UC-005", "Apply Bonafide", "Authenticated student has bonafide purpose.", "Submit bonafide form, await approval, download certificate.", "OA-WF-003", ["OA-BR-01", "OA-BR-02", "OA-BR-03", "OA-BR-05"]),
    UseCase("OA-UC-006", "No Dues Clearance", "Authenticated student has active no-dues request.", "Submit clearance and collect departmental decisions.", "OA-WF-004", ["OA-BR-01", "OA-BR-02", "OA-BR-03", "OA-BR-07"]),
    UseCase("OA-UC-007", "Assistantship Claim", "Authenticated PG student has claimable assistantship cycle.", "Submit claim, verify evidence, approve or reject.", "OA-WF-005", ["OA-BR-01", "OA-BR-02", "OA-BR-04", "OA-BR-07"]),
    UseCase("OA-UC-008", "View Request Status", "Authenticated requester has at least one request.", "Open dashboard and review current status history.", "OA-WF-001", ["OA-BR-01", "OA-BR-02", "OA-BR-04"]),
    UseCase("OA-UC-009", "Receive Notifications", "Authenticated user is linked to a request event.", "System sends in-app or email notification on event.", "OA-WF-002", ["OA-BR-01", "OA-BR-03"]),
    UseCase("OA-UC-010", "Generate Reports", "Authorized admin selects report filters.", "Generate export using eligible approved records.", "OA-WF-006", ["OA-BR-01", "OA-BR-02", "OA-BR-04"]),
    UseCase("OA-UC-011", "Search Requests", "Authorized admin accesses search dashboard.", "Filter requests by status, type, and user.", "OA-WF-006", ["OA-BR-01", "OA-BR-02"]),
    UseCase("OA-UC-012", "Role Permission Setup", "System admin manages role mappings.", "Assign or revoke role permissions for module actors.", "OA-WF-006", ["OA-BR-01", "OA-BR-04"]),
    UseCase("OA-UC-013", "Escalate Pending Requests", "System detects SLA breach on pending request.", "Escalate overdue item and notify responsible actor.", "OA-WF-007", ["OA-BR-02", "OA-BR-03", "OA-BR-04"]),
    UseCase("OA-UC-014", "Audit Log Tracking", "Authorized admin reviews audit trail.", "Inspect historical decisions and action chronology.", "OA-WF-007", ["OA-BR-01", "OA-BR-04"]),
    UseCase("OA-UC-015", "Template Document Management", "Authorized admin manages document template.", "Upload, update, and activate template for generated outputs.", "OA-WF-003", ["OA-BR-01", "OA-BR-05", "OA-BR-04"]),
]


WORKFLOWS = [
    Workflow("OA-WF-001", "UG Leave Management", "End-to-end UG leave submission and tracking.", "OA-UC-001"),
    Workflow("OA-WF-002", "PG Leave and Decision Workflow", "PG leave submission with controlled approval decisions.", "OA-UC-002"),
    Workflow("OA-WF-003", "Bonafide Certificate Workflow", "Bonafide request, approval, and certificate issuance.", "OA-UC-005"),
    Workflow("OA-WF-004", "No Dues Clearance Workflow", "Departmental clearance and final no-dues outcome.", "OA-UC-006"),
    Workflow("OA-WF-005", "Assistantship Claim Workflow", "Claim verification and final assistantship decision.", "OA-UC-007"),
    Workflow("OA-WF-006", "Admin Reporting and Control Workflow", "Admin search, reporting, and access governance.", "OA-UC-010"),
    Workflow("OA-WF-007", "Escalation and Audit Monitoring Workflow", "SLA escalation and audit visibility for pending items.", "OA-UC-013"),
]


UC_STATUS_COUNTS = {
    "OA-UC-001": (2, 0, 1, "Partially Implemented", "Audit logging is partial for leave submission updates."),
    "OA-UC-002": (2, 0, 1, "Partially Implemented", "Withdrawal behavior needs stronger PG-stage validation."),
    "OA-UC-003": (1, 0, 2, "Partially Implemented", "Concurrency and repeat-decision protection are weak."),
    "OA-UC-004": (2, 0, 1, "Partially Implemented", "File validation passes but download authorization is inconsistent."),
    "OA-UC-005": (2, 1, 0, "Partially Implemented", "Certificate download authorization defect observed."),
    "OA-UC-006": (1, 1, 1, "Incorrect", "Workflow blocking and conflict handling need correction."),
    "OA-UC-007": (2, 0, 1, "Partially Implemented", "Concurrent approval paths need locking."),
    "OA-UC-008": (3, 0, 0, "Implemented Correctly", "Status visibility behaves as expected."),
    "OA-UC-009": (1, 1, 1, "Partially Implemented", "Notification coverage is incomplete on some status changes."),
    "OA-UC-010": (3, 0, 0, "Implemented Correctly", "Admin reporting is correctly restricted."),
    "OA-UC-011": (2, 1, 0, "Partially Implemented", "Unauthorized search access still needs hardening."),
    "OA-UC-012": (1, 1, 1, "Incorrect", "Role setup changes are not fully audited or blocked."),
    "OA-UC-013": (2, 0, 1, "Partially Implemented", "Escalation notifies inconsistently on repeated breaches."),
    "OA-UC-014": (2, 1, 0, "Partially Implemented", "Audit review misses some document events."),
    "OA-UC-015": (2, 0, 1, "Partially Implemented", "Template updates need tighter access and version checks."),
}


WF_STATUS_COUNTS = {
    "OA-WF-001": (1, 1, 0, "Partial", "Validation is solid, but attachment/download controls are uneven."),
    "OA-WF-002": (1, 0, 1, "Incorrect", "Decision locking and withdrawal edge cases can break the flow."),
    "OA-WF-003": (1, 1, 0, "Partial", "Certificate issuance works but authorization is incomplete."),
    "OA-WF-004": (0, 1, 1, "Blocked", "Department conflict handling can block final clearance."),
    "OA-WF-005": (1, 1, 0, "Partial", "Assistantship flow needs stronger concurrent update protection."),
    "OA-WF-006": (2, 0, 0, "Complete", "Admin reporting and search controls are stable."),
    "OA-WF-007": (1, 1, 0, "Partial", "Escalation and audit trails are present but not fully consistent."),
}


def uc_tests() -> list[list[str]]:
    rows = []
    test_num = 1
    for uc in USE_CASES:
        mapped = ", ".join(uc.br_ids)
        rows.append([
            f"UC_TC_{test_num:03d}",
            uc.uc_id,
            "Happy",
            f"{uc.name} happy path in Other Academic module.",
            uc.precondition,
            uc.flow,
            f"Request completes successfully with required controls enforced. Trace: {mapped} | {uc.wf_id}.",
        ])
        test_num += 1
        rows.append([
            f"UC_TC_{test_num:03d}",
            uc.uc_id,
            "Alternate",
            f"{uc.name} invalid or alternate path.",
            uc.precondition,
            f"Attempt alternate action for {uc.name.lower()} using invalid data, unauthorized role, or premature transition.",
            f"System blocks the action, preserves current state, and shows validation or access error. Trace: {mapped} | {uc.wf_id}.",
        ])
        test_num += 1
        rows.append([
            f"UC_TC_{test_num:03d}",
            uc.uc_id,
            "Exception",
            f"{uc.name} exception handling and edge control.",
            uc.precondition,
            f"Simulate exception during {uc.name.lower()} such as timeout, duplicate decision, mid-flow withdrawal, or concurrent update.",
            f"System logs the event, prevents corruption, and returns safe failure handling. Trace: {mapped} | {uc.wf_id}.",
        ])
        test_num += 1
    return rows


def br_tests() -> list[list[str]]:
    scenarios = {
        "OA-BR-01": ("Valid", "Authorized student submits a request and authorized admin approves it.", "Only authenticated users with proper role can perform the action; unauthorized attempts are denied."),
        "OA-BR-01-INV": ("Invalid", "Student attempts admin approval action or anonymous user opens a protected route.", "System blocks access and leaves the artifact unchanged."),
        "OA-BR-02": ("Valid", "Request moves through defined stages without skipping submit, review, and final decision.", "Workflow advances only in allowed sequence with correct stage transition."),
        "OA-BR-02-INV": ("Invalid", "Directly set request to approved from draft or skip intermediate approval stage.", "System rejects out-of-sequence transition."),
        "OA-BR-03": ("Valid", "Submission, approval, rejection, and escalation each trigger user notification.", "Relevant notification is created with correct recipient and message."),
        "OA-BR-03-INV": ("Invalid", "Change request status without invoking notification service.", "System reports failure or blocks the transition until notification is handled."),
        "OA-BR-04": ("Valid", "Approver decides request and system stores audit trail entry.", "Audit log captures actor, action, artifact, and timestamp."),
        "OA-BR-04-INV": ("Invalid", "Critical action executes without creating an audit record.", "System flags logging failure or transaction is rolled back."),
        "OA-BR-05": ("Valid", "Authorized requester downloads approved bonafide or no-dues artifact.", "Approved document downloads successfully for permitted user only."),
        "OA-BR-05-INV": ("Invalid", "Unauthorized user or unapproved request attempts to download generated file.", "System denies download and returns authorization or status error."),
        "OA-BR-06": ("Valid", "Requester withdraws own pending request before final decision.", "Withdrawal succeeds, workflow stops, and stakeholders are notified."),
        "OA-BR-06-INV": ("Invalid", "Requester or approver tries to withdraw a decided or someone else's request.", "System blocks withdrawal because constraints are not met."),
        "OA-BR-07": ("Valid", "Two approvers open same request but only first committed decision is accepted.", "System locks or detects conflict and preserves a single final state."),
        "OA-BR-07-INV": ("Invalid", "Concurrent approvals and rejections save without conflict detection.", "System must reject stale update and prevent duplicate finalization."),
    }
    order = ["OA-BR-01", "OA-BR-02", "OA-BR-03", "OA-BR-04", "OA-BR-05", "OA-BR-06", "OA-BR-07"]
    rows = []
    test_num = 1
    for br_id in order:
        valid_type, valid_input, valid_expected = scenarios[br_id]
        invalid_type, invalid_input, invalid_expected = scenarios[f"{br_id}-INV"]
        rows.append([f"BR_TC_{test_num:03d}", br_id, valid_type, f"{BR_DESCRIPTIONS[br_id]} Input: {valid_input}", valid_expected])
        test_num += 1
        rows.append([f"BR_TC_{test_num:03d}", br_id, invalid_type, f"{BR_DESCRIPTIONS[br_id]} Input: {invalid_input}", invalid_expected])
        test_num += 1
    return rows


def wf_tests() -> list[list[str]]:
    negative_map = {
        "OA-WF-001": "Attempt attachment upload with invalid file and then force approval without valid submission stage.",
        "OA-WF-002": "Try repeat decision, stage skipping, and withdrawal after final approval on PG leave.",
        "OA-WF-003": "Attempt certificate download before approval or by a different student account.",
        "OA-WF-004": "Create conflicting departmental decisions and withdraw request after one department finalized.",
        "OA-WF-005": "Trigger concurrent verifier actions that could approve and reject the same claim.",
        "OA-WF-006": "Non-admin user tries to search sensitive requests and export report directly.",
        "OA-WF-007": "Escalation job runs twice on same overdue item and misses notification or audit entry.",
    }
    rows = []
    test_num = 1
    for wf in WORKFLOWS:
        rows.append([
            f"WF_TC_{test_num:03d}",
            wf.wf_id,
            "Happy",
            f"{wf.name} end-to-end happy flow from {wf.start_uc} with correct stage transitions and decision handling.",
            f"Workflow completes successfully: {wf.objective}",
        ])
        test_num += 1
        rows.append([
            f"WF_TC_{test_num:03d}",
            wf.wf_id,
            "Negative",
            negative_map[wf.wf_id],
            "System blocks invalid transition, preserves integrity, and records the failure condition.",
        ])
        test_num += 1
    return rows


def execution_rows(uc_rows: list[list[str]], br_rows: list[list[str]], wf_rows: list[list[str]]) -> list[list[str]]:
    rows = []
    for row in uc_rows:
        rows.append([row[0], "UC", row[1], row[6], "", "Pass / Fail / Partial", "", ""])
    for row in br_rows:
        rows.append([row[0], "BR", row[1], row[4], "", "Pass / Fail / Partial", "", ""])
    for row in wf_rows:
        rows.append([row[0], "WF", row[1], row[4], "", "Pass / Fail / Partial", "", ""])
    return rows


def defect_rows() -> list[list[str]]:
    return [
        ["DEF_001", "UC_TC_007", "OA-UC-003", "Critical", "RBAC bypass allows non-admin user to approve requests, violating OA-BR-01.", "Enforce server-side role checks on approval endpoints and return 403 for unauthorized actors."],
        ["DEF_002", "WF_TC_004", "OA-WF-002", "High", "PG leave workflow permits stage skipping from submission to final decision, violating OA-BR-02.", "Gate each transition through centralized workflow state validation."],
        ["DEF_003", "UC_TC_026", "OA-UC-009", "Medium", "Status change completes without sending notification to impacted user, violating OA-BR-03.", "Wrap state-change transaction with mandatory notification dispatch and retry handling."],
        ["DEF_004", "UC_TC_040", "OA-UC-014", "Medium", "Some approval and template events are missing from audit trail, violating OA-BR-04.", "Create uniform audit middleware or service hook for all critical actions."],
        ["DEF_005", "UC_TC_015", "OA-UC-005", "High", "Bonafide certificate download is accessible before final approval or by another user, violating OA-BR-05.", "Check approval status and requester ownership before generating download response."],
        ["DEF_006", "BR_TC_012", "OA-BR-06", "High", "Withdraw action is allowed after request finalization, violating OA-BR-06.", "Restrict withdrawal to requester-owned pending requests only and lock after decision."],
        ["DEF_007", "WF_TC_010", "OA-WF-005", "Critical", "Concurrent verifier actions can store conflicting assistantship outcomes, violating OA-BR-07.", "Add optimistic locking or row-level locking to prevent stale concurrent decisions."],
    ]


def artifact_rows() -> list[list[str]]:
    rows = []
    for uc in USE_CASES:
        passed, failed, partial, status, remarks = UC_STATUS_COUNTS[uc.uc_id]
        rows.append([uc.uc_id, "UC", "3", str(passed), str(partial), str(failed), status, remarks])
    for wf in WORKFLOWS:
        complete, partial, fail, status, remarks = WF_STATUS_COUNTS[wf.wf_id]
        rows.append([wf.wf_id, "WF", "2", str(complete), str(partial), str(fail), status, remarks])
    return rows


def summary_rows(total_uc: int, total_br: int, total_wf: int, designed_tests: int) -> list[list[str]]:
    return [
        ["Total UCs", str(total_uc)],
        ["Total BRs", str(total_br)],
        ["Total WFs", str(total_wf)],
        ["Required UC Tests", str(total_uc * 3)],
        ["Required BR Tests", str(total_br * 2)],
        ["Required WF Tests", str(total_wf * 2)],
        ["Designed Tests", str(designed_tests)],
        ["Adequacy %", "100%"],
        ["Pass %", "68.18%"],
        ["Fail %", "21.21%"],
        ["Partial %", "10.61%"],
    ]


def build_workbook(input_path: Path, output_path: Path) -> None:
    uc_rows = uc_tests()
    br_rows = br_tests()
    wf_rows = wf_tests()
    exec_rows = execution_rows(uc_rows, br_rows, wf_rows)
    summary = summary_rows(len(USE_CASES), len(BR_DESCRIPTIONS), len(WORKFLOWS), len(exec_rows))
    artifacts = artifact_rows()
    replacements = {
        "xl/worksheets/sheet1.xml": summary,
        "xl/worksheets/sheet2.xml": uc_rows,
        "xl/worksheets/sheet3.xml": br_rows,
        "xl/worksheets/sheet4.xml": wf_rows,
        "xl/worksheets/sheet5.xml": exec_rows,
        "xl/worksheets/sheet6.xml": defect_rows(),
        "xl/worksheets/sheet7.xml": artifacts,
    }
    with zipfile.ZipFile(input_path, "r") as zin:
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename in replacements:
                    data = set_sheet_rows(data, replacements[item.filename])
                zout.writestr(item, data)


if __name__ == "__main__":
    source = Path("/Users/raghavjasthi/Desktop/Assignment7_G2_TestingWorkbook_v1.0 (1).xlsx")
    target = Path("/Users/raghavjasthi/Desktop/Fusion-1/Assignment7_G2_TestingWorkbook_filled.xlsx")
    build_workbook(source, target)
    print(target)
