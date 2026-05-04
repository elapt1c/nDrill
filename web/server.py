import sys
import os
import json
import threading
import asyncio
import socketio
import uvicorn
from typing import Optional
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# Add parent and src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from main import Orchestrator

# Setup Socket.IO as an ASGI app
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = FastAPI(title="nDrill Web UI")

# CORS middleware for FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Standard ASGI app wrapper
socket_app = socketio.ASGIApp(sio, app)

class GlobalState:
    def __init__(self):
        self.orchestrator: Optional[Orchestrator] = None
        self.is_running = False
        self.loop = None

state = GlobalState()

def event_handler(event):
    if state.loop:
        # Cross-thread safe emit
        state.loop.call_soon_threadsafe(
            lambda: asyncio.create_task(sio.emit('assessment_event', event))
        )

@app.get("/", response_class=HTMLResponse)
async def get_index():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>nDrill - Security Assessment Platform</title>
    <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    <style>
        :root {
            --bg-color: #0d1117;
            --panel-bg: #161b22;
            --accent-color: #58a6ff;
            --text-color: #c9d1d9;
            --text-dim: #8b949e;
            --success: #238636;
            --warning: #d29922;
            --error: #f85149;
            --border: #30363d;
            --thought: #d2a8ff;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            display: flex;
            height: 100vh;
            overflow: hidden;
        }

        .sidebar {
            width: 380px;
            background-color: var(--panel-bg);
            border-right: 1px solid var(--border);
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 1.2rem;
            box-shadow: 2px 0 10px rgba(0,0,0,0.5);
            z-index: 10;
        }

        h1 {
            font-size: 2rem;
            margin: 0;
            color: var(--accent-color);
            display: flex;
            align-items: center;
            gap: 0.6rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 0.8rem;
            font-weight: 800;
        }

        .input-group {
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
        }

        label {
            font-size: 0.75rem;
            font-weight: 700;
            color: var(--text-dim);
        }

        input, textarea, select {
            background-color: var(--bg-color);
            border: 1px solid var(--border);
            color: var(--text-color);
            padding: 0.7rem;
            border-radius: 6px;
            font-size: 0.85rem;
            outline: none;
        }

        input:focus, textarea:focus { border-color: var(--accent-color); }

        button {
            padding: 0.8rem;
            border-radius: 6px;
            border: none;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 0.5rem;
        }

        .btn-primary { background-color: var(--accent-color); color: #0d1117; }
        .btn-primary:hover { opacity: 0.9; }
        .btn-primary:disabled { background-color: #21262d; color: var(--text-dim); cursor: not-allowed; }

        .btn-secondary { background-color: #21262d; border: 1px solid var(--border); color: #c9d1d9; }
        .btn-interrupt { background-color: var(--warning); color: #000; }

        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            background-color: var(--bg-color);
        }

        .header-bar {
            padding: 1rem 1.5rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background-color: var(--panel-bg);
        }

        .status-badge {
            padding: 0.3rem 0.8rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 700;
            background: #21262d;
            border: 1px solid var(--border);
        }

        .terminal {
            flex: 1;
            padding: 1.5rem;
            overflow-y: auto;
            font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
            font-size: 0.85rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
            scroll-behavior: smooth;
        }

        .log-entry {
            padding: 1rem;
            border-radius: 8px;
            background-color: #161b22;
            border: 1px solid var(--border);
            line-height: 1.6;
            max-width: 95%;
        }

        .log-phase { border-left: 4px solid var(--accent-color); color: var(--accent-color); font-weight: bold; }
        .log-thought { border-left: 4px solid var(--thought); color: #e2c5ff; background: rgba(210, 168, 255, 0.05); }
        .log-tool { border-left: 4px solid #f29059; }
        .log-success { border-left: 4px solid var(--success); color: #3fb950; font-weight: bold; }
        .log-error { border-left: 4px solid var(--error); color: #f85149; }
        .log-system { border-left: 4px solid var(--text-dim); color: var(--text-dim); font-style: italic; }

        .code-block {
            background: #010409;
            padding: 1rem;
            border-radius: 6px;
            overflow-x: auto;
            white-space: pre-wrap;
            border: 1px solid var(--border);
            color: #c9d1d9;
            font-size: 0.8rem;
            margin-top: 0.6rem;
        }

        .footer {
            margin-top: auto;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
            font-size: 0.7rem;
            color: var(--text-dim);
            text-align: center;
        }

        .extra-info-panel {
            padding: 1rem 1.5rem;
            border-top: 1px solid var(--border);
            background-color: var(--panel-bg);
            display: flex;
            gap: 1rem;
        }

        .extra-info-panel input { flex: 1; border-radius: 30px; padding-left: 1.5rem; }
        .extra-info-panel button { border-radius: 30px; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h1>nDrill</h1>
        
        <div class="input-group">
            <label>Target URL</label>
            <input type="text" id="target" value="https://pentest-ground.com:7001">
        </div>

        <div class="input-group">
            <label>OpenRouter API Key</label>
            <input type="password" id="apiKey" placeholder="sk-or-v1-...">
        </div>

        <div class="input-group">
            <label>Model Engine (Custom or Selection)</label>
            <input type="text" id="model" list="model-options" placeholder="Enter or select model...">
            <datalist id="model-options">
                <option value="arcee-ai/trinity-large-preview:free">
                <option value="google/gemini-2.0-flash-001">
                <option value="anthropic/claude-3.5-sonnet">
                <option value="openai/gpt-4o">
            </datalist>
        </div>

        <div class="input-group">
            <label>Assessment Objectives</label>
            <textarea id="comment" rows="5">Confirm and demonstrate RCE on the WebLogic instance. Focus on standard identification commands.</textarea>
        </div>

        <button id="startBtn" class="btn-primary">START ASSESSMENT</button>
        <button id="stopBtn" class="btn-secondary" disabled>ABORT</button>

        <div class="footer">
            nDrill v3.4 &bull; &copy; elapt1c 2026
        </div>
    </div>

    <div class="main-content">
        <div class="header-bar">
            <div id="active-target" style="font-weight: 700; color: var(--accent-color);">READY</div>
            <div id="status-badge" class="status-badge">IDLE</div>
        </div>

        <div id="terminal" class="terminal">
            <div class="log-entry log-system">nDrill system online. Connection status: <span id="conn-status">Waiting...</span></div>
        </div>

        <div class="extra-info-panel">
            <input type="text" id="extraInfoInput" placeholder="Add real-time context...">
            <button id="sendExtraBtn" class="btn-interrupt">ADD CONTEXT</button>
        </div>
    </div>

    <script>
        const socket = io();

        const terminal = document.getElementById('terminal');
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        const statusBadge = document.getElementById('status-badge');
        const activeTargetDisplay = document.getElementById('active-target');
        const connStatus = document.getElementById('conn-status');

        // Cookie Helper Functions
        function setCookie(name, value, days = 30) {
            const date = new Date();
            date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
            const expires = "expires=" + date.toUTCString();
            document.cookie = name + "=" + value + ";" + expires + ";path=/;SameSite=Strict";
        }

        function getCookie(name) {
            const nameEQ = name + "=";
            const ca = document.cookie.split(';');
            for(let i = 0; i < ca.length; i++) {
                let c = ca[i];
                while (c.charAt(0) == ' ') c = c.substring(1, c.length);
                if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length, c.length);
            }
            return null;
        }

        // Load saved preferences on startup
        window.onload = () => {
            const savedApiKey = getCookie('ndrill_api_key');
            const savedModel = getCookie('ndrill_model');
            if (savedApiKey) document.getElementById('apiKey').value = savedApiKey;
            if (savedModel) document.getElementById('model').value = savedModel;
        };

        socket.on('connect', () => {
            connStatus.textContent = 'Connected (sid: ' + socket.id + ')';
            appendLog({type: 'system', message: 'Socket.IO connection established.'});
        });

        socket.on('connect_error', (error) => {
            connStatus.textContent = 'Error: ' + error.message;
            console.error('Socket.IO Connection Error:', error);
        });

        socket.on('assessment_event', (event) => {
            appendLog(event);
        });

        function escapeHTML(str) {
            if (!str) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function appendLog(event) {
            if (!event) return;
            const entry = document.createElement('div');
            entry.className = `log-entry log-${event.type}`;
            
            let message = event.message || '';
            
            if (event.type === 'tool' && event.data) {
                const toolName = escapeHTML(event.data.tool || '');
                if (event.data.code) {
                    message = `<strong>GENERATING SCRIPT: ${toolName}</strong><pre class="code-block">${escapeHTML(event.data.code)}</pre>`;
                } else if (event.data.args) {
                    message = `<strong>EXECUTING TOOL: ${toolName}</strong><pre class="code-block">${toolName} ${escapeHTML(event.data.args.join(' '))}</pre>`;
                } else if (event.data.output) {
                    message = `<strong>OUTPUT: ${toolName}</strong><pre class="code-block">${escapeHTML(event.data.output)}</pre>`;
                }
            } else if (event.type === 'thought') {
                message = `<strong>AGENT REASONING</strong><div style="margin-top:0.4rem;">${escapeHTML(message)}</div>`;
            } else if (event.type === 'phase') {
                const cleanMessage = message.replace(/<[^>]*>?/gm, '');
                message = `<strong>ASSESSMENT PHASE: ${escapeHTML(cleanMessage.toUpperCase())}</strong>`;
                statusBadge.textContent = cleanMessage;
            } else if (event.type === 'success') {
                statusBadge.textContent = 'COMPLETED';
                startBtn.disabled = false;
                stopBtn.disabled = true;
                message = escapeHTML(message);
            } else {
                message = escapeHTML(message);
            }

            entry.innerHTML = message;
            terminal.appendChild(entry);
            terminal.scrollTop = terminal.scrollHeight;
        }

        startBtn.onclick = async () => {
            const target = document.getElementById('target').value;
            const apiKey = document.getElementById('apiKey').value;
            const model = document.getElementById('model').value;
            const comment = document.getElementById('comment').value;

            if (!target || !apiKey || !model) {
                alert("Target URL, API Key, and Model are required.");
                return;
            }

            // Save settings to cookies
            setCookie('ndrill_api_key', apiKey);
            setCookie('ndrill_model', model);

            terminal.innerHTML = '';
            appendLog({type: 'system', message: 'Initiating assessment sequence...'});
            startBtn.disabled = true;
            stopBtn.disabled = false;
            activeTargetDisplay.textContent = target.replace(/^https?:\\/\\//, '').toUpperCase();

            const response = await fetch('/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({ target, apiKey, model, comment })
            });
            const data = await response.json();
            if (data.status !== 'started') {
                appendLog({type: 'error', message: 'Error: ' + data.status});
                startBtn.disabled = false;
            }
        };

        stopBtn.onclick = async () => {
            await fetch('/stop', {method: 'POST'});
            startBtn.disabled = false;
            stopBtn.disabled = true;
        };

        document.getElementById('sendExtraBtn').onclick = async () => {
            const info = document.getElementById('extraInfoInput').value;
            if (!info) return;
            await fetch('/extra-info', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: new URLSearchParams({info})
            });
            document.getElementById('extraInfoInput').value = '';
            appendLog({type: 'system', message: `Context Added: ${info}`});
        };
    </script>
</body>
</html>
    """

@app.on_event("startup")
async def startup_event():
    state.loop = asyncio.get_running_loop()

@app.post("/start")
async def start_assessment(
    target: str = Form(...),
    apiKey: str = Form(...),
    model: str = Form(...),
    comment: str = Form(...)
):
    if state.is_running: return {"status": "busy"}
    state.is_running = True
    
    state.orchestrator = Orchestrator(
        target_url=target,
        model_id=model,
        user_instructions=comment,
        openrouter_key=apiKey,
        event_callback=event_handler
    )
    
    def run_in_thread():
        try:
            state.orchestrator.run_assessment()
        except Exception as e:
            event_handler({"type": "error", "message": f"Orchestrator Error: {str(e)}"})
        finally:
            state.is_running = False
            
    threading.Thread(target=run_in_thread, daemon=True).start()
    return {"status": "started"}

@app.post("/stop")
async def stop_assessment():
    if state.orchestrator:
        state.orchestrator.stop_event.set()
        state.is_running = False
    return {"status": "stopped"}

@app.post("/extra-info")
async def extra_info(info: str = Form(...)):
    if state.orchestrator:
        state.orchestrator.add_extra_info(info)
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(socket_app, host="0.0.0.0", port=8000, log_level="info")
