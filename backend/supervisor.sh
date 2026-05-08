#!/bin/bash

# Supervisor management script for Django backend

PROJECT_DIR="/Users/raghavjasthi/Desktop/Fusion-1"
VENV="$PROJECT_DIR/venv"
SUPERVISORD_CONF="$PROJECT_DIR/supervisord.conf"

# Activate virtual environment
source "$VENV/bin/activate"

case "$1" in
  start)
    echo "Starting supervisor..."
    supervisord -c "$SUPERVISORD_CONF"
    echo "Supervisor started. Use 'supervisorctl -c $SUPERVISORD_CONF' to manage processes."
    ;;
  stop)
    echo "Stopping supervisor..."
    supervisorctl -c "$SUPERVISORD_CONF" shutdown
    echo "Supervisor stopped."
    ;;
  restart)
    echo "Restarting supervisor..."
    supervisorctl -c "$SUPERVISORD_CONF" shutdown
    sleep 2
    supervisord -c "$SUPERVISORD_CONF"
    echo "Supervisor restarted."
    ;;
  status)
    echo "Supervisor status:"
    supervisorctl -c "$SUPERVISORD_CONF" status
    ;;
  django-restart)
    echo "Restarting Django backend..."
    supervisorctl -c "$SUPERVISORD_CONF" restart django-backend
    ;;
  django-stop)
    echo "Stopping Django backend..."
    supervisorctl -c "$SUPERVISORD_CONF" stop django-backend
    ;;
  django-start)
    echo "Starting Django backend..."
    supervisorctl -c "$SUPERVISORD_CONF" start django-backend
    ;;
  shell)
    echo "Opening supervisorctl shell..."
    supervisorctl -c "$SUPERVISORD_CONF"
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|django-restart|django-stop|django-start|shell}"
    echo ""
    echo "Commands:"
    echo "  start           - Start supervisor daemon"
    echo "  stop            - Stop supervisor daemon"
    echo "  restart         - Restart supervisor daemon"
    echo "  status          - Show status of all supervised processes"
    echo "  django-restart  - Restart Django backend process"
    echo "  django-stop     - Stop Django backend process"
    echo "  django-start    - Start Django backend process"
    echo "  shell           - Open interactive supervisorctl shell"
    exit 1
    ;;
esac

exit 0
