// ── 状态 ────────────────────────────────────────────────────
let chatHistory = [];   // [{role, content}, ...]
let profiles = {};
let sseSource = null;

// ── 初始化 ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    fetchProfiles();
    connectSSE();
    pollStatus();
    toggleHttp();
});

// ── SSE 日志流 ───────────────────────────────────────────────
function connectSSE() {
    if (sseSource) sseSource.close();
    sseSource = new EventSource('/api/logs');
    sseSource.onmessage = e => appendLog(e.data);
    sseSource.onerror = () => setTimeout(connectSSE, 3000);
}

function appendLog(text) {
    const box = document.getElementById('log-box');
    const div = document.createElement('div');
    div.className = classifyLog(text);
    div.textContent = text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
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
    document.getElementById('log-box').innerHTML = '';
}

// ── 状态轮询 ─────────────────────────────────────────────────
function pollStatus() {
    fetch('/api/status').then(r => r.json()).then(data => {
        setRunning(data.running, data.endpoint);
    }).catch(() => { });
    setTimeout(pollStatus, 2000);
}

function setRunning(running, endpoint) {
    document.getElementById('status-dot').textContent = running ? '🟢' : '🔴';
    document.getElementById('status-text').textContent = running ? '运行中' : '已停止';
    document.getElementById('status-text').style.color = running ? '#34d399' : '#64748b';
    document.getElementById('start-btn').disabled = running;
    document.getElementById('stop-btn').disabled = !running;

    const hint = document.getElementById('endpoint-hint');
    if (running && endpoint) {
        hint.textContent = '📡 HTTP 端点: ' + endpoint;
        hint.classList.remove('hidden');
    } else {
        hint.classList.add('hidden');
    }
}

// ── 控件联动 ─────────────────────────────────────────────────
function toggleHttp() {
    const isHttp = document.getElementById('transport').value === 'streamable-http';
    ['host-lbl', 'host', 'port-lbl', 'port'].forEach(id => {
        document.getElementById(id).classList.toggle('hidden', !isHttp);
    });
}

document.querySelectorAll('input[name="source_type"]').forEach(r => {
    r.addEventListener('change', () => {
        const isUrl = r.value === 'url';
        document.getElementById('open-btn').textContent = isUrl ? '浏览器打开' : '（手动输入路径）';
    });
});

function handleSourceBtn() {
    const type = document.querySelector('input[name="source_type"]:checked').value;
    if (type === 'url') {
        let url = document.getElementById('source').value.trim();
        if (!url) { alert('请先输入网址'); return; }
        if (!url.startsWith('http')) url = 'https://' + url;
        window.open(url, '_blank');
    } else {
        alert('本地文件夹模式：请直接在输入框中粘贴完整路径，例如 C:\\Users\\me\\docs');
    }
}

// ── Tab 切换 ─────────────────────────────────────────────────
function switchTab(name) {
    document.querySelectorAll('.tab-btn').forEach((b, i) => {
        b.classList.toggle('active', (i === 0 && name === 'log') || (i === 1 && name === 'chat'));
    });
    document.getElementById('tab-log').classList.toggle('hidden', name !== 'log');
    document.getElementById('tab-chat').classList.toggle('hidden', name !== 'chat');
}

// ── 历史配置 ─────────────────────────────────────────────────
function fetchProfiles() {
    fetch('/api/profiles').then(r => r.json()).then(data => {
        profiles = data;
        const sel = document.getElementById('profile-select');
        const cur = sel.value;
        sel.innerHTML = '<option value="">-- 选择历史配置 --</option>';
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
    document.getElementById('api-url').value = p.api_url || 'https://api.deepseek.com/chat/completions';
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
        if (d.ok) { fetchProfiles(); appendLog(`[UI] 已保存配置: ${d.name}`); }
    });
}

function deleteProfile() {
    const sel = document.getElementById('profile-select');
    const name = sel.value;
    if (!name) { alert('请先选择一个配置'); return; }
    if (!confirm(`确认删除配置「${name}」？`)) return;
    fetch(`/api/profiles/${encodeURIComponent(name)}`, { method: 'DELETE' })
        .then(r => r.json()).then(d => {
            if (d.ok) { fetchProfiles(); appendLog(`[UI] 已删除配置: ${name}`); }
        });
}

function collectForm() {
    return {
        source_type: document.querySelector('input[name="source_type"]:checked').value,
        source: document.getElementById('source').value.trim(),
        name: document.getElementById('name').value.trim() || 'MySite',
        pages: document.getElementById('pages').value || '20',
        css: document.getElementById('css_sel').value,
        transport: document.getElementById('transport').value,
        host: document.getElementById('host').value || '0.0.0.0',
        port: document.getElementById('port').value || '8000',
        api_key: document.getElementById('api-key').value.trim(),
        api_url: document.getElementById('api-url').value.trim(),
    };
}

// ── 服务器控制 ────────────────────────────────────────────────
function startServer() {
    const body = collectForm();
    if (!body.source) { alert('请填写来源（网址或路径）'); return; }
    fetch('/api/start', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    }).then(r => r.json()).then(d => {
        if (!d.ok) appendLog('[ERR] ' + d.msg);
    });
}

function stopServer() {
    fetch('/api/stop', { method: 'POST' }).then(r => r.json()).then(d => {
        if (!d.ok) appendLog('[ERR] ' + d.msg);
    });
}

// ── 导出 Claude 配置 ──────────────────────────────────────────
function exportClaude() {
    const body = collectForm();
    fetch('/api/export-claude', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    }).then(r => r.json()).then(d => {
        if (d.ok) {
            appendLog('[UI] 已写入 Claude 配置，重启 Claude Desktop 即可生效。');
            alert('✅ 写入成功！\n\n路径: ' + d.path + '\n\n请重启 Claude Desktop。');
        } else {
            appendLog('[ERR] ' + d.msg);
            alert('❌ 失败: ' + d.msg);
        }
    });
}

// ── AI 对话 ───────────────────────────────────────────────────
function sendChat() {
    const input = document.getElementById('chat-input');
    const query = input.value.trim();
    if (!query) return;
    input.value = '';

    appendChatMsg('user', '😎 我', query);

    const form = collectForm();
    if (!form.api_key) {
        appendChatMsg('sys', '🚨 系统提示', '请先填写 API Key');
        return;
    }

    const thinkingId = appendChatMsg('ai', '✨ AI', '正在阅读内容并思考中，请稍候…');

    // 把当前问题临时加入 history，不加 context（context 由后端注入）
    const history = chatHistory.map(t => ({ role: t.role, content: t.content }));

    fetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, api_key: form.api_key, api_url: form.api_url, history })
    }).then(r => r.json()).then(d => {
        removeMsg(thinkingId);
        if (d.ok) {
            appendChatMsg('ai', '✨ AI', d.reply);
            // 存入多轮记忆
            chatHistory.push({ role: 'user', content: query });
            chatHistory.push({ role: 'assistant', content: d.reply });
            if (chatHistory.length > 12) chatHistory.splice(0, 2); // 最多6轮
        } else {
            appendChatMsg('err', '❌ 错误', d.msg);
        }
    }).catch(e => {
        removeMsg(thinkingId);
        appendChatMsg('err', '❌ 错误', '网络请求失败: ' + e);
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
    box.scrollTop = box.scrollHeight;
    return id;
}

function removeMsg(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function escHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
}
