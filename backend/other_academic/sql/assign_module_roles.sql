-- Other Academic module role assignment SQL
-- Replace the variables and designation IDs/names as needed for your environment.
-- This module uses:
-- 1) other_academic_userprofile.role for API authorization
-- 2) globals_holdsdesignation for institute-wide designation mapping
-- 3) other_academic_assistantshipapprover for TA/Thesis/HoD assistantship approval chain

-- ============================================================================
-- 1. Set the target user
-- ============================================================================
SET @user_id = 5755;
SET @working_id = 5755;
SET @department = 'CSE';
SET @full_name = 'Dr. Example User';
SET @email = 'example.user@iiitdmj.ac.in';

-- ============================================================================
-- 2. Ensure the module profile exists and carries the module role
-- Choose one role at a time: hod / admin / acadadmin / ta_supervisor /
-- thesis_supervisor / dean_academic / director / librarian /
-- hostel_warden / mess_incharge / mess_warden
-- ============================================================================
UPDATE other_academic_userprofile
SET role = 'acadadmin',
    department = @department,
    updated_at = NOW()
WHERE user_id = @user_id;

INSERT INTO other_academic_userprofile (
    user_id,
    role,
    department,
    roll_no,
    is_pg_student,
    created_at,
    updated_at
)
SELECT
    @user_id,
    'acadadmin',
    @department,
    '',
    0,
    NOW(),
    NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM other_academic_userprofile
    WHERE user_id = @user_id
);

-- ============================================================================
-- 3. Assign institute designations in globals_holdsdesignation
-- Option A: exact style matching your sample query using known designation IDs
-- Replace the placeholder IDs with your actual globals_designation.id values.
-- ============================================================================
-- INSERT INTO globals_holdsdesignation (user_id, working_id, designation_id, held_at)
-- VALUES
--   (@user_id, @working_id, <HOD_DESIGNATION_ID>, NOW()),
--   (@user_id, @working_id, <ACADADMIN_DESIGNATION_ID>, NOW()),
--   (@user_id, @working_id, <LIBRARIAN_DESIGNATION_ID>, NOW()),
--   (@user_id, @working_id, <HOSTEL_WARDEN_DESIGNATION_ID>, NOW()),
--   (@user_id, @working_id, <MESS_INCHARGE_DESIGNATION_ID>, NOW()),
--   (@user_id, @working_id, <MESS_WARDEN_DESIGNATION_ID>, NOW()),
--   (@user_id, @working_id, <DEAN_ACADEMIC_DESIGNATION_ID>, NOW()),
--   (@user_id, @working_id, <DIRECTOR_DESIGNATION_ID>, NOW());

-- ============================================================================
-- 4. Safer designation assignment by name instead of hardcoded IDs
-- Run the lookup first, then adjust the names if your designation labels differ.
-- ============================================================================
-- SELECT id, name
-- FROM globals_designation
-- WHERE name IN ('HOD (CSE)', 'acadadmin', 'Librarian', 'Hostel Warden', 'Mess Incharge', 'Mess Warden', 'Dean Academic', 'Director');

INSERT INTO globals_holdsdesignation (user_id, working_id, designation_id, held_at)
SELECT @user_id, @working_id, gd.id, NOW()
FROM globals_designation gd
WHERE gd.name IN ('HOD (CSE)', 'acadadmin', 'Librarian', 'Hostel Warden', 'Mess Incharge', 'Mess Warden', 'Dean Academic', 'Director')
  AND NOT EXISTS (
      SELECT 1
      FROM globals_holdsdesignation ghd
      WHERE ghd.user_id = @user_id
        AND ghd.working_id = @working_id
        AND ghd.designation_id = gd.id
  );

-- ============================================================================
-- 5. Assistantship workflow approver mapping
-- TA Supervisor / Thesis Supervisor / HoD are read from other_academic_assistantshipapprover.
-- Add rows here if this user should appear in assistantship approver dropdowns.
-- ============================================================================
INSERT INTO other_academic_assistantshipapprover (
    name,
    role,
    department,
    email,
    is_active,
    created_at,
    updated_at
)
SELECT @full_name, 'ta_supervisor', @department, @email, 1, NOW(), NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM other_academic_assistantshipapprover
    WHERE name = @full_name
      AND role = 'ta_supervisor'
);

INSERT INTO other_academic_assistantshipapprover (
    name,
    role,
    department,
    email,
    is_active,
    created_at,
    updated_at
)
SELECT @full_name, 'thesis_supervisor', @department, @email, 1, NOW(), NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM other_academic_assistantshipapprover
    WHERE name = @full_name
      AND role = 'thesis_supervisor'
);

INSERT INTO other_academic_assistantshipapprover (
    name,
    role,
    department,
    email,
    is_active,
    created_at,
    updated_at
)
SELECT @full_name, 'hod', @department, @email, 1, NOW(), NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM other_academic_assistantshipapprover
    WHERE name = @full_name
      AND role = 'hod'
);

-- ============================================================================
-- 6. Example single-user all-role assignment for this module
-- Use this when one user must test all approval stages locally.
-- ============================================================================
-- UPDATE other_academic_userprofile
-- SET role = 'admin', department = @department, updated_at = NOW()
-- WHERE user_id = @user_id;
--
-- INSERT INTO globals_holdsdesignation (user_id, working_id, designation_id, held_at)
-- VALUES
--   (@user_id, @working_id, 15, NOW()),   -- HOD (example)
--   (@user_id, @working_id, 45, NOW()),   -- academic_user / admin-like role (example)
--   (@user_id, @working_id, 106, NOW());  -- deptadmin_cse (example)
