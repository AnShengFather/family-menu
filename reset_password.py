#!/usr/bin/env python3
"""重置用户密码"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app, db, User

if len(sys.argv) < 3:
    print("用法: python3 reset_password.py <email> <新密码>")
    sys.exit(1)

email = sys.argv[1].strip().lower()
pwd = sys.argv[2]

with app.app_context():
    user = User.query.filter_by(email=email).first()
    if not user:
        print(f"用户 {email} 不存在")
        sys.exit(1)
    user.set_password(pwd)
    db.session.commit()
    print(f"✅ 用户 {email} 密码已重置")
