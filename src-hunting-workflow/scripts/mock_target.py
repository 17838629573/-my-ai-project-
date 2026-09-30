#!/usr/bin/env python3
# 本地 mock 靶场：仅用于验证 src_scout.py 的判据是否正确
from http.server import BaseHTTPRequestHandler, HTTPServer
import json, re
from urllib.parse import urlparse, parse_qs

ORDERS = {"1001": {"user": "A", "phone": "13800000001", "addr": "A的地址"},
          "1002": {"user": "B", "phone": "13900000002", "addr": "B的地址"}}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/order/detail":
            cookie = self.headers.get("Cookie", "")
            oid = q.get("orderId", [""])[0]
            if "session=" not in cookie:
                return self._send(401, json.dumps({"code": 401, "msg": "请先登录"}))
            return self._send(200, json.dumps({"code": 0, "data": ORDERS.get(oid, {})}))
        if u.path == "/api/user/list":
            # 故意未鉴权
            return self._send(200, json.dumps({"code": 0, "data": [
                {"id": 1, "phone": "13800000001"}, {"id": 2, "phone": "13900000002"}]}))
        if u.path == "/.git/config":
            return self._send(200, "[core]\n\trepositoryformatversion = 0\n", "text/plain")
        if u.path == "/swagger-ui.html":
            return self._send(200, "<html>swagger</html>", "text/html")
        return self._send(404, json.dumps({"code": 404, "msg": "not found"}))

    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(ln).decode(errors="ignore")
        u = urlparse(self.path)
        if u.path == "/api/comment/add":
            cookie = self.headers.get("Cookie", "")
            if "session=" not in cookie:
                return self._send(401, json.dumps({"code": 401, "msg": "unauthorized"}))
            try:
                obj = json.loads(raw)
            except Exception:
                obj = {}
            return self._send(200, json.dumps({"code": 0, "msg": "ok", "owner": obj.get("userId")}))
        return self._send(404, json.dumps({"code": 404}))


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8899), H).serve_forever()
