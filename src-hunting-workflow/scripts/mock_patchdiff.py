#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mock_patchdiff.py —— 补丁前后对比的本地靶场

同时起两个服务模拟「修复前版本」和「修复后版本」：
  :8901 = 修复前（漏洞存在）
  :8902 = 修复后（加了校验）

用于验证 src_patchdiff.py 能否正确定位「新增的拒绝」= 校验点。
"""

import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.parse import urlparse, parse_qs

# 模拟：修复后新增的校验
#  key: (method, path前缀)  →  (修复前状态, 修复后状态, 修复后拒绝消息)


class Handler:
    def __init__(self, patched):
        self.patched = patched  # True = 修复后版本

    def handle(self, h, method, u, q, body, headers):
        path = u.path

        def send(code, obj, ctype="application/json"):
            b = json.dumps(obj, ensure_ascii=False).encode() if not isinstance(obj, bytes) else obj
            h.send_response(code)
            h.send_header("Content-Type", ctype)
            h.send_header("Content-Length", str(len(b)))
            h.end_headers()
            h.wfile.write(b)

        # 1. 路径穿越：修复后校验
        if path.startswith("/api/file"):
            name = q.get("name", [""])[0]
            if self.patched and (".." in name or "%2f" in name.lower()):
                return send(400, {"error": "invalid name: path traversal not permitted; "
                                           "name must be under allowed_dir"})
            return send(200, {"data": "file-content-of-" + name})

        # 2. 越界/负数 ID：修复后校验
        m = re.match(r"^/api/items/(-?\d+)$", path)
        if m:
            iid = m.group(1)
            if self.patched and (not iid.lstrip("-").isdigit() or int(iid) <= 0
                                 or int(iid) > 10000):
                return send(400, {"error": "invalid item_id: must be positive integer "
                                           "and owned by current user"})
            return send(200, {"id": iid, "name": "item-" + iid, "owner": "someone"})

        # 3. 管理接口：修复前未授权可访问，修复后要求鉴权
        if path.startswith("/api/admin"):
            if self.patched and "cookie" not in {k.lower() for k in headers}:
                return send(403, {"error": "forbidden: admin scope required; "
                                           "unauthorized access denied"})
            return send(200, {"users": [{"id": 1, "phone": "13800000001"}]})

        # 4. 内部头覆盖：修复后剥离
        if path.startswith("/api/items"):
            if self.patched and any(k.lower().startswith("x-internal")
                                    or k.lower() == "x-tenant-id" for k in headers):
                return send(400, {"error": "invalid request: internal header "
                                           "X-Internal-*/X-Tenant-Id not allowed from client"})
            return send(200, {"items": [{"id": 1}, {"id": 2}]})

        # 5. Actuator：修复后关闭
        if path.startswith("/actuator"):
            if self.patched:
                return send(404, {"error": "not found"})
            return send(200, {"env": {"DB_PASSWORD": "secret", "AK": "xxxx"}})

        # 6. 危险方法：修复后拒绝
        if method in ("DELETE", "PUT", "TRACE") and self.patched:
            return send(405, {"error": "method not allowed: " + method +
                              " is unsupported on this resource"})

        # 7. Swagger：修复后关闭
        if path.startswith("/v2/api-docs") or path.startswith("/swagger"):
            if self.patched:
                return send(404, {"error": "not found"})
            return send(200, {"paths": {"/api/admin/users": {}, "/api/items": {}}})

        # 8. 老版本前缀：修复后下线（这是"修复后反而变了"的典型）
        if path.startswith("/v1/"):
            if self.patched:
                return send(410, {"error": "deprecated: /v1/ API has been removed"})
            return send(200, {"legacy": True, "items": [{"id": 1, "secret": "old-logic"}]})

        # 9. 未授权资源：修复后加鉴权
        if path.startswith("/api/orders"):
            if self.patched:
                return send(401, {"error": "unauthorized: valid session required"})
            return send(200, {"orders": [{"id": "o1", "phone": "13900000002"}]})

        if path.startswith("/admin"):
            if self.patched:
                return send(403, {"error": "forbidden"})
            return send(200, {"page": "admin-login"})

        return send(404 if self.patched else 404, {"code": 404, "msg": "not found"})


def make_server(port, patched):
    h = Handler(patched)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _dispatch(self, method):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            ln = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(ln).decode(errors="ignore") if ln else ""
            h.handle(self, method, u, q, body, dict(self.headers))

        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

        def do_PUT(self):
            self._dispatch("PUT")

        def do_DELETE(self):
            self._dispatch("DELETE")

        def do_OPTIONS(self):
            self._dispatch("OPTIONS")

        def do_TRACE(self):
            self._dispatch("TRACE")

    return HTTPServer(("127.0.0.1", port), H)


if __name__ == "__main__":
    s1 = make_server(8901, patched=False)
    s2 = make_server(8902, patched=True)
    print("[*] 修复前版本 : http://127.0.0.1:8901")
    print("[*] 修复后版本 : http://127.0.0.1:8902")
    Thread(target=s1.serve_forever, daemon=True).start()
    s2.serve_forever()
