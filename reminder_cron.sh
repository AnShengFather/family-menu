#!/bin/bash
# Called by cron at 16:00 daily to trigger a reminder
PASS=$(cat /opt/family-menu/.admin_pass)
curl -s -X POST http://127.0.0.1:5000/api/reminder \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $PASS" \
  -d '{"token":"'"$PASS"'"}' > /dev/null
