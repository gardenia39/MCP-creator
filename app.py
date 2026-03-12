"""Flask Web UI — 配置和管理 MCP Server"""

import json
import os
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

import yaml
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# 全局状态
server_process: subprocess.Popen | None = None
server_logs: deque = deque(maxlen=200)  # 最近200条日志
server_config: dict = {}


def read_process_output(proc: subprocess.Popen):
    """后台线程：持续读取子进程 stderr 输出"""
    try:
        for line in iter(proc.stderr.readline, ""):
            if line:
                server_logs.append(line.strip())
            if proc.poll() is not None:
                break
    except Exception:
        pass


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/start", methods=["POST"])
def start_server():
    global server_process, server_config

    if server_process and server_process.poll() is None:
        return jsonify({"ok": False, "msg": "Server 已在运行中"})

    data = request.json
    site_url = data.get("site_url", "").strip()
    site_name = data.get("site_name", "MySite").strip()
    max_pages = int(data.get("max_pages", 20))
    transport = data.get("transport", "stdio")
    host = data.get("host", "0.0.0.0").strip()
    port = int(data.get("port", 8000))

    if not site_url:
        return jsonify({"ok": False, "msg": "请填写网站 URL"})

    server_config = {
        "site_url": site_url,
        "site_name": site_name,
        "max_pages": max_pages,
        "transport": transport,
        "host": host,
        "port": port,
    }

    # 保存配置文件
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(server_config, f, allow_unicode=True)

    # 启动 MCP Server 子进程
    python_exe = str(Path(__file__).parent / ".venv" / "Scripts" / "python.exe")
    cmd = [
        python_exe, "-u",
        str(Path(__file__).parent / "server.py"),
        site_url,
        transport,
    ]

    env = os.environ.copy()
    env["MCP_SITE_NAME"] = site_name
    env["MCP_MAX_PAGES"] = str(max_pages)
    env["MCP_HOST"] = host
    env["MCP_PORT"] = str(port)

    server_logs.clear()
    server_logs.append(f"[UI] 正在启动 MCP Server ({transport} 模式)...")

    try:
        server_process = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE if transport == "stdio" else None,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=str(Path(__file__).parent),
        )
        # 后台读取日志
        t = threading.Thread(target=read_process_output, args=(server_process,), daemon=True)
        t.start()

        server_logs.append(f"[UI] Server 进程已启动 (PID: {server_process.pid})")
        if transport == "streamable-http":
            server_logs.append(f"[UI] HTTP 端点: http://{host}:{port}/mcp")

    except Exception as e:
        return jsonify({"ok": False, "msg": f"启动失败: {e}"})

    return jsonify({"ok": True, "msg": "Server 启动成功"})


@app.route("/stop", methods=["POST"])
def stop_server():
    global server_process

    if not server_process or server_process.poll() is not None:
        server_process = None
        return jsonify({"ok": False, "msg": "没有正在运行的 Server"})

    server_process.terminate()
    try:
        server_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server_process.kill()

    server_logs.append("[UI] Server 已停止")
    server_process = None
    return jsonify({"ok": True, "msg": "Server 已停止"})


@app.route("/status")
def status():
    running = server_process is not None and server_process.poll() is None
    return jsonify({
        "running": running,
        "logs": list(server_logs),
        "config": server_config,
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
