#!/bin/bash
BACKUP_DIR="/opt/family-menu/backups"
mkdir -p "$BACKUP_DIR"
cp /opt/family-menu/menu.db "$BACKUP_DIR/menu_$(date +%Y%m%d_%H%M%S).db"
# Keep only last 30 backups
ls -t "$BACKUP_DIR"/*.db 2>/dev/null | tail -n +31 | xargs -r rm
