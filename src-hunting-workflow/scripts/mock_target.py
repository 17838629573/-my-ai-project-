#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mock_target.py —— 本地模拟目标，用于验证 rk_* 工具链
完全无害：只监听 127.0.0.1，复现本项目遇到的关键分流场景。
场景:
  /<random>/           -> 404·<LEN-1693>  网关层模板
  /<random>.jsp        -> 404·<LEN-2455>  应用层模板
  /system/             -> 200·<LEN-912>   登录墙
  /examples/           -> 404·<LEN-1693>  网关拦（目录形态）
  /examples/index.jsp  -> 404·<LEN-2455>  穿透（文件形态）  <-- 本项目栽过的坑
  <APPROOT>/public/a.html  -> 200·<LEN-577>   filter 拦
  <APPROOT>/public/a.jsp   -> 200        放行             <-- jwmis 栽过的坑
  /docs/               -> 404·<LEN-649>   原生 Tomcat 页（页脚含 Apache Tomcat/9.0.99）
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import re

def pad(n, seed):
    s = f"<!-- {seed} -->\n" + ("x" * 60 + "\n") * ((n // 61) + 1)
    return s[:n].encode()

GW404 = pad(1693, "gateway-404")
APP404 = pad(2455, "app-404")
AUTH = pad(912, "system-login")
FILTER = b'<script>alert(\'<!-- 1 -->credential invalid\');window.top.location.href=\'<APPROOT>/\';</script>' + b'y' * (577 - 76)
NATIVE = b'<html><head><title>404</title></head><body><h1>404 - Not Found</h1><hr><h3>Apache Tomcat/9.0.99</h3></body></html>'

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, body, ct="text/html;charset=UTF-8"):
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p.startswith("/system"):
            return self.send(200, AUTH)
        if p.startswith("/docs") or p == "/manager/html":
            return self.send(404, NATIVE)
        if p.startswith("<APPROOT>/public/"):
            if p.endswith(".jsp"):
                return self.send(200, b"<html>public jsp ok</html>")
            return self.send(200, FILTER)
        if p.startswith("/examples/"):
            # 目录形态网关拦，文件形态穿透
            if p.endswith(".jsp"):
                return self.send(404, APP404)
            return self.send(404, GW404)
        if p.endswith(".jsp"):
            return self.send(404, APP404)
        if p == "/":
            return self.send(200, pad(4321, "index"))
        return self.send(404, GW404)

if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8899), H).serve_forever()
