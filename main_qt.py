import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QFormLayout, QLineEdit, QComboBox, 
                             QPushButton, QLabel, QPlainTextEdit, QMessageBox,
                             QSpinBox, QGroupBox)
from PyQt6.QtCore import QProcess, Qt
from PyQt6.QtGui import QFont, QTextCursor

class MCPCreaterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("⚡ MCP Creater")
        self.resize(800, 600)
        self.process = None

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 1. Configuration Group
        config_group = QGroupBox("📌 网站配置")
        config_layout = QFormLayout()
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://your-website.com")
        self.url_input.setStyleSheet("padding: 8px; border: 1px solid #ccc; border-radius: 4px;")
        
        self.name_input = QLineEdit()
        self.name_input.setText("MySite")
        self.name_input.setStyleSheet("padding: 8px; border: 1px solid #ccc; border-radius: 4px;")
        
        self.pages_input = QSpinBox()
        self.pages_input.setRange(1, 100)
        self.pages_input.setValue(20)
        self.pages_input.setStyleSheet("padding: 8px; border: 1px solid #ccc; border-radius: 4px;")

        config_layout.addRow("网站 URL:", self.url_input)
        config_layout.addRow("网站名称:", self.name_input)
        config_layout.addRow("最大抓取页数:", self.pages_input)
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)

        # 2. Transport Group
        transport_group = QGroupBox("🔌 传输模式")
        transport_layout = QFormLayout()

        self.transport_combo = QComboBox()
        self.transport_combo.addItem("stdio — 本地子进程模式", "stdio")
        self.transport_combo.addItem("Streamable HTTP — 远程模式", "streamable-http")
        self.transport_combo.setStyleSheet("padding: 8px; border: 1px solid #ccc; border-radius: 4px;")
        self.transport_combo.currentIndexChanged.connect(self.toggle_http_fields)

        self.host_input = QLineEdit("0.0.0.0")
        self.host_input.setStyleSheet("padding: 8px; border: 1px solid #ccc; border-radius: 4px;")
        
        self.port_input = QSpinBox()
        self.port_input.setRange(1024, 65535)
        self.port_input.setValue(8000)
        self.port_input.setStyleSheet("padding: 8px; border: 1px solid #ccc; border-radius: 4px;")

        transport_layout.addRow("模式:", self.transport_combo)
        self.host_label = QLabel("监听地址:")
        self.port_label = QLabel("端口:")
        
        transport_layout.addRow(self.host_label, self.host_input)
        transport_layout.addRow(self.port_label, self.port_input)
        
        self.host_input.hide()
        self.host_label.hide()
        self.port_input.hide()
        self.port_label.hide()

        transport_group.setLayout(transport_layout)
        main_layout.addWidget(transport_group)

        # 3. Buttons
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("🚀 启动 Server")
        self.start_btn.setStyleSheet("""
            QPushButton { background-color: #3b82f6; color: white; padding: 12px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #2563eb; }
            QPushButton:disabled { background-color: #93c5fd; }
        """)
        self.start_btn.clicked.connect(self.start_server)
        
        self.stop_btn = QPushButton("■ 停止")
        self.stop_btn.setStyleSheet("""
            QPushButton { background-color: #ef4444; color: white; padding: 12px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #dc2626; }
            QPushButton:disabled { background-color: #fca5a5; }
        """)
        self.stop_btn.clicked.connect(self.stop_server)
        self.stop_btn.setEnabled(False)
        
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        main_layout.addLayout(btn_layout)

        # 4. Status
        status_layout = QHBoxLayout()
        self.status_dot = QLabel("🔴")
        self.status_text = QLabel("未运行")
        self.status_text.setStyleSheet("font-weight: bold; color: #64748b;")
        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_text)
        status_layout.addStretch()
        main_layout.addLayout(status_layout)

        self.conn_hint = QPlainTextEdit()
        self.conn_hint.setMaximumHeight(65)
        self.conn_hint.setReadOnly(True)
        self.conn_hint.setStyleSheet("background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; border-radius: 4px; padding: 8px;")
        self.conn_hint.hide()
        main_layout.addWidget(self.conn_hint)

        # 5. Logs
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("background-color: #0f172a; color: #cbd5e1; font-family: Consolas, monospace; padding: 10px; border-radius: 6px;")
        main_layout.addWidget(self.log_box)

    def toggle_http_fields(self):
        mode = self.transport_combo.currentData()
        is_http = (mode == "streamable-http")
        self.host_label.setVisible(is_http)
        self.host_input.setVisible(is_http)
        self.port_label.setVisible(is_http)
        self.port_input.setVisible(is_http)

    def start_server(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "错误", "请填写网站 URL")
            return

        self.log_box.clear()

        mode = self.transport_combo.currentData()
        name = self.name_input.text().strip() or "MySite"
        pages = str(self.pages_input.value())
        host = self.host_input.text().strip()
        port = str(self.port_input.value())

        self.process = QProcess(self)
        
        # 传递环境变量
        env = self.process.processEnvironment()
        env.insert("MCP_SITE_NAME", name)
        env.insert("MCP_MAX_PAGES", pages)
        env.insert("MCP_HOST", host)
        env.insert("MCP_PORT", port)
        env.insert("PYTHONIOENCODING", "utf-8")
        self.process.setProcessEnvironment(env)

        # 绑定信号
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.stateChanged.connect(self.handle_state)

        server_script = os.path.join(os.path.dirname(__file__), "server.py")
        
        # 使用当前虚拟环境的 Python
        venv_python = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")
        python_exe = venv_python if os.path.exists(venv_python) else sys.executable

        # 启动 QProcess
        self.append_log(f"[UI] 正在启动 MCP Server ({mode} 模式)...")
        self.process.start(python_exe, ["-u", server_script, url, mode])

        # 连接提示信息
        if mode == "streamable-http":
            endpoint = f"http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}/mcp"
            hint = f"HTTP 端点: {endpoint}\nClaude CLI: claude mcp add --transport http {name} {endpoint}"
        else:
            hint = f"stdio 模式已启动，由 MCP 客户端以子进程方式调用\nClaude CLI: claude mcp add {name} -- python server.py {url} stdio"
        
        self.conn_hint.setPlainText(hint)
        self.conn_hint.show()

    def stop_server(self):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.process.terminate()
            if not self.process.waitForFinished(3000):
                self.process.kill()
            self.append_log("[UI] Server 已强制停止")

    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        self.append_log(data)

    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode("utf-8", errors="replace")
        self.append_log(data)

    def handle_state(self, state):
        if state == QProcess.ProcessState.Running:
            self.status_dot.setText("🟢")
            self.status_text.setText("运行中")
            self.status_text.setStyleSheet("font-weight: bold; color: #10b981;")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
        elif state == QProcess.ProcessState.NotRunning:
            self.status_dot.setText("🔴")
            self.status_text.setText("已停止")
            self.status_text.setStyleSheet("font-weight: bold; color: #64748b;")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.conn_hint.hide()
            self.process = None

    def append_log(self, text):
        text = text.strip()
        if not text:
            return
        
        # 移至文末并插入新日志
        self.log_box.moveCursor(QTextCursor.MoveOperation.End)
        self.log_box.insertPlainText(text + "\\n")
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum()
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 强制让 Qt 支持高分屏缩放并设置默认字体
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    
    window = MCPCreaterApp()
    window.show()
    sys.exit(app.exec())
