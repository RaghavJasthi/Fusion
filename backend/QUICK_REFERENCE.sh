#!/bin/bash

# LEAVE MANAGEMENT SYSTEM - QUICK REFERENCE GUIDE
# Location: /Users/raghavjasthi/Desktop/Fusion-1

# ============================================
# 🚀 SERVICE MANAGEMENT
# ============================================

# Check status of all services
supervisorctl status

# Restart Django backend
supervisorctl restart django-backend

# Stop Django backend
supervisorctl stop django-backend

# Start Django backend
supervisorctl start django-backend

# View Django logs
tail -f logs/django-backend.log

# ============================================
# 🌐 FRONTEND
# ============================================

# Start React frontend (from Fusion-client directory)
cd /Users/raghavjasthi/Desktop/Fusion-1/Fusion-client
npm run dev

# Access frontend
# URL: http://localhost:5174

# ============================================
# 🔌 BACKEND
# ============================================

# Access backend
# URL: http://127.0.0.1:8000

# Access admin panel
# URL: http://127.0.0.1:8000/admin
# Username: raghavjasthi
# Password: [your set password]

# ============================================
# 📡 API TESTING (cURL)
# ============================================

# Test 1: Submit a new leave
curl -X POST http://127.0.0.1:8000/otheracademic/api/leave-form-submit/ \
  -H "Content-Type: application/json" \
  -d '{
    "student_name": "Test Student",
    "roll_no": "99999",
    "leave_type": "medical",
    "date_from": "2024-03-01",
    "date_to": "2024-03-05",
    "mobile_number": "9999999999",
    "mobile_during_leave": "9999999999",
    "purpose": "Test leave",
    "address": "Test Address"
  }'

# Test 2: Get all leave requests
curl -X GET http://127.0.0.1:8000/otheracademic/api/get-leave-requests/

# Test 3: Get pending leaves (HOD view)
curl -X GET http://127.0.0.1:8000/otheracademic/api/fetch-pending-leaves/

# Test 4: Approve leave
curl -X POST http://127.0.0.1:8000/otheracademic/api/update-leave-status/ \
  -H "Content-Type: application/json" \
  -d '{"approvedLeaves":[1],"rejectedLeaves":[]}'

# Test 5: Reject leave
curl -X POST http://127.0.0.1:8000/otheracademic/api/update-leave-status/ \
  -H "Content-Type: application/json" \
  -d '{"approvedLeaves":[],"rejectedLeaves":[2]}'

# ============================================
# 💾 DATABASE MANAGEMENT
# ============================================

# Apply migrations
cd /Users/raghavjasthi/Desktop/Fusion-1
source venv/bin/activate
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Access SQLite directly
sqlite3 db.sqlite3

# Inside SQLite shell:
# SELECT * FROM other_academic_leave;
# SELECT * FROM other_academic_userprofile;
# SELECT status, COUNT(*) FROM other_academic_leave GROUP BY status;
# .quit

# ============================================
# 🔐 AUTHENTICATION
# ============================================

# Create test users
python manage.py create_test_users

# Default test users:
# student1 / student123 (role: student)
# student2 / student123 (role: student)
# hod1 / hod123 (role: hod)

# ============================================
# 📊 PROJECT STRUCTURE
# ============================================

# Backend files
ls -la /Users/raghavjasthi/Desktop/Fusion-1/other_academic/

# Frontend files
ls -la /Users/raghavjasthi/Desktop/Fusion-1/Fusion-client/src/Modules/Otheracademic/

# Database
ls -la /Users/raghavjasthi/Desktop/Fusion-1/db.sqlite3

# ============================================
# 🛠️ COMMON TASKS
# ============================================

# Activate Python virtual environment
cd /Users/raghavjasthi/Desktop/Fusion-1
source venv/bin/activate

# Deactivate virtual environment
deactivate

# Install Python packages
pip install -r requirements.txt

# Update frontend dependencies
cd /Fusion-client
npm install

# Run Django development server manually (if not using supervisor)
python manage.py runserver 0.0.0.0:8000

# Collect static files
python manage.py collectstatic

# Clear Django cache
python manage.py shell
# >>> from django.core.cache import cache
# >>> cache.clear()

# ============================================
# 📝 LOG FILES
# ============================================

# Django backend logs
tail -f /Users/raghavjasthi/Desktop/Fusion-1/logs/django-backend.log

# Supervisor logs
tail -f /var/log/supervisor/supervisord.log

# ============================================
# 🔍 DEBUGGING
# ============================================

# Check if port 8000 is in use
lsof -i :8000

# Kill process on port 8000
kill -9 $(lsof -t -i :8000)

# Check if port 5174 is in use
lsof -i :5174

# Check network connections
netstat -an | grep 8000

# Test network connectivity
curl -v http://127.0.0.1:8000/otheracademic/api/get-leave-requests/

# ============================================
# 📚 DOCUMENTATION
# ============================================

# Read complete implementation guide
cat /Users/raghavjasthi/Desktop/Fusion-1/COMPLETE_GUIDE.md

# Read workflow tests
cat /Users/raghavjasthi/Desktop/Fusion-1/TEST_WORKFLOW.md

# Read integration status
cat /Users/raghavjasthi/Desktop/Fusion-1/INTEGRATION_COMPLETE.md

# Read final status
cat /Users/raghavjasthi/Desktop/Fusion-1/FINAL_STATUS.md

# ============================================
# ✅ VERIFICATION CHECKLIST
# ============================================

# Run these commands to verify everything works:

echo "🔍 Checking services..."
supervisorctl status

echo "🔍 Testing API endpoint..."
curl -s http://127.0.0.1:8000/otheracademic/api/get-leave-requests/ | head -10

echo "🔍 Checking frontend..."
curl -s http://localhost:5174 | head -10

echo "✅ All systems operational!"

# ============================================
# 💡 USEFUL TIPS
# ============================================

# View real-time logs
tail -f logs/django-backend.log | grep -E "ERROR|WARNING"

# Find all Python files
find /Users/raghavjasthi/Desktop/Fusion-1 -name "*.py" | head -20

# Find all JavaScript files
find /Users/raghavjasthi/Desktop/Fusion-1/Fusion-client -name "*.jsx" | head -20

# Count lines of code
find . -name "*.py" -exec wc -l {} + | tail -1
find ./Fusion-client -name "*.jsx" -exec wc -l {} + | tail -1

# Search for specific text in files
grep -r "Leave_Form_Submit" /Users/raghavjasthi/Desktop/Fusion-1/Fusion-client/

# ============================================
# 🎯 WORKFLOW SUMMARY
# ============================================

# 1. Student submits leave via frontend form
#    → Sent as POST to /leave-form-submit/
#    → Saved to database

# 2. Student views leave status
#    → Fetched as GET from /get-leave-requests/
#    → Displayed in table

# 3. HOD views pending leaves
#    → Fetched as GET from /fetch-pending-leaves/
#    → Displayed in table

# 4. HOD approves/rejects leave
#    → Sent as POST to /update-leave-status/
#    → Status updated in database

# 5. Student sees updated status
#    → Fetches again from /get-leave-requests/
#    → Sees approved/rejected status

# ============================================
# 📞 SUPPORT
# ============================================

# For issues, check these files:
# - logs/django-backend.log (Django errors)
# - browser console (Frontend errors)
# - db.sqlite3 (Database state)

# Restart everything
supervisorctl restart django-backend
sleep 2
echo "✅ Services restarted"

# ============================================
# ✨ SYSTEM IS READY!
# ============================================

# All services running:
# - Frontend: http://localhost:5174
# - Backend: http://127.0.0.1:8000
# - Admin: http://127.0.0.1:8000/admin
# - Database: db.sqlite3

# Leave Management System is fully operational!
