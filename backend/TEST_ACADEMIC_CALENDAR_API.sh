#!/bin/bash

# Academic Calendar Management - API Testing Guide
# This script demonstrates how to test all Academic Calendar APIs

API_BASE="http://127.0.0.1:8000/api/other-academic"
AUTH_TOKEN="YOUR_AUTH_TOKEN_HERE"

echo "======================================"
echo "Academic Calendar API Testing Guide"
echo "======================================"
echo ""

# Test 1: List all calendars
echo "Test 1: List all calendars"
echo "Command: curl \"$API_BASE/calendars/\""
echo "Expected: Array of calendar objects"
echo ""

# Test 2: List calendars with filters
echo "Test 2: List calendars with filters"
echo "Command: curl \"$API_BASE/calendars/?semester=1&academic_year=2023-24&window_type=registration\""
echo "Expected: Filtered calendar objects"
echo ""

# Test 3: Create new calendar (requires auth)
echo "Test 3: Create new calendar"
echo "Command: curl -X POST \"$API_BASE/calendars/create/\" \\"
echo "  -H \"Authorization: Token \$AUTH_TOKEN\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{"
echo "    \"title\": \"Test Calendar\","
echo "    \"window_type\": \"registration\","
echo "    \"description\": \"Test calendar\","
echo "    \"start_date\": \"2024-06-01\","
echo "    \"end_date\": \"2024-06-10\","
echo "    \"semester\": 2,"
echo "    \"academic_year\": \"2024-25\","
echo "    \"status\": \"upcoming\""
echo "  }'"
echo "Expected: 201 Created with calendar object"
echo ""

# Test 4: Get calendar details
echo "Test 4: Get calendar details"
echo "Command: curl \"$API_BASE/calendars/1/\""
echo "Expected: Single calendar object with all fields"
echo ""

# Test 5: Update calendar (requires auth)
echo "Test 5: Update calendar"
echo "Command: curl -X PUT \"$API_BASE/calendars/1/\" \\"
echo "  -H \"Authorization: Token \$AUTH_TOKEN\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"status\": \"closed\"}'"
echo "Expected: 200 OK with updated calendar"
echo ""

# Test 6: Delete calendar (requires auth)
echo "Test 6: Delete calendar"
echo "Command: curl -X DELETE \"$API_BASE/calendars/1/\" \\"
echo "  -H \"Authorization: Token \$AUTH_TOKEN\""
echo "Expected: 204 No Content"
echo ""

# Test 7: Get active calendar window
echo "Test 7: Get active calendar window"
echo "Command: curl \"$API_BASE/calendars/active/?window_type=registration&semester=1&academic_year=2023-24\""
echo "Expected: Single active calendar object or null"
echo ""

# Test 8: Validate action against calendar
echo "Test 8: Validate action"
echo "Command: curl -X POST \"$API_BASE/calendars/validate-action/\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"action\": \"registration\", \"semester\": 1, \"academic_year\": \"2023-24\"}'"
echo "Expected: {\"allowed\": true/false, \"message\": \"...\", \"calendar\": {...}}"
echo ""

# Test 9: Get upcoming windows
echo "Test 9: Get upcoming calendar windows"
echo "Command: curl \"$API_BASE/calendars/upcoming/?days=30&semester=1&academic_year=2023-24\""
echo "Expected: Array of upcoming calendar objects"
echo ""

echo ""
echo "======================================"
echo "Sample cURL Commands for Testing"
echo "======================================"
echo ""

echo "# Get calendars"
echo "curl http://127.0.0.1:8000/api/other-academic/calendars/"
echo ""

echo "# Get calendars for Semester 1, Academic Year 2023-24"
echo "curl \"http://127.0.0.1:8000/api/other-academic/calendars/?semester=1&academic_year=2023-24\""
echo ""

echo "# Validate registration"
echo "curl -X POST http://127.0.0.1:8000/api/other-academic/calendars/validate-action/ \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"action\": \"registration\", \"semester\": 1, \"academic_year\": \"2023-24\"}'"
echo ""

echo "# Get active registration window"
echo "curl \"http://127.0.0.1:8000/api/other-academic/calendars/active/?window_type=registration\""
echo ""

echo "# Get upcoming windows (next 60 days)"
echo "curl \"http://127.0.0.1:8000/api/other-academic/calendars/upcoming/?days=60\""
echo ""

echo ""
echo "======================================"
echo "Testing with JavaScript/Fetch"
echo "======================================"
echo ""

cat << 'EOF'
// List all calendars
fetch('http://127.0.0.1:8000/api/other-academic/calendars/')
  .then(r => r.json())
  .then(calendars => console.log(calendars));

// Validate action
fetch('http://127.0.0.1:8000/api/other-academic/calendars/validate-action/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    action: 'registration',
    semester: 1,
    academic_year: '2023-24'
  })
})
.then(r => r.json())
.then(result => console.log(result));

// Get upcoming windows
fetch('http://127.0.0.1:8000/api/other-academic/calendars/upcoming/?days=30')
  .then(r => r.json())
  .then(windows => console.log(windows));
EOF

echo ""
echo ""
echo "======================================"
echo "Response Examples"
echo "======================================"
echo ""

cat << 'EOF'
# List Calendars Response
[
  {
    "id": 1,
    "title": "Spring 2024 Registration",
    "window_type": "registration",
    "description": "Course registration for Spring 2024",
    "start_date": "2024-01-15",
    "end_date": "2024-01-25",
    "semester": 1,
    "academic_year": "2023-24",
    "status": "active",
    "created_by_username": "admin",
    "created_at": "2023-12-20T10:30:00Z",
    "updated_at": "2023-12-20T10:30:00Z",
    "days_remaining": 5,
    "is_active": true
  },
  ...
]

# Validate Action Response (Allowed)
{
  "allowed": true,
  "message": "registration is allowed",
  "calendar": {
    "id": 1,
    "title": "Spring 2024 Registration",
    "start_date": "2024-01-15",
    "end_date": "2024-01-25",
    "status": "active",
    "days_remaining": 5,
    "is_active": true
  }
}

# Validate Action Response (Not Allowed)
{
  "allowed": false,
  "message": "registration is not currently allowed",
  "calendar": null
}

# Create Calendar Response
{
  "message": "Academic calendar created successfully",
  "data": {
    "id": 10,
    "title": "New Calendar",
    "window_type": "other",
    "start_date": "2024-06-01",
    "end_date": "2024-06-10",
    "semester": 2,
    "academic_year": "2024-25",
    "status": "upcoming",
    "days_remaining": 158,
    "is_active": false
  }
}
EOF

echo ""
echo ""
echo "======================================"
echo "Testing Checklist"
echo "======================================"
echo ""
echo "Frontend Testing:"
echo "[ ] Visit http://localhost:5173/"
echo "[ ] Login with admin account"
echo "[ ] Navigate to Academic Module"
echo "[ ] Open 'Calendar Management' tab"
echo "[ ] See list of academic calendars"
echo "[ ] Create a new calendar"
echo "[ ] Edit an existing calendar"
echo "[ ] Delete a calendar"
echo "[ ] Check calendar validator in registration"
echo ""

echo "Backend Testing:"
echo "[ ] Visit http://127.0.0.1:8000/admin/"
echo "[ ] Login with admin account"
echo "[ ] Go to 'Other Academic > Academic Calendars'"
echo "[ ] See list of all calendars"
echo "[ ] Create new calendar in admin"
echo "[ ] Edit existing calendar"
echo "[ ] Delete calendar"
echo "[ ] Test API endpoints with curl"
echo ""

echo "Integration Testing:"
echo "[ ] Check registration window validation"
echo "[ ] Check add/drop period validation"
echo "[ ] Check upcoming events on dashboard"
echo "[ ] Verify calendar data in database"
echo "[ ] Test with different semesters/years"
echo ""

echo "Performance Testing:"
echo "[ ] Check response time for list endpoint"
echo "[ ] Check response time for validate endpoint"
echo "[ ] Check database query count"
echo "[ ] Test with large number of calendars"
echo ""
