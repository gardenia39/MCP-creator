"""MCP Creater — tkinter 桌面版 (零依赖)"""

import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path


class MCPCreaterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("⚡ MCP Creater")
        self.geometry("780x620")
        self.configure(bg="#0f172a")
        self.resizable(True, True)

        self.process = None
        self._after_id = None

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────
    def _build_ui(self):
        pad = dict(padx=14, pady=6)

        # ── Header ──
        hdr = tk.Frame(self, bg="#0f172a")
        hdr.pack(fill="x", padx=18, pady=(18, 0))
        tk.Label(hdr, text="⚡ MCP Creater", bg="#0f172a", fg="#7dd3fc",
                 font=("Microsoft YaHei", 18, "bold")).pack(side="left")

        # ── 配置 ──
        self._card("📌 网站配置").pack(fill="x", padx=14, pady=(12, 0))
        cfg = self._last_card
        self._row(cfg, "网站 URL", 0)
        self.url_var = tk.StringVar()
        self._entry(cfg, self.url_var, "https://your-website.com", 0)

        self._row(cfg, "网站名称", 1)
        self.name_var = tk.StringVar(value="MySite")
        self._entry(cfg, self.name_var, "MySite", 1)

        self._row(cfg, "最大抓取页数", 2)
        self.pages_var = tk.StringVar(value="20")
        self._entry(cfg, self.pages_var, "20", 2, width=8)

        # ── 传输模式 ──
        self._card("🔌 传输模式").pack(fill="x", padx=14, pady=(10, 0))
        trs = self._last_card
        self._row(trs, "模式", 0)
        self.transport_var = tk.StringVar(value="stdio")
        combo = ttk.Combobox(trs, textvariable=self.transport_var, state="readonly",
                              values=["stdio", "streamable-http"], width=30)
        combo.grid(row=0, column=1, sticky="w", **pad)
        combo.bind("<<ComboboxSelected>>", self._toggle_http)

        self.host_lbl = tk.Label(trs, text="监听地址", bg="#1e293b", fg="#94a3b8",
                                  font=("Microsoft YaHei", 9))
        self.host_var = tk.StringVar(value="0.0.0.0")
        self.host_entry = self._raw_entry(trs, self.host_var)
        self.port_lbl = tk.Label(trs, text="端口", bg="#1e293b", fg="#94a3b8",
                                  font=("Microsoft YaHei", 9))
        self.port_var = tk.StringVar(value="8000")
        self.port_entry = self._raw_entry(trs, self.port_var, width=8)

        # ── 按钮 ──
        btn_row = tk.Frame(self, bg="#0f172a")
        btn_row.pack(fill="x", padx=14, pady=10)
        self.start_btn = tk.Button(btn_row, text="🚀 启动 Server",
                                    bg="#3b82f6", fg="white", relief="flat",
                                    font=("Microsoft YaHei", 11, "bold"),
                                    padx=24, pady=10, cursor="hand2",
                                    command=self.start_server)
        self.start_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = tk.Button(btn_row, text="■ 停止",
                                   bg="#374151", fg="#f87171", relief="flat",
                                   font=("Microsoft YaHei", 11, "bold"),
                                   padx=24, pady=10, cursor="hand2",
                                   command=self.stop_server, state="disabled")
        self.stop_btn.pack(side="left")

        # ── 状态 ──
        status_row = tk.Frame(self, bg="#0f172a")
        status_row.pack(fill="x", padx=18)
        self.dot_lbl = tk.Label(status_row, text="🔴", bg="#0f172a", font=("", 12))
        self.dot_lbl.pack(side="left")
        self.status_lbl = tk.Label(status_row, text="未运行", bg="#0f172a",
                                    fg="#64748b", font=("Microsoft YaHei", 10, "bold"))
        self.status_lbl.pack(side="left", padx=6)

        self.hint_var = tk.StringVar()
        self.hint_lbl = tk.Label(self, textvariable=self.hint_var, bg="#0c4a6e",
                                  fg="#7dd3fc", font=("Consolas", 9),
                                  anchor="w", padx=10, pady=6, justify="left",
                                  wraplength=740)

        # ── 日志 ──
        log_frame = tk.Frame(self, bg="#0f172a")
        log_frame.pack(fill="both", expand=True, padx=14, pady=(8, 14))
        self.log_box = tk.Text(log_frame, bg="#020617", fg="#cbd5e1",
                                font=("Consolas", 10), relief="flat",
                                wrap="word", state="disabled", padx=10, pady=8)
        sb = ttk.Scrollbar(log_frame, command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=sb.set)
        self.log_box.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # 日志颜色标签
        self.log_box.tag_config("info", foreground="#22d3ee")
        self.log_box.tag_config("ok", foreground="#34d399")
        self.log_box.tag_config("err", foreground="#f87171")
        self.log_box.tag_config("def", foreground="#94a3b8")

    # ── 辅助 UI 构建 ──────────────────────────────────────────────
    def _card(self, title):
        f = tk.LabelFrame(self, text=title, bg="#1e293b", fg="#7dd3fc",
                          font=("Microsoft YaHei", 10, "bold"),
                          bd=1, relief="solid")
        self._last_card = f
        return f

    def _row(self, parent, text, row):
        tk.Label(parent, text=text, bg="#1e293b", fg="#94a3b8",
                 font=("Microsoft YaHei", 9)).grid(
            row=row, column=0, sticky="w", padx=14, pady=5)

    def _entry(self, parent, var, placeholder, row, width=35):
        e = tk.Entry(parent, textvariable=var, bg="#334155", fg="#f1f5f9",
                     insertbackground="#f1f5f9", relief="flat",
                     font=("Microsoft YaHei", 10), width=width)
        e.grid(row=row, column=1, sticky="w", padx=14, pady=5)
        return e

    def _raw_entry(self, parent, var, width=18):
        return tk.Entry(parent, textvariable=var, bg="#334155", fg="#f1f5f9",
                        insertbackground="#f1f5f9", relief="flat",
                        font=("Microsoft YaHei", 10), width=width)

    def _toggle_http(self, _=None):
        is_http = self.transport_var.get() == "streamable-http"
        pad = dict(padx=14, pady=5)
        if is_http:
            self.host_lbl.grid(row=1, column=0, sticky="w", **pad)
            self.host_entry.grid(row=1, column=1, sticky="w", **pad)
            self.port_lbl.grid(row=2, column=0, sticky="w", **pad)
            self.port_entry.grid(row=2, column=1, sticky="w", **pad)
        else:
            self.host_lbl.grid_remove()
            self.host_entry.grid_remove()
            self.port_lbl.grid_remove()
            self.port_entry.grid_remove()

    # ── 服务器控制 ────────────────────────────────────────────────
    def start_server(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("错误", "请填写网站 URL")
            return

        mode = self.transport_var.get()
        name = self.name_var.get().strip() or "MySite"
        pages = self.pages_var.get().strip() or "20"
        host = self.host_var.get().strip()
        port = self.port_var.get().strip()

        venv_python = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
        python_exe = str(venv_python) if venv_python.exists() else sys.executable
        server_script = str(Path(__file__).parent / "server.py")

        env = os.environ.copy()
        env.update(MCP_SITE_NAME=name, MCP_MAX_PAGES=pages,
                   MCP_HOST=host, MCP_PORT=port, PYTHONIOENCODING="utf-8")

        self._log(f"[UI] 正在启动 MCP Server ({mode} 模式)...\n", "info")

        self.process = subprocess.Popen(
            [python_exe, "-u", server_script, url, mode],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE if mode == "stdio" else subprocess.DEVNULL,
            env=env, cwd=str(Path(__file__).parent),
            encoding="utf-8", errors="replace"
        )

        self._log(f"[UI] Server 进程已启动 (PID: {self.process.pid})\n", "ok")
        self._set_state(running=True)

        # 连接提示
        if mode == "streamable-http":
            ep = f"http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}/mcp"
            self.hint_var.set(f"HTTP 端点: {ep}\n"
                              f"Claude CLI:  claude mcp add --transport http {name} {ep}")
        else:
            self.hint_var.set(
                f"stdio 模式已启动，由 MCP 客户端以子进程方式调用\n"
                f"Claude CLI:  claude mcp add {name} -- python server.py {url} stdio")
        self.hint_lbl.pack(fill="x", padx=14, pady=(0, 6), before=self.log_box.master)

        # 后台读取输出
        threading.Thread(target=self._read_output, daemon=True).start()
        # 轮询进程是否结束
        self._poll()

    def stop_server(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self._log("\n[UI] Server 已停止\n", "err")
            self._set_state(running=False)

    def _read_output(self):
        try:
            for line in iter(self.process.stderr.readline, ""):
                if line:
                    self.after(0, self._log, line, self._classify(line))
        except Exception:
            pass

    def _poll(self):
        if self.process and self.process.poll() is not None:
            self.after(0, self._set_state, False)
            return
        self._after_id = self.after(800, self._poll)

    def _set_state(self, running):
        if running:
            self.dot_lbl.config(text="🟢")
            self.status_lbl.config(text="运行中", fg="#34d399")
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
        else:
            self.dot_lbl.config(text="🔴")
            self.status_lbl.config(text="已停止", fg="#64748b")
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.hint_lbl.pack_forget()
            self.process = None

    # ── 日志 ──────────────────────────────────────────────────────
    def _classify(self, line: str) -> str:
        l = line.lower()
        if "[ui]" in l or "[mcp]" in l:
            return "info"
        if any(w in l for w in ("完成", "成功", "启动", "success", "started")):
            return "ok"
        if any(w in l for w in ("错误", "失败", "error", "traceback", "exception")):
            return "err"
        return "def"

    def _log(self, text: str, tag: str = "def"):
        self.log_box.config(state="normal")
        self.log_box.insert("end", text.rstrip("\n") + "\n", tag)
        self.log_box.see("end")
        self.log_box.config(state="disabled")


if __name__ == "__main__":
    app = MCPCreaterApp()
    app.mainloop()
