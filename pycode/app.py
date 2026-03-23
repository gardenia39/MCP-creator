
import os
import sys
import json
import queue
import subprocess
import threading
from pathlib import Path
import urllib.request

from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = "mcp_creater_secret"

BASE_DIR = Path(__file__).parent
PROFILES_FILE = BASE_DIR / "profiles.json"
CACHE_FILE = BASE_DIR / "mcp_cache.json"

# 全局进程状态
_proc = None
_log_queue = queue.Queue()
_status = {"running": False, "endpoint": ""}

# 后台状态
scheduler = BackgroundScheduler()
scheduler.start()

def _load_profiles() -> dict:
    if PROFILES_FILE.exists():
        try:
            with open(PROFILES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_profiles(data: dict):
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _enqueue_log(text: str):
    _log_queue.put(text)


def _read_stderr(proc):
    try:
        for line in iter(proc.stderr.readline, ""):
            if line:
                _enqueue_log(line.rstrip())
    except Exception:
        pass
    _enqueue_log("[UI] 子进程输出结束")


def _periodic_scrape(src, stype, pages, css_sel):
    _enqueue_log("[UI] 正在执行后台定时更新任务，抓取最新数据")
    try:
        if stype == "url":
            from scraper import scrape_site_sync
            res = scrape_site_sync(src, int(pages), css_sel)
        else:
            from scraper import read_local_folder_sync
            res = read_local_folder_sync(src, int(pages))
            
        if res:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False)
            _enqueue_log(f"[UI] 后台定时抓取完成，更新了 {len(res)} 条记录到缓存！")
    except Exception as e:
         _enqueue_log(f"[ERR] 后台抓取失败：{e}")


# 页面

@app.route("/")
def index():
    profiles = _load_profiles()
    return render_template("index.html", profiles=profiles)


# API

@app.route("/api/select_folder", methods=["GET"])
def select_folder():
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        folder_path = filedialog.askdirectory(title="选择文件夹")
        root.destroy()
        
        if folder_path:
            return jsonify({"ok": True, "path": folder_path})
        else:
            return jsonify({"ok": False, "msg": "用户取消了选择"})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"无法打开文件夹选择对话框: {str(e)}"})


@app.route("/api/profiles", methods=["GET"])
def get_profiles():
    return jsonify(_load_profiles())


@app.route("/api/profiles", methods=["POST"])
def save_profile():
    body = request.get_json()
    name = (body.get("name") or "Unnamed").strip()
    profiles = _load_profiles()
    profiles[name] = body
    _save_profiles(profiles)
    return jsonify({"ok": True, "name": name})


@app.route("/api/profiles/<name>", methods=["DELETE"])
def delete_profile(name: str):
    profiles = _load_profiles()
    profiles.pop(name, None)
    _save_profiles(profiles)
    return jsonify({"ok": True})


@app.route("/api/start", methods=["POST"])
def start_server():
    global _proc, _status

    if _proc and _proc.poll() is None:
        return jsonify({"ok": False, "msg": "服务已在运行中"}), 400

    body = request.get_json()
    src = (body.get("source") or "").strip()
    if not src:
        return jsonify({"ok": False, "msg": "请填写来源（网址或路径）"}), 400

    stype = body.get("source_type", "url")
    name = (body.get("name") or "MySite").strip()
    pages = str(body.get("pages") or "20")
    css_sel = body.get("css", "")
    transport = body.get("transport", "stdio")
    host = body.get("host", "0.0.0.0")
    port = str(body.get("port", "8000"))

    # 清旧缓存
    if CACHE_FILE.exists():
        try:
            CACHE_FILE.unlink()
        except Exception:
            pass

    venv_python = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    python_exe = str(venv_python) if venv_python.exists() else sys.executable
    server_script = str(BASE_DIR / "server.py")

    env = os.environ.copy()
    env.update(
        MCP_SOURCE_TYPE=stype,
        MCP_SITE_NAME=name,
        MCP_MAX_PAGES=pages,
        MCP_CSS_SELECTOR=css_sel,
        MCP_HOST=host,
        MCP_PORT=port,
        PYTHONIOENCODING="utf-8",
    )

    _enqueue_log(f"[UI] 正在启动 MCP Server ({transport} 模式)...")

    _proc = subprocess.Popen(
        [python_exe, "-u", server_script, src, transport],
        stderr=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        env=env,
        cwd=str(BASE_DIR),
        encoding="utf-8",
        errors="replace",
    )

    _enqueue_log(f"[UI] Server 进程已启动 (PID: {_proc.pid})")
    
    # 注册定时刷新任务 
    scheduler.remove_all_jobs()
    scheduler.add_job(
        _periodic_scrape, 
        'interval', 
        hours=24, 
        args=[src, stype, pages, css_sel], 
        id='auto_scrape'
    )
    _enqueue_log("[UI] 已开启后台定时任务：每 24 小时自动更新数据")

    if transport == "streamable-http":
        disp_host = "127.0.0.1" if host == "0.0.0.0" else host
        endpoint = f"http://{disp_host}:{port}/mcp"
    else:
        endpoint = ""

    _status["running"] = True
    _status["endpoint"] = endpoint

    threading.Thread(target=_read_stderr, args=(_proc,), daemon=True).start()

    return jsonify({"ok": True, "pid": _proc.pid, "endpoint": endpoint})


@app.route("/api/stop", methods=["POST"])
def stop_server():
    global _proc, _status
    if not _proc or _proc.poll() is not None:
        return jsonify({"ok": False, "msg": "服务未在运行"}), 400

    _proc.terminate()
    try:
        _proc.wait(timeout=4)
    except Exception:
        _proc.kill()

    scheduler.remove_all_jobs()
    _enqueue_log("[UI] Server 已停止，定时更新任务已取消")
    _status["running"] = False
    _status["endpoint"] = ""
    _proc = None
    return jsonify({"ok": True})


@app.route("/api/status", methods=["GET"])
def get_status():
    running = bool(_proc and _proc.poll() is None)
    if not running and _status["running"]:
        _status["running"] = False
        _status["endpoint"] = ""
    return jsonify({"running": _status["running"], "endpoint": _status["endpoint"]})


@app.route("/api/logs")
def stream_logs():
    def generate():
        yield "retry: 1000\n\n"
        while True:
            try:
                line = _log_queue.get(timeout=15)
                yield f"data: {line}\n\n"
            except queue.Empty:
                yield ": heartbeat\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json()
    query = (body.get("query") or "").strip()
    api_key = (body.get("api_key") or "").strip()
    api_url = (body.get("api_url") or "https://open.bigmodel.cn/api/paas/v4/chat/completions").strip()
    history = body.get("history") or []

    if not query:
        return jsonify({"ok": False, "msg": "消息不能为空"}), 400
    if not api_key:
        return jsonify({"ok": False, "msg": "请填写 API Key"}), 400
    if not CACHE_FILE.exists():
        return jsonify({"ok": False, "msg": "尚未抓取数据，请先启动服务"}), 400

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            pages = json.load(f)
    except Exception:
        pages = []

    try:
        import jieba
        from rank_bm25 import BM25Okapi
        
        chunks = []
        for p in pages:
            content = p.get("content", "")
            paras = [para.strip() for para in content.split('\n') if len(para.strip()) > 30]
            if not paras:
                paras = [content[:500]]
            for para in paras:
                chunks.append({"title": p.get("title"), "url": p.get("url"), "text": para})
                
        if not chunks:
            raise ValueError("没有可供检索的有效文本")

        # 对切片和查询分词
        tokenized_corpus = [list(jieba.cut(c["text"])) for c in chunks]
        bm25 = BM25Okapi(tokenized_corpus)
        tokenized_query = list(jieba.cut(query))
        
        # 取评分最高的Top3内容
        top_n = bm25.get_top_n(tokenized_query, chunks, n=3)
        snippets = [f"【页面】{c['title']}\n【来源】{c['url']}\n【内容片段】\n{c['text']}" for c in top_n]
        context_text = "\n\n---\n\n".join(snippets)
        
    except Exception as e:
        print(f"BM25 RAG 降级: {e}")
        snippets = []
        for p in pages:
            c = p.get("content", "")
            if query.lower() in c.lower() or len(snippets) < 3:
                snippets.append(f"标题：{p.get('title')}\n网址：{p.get('url')}\n内容：\n{c[:1500]}")
        context_text = "\n\n---\n\n".join(snippets)[:10000]

    system_msg = (
        "你是部署在此站点的智能助手。请严格根据[知识库片段]回答用户的问题。"
        "根据[知识库片段]中的片段推导回答用户的问题."
    )

    messages = [{"role": "system", "content": system_msg}]
    for turn in history[-6:]:  # 最多保留最近6轮
        messages.append(turn)
    user_content = f"[知识库片段]\n{context_text}\n\n[我的当前问题]\n{query}"
    messages.append({"role": "user", "content": user_content})

    payload = json.dumps({
        "model": "glm-4",
        "messages": messages,
        "temperature": 0.3,
    }).encode("utf-8")

    req = urllib.request.Request(api_url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            res_data = json.loads(resp.read())
            reply = res_data["choices"][0]["message"]["content"]
        return jsonify({"ok": True, "reply": reply})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"接口请求失败: {e}"}), 500


@app.route("/api/export-claude", methods=["POST"])
def export_claude():
    body = request.get_json()
    src = (body.get("source") or "").strip()
    name = (body.get("name") or "MySite").strip()
    transport = body.get("transport", "stdio")

    if not src:
        return jsonify({"ok": False, "msg": "请填写数据来源"}), 400
    if transport != "stdio":
        return jsonify({"ok": False, "msg": "Claude Desktop 仅支持 stdio 模式，请切换后再导出"}), 400

    cfg_path = Path(os.path.expandvars(r"%APPDATA%\Claude\claude_desktop_config.json"))
    cfg_data = {"mcpServers": {}}
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg_data = json.load(f)
            cfg_data.setdefault("mcpServers", {})
        except Exception as e:
            return jsonify({"ok": False, "msg": f"无法解析现有 Claude 配置: {e}"}), 500

    venv_python = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    python_exe = str(venv_python) if venv_python.exists() else sys.executable
    server_script = str(BASE_DIR / "server.py")

    cfg_data["mcpServers"][name] = {
        "command": python_exe,
        "args": ["-u", server_script, src, "stdio"],
        "env": {
            "MCP_SOURCE_TYPE": body.get("source_type", "url"),
            "MCP_SITE_NAME": name,
            "MCP_MAX_PAGES": str(body.get("pages", "20")),
            "MCP_CSS_SELECTOR": body.get("css", ""),
        },
    }

    try:
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg_data, f, ensure_ascii=False, indent=2)
        return jsonify({"ok": True, "path": str(cfg_path)})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500


if __name__ == "__main__":
    print("MCP Creater Web 已启动 :http://127.0.0.1:5000")
    app.run(debug=True, use_reloader=False, port=5000, threaded=True)
