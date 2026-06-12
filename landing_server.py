#!/usr/bin/env python3
"""只服务 landing 页面的独立服务器 + 预约API代理"""
import os, sys, json, shutil

# ── 简单的 WSGI 服务器 ──
from wsgiref.simple_server import make_server

BASE = os.path.dirname(os.path.abspath(__file__))
LANDING_HTML = os.path.join(BASE, "templates", "landing.html")
WAITLIST_FILE = os.path.join(BASE, ".waitlist_emails.txt")

def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET")

    # POST /api/waitlist — 收集邮箱
    if path == "/api/waitlist" and method == "POST":
        try:
            length = int(environ.get("CONTENT_LENGTH", 0))
            body = json.loads(environ["wsgi.input"].read(length).decode())
            email = (body.get("email") or "").strip().lower()
            if not email or "@" not in email:
                return json_resp(start_response, 400, {"error": "无效邮箱"})
            exists = False
            if os.path.exists(WAITLIST_FILE):
                with open(WAITLIST_FILE) as f:
                    exists = email in f.read()
            if not exists:
                with open(WAITLIST_FILE, "a") as f:
                    f.write(email + "\n")
                os.chmod(WAITLIST_FILE, 0o600)
            return json_resp(start_response, 200, {"ok": True, "new": not exists})
        except Exception as e:
            return json_resp(start_response, 500, {"error": str(e)})

    # GET /api/waitlist — 查看已收集邮箱（仅限本地）
    if path == "/api/waitlist" and method == "GET":
        emails = []
        if os.path.exists(WAITLIST_FILE):
            with open(WAITLIST_FILE) as f:
                emails = [line.strip() for line in f if line.strip()]
        return json_resp(start_response, 200, {
            "total": len(emails),
            "emails": emails,
            "file": WAITLIST_FILE
        })

    # GET / — 返回 landing.html
    if path == "/" or path == "":
        if os.path.exists(LANDING_HTML):
            with open(LANDING_HTML, "rb") as f:
                html = f.read()
            start_response("200 OK", [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Cache-Control", "no-cache, no-store, must-revalidate"),
                ("Content-Length", str(len(html))),
            ])
            return [html]
        else:
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"Landing page not found"]

    # 其他路径 404
    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"Not Found"]

def json_resp(start_response, status, data):
    body = json.dumps(data, ensure_ascii=False).encode()
    start_response(f"{status} OK" if status == 200 else f"{status} Error", [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
    ])
    return [body]

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    httpd = make_server("127.0.0.1", port, app)
    print(f"Landing server on :{port}")
    httpd.serve_forever()
