let chatHistory = [];
let profiles = {};
let sseSource = null;
// 初始化
document.addEventListener('DOMContentLoaded', () => {
    fetchProfiles();
    connectSSE();
    pollStatus();
    toggleHttp();
});

// 记录日志
function connectSSE() {
    if (sseSource) sseSource.close();
    sseSource = new EventSource('/api/logs');
    sseSource.onmessage = e => appendLog(e.data);
    sseSource.onerror = () => setTimeout(connectSSE, 3000);
}

function appendLog(text) {
    const box = document.getElementById('log-box');
    const div = document.createElement('div');
    div.className = `log-row ${classifyLog(text)}`;
    div.textContent = text;
    box.appendChild(div);

    // 固定滚动
    box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' });
}

function classifyLog(t) {
    const l = t.toLowerCase();
    if (l.includes('[ui]') || l.includes('[mcp]')) return 'log-info';
    if (/完成|成功|启动|success|started|加载完成/.test(l)) return 'log-ok';
    if (/警告|warn/.test(l)) return 'log-warn';
    if (/错误|失败|error|traceback|exception/.test(l)) return 'log-err';
    return 'log-def';
}

function clearLog() {
    const box = document.getElementById('log-box');
    box.innerHTML = '';
}

// 查看状态
function pollStatus() {
    fetch('/api/status').then(r => r.json()).then(data => {
        setRunning(data.running, data.endpoint);
    }).catch(() => { });
    setTimeout(pollStatus, 2000);
}

function setRunning(running, endpoint) {
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const hint = document.getElementById('endpoint-hint');

    if (running) {
        dot.textContent = '🟢';
        text.textContent = '已经连接';
        text.style.color = 'var(--success)';
        startBtn.disabled = true;
        stopBtn.disabled = false;
        if (endpoint) {
            hint.textContent = '📡 HTTP EndPoint: ' + endpoint;
            hint.classList.remove('hidden');
        } else {
            hint.classList.add('hidden');
        }
    } else {
        dot.textContent = '🔴';
        text.textContent = '系统休眠';
        text.style.color = 'var(--text-muted)';
        startBtn.disabled = false;
        stopBtn.disabled = true;
        hint.classList.add('hidden');
    }
}

// 控制各个部件
function toggleHttp() {
    const isHttp = document.getElementById('transport').value === 'streamable-http';
    ['host-lbl', 'host', 'port-lbl', 'port'].forEach(id => {
        document.getElementById(id).classList.toggle('hidden', !isHttp);
    });
}

document.querySelectorAll('input[name="source_type"]').forEach(r => {
    r.addEventListener('change', () => {
        const isUrl = r.value === 'url';
        const btn = document.getElementById('open-btn');
        btn.textContent = '浏览';
        if (!isUrl) {
            btn.title = "点击选择本地文件夹，或直接在输入框中粘贴路径";
            handleSourceBtn(); // 选中文件夹模式时立即弹出选择框
        } else {
            btn.title = "";
        }
    });
});

function handleSourceBtn() {
    const type = document.querySelector('input[name="source_type"]:checked').value;
    if (type === 'url') {
        let url = document.getElementById('source').value.trim();
        if (!url) { alert('请输入有效的网站'); return; }
        if (!url.startsWith('http')) url = 'https://' + url;
        window.open(url, '_blank');
    } else {
        fetch('/api/select_folder')
            .then(r => r.json())
            .then(d => {
                if (d.ok && d.path) {
                    document.getElementById('source').value = d.path;
                } else if (d.msg && d.msg !== "用户取消了选择") {
                    alert('提示：' + d.msg + '\n\n请直接在输入框中粘贴完整路径。');
                }
            })
            .catch(err => {
                alert('本地文件夹模式：请直接在输入框中粘贴完整路径，例如 C:\\Users\\me\\docs');
            });
    }
}

// 切换制作
function switchTab(name) {
    document.querySelectorAll('.tab-btn').forEach((b, i) => {
        b.classList.toggle('active', (i === 0 && name === 'log') || (i === 1 && name === 'chat'));
    });

    const logTab = document.getElementById('tab-log');
    const chatTab = document.getElementById('tab-chat');

    if (name === 'log') {
        chatTab.classList.add('hidden');
        chatTab.classList.remove('smooth-appear');
        logTab.classList.remove('hidden');
        // 触发动画
        void logTab.offsetWidth;
        logTab.classList.add('smooth-appear');
    } else {
        logTab.classList.add('hidden');
        logTab.classList.remove('smooth-appear');
        chatTab.classList.remove('hidden');
        void chatTab.offsetWidth;
        chatTab.classList.add('smooth-appear');
    }
}

// 历史配置记录
function fetchProfiles() {
    fetch('/api/profiles').then(r => r.json()).then(data => {
        profiles = data;
        const sel = document.getElementById('profile-select');
        const cur = sel.value;
        sel.innerHTML = '<option value="">选择历史记录</option>';
        Object.keys(data).forEach(k => {
            const opt = document.createElement('option');
            opt.value = opt.textContent = k;
            sel.appendChild(opt);
        });
        if (cur && data[cur]) sel.value = cur;
    });
}

function loadProfile() {
    const key = document.getElementById('profile-select').value;
    if (!key || !profiles[key]) return;
    const p = profiles[key];
    document.getElementById('source').value = p.source || '';
    document.getElementById('name').value = p.name || 'MySite';
    document.getElementById('pages').value = p.pages || '20';
    document.getElementById('css_sel').value = p.css || '';
    document.getElementById('transport').value = p.transport || 'stdio';
    document.getElementById('host').value = p.host || '0.0.0.0';
    document.getElementById('port').value = p.port || '8000';
    document.getElementById('api-key').value = p.api_key || '';
    document.getElementById('api-url').value = p.api_url || 'https://open.bigmodel.cn/api/paas/v4/chat/completions';
    const typeRadio = p.source_type === 'folder' ? 'folder' : 'url';
    document.querySelector(`input[name="source_type"][value="${typeRadio}"]`).checked = true;
    toggleHttp();
}

function saveProfile() {
    const body = collectForm();
    fetch('/api/profiles', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    }).then(r => r.json()).then(d => {
        if (d.ok) { fetchProfiles(); appendLog(`[UI] 已保存: ${d.name}`); }
    });
}

function deleteProfile() {
    const sel = document.getElementById('profile-select');
    const name = sel.value;
    if (!name) { alert('请先选择一个历史记录'); return; }
    if (!confirm(`将永久抹除历史记录「${name}」，确认执行？`)) return;
    fetch(`/api/profiles/${encodeURIComponent(name)}`, { method: 'DELETE' })
        .then(r => r.json()).then(d => {
            if (d.ok) { fetchProfiles(); appendLog(`[UI] 已删除: ${name}`); }
        });
}

function collectForm() {
    return {
        source_type: document.querySelector('input[name="source_type"]:checked').value,
        source: document.getElementById('source').value.trim(),
        name: document.getElementById('name').value.trim() || '我的网站',
        pages: document.getElementById('pages').value || '20',
        css: document.getElementById('css_sel').value,
        transport: document.getElementById('transport').value,
        host: document.getElementById('host').value || '0.0.0.0',
        port: document.getElementById('port').value || '8000',
        api_key: document.getElementById('api-key').value.trim(),
        api_url: document.getElementById('api-url').value.trim(),
    };
}

// 控制服务器
function startServer() {
    const body = collectForm();
    if (!body.source) { alert('需要先连接'); return; }
    fetch('/api/start', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    }).then(r => r.json()).then(d => {
        if (!d.ok) appendLog('[ERR]连接失败: ' + d.msg);
    });
}

function stopServer() {
    fetch('/api/stop', { method: 'POST' }).then(r => r.json()).then(d => {
        if (!d.ok) appendLog('[ERR] 关闭连接失败: ' + d.msg);
    });
}

// 导出到claude的setting中
function exportClaude() {
    const body = collectForm();
    fetch('/api/export-claude', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    }).then(r => r.json()).then(d => {
        if (d.ok) {
            appendLog('[UI] 已注入 Claude Config,请重启客户端。');
            alert('✅ 注入成功！\n\n路径: ' + d.path + '\n\n请重启 Claude Desktop。');
        } else {
            appendLog('[ERR] 注入失败: ' + d.msg);
            alert('❌ 注入失败: ' + d.msg);
        }
    });
}

// AI对话测试
function sendChat() {
    const input = document.getElementById('chat-input');
    const query = input.value.trim();
    if (!query) return;
    input.value = '';

    const emptyState = document.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    appendChatMsg('user', 'USER', query);

    const form = collectForm();
    if (!form.api_key) {
        appendChatMsg('sys', 'SYSTEM', '错误: 没有填写API Key');
        return;
    }

    const thinkingId = appendChatMsg('sys', 'SYSTEM', '正在读取页面内容');

    const history = chatHistory.map(t => ({ role: t.role, content: t.content }));

    fetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, api_key: form.api_key, api_url: form.api_url, history })
    }).then(r => r.json()).then(d => {
        removeMsg(thinkingId);
        if (d.ok) {
            appendChatMsg('ai', 'AGENT', d.reply);
            chatHistory.push({ role: 'user', content: query });
            chatHistory.push({ role: 'assistant', content: d.reply });
            if (chatHistory.length > 12) chatHistory.splice(0, 2);
        } else {
            appendChatMsg('err', 'FATAL', d.msg);
        }
    }).catch(e => {
        removeMsg(thinkingId);
        appendChatMsg('err', 'FATAL', '连接中断: ' + e);
    });
}

let _msgId = 0;
function appendChatMsg(type, role, text) {
    const id = 'msg-' + (++_msgId);
    const box = document.getElementById('chat-box');
    const wrap = document.createElement('div');
    wrap.className = 'msg-wrap msg-' + type;
    wrap.id = id;
    wrap.innerHTML = `<div class="msg-role">${role}</div><div class="msg-body">${escHtml(text)}</div>`;
    box.appendChild(wrap);

    box.scrollTo({ top: box.scrollHeight, behavior: 'smooth' });
    return id;
}

function removeMsg(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function escHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
}
