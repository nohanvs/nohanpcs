import os, subprocess, platform, psutil, json, threading, time, base64, io, re, socket, requests
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, Response
from functools import wraps

try:
    from ctypes import windll, cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    audio_available = True
except:
    audio_available = False

try:
    import mss
    screenshot_available = True
except:
    screenshot_available = False

try:
    import pyperclip
    clipboard_available = True
except:
    clipboard_available = False

try:
    import wmi as wmi_module
    wmi_available = True
except:
    wmi_available = False

app = Flask(__name__)
app.secret_key = os.urandom(24)

AUTH_PASSWORD = "admin123"
AUTHENTICATED_SESSIONS = set()

HOSTNAME = platform.node()
USERNAME = os.getlogin()
PANEL_ID = f"{USERNAME}@{HOSTNAME}"

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1520928281518407785/iVJGAatuP-2JKqaiRRo8LnmzPvWL4NyBdrcczFP6WlJlHwCR4Jhjep4gwRIih7UizokM"
HUB_URL = ""

connected_panels = {}
connected_panels[PANEL_ID] = {
    'hostname': HOSTNAME,
    'username': USERNAME,
    'ip': None,
    'last_seen': time.time()
}

downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
notepad_content = {"text": ""}
download_tasks = {}
script_library = []
favorites = [
    {"name": "Downloads", "path": downloads_folder},
    {"name": "Desktop", "path": os.path.join(os.path.expanduser("~"), "Desktop")},
    {"name": "Documents", "path": os.path.join(os.path.expanduser("~"), "Documents")},
    {"name": "Pictures", "path": os.path.join(os.path.expanduser("~"), "Pictures")},
    {"name": "C:", "path": "C:\\"},
]

def send_discord_webhook(event_type, details=""):
    if not DISCORD_WEBHOOK:
        return
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        if event_type == "login":
            color = 0x00b894
            title = "Login detectado"
            desc = f"**{USERNAME}** conectou no painel"
        elif event_type == "start":
            color = 0x6c5ce7
            title = "Painel iniciado"
            desc = f"PC **{HOSTNAME}** ({USERNAME}) ligou o painel"
        else:
            color = 0xff6b6b
            title = event_type
            desc = details

        payload = {
            "embeds": [{
                "color": color,
                "title": f"Remote Control - {title}",
                "description": desc,
                "fields": [
                    {"name": "PC", "value": HOSTNAME, "inline": True},
                    {"name": "Usuario", "value": USERNAME, "inline": True},
                    {"name": "IP Local", "value": local_ip, "inline": True},
                ],
                "footer": {"text": "Remote Control Family"},
                "timestamp": datetime.utcnow().isoformat()
            }]
        }
        requests.post(DISCORD_WEBHOOK, json=payload, timeout=5)
    except:
        pass

def register_with_hub():
    if not HUB_URL:
        return
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        requests.post(f"{HUB_URL}/api/register", json={
            "panel_id": PANEL_ID,
            "hostname": HOSTNAME,
            "username": USERNAME,
            "ip": local_ip,
            "port": 5000
        }, timeout=5)
    except:
        pass

def hub_heartbeat():
    while True:
        try:
            register_with_hub()
        except:
            pass
        time.sleep(30)

PAGE_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Remote Control Ultimate</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#06060f;--bg2:#0c0c1d;--bg3:#111128;--card:#141432;--card2:#1a1a40;--accent:#6c5ce7;--accent2:#a29bfe;--green:#00b894;--red:#ff6b6b;--yellow:#ffeaa7;--blue:#74b9ff;--pink:#fd79a8;--text:#fff;--text2:#8b8baa;--border:rgba(255,255,255,.06);--glow:rgba(108,92,231,.15)}
html,body{height:100%;font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);overflow:hidden}

/* ── LOGIN ── */
.login-bg{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:radial-gradient(ellipse at 30% 50%,#0c0c1d 0%,#06060f 100%);z-index:9999}
.login-card{width:420px;max-width:92vw;padding:50px 40px;background:linear-gradient(145deg,rgba(20,20,50,.9),rgba(10,10,30,.95));border:1px solid var(--border);border-radius:28px;backdrop-filter:blur(30px);box-shadow:0 25px 80px rgba(0,0,0,.6),0 0 120px var(--glow);text-align:center;animation:fadeUp .6s ease}
@keyframes fadeUp{from{opacity:0;transform:translateY(30px)}to{opacity:1;transform:translateY(0)}}
.login-icon{width:90px;height:90px;margin:0 auto 28px;background:linear-gradient(135deg,var(--accent),#4834d4);border-radius:24px;display:flex;align-items:center;justify-content:center;font-size:40px;box-shadow:0 10px 40px var(--glow)}
.login-card h1{font-size:28px;font-weight:800;margin-bottom:6px;background:linear-gradient(135deg,#fff,var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.login-card p{color:var(--text2);font-size:14px;margin-bottom:32px}
.login-card input{width:100%;padding:16px 20px 16px 50px;background:rgba(255,255,255,.06);border:1px solid var(--border);border-radius:14px;color:#fff;font-size:15px;transition:.3s}
.login-card input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 25px var(--glow)}
.login-card .input-wrap{position:relative}
.login-card .input-wrap i{position:absolute;left:18px;top:50%;transform:translateY(-50%);color:var(--text2);font-size:16px}
.login-card button{width:100%;padding:16px;margin-top:20px;background:linear-gradient(135deg,var(--accent),#4834d4);border:none;border-radius:14px;color:#fff;font-size:16px;font-weight:700;cursor:pointer;transition:.3s;letter-spacing:.5px}
.login-card button:hover{transform:translateY(-2px);box-shadow:0 12px 35px var(--glow)}
.login-error{color:var(--red);margin-top:14px;font-size:13px;min-height:20px}

/* ── LAYOUT ── */
.app{display:none;height:100vh;flex-direction:column}
.app.active{display:flex}
.topbar{height:56px;background:rgba(12,12,29,.9);backdrop-filter:blur(20px);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 24px;gap:16px;flex-shrink:0;z-index:100}
.topbar-logo{font-size:20px;font-weight:800;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.topbar-tabs{display:flex;gap:4px;margin-left:24px;flex:1;overflow-x:auto}
.topbar-tab{padding:8px 18px;background:transparent;border:none;color:var(--text2);font-size:13px;font-weight:600;border-radius:10px;cursor:pointer;transition:.2s;white-space:nowrap;display:flex;align-items:center;gap:8px}
.topbar-tab:hover{color:#fff;background:rgba(255,255,255,.05)}
.topbar-tab.active{color:#fff;background:var(--accent);box-shadow:0 4px 15px var(--glow)}
.topbar-right{display:flex;align-items:center;gap:12px}
.topbar-right .status{width:8px;height:8px;background:var(--green);border-radius:50%;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.btn-icon{width:38px;height:38px;border:1px solid var(--border);background:rgba(255,255,255,.04);border-radius:10px;color:var(--text2);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:.2s;font-size:15px}
.btn-icon:hover{color:#fff;background:rgba(255,255,255,.08);border-color:var(--accent)}
.content{flex:1;overflow-y:auto;padding:24px;background:var(--bg)}

/* ── SECTIONS ── */
.section{display:none}
.section.active{display:block;animation:fadeIn .3s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}

/* ── STATS ROW ── */
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}
.stat{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:22px;transition:.3s}
.stat:hover{border-color:rgba(108,92,231,.3);transform:translateY(-2px)}
.stat .ico{width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:18px;margin-bottom:14px}
.stat .ico.c1{background:rgba(108,92,231,.15);color:var(--accent)}
.stat .ico.c2{background:rgba(0,184,148,.15);color:var(--green)}
.stat .ico.c3{background:rgba(255,107,107,.15);color:var(--red)}
.stat .ico.c4{background:rgba(116,185,255,.15);color:var(--blue)}
.stat .lbl{font-size:12px;color:var(--text2);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}
.stat .val{font-size:30px;font-weight:800}
.stat .sub{font-size:12px;color:var(--text2);margin-top:4px}
.pbar{width:100%;height:5px;background:rgba(255,255,255,.06);border-radius:3px;margin-top:14px;overflow:hidden}
.pfill{height:100%;border-radius:3px;transition:width .5s}
.pfill.c1{background:linear-gradient(90deg,var(--accent),var(--accent2))}
.pfill.c2{background:var(--green)}
.pfill.c3{background:var(--red)}

/* ── GRID ── */
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:16px;margin-bottom:24px}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;margin-bottom:24px}

/* ── CARD ── */
.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:24px;transition:.3s}
.card:hover{border-color:rgba(108,92,231,.2)}
.card-h{display:flex;align-items:center;gap:12px;margin-bottom:18px}
.card-h i{font-size:17px;color:var(--accent)}
.card-h h3{font-size:15px;font-weight:700}
.card-h span{margin-left:auto;font-size:12px;color:var(--text2)}

/* ── BUTTONS ── */
.bgrid{display:grid;gap:10px}
.bgrid.g2{grid-template-columns:1fr 1fr}
.bgrid.g3{grid-template-columns:1fr 1fr 1fr}
.bgrid.g4{grid-template-columns:repeat(4,1fr)}
.btn{padding:14px;border:none;border-radius:12px;font-size:13px;font-weight:600;cursor:pointer;transition:.25s;display:flex;align-items:center;justify-content:center;gap:8px;color:#fff}
.btn:hover{transform:translateY(-2px);filter:brightness(1.15)}
.btn:active{transform:translateY(0)}
.btn.a{background:var(--accent)}.btn.g{background:var(--green);color:#000}.btn.r{background:var(--red)}.btn.y{background:var(--yellow);color:#000}.btn.b{background:var(--blue);color:#000}.btn.p{background:var(--pink)}.btn.d{background:rgba(255,255,255,.06);border:1px solid var(--border)}.btn.o{background:transparent;border:1px solid var(--border)}

/* ── VOLUME ── */
.vol-row{display:flex;align-items:center;gap:16px;margin-bottom:16px}
.vol-slider{flex:1;-webkit-appearance:none;height:8px;border-radius:4px;background:rgba(255,255,255,.08);outline:none}
.vol-slider::-webkit-slider-thumb{-webkit-appearance:none;width:26px;height:26px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent2));cursor:pointer;box-shadow:0 0 20px var(--glow)}
.vol-val{font-size:28px;font-weight:800;min-width:70px;text-align:center}

/* ── PROCESS LIST ── */
.plist{max-height:380px;overflow-y:auto}
.pitem{display:grid;grid-template-columns:1fr 70px 70px 80px;gap:8px;align-items:center;padding:10px 12px;border-radius:10px;transition:.15s;font-size:13px}
.pitem:hover{background:rgba(255,255,255,.04)}
.pitem.hdr{color:var(--text2);font-size:11px;text-transform:uppercase;letter-spacing:1px;font-weight:700}
.pname{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pval{text-align:right;color:var(--text2);font-size:12px}
.btn-k{padding:4px 12px;background:rgba(255,107,107,.12);border:1px solid rgba(255,107,107,.2);border-radius:8px;color:var(--red);cursor:pointer;font-size:11px;transition:.2s}
.btn-k:hover{background:var(--red);color:#fff}

/* ── TERMINAL ── */
.term{background:#080812;padding:18px;border-radius:14px;font-family:'Cascadia Code','Fira Code',monospace;font-size:13px;max-height:300px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;border:1px solid var(--border);color:var(--green)}
.term-row{display:flex;gap:10px;margin-bottom:14px}
.term-row input{flex:1;padding:14px 18px;background:rgba(255,255,255,.05);border:1px solid var(--border);border-radius:12px;color:#fff;font-family:'Cascadia Code',monospace;font-size:13px}
.term-row input:focus{outline:none;border-color:var(--accent)}

/* ── FILE MANAGER ── */
.fm-toolbar{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
.fm-path{flex:1;padding:12px 16px;background:rgba(255,255,255,.05);border:1px solid var(--border);border-radius:12px;color:#fff;font-size:13px}
.fm-path:focus{outline:none;border-color:var(--accent)}
.fm-list{max-height:420px;overflow-y:auto;border:1px solid var(--border);border-radius:12px}
.fm-item{display:grid;grid-template-columns:24px 1fr auto auto;gap:12px;align-items:center;padding:10px 14px;transition:.15s;cursor:pointer;font-size:13px}
.fm-item:hover{background:rgba(255,255,255,.04)}
.fm-item .fi{font-size:18px;text-align:center;width:24px}
.fm-item .fn{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fm-item .fs{font-size:11px;color:var(--text2);text-align:right}
.fm-item .fm{font-size:11px;color:var(--text2)}
.fm-bread{display:flex;gap:4px;margin-bottom:12px;flex-wrap:wrap}
.fm-bread span{padding:6px 12px;background:rgba(255,255,255,.05);border-radius:8px;font-size:12px;cursor:pointer;transition:.2s;color:var(--text2)}
.fm-bread span:hover,.fm-bread span:last-child{color:var(--accent);background:rgba(108,92,231,.1)}

/* ── NOTEPAD ── */
.np-area{width:100%;min-height:280px;background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:14px;padding:18px;color:#fff;font-family:'Cascadia Code',monospace;font-size:14px;resize:vertical;line-height:1.7}
.np-area:focus{outline:none;border-color:var(--accent)}
.np-bar{display:flex;gap:10px;margin-top:12px}

/* ── AI CHAT ── */
.ai-chat{display:flex;flex-direction:column;height:calc(100vh - 160px);max-height:600px}
.ai-messages{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
.ai-msg{max-width:80%;padding:14px 18px;border-radius:16px;font-size:14px;line-height:1.6;animation:fadeUp .3s ease}
.ai-msg.user{align-self:flex-end;background:var(--accent);border-bottom-right-radius:4px}
.ai-msg.bot{align-self:flex-start;background:var(--card2);border:1px solid var(--border);border-bottom-left-radius:4px}
.ai-msg pre{background:#000;padding:10px;border-radius:8px;margin-top:8px;font-size:12px;overflow-x:auto;font-family:'Cascadia Code',monospace}
.ai-input{display:flex;gap:10px;padding:16px;border-top:1px solid var(--border)}
.ai-input input{flex:1;padding:14px 18px;background:rgba(255,255,255,.06);border:1px solid var(--border);border-radius:12px;color:#fff;font-size:14px}
.ai-input input:focus{outline:none;border-color:var(--accent)}

/* ── SCREENSHOT ── */
.ss-preview{background:#000;border-radius:14px;overflow:hidden;margin-top:14px;border:1px solid var(--border)}
.ss-preview img{width:100%;display:block}

/* ── DOWNLOAD ── */
.dl-input{display:flex;gap:10px;margin-bottom:12px}
.dl-input input{flex:1;padding:14px 18px;background:rgba(255,255,255,.05);border:1px solid var(--border);border-radius:12px;color:#fff;font-size:14px}
.dl-input input:focus{outline:none;border-color:var(--accent)}

/* ── SERVICES ── */
.svc-list{max-height:350px;overflow-y:auto}
.svc-item{display:grid;grid-template-columns:1fr auto auto auto;gap:10px;align-items:center;padding:10px 12px;border-radius:8px;font-size:13px;transition:.15s}
.svc-item:hover{background:rgba(255,255,255,.04)}
.svc-item.hdr{color:var(--text2);font-size:11px;text-transform:uppercase;letter-spacing:1px;font-weight:700}
.svc-state{font-size:11px;padding:3px 10px;border-radius:6px;font-weight:600}
.svc-state.on{background:rgba(0,184,148,.15);color:var(--green)}
.svc-state.off{background:rgba(255,107,107,.15);color:var(--red)}
.btn-sm{padding:5px 12px;background:rgba(255,255,255,.06);border:1px solid var(--border);border-radius:8px;color:var(--text2);cursor:pointer;font-size:11px;transition:.2s}
.btn-sm:hover{color:#fff;background:rgba(255,255,255,.1)}

/* ── DRIVES ── */
.drive-item{margin-bottom:14px}
.drive-head{display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px}
.drive-head strong{color:var(--text)}

/* ── MODAL ── */
.modal-bg{position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(8px);display:none;align-items:center;justify-content:center;z-index:999}
.modal-bg.active{display:flex}
.modal{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:30px;width:500px;max-width:92vw;max-height:80vh;overflow-y:auto}
.modal h3{margin-bottom:20px;font-size:18px}
.modal textarea{width:100%;min-height:150px;background:rgba(0,0,0,.3);border:1px solid var(--border);border-radius:12px;padding:14px;color:#fff;font-family:'Cascadia Code',monospace;font-size:13px;resize:vertical}
.modal textarea:focus{outline:none;border-color:var(--accent)}

/* ── TOAST ── */
.toast-c{position:fixed;bottom:24px;right:24px;z-index:9999;display:flex;flex-direction:column;gap:10px}
.toast{padding:14px 22px;background:var(--card);border:1px solid var(--border);border-radius:14px;display:flex;align-items:center;gap:12px;font-size:13px;animation:slideR .3s ease;box-shadow:0 10px 40px rgba(0,0,0,.4)}
.toast.ok{border-left:3px solid var(--green)}.toast.err{border-left:3px solid var(--red)}
@keyframes slideR{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{width:5px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:rgba(255,255,255,.1);border-radius:3px}::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,.2)}

/* ── RESPONSIVE ── */
@media(max-width:900px){.stats{grid-template-columns:1fr 1fr}.grid2,.grid3{grid-template-columns:1fr}.bgrid.g3,.bgrid.g4{grid-template-columns:1fr 1fr}.topbar-tabs{gap:2px}.topbar-tab{padding:8px 12px;font-size:12px}}
@media(max-width:600px){.stats{grid-template-columns:1fr}.topbar{padding:0 12px}.topbar-tab span.txt{display:none}.content{padding:16px}}
</style>
</head>
<body>

<!-- LOGIN -->
<div class="login-bg" id="loginBg">
<div class="login-card">
<div class="login-icon"><i class="fas fa-shield-halved"></i></div>
<h1>Remote Control</h1>
<p>Controle total do seu PC de qualquer lugar</p>
<div class="input-wrap"><i class="fas fa-lock"></i><input type="password" id="pw" placeholder="Digite sua senha" onkeypress="if(event.key==='Enter')doLogin()"></div>
<button onclick="doLogin()"><i class="fas fa-arrow-right"></i> Entrar</button>
<div class="login-error" id="loginErr"></div>
</div>
</div>

<!-- APP -->
<div class="app" id="app">
<div class="topbar">
<div class="topbar-logo">⚡ RC Ultimate</div>
<div class="topbar-tabs" id="tabs">
<button class="topbar-tab active" data-tab="dashboard"><i class="fas fa-chart-pie"></i><span class="txt">Dashboard</span></button>
<button class="topbar-tab" data-tab="power"><i class="fas fa-power-off"></i><span class="txt">Energia</span></button>
<button class="topbar-tab" data-tab="files"><i class="fas fa-folder-open"></i><span class="txt">Arquivos</span></button>
<button class="topbar-tab" data-tab="apps"><i class="fas fa-th"></i><span class="txt">Apps</span></button>
<button class="topbar-tab" data-tab="tools"><i class="fas fa-tools"></i><span class="txt">Ferramentas</span></button>
<button class="topbar-tab" data-tab="terminal"><i class="fas fa-terminal"></i><span class="txt">Terminal</span></button>
<button class="topbar-tab" data-tab="ai"><i class="fas fa-robot"></i><span class="txt">IA</span></button>
</div>
<div class="topbar-right">
<div class="panel-selector" id="panelSelector" style="position:relative">
<button class="btn-icon" onclick="togglePanelList()" title="Selecionar PC" style="font-size:12px;gap:6px;width:auto;padding:0 12px">
<i class="fas fa-desktop"></i><span id="currentPanelName" style="font-size:12px">-</span><i class="fas fa-chevron-down" style="font-size:10px"></i>
</button>
<div class="panel-dropdown" id="panelDropdown" style="display:none;position:absolute;top:100%;right:0;margin-top:8px;background:var(--card);border:1px solid var(--border);border-radius:12px;padding:8px;min-width:220px;z-index:9999;box-shadow:0 10px 40px rgba(0,0,0,.5)"></div>
</div>
<div class="status"></div>
<button class="btn-icon" onclick="doLogout()" title="Sair"><i class="fas fa-sign-out-alt"></i></button>
</div>
</div>

<div class="content">
<!-- ═══ DASHBOARD ═══ -->
<div class="section active" id="sec-dashboard">
<div class="stats">
<div class="stat"><div class="ico c1"><i class="fas fa-microchip"></i></div><div class="lbl">CPU</div><div class="val" id="d-cpu">-</div><div class="sub" id="d-cpuinfo">-</div><div class="pbar"><div class="pfill c1" id="d-cpubar" style="width:0"></div></div></div>
<div class="stat"><div class="ico c2"><i class="fas fa-memory"></i></div><div class="lbl">RAM</div><div class="val" id="d-ram">-</div><div class="sub" id="d-raminfo">-</div><div class="pbar"><div class="pfill c2" id="d-rambar" style="width:0"></div></div></div>
<div class="stat"><div class="ico c3"><i class="fas fa-hdd"></i></div><div class="lbl">Disco</div><div class="val" id="d-disk">-</div><div class="sub" id="d-diskinfo">-</div><div class="pbar"><div class="pfill c3" id="d-diskbar" style="width:0"></div></div></div>
<div class="stat"><div class="ico c4"><i class="fas fa-network-wired"></i></div><div class="lbl">Rede</div><div class="val" id="d-host">-</div><div class="sub" id="d-ip">-</div><div class="sub" id="d-net">↑ 0 MB ↓ 0 MB</div></div>
</div>
<div class="grid2">
<div class="card"><div class="card-h"><i class="fas fa-volume-up"></i><h3>Volume</h3><span id="vol-pct">50%</span></div>
<div class="vol-row"><button class="btn d" style="width:44px;height:44px;padding:0" onclick="volSet(Math.max(0,volCur-5))"><i class="fas fa-minus"></i></button><input type="range" class="vol-slider" id="volSlider" min="0" max="100" value="50" oninput="volSet(this.value)"><button class="btn d" style="width:44px;height:44px;padding:0" onclick="volSet(Math.min(100,volCur+5))"><i class="fas fa-plus"></i></button></div>
<div class="bgrid g2"><button class="btn y" onclick="volMute(true)"><i class="fas fa-volume-mute"></i> Mudo</button><button class="btn g" onclick="volMute(false)"><i class="fas fa-volume-up"></i> Ativar</button></div></div>
<div class="card"><div class="card-h"><i class="fas fa-robot"></i><h3>IA Assistant</h3><span>Rápido</span></div>
<div class="ai-chat" style="height:auto;max-height:250px"><div class="ai-messages" id="aiQuick" style="min-height:120px"><div class="ai-msg bot">Olá! Sou sua IA. Digite algo ou use os botões abaixo.</div></div>
<div class="ai-input" style="border:none;padding:10px 0 0"><input type="text" id="aiQuickIn" placeholder="Pergunte algo..." onkeypress="if(event.key==='Enter')aiSend('quick')"><button class="btn a" style="width:auto;padding:12px 20px" onclick="aiSend('quick')"><i class="fas fa-paper-plane"></i></button></div></div>
</div>
</div>
</div>

<!-- ═══ POWER ═══ -->
<div class="section" id="sec-power">
<div class="grid2">
<div class="card"><div class="card-h"><i class="fas fa-power-off"></i><h3>Controle de Energia</h3></div>
<div class="bgrid g3">
<button class="btn r" onclick="pwr('shutdown')"><i class="fas fa-power-off"></i> Desligar</button>
<button class="btn r" onclick="pwr('shutdown-now')"><i class="fas fa-bolt"></i> Desligar Agora</button>
<button class="btn y" onclick="pwr('restart')"><i class="fas fa-sync"></i> Reiniciar</button>
<button class="btn y" onclick="pwr('restart-now')"><i class="fas fa-bolt"></i> Reiniciar Agora</button>
<button class="btn b" onclick="pwr('hibernate')"><i class="fas fa-moon"></i> Hibernar</button>
<button class="btn a" onclick="pwr('sleep')"><i class="fas fa-bed"></i> Dormir</button>
<button class="btn d" onclick="pwr('lock')"><i class="fas fa-lock"></i> Bloquear</button>
<button class="btn d" onclick="pwr('logoff')"><i class="fas fa-sign-out-alt"></i> Logoff</button>
<button class="btn g" onclick="pwr('cancel')" style="grid-column:span 3"><i class="fas fa-times"></i> Cancelar Agendamento</button>
</div></div>
<div class="card"><div class="card-h"><i class="fas fa-info-circle"></i><h3>Info do Sistema</h3></div>
<div style="font-size:14px;line-height:2.2" id="sysInfo"><p style="color:var(--text2)">Carregando...</p></div></div>
</div>
</div>

<!-- ═══ FILES ═══ -->
<div class="section" id="sec-files">
<div class="card">
<div class="card-h"><i class="fas fa-folder-open"></i><h3>Gerenciador de Arquivos</h3><span id="fm-count">0 itens</span></div>
<div class="fm-toolbar">
<input class="fm-path" id="fmPath" value="C:\\" onkeypress="if(event.key==='Enter')fmGo(this.value)">
<button class="btn a" onclick="fmGo(document.getElementById('fmPath').value)"><i class="fas fa-arrow-right"></i></button>
<button class="btn d" onclick="fmNewFolder()"><i class="fas fa-folder-plus"></i></button>
<button class="btn d" onclick="fmUpload()"><i class="fas fa-upload"></i></button>
<button class="btn d" onclick="fmSearch()"><i class="fas fa-search"></i></button>
</div>
<div class="fm-bread" id="fmBread"></div>
<div class="fm-list" id="fmList"><p style="padding:20px;color:var(--text2)">Carregando...</p></div>
</div>
</div>

<!-- ═══ APPS ═══ -->
<div class="section" id="sec-apps">
<div class="grid2">
<div class="card"><div class="card-h"><i class="fas fa-rocket"></i><h3>Abrir Aplicativo</h3></div>
<div class="bgrid g3">
<button class="btn a" onclick="openApp('brave')"><i class="fas fa-globe"></i> Brave</button>
<button class="btn a" onclick="openApp('firefox')"><i class="fab fa-firefox-browser"></i> Firefox</button>
<button class="btn a" onclick="openApp('edge')"><i class="fab fa-edge"></i> Edge</button>
<button class="btn d" onclick="openApp('notepad')"><i class="fas fa-file-alt"></i> Notepad</button>
<button class="btn d" onclick="openApp('calculator')"><i class="fas fa-calculator"></i> Calculadora</button>
<button class="btn d" onclick="openApp('explorer')"><i class="fas fa-folder"></i> Explorador</button>
<button class="btn d" onclick="openApp('cmd')"><i class="fas fa-terminal"></i> CMD</button>
<button class="btn d" onclick="openApp('powershell')"><i class="fas fa-code"></i> PowerShell</button>
<button class="btn d" onclick="openApp('taskmgr')"><i class="fas fa-chart-bar"></i> Task Manager</button>
<button class="btn d" onclick="openApp('paint')"><i class="fas fa-paint-brush"></i> Paint</button>
<button class="btn d" onclick="openApp('regedit')"><i class="fas fa-cogs"></i> RegEdit</button>
<button class="btn d" onclick="openApp('control')"><i class="fas fa-sliders-h"></i> Painel</button>
<button class="btn d" onclick="openApp('dxdiag')"><i class="fas fa-info-circle"></i> DXDiag</button>
<button class="btn d" onclick="openApp('resmon')"><i class="fas fa-heartbeat"></i> ResMon</button>
<button class="btn d" onclick="openApp('charmap')"><i class="fas fa-font"></i> CharMap</button>
</div></div>
<div class="card"><div class="card-h"><i class="fas fa-file-alt"></i><h3>Bloco de Notas</h3></div>
<textarea class="np-area" id="npText" placeholder="Escreva algo aqui..."></textarea>
<div class="np-bar"><button class="btn g" onclick="npSave()"><i class="fas fa-save"></i> Salvar</button><button class="btn a" onclick="npOpen()"><i class="fas fa-external-link-alt"></i> Abrir no PC</button></div></div>
</div>
</div>

<!-- ═══ TOOLS ═══ -->
<div class="section" id="sec-tools">
<div class="grid2">
<div class="card"><div class="card-h"><i class="fas fa-camera"></i><h3>Screenshot Remoto</h3></div>
<button class="btn a" onclick="takeScreenshot()" style="width:100%"><i class="fas fa-camera"></i> Capturar Tela</button>
<div class="ss-preview" id="ssPreview" style="display:none"><img id="ssImg"></div></div>
<div class="card"><div class="card-h"><i class="fas fa-clipboard"></i><h3>Clipboard Sync</h3></div>
<textarea class="np-area" id="clipText" style="min-height:100px" placeholder="Cole ou escreva algo..."></textarea>
<div class="np-bar"><button class="btn a" onclick="clipGet()"><i class="fas fa-download"></i> Pegar do PC</button><button class="btn g" onclick="clipSet()"><i class="fas fa-upload"></i> Enviar ao PC</button></div></div>
<div class="card"><div class="card-h"><i class="fas fa-cloud-download-alt"></i><h3>Download</h3></div>
<div class="dl-input"><input type="text" id="dlUrl" placeholder="URL do arquivo..."></div>
<div class="dl-input" style="margin-top:-4px"><input type="text" id="dlName" placeholder="Nome (opcional)"></div>
<button class="btn a" style="width:100%" onclick="dlStart()"><i class="fas fa-download"></i> Baixar</button>
<div id="dlProg" style="margin-top:14px;display:none"><div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px"><span id="dlStatus">Baixando...</span><span id="dlPct">0%</span></div><div class="pbar"><div class="pfill c1" id="dlBar" style="width:0"></div></div></div></div>
<div class="card"><div class="card-h"><i class="fas fa-broom"></i><h3>Limpeza & Rede</h3></div>
<div class="bgrid g2">
<button class="btn r" onclick="sysAct('clear-temp')"><i class="fas fa-trash"></i> Limpar Temp</button>
<button class="btn r" onclick="sysAct('empty-recycle')"><i class="fas fa-recycle"></i> Esvaziar Lixeira</button>
<button class="btn d" onclick="sysAct('flush-dns')"><i class="fas fa-sync"></i> Flush DNS</button>
<button class="btn d" onclick="sysAct('clear-recent')"><i class="fas fa-history"></i> Limpar Recentes</button>
<button class="btn d" onclick="sysAct('clear-clipboard')"><i class="fas fa-clipboard"></i> Limpar Clip</button>
<button class="btn d" onclick="sysAct('disable-firewall')"><i class="fas fa-shield-alt"></i> Desativar FW</button>
<button class="btn d" onclick="sysAct('enable-firewall')"><i class="fas fa-shield-alt"></i> Ativar FW</button>
</div></div>
<div class="card"><div class="card-h"><i class="fas fa-hdd"></i><h3>Discos</h3></div><div id="driveList"><p style="color:var(--text2)">Carregando...</p></div></div>
<div class="card"><div class="card-h"><i class="fas fa-cogs"></i><h3>Serviços</h3></div>
<div class="svc-list" id="svcList"><p style="color:var(--text2)">Carregando...</p></div></div>
</div>
</div>

<!-- ═══ TERMINAL ═══ -->
<div class="section" id="sec-terminal">
<div class="card"><div class="card-h"><i class="fas fa-terminal"></i><h3>Terminal Remoto</h3></div>
<div class="term-row"><input type="text" id="cmdIn" placeholder="Digite um comando..." onkeypress="if(event.key==='Enter')runCmd()"><button class="btn a" onclick="runCmd()"><i class="fas fa-play"></i> Executar</button></div>
<div class="term" id="cmdOut">Remote Control Terminal v3.0<br>─────────────────────────────<br></div></div>
<div class="card" style="margin-top:16px"><div class="card-h"><i class="fas fa-list"></i><h3>Processos</h3><button class="btn-sm" onclick="loadProcs()" style="margin-left:auto"><i class="fas fa-sync"></i></button></div>
<div class="plist" id="procList"><p style="color:var(--text2)">Carregando...</p></div></div>
<div class="card" style="margin-top:16px"><div class="card-h"><i class="fas fa-code"></i><h3>Scripts Python</h3></div>
<textarea class="np-area" id="scriptCode" style="min-height:120px" placeholder="print('Hello World')"></textarea>
<div class="np-bar"><button class="btn a" onclick="runScript()"><i class="fas fa-play"></i> Executar</button><button class="btn g" onclick="saveScript()"><i class="fas fa-save"></i> Salvar</button></div>
<div class="term" id="scriptOut" style="margin-top:12px;display:none"></div></div>
</div>

<!-- ═══ AI ═══ -->
<div class="section" id="sec-ai">
<div class="card" style="height:calc(100vh - 160px)">
<div class="card-h"><i class="fas fa-robot"></i><h3>AI Assistant</h3><span style="color:var(--green)">● Online</span></div>
<div class="ai-chat">
<div class="ai-messages" id="aiMsgs">
<div class="ai-msg bot">Olá! Sou sua IA assistente. Posso controlar seu PC, executar comandos, abrir apps, e muito mais. O que deseja?</div>
</div>
<div class="ai-input">
<input type="text" id="aiIn" placeholder="Ex: desligar o pc, abrir brave, screenshot, cpu..." onkeypress="if(event.key==='Enter')aiSend('full')">
<button class="btn a" style="width:auto;padding:14px 24px" onclick="aiSend('full')"><i class="fas fa-paper-plane"></i></button>
</div>
<div style="display:flex;gap:8px;padding:10px 16px;flex-wrap:wrap">
<button class="btn o" style="font-size:11px;padding:6px 12px" onclick="aiQuick('cpu')">CPU</button>
<button class="btn o" style="font-size:11px;padding:6px 12px" onclick="aiQuick('ram')">RAM</button>
<button class="btn o" style="font-size:11px;padding:6px 12px" onclick="aiQuick('disco')">Disco</button>
<button class="btn o" style="font-size:11px;padding:6px 12px" onclick="aiQuick('ip')">IP</button>
<button class="btn o" style="font-size:11px;padding:6px 12px" onclick="aiQuick('screenshot')">Screenshot</button>
<button class="btn o" style="font-size:11px;padding:6px 12px" onclick="aiQuick('abrir brave')">Abrir Brave</button>
<button class="btn o" style="font-size:11px;padding:6px 12px" onclick="aiQuick('limpar temporários')">Limpar</button>
<button class="btn o" style="font-size:11px;padding:6px 12px" onclick="aiQuick('travar pc')">Travar</button>
<button class="btn o" style="font-size:11px;padding:6px 12px" onclick="aiQuick('ajuda')">Ajuda</button>
</div>
</div>
</div>
</div>
</div>
</div>

<!-- MODAL -->
<div class="modal-bg" id="modal"><div class="modal" id="modalContent"></div></div>
<div class="toast-c" id="toastC"></div>
<input type="file" id="fileUpload" style="display:none">

<script>
let volCur=50,curTab='dashboard';
const api=async(u,o={})=>{const r=await fetch(u,{...o,headers:{'Content-Type':'application/json',...o.headers}});if(r.status===401){doLogout();return null}return r.json()};
function toast(m,t='ok'){const c=document.getElementById('toastC'),d=document.createElement('div');d.className='toast '+t;d.innerHTML=`<i class="fas fa-${t==='ok'?'check-circle':'exclamation-circle'}"></i> ${m}`;c.appendChild(d);setTimeout(()=>d.remove(),3000)}
function showModal(h){document.getElementById('modalContent').innerHTML=h;document.getElementById('modal').classList.add('active')}
function hideModal(){document.getElementById('modal').classList.remove('active')}
document.getElementById('modal').addEventListener('click',e=>{if(e.target===e.currentTarget)hideModal()});

// ── TABS ──
document.querySelectorAll('.topbar-tab').forEach(t=>{
t.addEventListener('click',()=>{
document.querySelectorAll('.topbar-tab').forEach(x=>x.classList.remove('active'));
document.querySelectorAll('.section').forEach(x=>x.classList.remove('active'));
t.classList.add('active');
const tab=t.dataset.tab;
document.getElementById('sec-'+tab).classList.add('active');
curTab=tab;
if(tab==='dashboard'){loadSys();loadVol()}
if(tab==='files')fmGo(document.getElementById('fmPath').value);
if(tab==='terminal')loadProcs();
if(tab==='tools'){loadDrives();loadServices()}
if(tab==='apps')npLoad();
})});

// ── AUTH ──
async function doLogin(){const pw=document.getElementById('pw').value;const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pw})});if(r.ok){document.getElementById('loginBg').style.display='none';document.getElementById('app').classList.add('active');init();initPanel()}else{document.getElementById('loginErr').textContent='Senha incorreta!'}}
async function doLogout(){await fetch('/api/logout',{method:'POST'});location.reload()}

function init(){loadSys();loadVol();setInterval(()=>{if(curTab==='dashboard'){loadSys();loadVol()}if(curTab==='terminal')loadProcs()},3000)}

// ── SYSTEM ──
async function loadSys(){const d=await api('/api/system-info');if(!d)return;
document.getElementById('d-cpu').textContent=d.cpu_percent+'%';
document.getElementById('d-cpubar').style.width=d.cpu_percent+'%';
document.getElementById('d-cpuinfo').textContent=d.cpu_count+' cores • '+d.cpu_freq+' MHz';
document.getElementById('d-ram').textContent=d.memory_percent+'%';
document.getElementById('d-rambar').style.width=d.memory_percent+'%';
document.getElementById('d-raminfo').textContent=d.memory_used+' / '+d.memory_total+' GB';
document.getElementById('d-disk').textContent=d.disk_percent+'%';
document.getElementById('d-diskbar').style.width=d.disk_percent+'%';
document.getElementById('d-diskinfo').textContent=d.disk_used+' / '+d.disk_total+' GB';
document.getElementById('d-host').textContent=d.hostname;
document.getElementById('d-ip').textContent=d.username;
document.getElementById('d-net').textContent='↑ '+d.net_sent+' MB ↓ '+d.net_recv+' MB';
let info=`<div><span style="color:var(--text2)">Hostname:</span> <strong>${d.hostname}</strong></div>
<div><span style="color:var(--text2)">Usuário:</span> <strong>${d.username}</strong></div>
<div><span style="color:var(--text2)">Sistema:</span> <strong>${d.os}</strong></div>
<div><span style="color:var(--text2)">Uptime:</span> <strong>${d.uptime}</strong></div>
<div><span style="color:var(--text2)">Boot:</span> <strong>${d.boot_time}</strong></div>
<div><span style="color:var(--text2)">CPU Cores:</span> <strong>${d.cpu_count}</strong></div>`;
if(d.battery)info+=`<div><span style="color:var(--text2)">Bateria:</span> <strong>${d.battery.percent}% ${d.battery.plugged?'(Carregando)':''}</strong></div>`;
if(Object.keys(d.temps||{}).length)info+=`<div><span style="color:var(--text2)">Temp:</span> <strong>${Object.entries(d.temps).map(([k,v])=>k+': '+v+'°C').join(', ')}</strong></div>`;
document.getElementById('sysInfo').innerHTML=info}

// ── VOLUME ──
async function loadVol(){const d=await api('/api/volume/get');if(!d)return;volCur=d.volume;document.getElementById('volSlider').value=d.volume;document.getElementById('vol-pct').textContent=d.volume+'%'}
async function volSet(v){volCur=parseInt(v);document.getElementById('volSlider').value=v;document.getElementById('vol-pct').textContent=v+'%';await api('/api/volume/set',{method:'POST',body:JSON.stringify({volume:v})})}
async function volMute(m){await api('/api/volume/mute',{method:'POST',body:JSON.stringify({muted:m})});toast(m?'Áudio mutado':'Áudio ativado')}

// ── POWER ──
async function pwr(a){if(!['cancel'].includes(a)){if(!confirm('Tem certeza?'))return}const d=await api('/api/power/'+a);if(d)toast(d.message||d.err,d.success?'ok':'err')}

// ── APPS ──
async function openApp(n){const d=await api('/api/open-app',{method:'POST',body:JSON.stringify({app:n})});if(d&&d.success)toast(n+' aberto!');else if(d)toast(d.error,'err')}

// ── NOTEPAD ──
async function npSave(){await api('/api/notepad/save',{method:'POST',body:JSON.stringify({text:document.getElementById('npText').value})});toast('Salvo!')}
async function npLoad(){const d=await api('/api/notepad/get');if(d)document.getElementById('npText').value=d.text}
async function npOpen(){await npSave();await api('/api/notepad/open',{method:'POST'});toast('Abrindo no PC...')}

// ── FILES ──
async function fmGo(path){document.getElementById('fmPath').value=path;const d=await api('/api/files/list',{method:'POST',body:JSON.stringify({path})});if(!d||d.error){document.getElementById('fmList').innerHTML=`<p style="padding:20px;color:var(--red)">${d?d.error:'Erro'}</p>`;return}
let html='';
if(d.parent)html+=`<div class="fm-item" onclick="fmGo('${d.parent.replace(/\\\\/g,'\\\\\\\\')}')"><span class="fi" style="color:var(--accent)"><i class="fas fa-arrow-up"></i></span><span class="fn" style="color:var(--accent)">.. Voltar</span></div>`;
d.items.forEach(i=>{
const ic=i.is_dir?'fa-folder':'fa-file';
const col=i.is_dir?'var(--yellow)':'var(--text2)';
const sz=i.size>1048576?(i.size/1048576).toFixed(1)+' MB':i.size>1024?(i.size/1024).toFixed(1)+' KB':i.size+' B';
if(i.is_dir)html+=`<div class="fm-item" ondblclick="fmGo('${i.path.replace(/\\\\/g,'\\\\\\\\')}')"><span class="fi" style="color:${col}"><i class="fas ${ic}"></i></span><span class="fn">${i.name}</span><span class="fs">${i.modified}</span><span class="fm"><button class="btn-sm" onclick="event.stopPropagation();fmRename('${i.path.replace(/\\\\/g,'\\\\\\\\').replace(/'/g,"\\\\'")}','${i.name}')"><i class="fas fa-pen"></i></button> <button class="btn-sm" onclick="event.stopPropagation();fmDel('${i.path.replace(/\\\\/g,'\\\\\\\\').replace(/'/g,"\\\\'")}')"><i class="fas fa-trash"></i></button></span></div>`;
else html+=`<div class="fm-item" ondblclick="fmView('${i.path.replace(/\\\\/g,'\\\\\\\\').replace(/'/g,"\\\\'")}','${i.ext}')"><span class="fi" style="color:${col}"><i class="fas ${ic}"></i></span><span class="fn">${i.name}</span><span class="fs">${sz} • ${i.modified}</span><span class="fm"><button class="btn-sm" onclick="event.stopPropagation();fmDl('${i.path.replace(/\\\\/g,'\\\\\\\\').replace(/'/g,"\\\\'")}')"><i class="fas fa-download"></i></button> <button class="btn-sm" onclick="event.stopPropagation();fmRename('${i.path.replace(/\\\\/g,'\\\\\\\\').replace(/'/g,"\\\\'")}','${i.name}')"><i class="fas fa-pen"></i></button> <button class="btn-sm" onclick="event.stopPropagation();fmDel('${i.path.replace(/\\\\/g,'\\\\\\\\').replace(/'/g,"\\\\'")}')"><i class="fas fa-trash"></i></button></span></div>`;
});
document.getElementById('fmList').innerHTML=html||'<p style="padding:20px;color:var(--text2)">Pasta vazia</p>';
document.getElementById('fm-count').textContent=d.total+' itens';
// Breadcrumb
const parts=path.replace(/\\\\/g,'/').split('/').filter(Boolean);
let bc='';
let acc='';
parts.forEach((p,i)=>{
acc+=p.includes(':')?p+'\\\\\\\\':p+'\\\\\\\\';
const full=i===0?p+'\\\\\\\\':acc;
bc+=`<span onclick="fmGo('${full.replace(/\\\\/g,'\\\\\\\\')}')">${p}</span>`;
});
document.getElementById('fmBread').innerHTML=bc}
function fmNewFolder(){showModal(`<h3>Nova Pasta</h3><input id="mInput" style="width:100%;padding:14px;background:rgba(255,255,255,.06);border:1px solid var(--border);border-radius:12px;color:#fff;font-size:14px" placeholder="Nome da pasta"><div style="display:flex;gap:10px;margin-top:16px"><button class="btn a" onclick="fmCreateFolder()">Criar</button><button class="btn d" onclick="hideModal()">Cancelar</button></div>`)}
async function fmCreateFolder(){const name=document.getElementById('mInput').value;if(!name)return;const path=document.getElementById('fmPath').value+'\\\\'+name;await api('/api/files/mkdir',{method:'POST',body:JSON.stringify({path})});hideModal();fmGo(document.getElementById('fmPath').value);toast('Pasta criada!')}
async function fmDel(path){if(!confirm('Deletar?'))return;await api('/api/files/delete',{method:'POST',body:JSON.stringify({path})});fmGo(document.getElementById('fmPath').value);toast('Deletado!')}
function fmRename(path,name){showModal(`<h3>Renomear</h3><input id="mInput" style="width:100%;padding:14px;background:rgba(255,255,255,.06);border:1px solid var(--border);border-radius:12px;color:#fff;font-size:14px" value="${name}"><div style="display:flex;gap:10px;margin-top:16px"><button class="btn a" onclick="fmDoRename('${path.replace(/\\\\/g,'\\\\\\\\').replace(/'/g,"\\\\'")}')">Renomear</button><button class="btn d" onclick="hideModal()">Cancelar</button></div>`)}
async function fmDoRename(oldPath){const newName=document.getElementById('mInput').value;if(!newName)return;await api('/api/files/rename',{method:'POST',body:JSON.stringify({old_path:oldPath,new_name:newName})});hideModal();fmGo(document.getElementById('fmPath').value);toast('Renomeado!')}
async function fmView(path,ext){const textExts=['.txt','.py','.js','.html','.css','.json','.xml','.csv','.log','.md','.ini','.cfg','.bat','.ps1','.reg','.yml','.yaml','.toml'];
if(textExts.includes(ext)){const d=await api('/api/files/read',{method:'POST',body:JSON.stringify({path})});if(d&&d.content){showModal(`<h3>${path.split('\\\\\\\\').pop()}</h3><textarea class="np-area" id="mTextarea" style="min-height:300px">${d.content}</textarea><div style="display:flex;gap:10px;margin-top:12px"><button class="btn g" onclick="fmSaveFile('${path.replace(/\\\\/g,'\\\\\\\\').replace(/'/g,"\\\\'")}')">Salvar</button><button class="btn d" onclick="hideModal()">Fechar</button></div>`)}}
else toast('Pré-visualização não disponível para este tipo','err')}
async function fmSaveFile(path){const content=document.getElementById('mTextarea').value;await api('/api/files/write',{method:'POST',body:JSON.stringify({path,content})});hideModal();toast('Salvo!')}
function fmDl(path){window.open('/api/files/download?path='+encodeURIComponent(path),'_blank')}
function fmUpload(){const input=document.getElementById('fileUpload');input.onchange=async()=>{const file=input.files[0];if(!file)return;const fd=new FormData();fd.append('file',file);fd.append('path',document.getElementById('fmPath').value);await fetch('/api/files/upload',{method:'POST',body:fd});fmGo(document.getElementById('fmPath').value);toast('Arquivo enviado!')};input.click()}
function fmSearch(){showModal(`<h3>Buscar Arquivo</h3><input id="mInput" style="width:100%;padding:14px;background:rgba(255,255,255,.06);border:1px solid var(--border);border-radius:12px;color:#fff;font-size:14px" placeholder="Nome do arquivo..."><div style="display:flex;gap:10px;margin-top:16px"><button class="btn a" onclick="fmDoSearch()">Buscar</button><button class="btn d" onclick="hideModal()">Cancelar</button></div><div id="mResults" style="margin-top:14px;max-height:300px;overflow-y:auto"></div>`)}

async function fmDoSearch(){const q=document.getElementById('mInput').value;const d=await api('/api/files/search',{method:'POST',body:JSON.stringify({query:q,path:document.getElementById('fmPath').value})});if(!d)return;let html='';d.results.forEach(r=>{const ic=r.is_dir?'fa-folder':'fa-file';html+=`<div class="fm-item" onclick="fmGo('${(r.is_dir?r.path:r.path.split('\\\\\\\\').slice(0,-1).join('\\\\\\\\')).replace(/\\\\/g,'\\\\\\\\')}')"><span class="fi" style="color:${r.is_dir?'var(--yellow)':'var(--text2)'}"><i class="fas ${ic}"></i></span><span class="fn">${r.name}</span><span class="fs">${r.path}</span></div>`});document.getElementById('mResults').innerHTML=html||'<p style="color:var(--text2)">Nenhum resultado</p>'}

// ── PROCESSES ──
async function loadProcs(){const p=await api('/api/processes');if(!p)return;let h='<div class="pitem hdr"><span>NOME</span><span>CPU</span><span>RAM</span><span></span></div>';p.forEach(x=>{h+=`<div class="pitem"><span class="pname">${x.name}</span><span class="pval">${x.cpu}%</span><span class="pval">${x.memory}%</span><button class="btn-k" onclick="killP(${x.pid})">Matar</button></div>`});document.getElementById('procList').innerHTML=h}
async function killP(pid){if(!confirm('Matar PID '+pid+'?'))return;await api('/api/process/kill',{method:'POST',body:JSON.stringify({pid})});loadProcs();toast('Processo finalizado')}

// ── SERVICES ──
async function loadServices(){const s=await api('/api/services');if(!s)return;let h='<div class="svc-item hdr"><span>NOME</span><span>ESTADO</span><span></span><span></span></div>';s.forEach(x=>{h+=`<div class="svc-item"><span class="pname">${x.display||x.name}</span><span class="svc-state ${x.running?'on':'off'}">${x.state}</span><button class="btn-sm" onclick="svcAct('start','${x.name}')"><i class="fas fa-play"></i></button><button class="btn-sm" onclick="svcAct('stop','${x.name}')"><i class="fas fa-stop"></i></button></div>`});document.getElementById('svcList').innerHTML=h}
async function svcAct(a,n){await api('/api/service/'+a,{method:'POST',body:JSON.stringify({name:n})});loadServices();toast('Ação executada')}

// ── DRIVES ──
async function loadDrives(){const d=await api('/api/drives');if(!d)return;let h='';d.forEach(x=>{h+=`<div class="drive-item"><div class="drive-head"><span><strong>${x.device}</strong> ${x.mountpoint}</span><span style="color:var(--text2)">${x.free} livres / ${x.total} GB</span></div><div class="pbar"><div class="pfill c3" style="width:${x.percent}%"></div></div></div>`});document.getElementById('driveList').innerHTML=h}

// ── SCREENSHOT ──
async function takeScreenshot(){const d=await api('/api/screenshot');if(!d||d.error){toast(d?d.error:'Erro','err');return}document.getElementById('ssImg').src='data:image/png;base64,'+d.image;document.getElementById('ssPreview').style.display='block';toast('Screenshot capturado!')}

// ── CLIPBOARD ──
async function clipGet(){const d=await api('/api/clipboard/get');if(d)document.getElementById('clipText').value=d.text}
async function clipSet(){await api('/api/clipboard/set',{method:'POST',body:JSON.stringify({text:document.getElementById('clipText').value})});toast('Clipboard atualizado!')}

// ── DOWNLOAD ──
async function dlStart(){const url=document.getElementById('dlUrl').value.trim();if(!url){toast('Cole uma URL!','err');return}const name=document.getElementById('dlName').value.trim();const d=await api('/api/download',{method:'POST',body:JSON.stringify({url,filename:name})});if(!d||!d.success){toast('Erro','err');return}document.getElementById('dlProg').style.display='block';const iv=setInterval(async()=>{const s=await api('/api/download-status/'+d.task_id);if(!s)return;document.getElementById('dlBar').style.width=s.progress+'%';document.getElementById('dlPct').textContent=s.progress+'%';if(s.status==='completed'){clearInterval(iv);document.getElementById('dlStatus').textContent='Concluído!';toast('Download completo!');setTimeout(()=>document.getElementById('dlProg').style.display='none',2000)}else if(s.status==='error'){clearInterval(iv);document.getElementById('dlStatus').textContent='Erro: '+s.error;toast('Erro','err')}},500)}

// ── SYSTEM ACTIONS ──
async function sysAct(a){const d=await api('/api/sys-action/'+a,{method:'POST'});if(d&&d.success)toast('Ação executada!')}

// ── COMMANDS ──
async function runCmd(){const inp=document.getElementById('cmdIn');const out=document.getElementById('cmdOut');const cmd=inp.value.trim();if(!cmd)return;out.innerHTML+=`<span style="color:var(--accent)">$ ${cmd}</span>\\n`;inp.value='';const d=await api('/api/command',{method:'POST',body:JSON.stringify({command:cmd})});if(d){if(d.stdout)out.innerHTML+=d.stdout;if(d.stderr)out.innerHTML+=`<span style="color:var(--red)">${d.stderr}</span>`;if(d.error)out.innerHTML+=`<span style="color:var(--red)">${d.error}</span>`}out.innerHTML+='\\n';out.scrollTop=out.scrollHeight}

// ── SCRIPTS ──
async function runScript(){const code=document.getElementById('scriptCode').value;const out=document.getElementById('scriptOut');out.style.display='block';const d=await api('/api/scripts/run',{method:'POST',body:JSON.stringify({code})});if(d){out.innerHTML='';if(d.stdout)out.innerHTML+=d.stdout;if(d.stderr)out.innerHTML+=`<span style="color:var(--red)">${d.stderr}</span>`;if(d.error)out.innerHTML=`<span style="color:var(--red)">${d.error}</span>`;out.scrollTop=out.scrollHeight}}
async function saveScript(){const name=prompt('Nome do script:');if(!name)return;await api('/api/scripts/save',{method:'POST',body:JSON.stringify({name,code:document.getElementById('scriptCode').value})});toast('Script salvo!')}

// ── AI ──
async function aiSend(target){const input=document.getElementById(target==='quick'?'aiQuickIn':'aiIn');const msg=input.value.trim();if(!msg)return;input.value='';const container=document.getElementById(target==='quick'?'aiQuick':'aiMsgs');container.innerHTML+=`<div class="ai-msg user">${msg}</div>`;container.scrollTop=container.scrollHeight;
const d=await api('/api/ai/chat',{method:'POST',body:JSON.stringify({message:msg})});if(!d)return;
d.responses.forEach(r=>{let html=r.result||'';
if(r.image)html=`<img src="data:image/png;base64,${r.image}" style="max-width:100%;border-radius:8px">`;
if(r.action==='command')html=`<pre>${r.result}</pre>`;
container.innerHTML+=`<div class="ai-msg bot">${html}</div>`});
container.scrollTop=container.scrollHeight}
function aiQuick(msg){aiSend('full');document.getElementById('aiIn').value=msg;aiSend('full')}

document.getElementById('pw').focus();

// ── PANELS ──
let currentPanelId = null;
let panelsList = [];

async function loadPanels() {
  const d = await api('/api/panels');
  if (!d) return;
  panelsList = d;
  const current = d.find(p => p.id === currentPanelId);
  document.getElementById('currentPanelName').textContent = current ? `${current.username}@${current.hostname}` : '-';

  let html = '';
  d.forEach(p => {
    const online = p.online;
    const dot = online ? 'var(--green)' : 'var(--red)';
    const isCurrent = p.id === currentPanelId;
    html += `<div style="padding:10px 14px;border-radius:8px;cursor:pointer;transition:.15s;${isCurrent ? 'background:var(--accent);' : ''}display:flex;align-items:center;gap:10px;font-size:13px" onmouseover="this.style.background='rgba(255,255,255,.06)'" onmouseout="this.style.background='${isCurrent ? 'var(--accent)' : 'transparent'}'" onclick="selectPanel('${p.id}')">
      <div style="width:8px;height:8px;border-radius:50%;background:${dot};flex-shrink:0"></div>
      <div style="flex:1;min-width:0">
        <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${p.username}</div>
        <div style="font-size:11px;color:var(--text2)">${p.hostname}${p.ip ? ' (' + p.ip + ')' : ''}</div>
      </div>
    </div>`;
  });
  document.getElementById('panelDropdown').innerHTML = html || '<div style="padding:14px;color:var(--text2);font-size:13px;text-align:center">Nenhum painel encontrado</div>';
}

function togglePanelList() {
  const dd = document.getElementById('panelDropdown');
  dd.style.display = dd.style.display === 'none' ? 'block' : 'none';
}

function selectPanel(id) {
  document.getElementById('panelDropdown').style.display = 'none';
  if (id === currentPanelId) return;
  const panel = panelsList.find(p => p.id === id);
  if (panel && panel.ip) {
    window.location.href = `http://${panel.ip}:5000`;
  }
}

async function reportPanel() {
  await api('/api/panels/report', { method: 'POST', body: JSON.stringify({}) });
}

document.addEventListener('click', (e) => {
  if (!e.target.closest('#panelSelector')) {
    document.getElementById('panelDropdown').style.display = 'none';
  }
});

async function initPanel() {
  const d = await api('/api/panel-id');
  if (d) {
    currentPanelId = d.panel_id;
    document.getElementById('currentPanelName').textContent = `${d.username}@${d.hostname}`;
  }
  loadPanels();
  setInterval(() => { reportPanel(); loadPanels(); }, 60000);
}

</script>
</body>
</html>
"""

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('auth_token')
        if token not in AUTHENTICATED_SESSIONS:
            return jsonify({'error': 'Não autorizado'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    return PAGE_HTML

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    if data.get('password') == AUTH_PASSWORD:
        import secrets
        token = secrets.token_hex(32)
        AUTHENTICATED_SESSIONS.add(token)
        send_discord_webhook("login")
        resp = jsonify({'success': True})
        resp.set_cookie('auth_token', token, httponly=True, samesite='Strict', max_age=86400*7)
        return resp
    return jsonify({'error': 'Senha incorreta'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    token = request.cookies.get('auth_token')
    if token:
        AUTHENTICATED_SESSIONS.discard(token)
    resp = jsonify({'success': True})
    resp.delete_cookie('auth_token')
    return resp

@app.route('/api/check-auth')
def check_auth():
    token = request.cookies.get('auth_token')
    return jsonify({'authenticated': token in AUTHENTICATED_SESSIONS})

@app.route('/api/panel-id')
@require_auth
def panel_id():
    return jsonify({'panel_id': PANEL_ID, 'hostname': HOSTNAME, 'username': USERNAME})

@app.route('/api/panels', methods=['GET'])
@require_auth
def list_panels():
    panels = []
    for pid, info in connected_panels.items():
        panels.append({
            'id': pid,
            'hostname': info['hostname'],
            'username': info['username'],
            'ip': info['ip'],
            'online': (time.time() - info['last_seen']) < 300
        })
    return jsonify(panels)

@app.route('/api/panels/report', methods=['POST'])
@require_auth
def report_panel():
    data = request.get_json()
    connected_panels[PANEL_ID]['ip'] = data.get('ip', request.remote_addr)
    connected_panels[PANEL_ID]['last_seen'] = time.time()
    return jsonify({'success': True})

# ─── SYSTEM INFO ────────────────────────────────────────────────

@app.route('/api/system-info')
@require_auth
def system_info():
    cpu_percent = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    net = psutil.net_io_counters()
    temps = {}
    try:
        for name, entries in psutil.sensors_temperatures().items():
            for entry in entries:
                temps[name] = entry.current
    except:
        pass

    battery = None
    try:
        bat = psutil.sensors_battery()
        if bat:
            battery = {'percent': bat.percent, 'plugged': bat.power_plugged, 'secs_left': bat.secsleft}
    except:
        pass

    return jsonify({
        'cpu_percent': cpu_percent,
        'memory_percent': memory.percent,
        'memory_used': round(memory.used / (1024**3), 2),
        'memory_total': round(memory.total / (1024**3), 2),
        'disk_percent': disk.percent,
        'disk_used': round(disk.used / (1024**3), 2),
        'disk_total': round(disk.total / (1024**3), 2),
        'boot_time': boot_time.strftime('%d/%m/%Y %H:%M:%S'),
        'uptime': str(uptime).split('.')[0],
        'hostname': platform.node(),
        'os': f"{platform.system()} {platform.release()}",
        'username': os.getlogin(),
        'net_sent': round(net.bytes_sent / (1024**2), 2),
        'net_recv': round(net.bytes_recv / (1024**2), 2),
        'cpu_count': psutil.cpu_count(),
        'cpu_freq': round(psutil.cpu_freq().current, 0) if psutil.cpu_freq() else 0,
        'cpu_per_core': psutil.cpu_percent(interval=0, percpu=True),
        'temps': temps,
        'battery': battery,
    })

# ─── VOLUME ─────────────────────────────────────────────────────

def get_volume_obj():
    if not audio_available:
        return None
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return interface.QueryInterface(IAudioEndpointVolume)
    except:
        return None

@app.route('/api/volume/get')
@require_auth
def volume_get():
    v = get_volume_obj()
    if not v:
        return jsonify({'volume': 50, 'muted': False, 'available': False})
    try:
        return jsonify({'volume': round(v.GetMasterVolumeLevelScalar() * 100), 'muted': bool(v.GetMute()), 'available': True})
    except:
        return jsonify({'volume': 50, 'muted': False, 'available': False})

@app.route('/api/volume/set', methods=['POST'])
@require_auth
def volume_set():
    v = get_volume_obj()
    if not v: return jsonify({'error': 'N/A'}), 500
    try:
        data = request.get_json()
        v.SetMasterVolumeLevelScalar(max(0.0, min(1.0, int(data.get('volume', 50)) / 100)), None)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/volume/mute', methods=['POST'])
@require_auth
def volume_mute():
    v = get_volume_obj()
    if not v: return jsonify({'error': 'N/A'}), 500
    try:
        data = request.get_json()
        v.SetMute(1 if data.get('muted', True) else 0, None)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── POWER ──────────────────────────────────────────────────────

@app.route('/api/power/<action>')
@require_auth
def power_action(action):
    cmds = {
        'shutdown': 'shutdown /s /t 60', 'shutdown-now': 'shutdown /s /t 0',
        'restart': 'shutdown /r /t 60', 'restart-now': 'shutdown /r /t 0',
        'cancel': 'shutdown /a', 'hibernate': 'rundll32.exe powrprof.dll,SetSuspendState 0,1,0',
        'sleep': 'rundll32.exe powrprof.dll,SetSuspendState 0,0,0',
        'lock': 'rundll32.exe user32.dll,LockWorkStation',
        'logoff': 'shutdown /l',
    }
    msgs = {
        'shutdown': 'Desligando em 60s', 'shutdown-now': 'Desligando!',
        'restart': 'Reiniciando em 60s', 'restart-now': 'Reiniciando!',
        'cancel': 'Agendamento cancelado', 'hibernate': 'Hibernando',
        'sleep': 'Indo dormir', 'lock': 'Bloqueando tela', 'logoff': 'Fazendo logoff',
    }
    try:
        os.system(cmds.get(action, ''))
        return jsonify({'success': True, 'message': msgs.get(action, action)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── PROCESSES ──────────────────────────────────────────────────

@app.route('/api/processes')
@require_auth
def get_processes():
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status', 'username']):
        try:
            pinfo = proc.info
            processes.append({
                'pid': pinfo['pid'], 'name': pinfo['name'],
                'cpu': round(pinfo['cpu_percent'] or 0, 1),
                'memory': round(pinfo['memory_percent'] or 0, 1),
                'status': pinfo['status'], 'user': pinfo.get('username', '')
            })
        except:
            pass
    processes.sort(key=lambda x: x['cpu'], reverse=True)
    return jsonify(processes[:200])

@app.route('/api/process/kill', methods=['POST'])
@require_auth
def kill_process():
    data = request.get_json()
    try:
        psutil.Process(data.get('pid')).terminate()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/process/details/<int:pid>')
@require_auth
def process_details(pid):
    try:
        p = psutil.Process(pid)
        with p.oneshot():
            return jsonify({
                'pid': p.pid, 'name': p.name(), 'status': p.status(),
                'created': datetime.fromtimestamp(p.create_time()).strftime('%d/%m/%Y %H:%M:%S'),
                'cpu_percent': p.cpu_percent(), 'memory_percent': round(p.memory_percent(), 2),
                'memory_info': round(p.memory_info().rss / (1024**2), 2),
                'threads': p.num_threads(), 'user': p.username(),
                'exe': p.exe() if p.exe() else 'N/A',
                'cmdline': ' '.join(p.cmdline()) if p.cmdline() else 'N/A',
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── SCREENSHOT ─────────────────────────────────────────────────

@app.route('/api/screenshot')
@require_auth
def screenshot():
    if not screenshot_available:
        return jsonify({'error': 'mss não disponível'}), 500
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            img = sct.grab(monitor)
            img_bytes = mss.tools.to_png(img.rgb, img.size)
            b64 = base64.b64encode(img_bytes).decode()
            return jsonify({'image': b64, 'width': img.width, 'height': img.height})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── CLIPBOARD ──────────────────────────────────────────────────

@app.route('/api/clipboard/get')
@require_auth
def clipboard_get():
    if not clipboard_available:
        return jsonify({'text': '', 'available': False})
    try:
        return jsonify({'text': pyperclip.paste(), 'available': True})
    except:
        return jsonify({'text': '', 'available': False})

@app.route('/api/clipboard/set', methods=['POST'])
@require_auth
def clipboard_set():
    if not clipboard_available:
        return jsonify({'error': 'Clipboard não disponível'}), 500
    try:
        data = request.get_json()
        pyperclip.copy(data.get('text', ''))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── FILE MANAGER ───────────────────────────────────────────────

@app.route('/api/files/list', methods=['POST'])
@require_auth
def file_list():
    data = request.get_json()
    path = data.get('path', 'C:\\')
    try:
        p = Path(path)
        if not p.exists():
            return jsonify({'error': 'Caminho não existe', 'path': path})
        
        items = []
        for item in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            try:
                stat = item.stat()
                items.append({
                    'name': item.name,
                    'path': str(item),
                    'is_dir': item.is_dir(),
                    'size': stat.st_size if item.is_file() else 0,
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m/%Y %H:%M'),
                    'ext': item.suffix.lower() if item.is_file() else '',
                })
            except PermissionError:
                items.append({'name': item.name, 'path': str(item), 'is_dir': True, 'size': 0, 'modified': '-', 'ext': '', 'no_access': True})
            except:
                pass

        parent = str(p.parent) if str(p) != p.anchor else None
        return jsonify({'path': str(p), 'parent': parent, 'items': items, 'total': len(items)})
    except Exception as e:
        return jsonify({'error': str(e), 'path': path})

@app.route('/api/files/mkdir', methods=['POST'])
@require_auth
def file_mkdir():
    data = request.get_json()
    try:
        Path(data['path']).mkdir(parents=True, exist_ok=True)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/delete', methods=['POST'])
@require_auth
def file_delete():
    data = request.get_json()
    try:
        p = Path(data['path'])
        if p.is_dir():
            import shutil
            shutil.rmtree(p)
        else:
            p.unlink()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/rename', methods=['POST'])
@require_auth
def file_rename():
    data = request.get_json()
    try:
        p = Path(data['old_path'])
        p.rename(p.parent / data['new_name'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/read', methods=['POST'])
@require_auth
def file_read():
    data = request.get_json()
    try:
        p = Path(data['path'])
        if p.stat().st_size > 5 * 1024 * 1024:
            return jsonify({'error': 'Arquivo muito grande (>5MB)'})
        content = p.read_text(encoding='utf-8', errors='replace')
        return jsonify({'content': content, 'name': p.name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/write', methods=['POST'])
@require_auth
def file_write():
    data = request.get_json()
    try:
        Path(data['path']).write_text(data['content'], encoding='utf-8')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/upload', methods=['POST'])
@require_auth
def file_upload():
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo'}), 400
    file = request.files['file']
    dest = request.form.get('path', downloads_folder)
    file.save(os.path.join(dest, file.filename))
    return jsonify({'success': True})

@app.route('/api/files/download')
@require_auth
def file_download():
    path = request.args.get('path', '')
    try:
        return send_file(path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/search', methods=['POST'])
@require_auth
def file_search():
    data = request.get_json()
    query = data.get('query', '').lower()
    root = data.get('path', 'C:\\')
    results = []
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            for f in filenames:
                if query in f.lower():
                    full = os.path.join(dirpath, f)
                    results.append({'name': f, 'path': full, 'size': os.path.getsize(full)})
                    if len(results) >= 50:
                        return jsonify({'results': results})
            for d in dirnames:
                if query in d.lower():
                    full = os.path.join(dirpath, d)
                    results.append({'name': d, 'path': full, 'size': 0, 'is_dir': True})
                    if len(results) >= 50:
                        return jsonify({'results': results})
    except:
        pass
    return jsonify({'results': results})

# ─── DOWNLOAD ───────────────────────────────────────────────────

@app.route('/api/download', methods=['POST'])
@require_auth
def download_url():
    import requests as req
    data = request.get_json()
    url = data.get('url', '')
    filename = data.get('filename', '') or url.split('/')[-1].split('?')[0] or 'download'
    dest = data.get('dest', downloads_folder)

    task_id = str(int(time.time() * 1000))
    download_tasks[task_id] = {'status': 'downloading', 'progress': 0}

    def do_download():
        try:
            r = req.get(url, stream=True, timeout=120)
            r.raise_for_status()
            total = int(r.headers.get('content-length', 0))
            path = os.path.join(dest, filename)
            downloaded = 0
            with open(path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            download_tasks[task_id]['progress'] = round((downloaded/total)*100)
            download_tasks[task_id] = {'status': 'completed', 'progress': 100, 'path': path, 'size': downloaded}
        except Exception as e:
            download_tasks[task_id] = {'status': 'error', 'error': str(e)}

    threading.Thread(target=do_download, daemon=True).start()
    return jsonify({'success': True, 'task_id': task_id})

@app.route('/api/download-status/<task_id>')
@require_auth
def download_status(task_id):
    return jsonify(download_tasks.get(task_id, {'error': 'Não encontrado'}))

# ─── NOTEPAD ────────────────────────────────────────────────────

@app.route('/api/notepad/get')
@require_auth
def notepad_get():
    return jsonify({'text': notepad_content['text']})

@app.route('/api/notepad/save', methods=['POST'])
@require_auth
def notepad_save():
    notepad_content['text'] = request.get_json().get('text', '')
    return jsonify({'success': True})

@app.route('/api/notepad/open', methods=['POST'])
@require_auth
def notepad_open():
    filepath = os.path.join(os.environ.get('TEMP', ''), 'remote_notepad.txt')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(notepad_content.get('text', ''))
    subprocess.Popen(['notepad.exe', filepath])
    return jsonify({'success': True})

# ─── OPEN APP ───────────────────────────────────────────────────

@app.route('/api/open-app', methods=['POST'])
@require_auth
def open_app():
    apps = {
        'notepad': 'notepad.exe', 'calculator': 'calc.exe', 'explorer': 'explorer.exe',
        'cmd': 'cmd.exe', 'powershell': 'powershell.exe', 'taskmgr': 'taskmgr.exe',
        'brave': 'brave.exe', 'firefox': 'firefox.exe', 'edge': 'msedge.exe',
        'paint': 'mspaint.exe', 'regedit': 'regedit.exe', 'control': 'control.exe',
        'msconfig': 'msconfig.exe', 'devmgmt': 'devmgmt.msc', 'snippingtool': 'SnippingTool.exe',
        'wordpad': 'write.exe', 'magnifier': 'magnify.exe', 'charmap': 'charmap.exe',
        'dxdiag': 'dxdiag.exe', 'resmon': 'resmon.exe', 'perfmon': 'perfmon.exe',
    }
    data = request.get_json()
    app_name = data.get('app', '').lower()
    if app_name in apps:
        try:
            subprocess.Popen(apps[app_name])
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'App não encontrado'}), 400

# ─── COMMANDS ───────────────────────────────────────────────────

@app.route('/api/command', methods=['POST'])
@require_auth
def run_command():
    data = request.get_json()
    cmd = data.get('command', '')
    blacklisted = ['format', 'del /s', 'rd /s', 'rmdir /s', 'rm -rf']
    if any(b in cmd.lower() for b in blacklisted):
        return jsonify({'error': 'Comando bloqueado'}), 400
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='replace')
        return jsonify({'stdout': r.stdout, 'stderr': r.stderr, 'returncode': r.returncode})
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout (30s)'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── SERVICES ───────────────────────────────────────────────────

@app.route('/api/services')
@require_auth
def list_services():
    try:
        r = subprocess.run('sc query type= service state= all', shell=True, capture_output=True, text=True, timeout=10)
        services = []
        current = {}
        for line in r.stdout.split('\n'):
            line = line.strip()
            if line.startswith('SERVICE_NAME:'):
                if current:
                    services.append(current)
                current = {'name': line.split(':', 1)[1].strip()}
            elif line.startswith('DISPLAY_NAME:'):
                current['display'] = line.split(':', 1)[1].strip()
            elif line.startswith('STATE:'):
                state = line.split(':', 1)[1].strip()
                current['state'] = state
                current['running'] = 'RUNNING' in state
        if current:
            services.append(current)
        services.sort(key=lambda x: x.get('display', '').lower())
        return jsonify(services)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/service/<action>', methods=['POST'])
@require_auth
def service_action(action):
    data = request.get_json()
    name = data.get('name', '')
    if action in ('start', 'stop', 'restart'):
        try:
            if action == 'restart':
                subprocess.run(f'sc stop "{name}"', shell=True, capture_output=True, timeout=10)
                time.sleep(1)
                subprocess.run(f'sc start "{name}"', shell=True, capture_output=True, timeout=10)
            else:
                subprocess.run(f'sc {action} "{name}"', shell=True, capture_output=True, timeout=10)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Ação inválida'})

# ─── NETWORK ────────────────────────────────────────────────────

@app.route('/api/network')
@require_auth
def network_info():
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    wifi_password = None
    try:
        r = subprocess.run('netsh wlan show profile', shell=True, capture_output=True, text=True, timeout=5)
        profiles = re.findall(r'All User Profile\s*:\s*(.*)', r.stdout)
        if profiles:
            profile = profiles[0].strip()
            r2 = subprocess.run(f'netsh wlan show profile name="{profile}" key=clear', shell=True, capture_output=True, text=True, timeout=5)
            match = re.search(r'Key Content\s*:\s*(.*)', r2.stdout)
            if match:
                wifi_password = match.group(1).strip()
    except:
        pass

    connections = []
    for conn in psutil.net_connections(kind='inet'):
        if conn.status == 'ESTABLISHED':
            try:
                proc_name = psutil.Process(conn.pid).name() if conn.pid else '-'
            except:
                proc_name = '-'
            connections.append({
                'local': f"{conn.laddr.ip}:{conn.laddr.port}",
                'remote': f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else '-',
                'status': conn.status, 'process': proc_name
            })

    return jsonify({
        'hostname': hostname, 'local_ip': local_ip,
        'wifi_password': wifi_password,
        'connections': connections[:50]
    })

# ─── SYSTEM ACTIONS ─────────────────────────────────────────────

@app.route('/api/sys-action/<action>', methods=['POST'])
@require_auth
def sys_action(action):
    try:
        if action == 'flush-dns':
            os.system('ipconfig /flushdns')
        elif action == 'clear-clipboard':
            os.system('echo off | clip')
        elif action == 'clear-recent':
            recent = os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Recent')
            if os.path.exists(recent):
                for f in os.listdir(recent):
                    try: os.remove(os.path.join(recent, f))
                    except: pass
        elif action == 'empty-recycle':
            os.system('rd /s /q %systemdrive%\\$Recycle.Bin')
        elif action == 'clear-temp':
            for d in [os.environ.get('TEMP', ''), os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp'), 'C:\\Windows\\Temp']:
                if d and os.path.exists(d):
                    for f in os.listdir(d):
                        try:
                            p = os.path.join(d, f)
                            if os.path.isfile(p): os.remove(p)
                            else: 
                                import shutil
                                shutil.rmtree(p, ignore_errors=True)
                        except: pass
        elif action == 'disable-firewall':
            os.system('netsh advfirewall set allprofiles state off')
        elif action == 'enable-firewall':
            os.system('netsh advfirewall set allprofiles state on')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── DRIVES ─────────────────────────────────────────────────────

@app.route('/api/drives')
@require_auth
def list_drives():
    drives = []
    for part in psutil.disk_partitions():
        try:
            u = psutil.disk_usage(part.mountpoint)
            drives.append({
                'device': part.device, 'mountpoint': part.mountpoint, 'fstype': part.fstype,
                'total': round(u.total/(1024**3),2), 'used': round(u.used/(1024**3),2),
                'free': round(u.free/(1024**3),2), 'percent': u.percent
            })
        except: pass
    return jsonify(drives)

# ─── STARTUP APPS ───────────────────────────────────────────────

@app.route('/api/startup')
@require_auth
def list_startup():
    items = []
    reg_paths = [
        (r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run', 'HKCU'),
        (r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run', 'HKLM'),
        (r'SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce', 'HKCU'),
    ]
    try:
        import winreg
        for subpath, hive_name in reg_paths:
            hive = winreg.HKEY_CURRENT_USER if hive_name == 'HKCU' else winreg.HKEY_LOCAL_MACHINE
            try:
                key = winreg.OpenKey(hive, subpath)
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        items.append({'name': name, 'command': value, 'hive': hive_name, 'path': subpath})
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except:
                pass
    except:
        pass
    return jsonify(items)

# ─── EVENT LOGS ─────────────────────────────────────────────────

@app.route('/api/event-logs')
@require_auth
def event_logs():
    logs = []
    try:
        for entry in psutil.win_service_iter():
            pass
    except:
        pass
    
    r = subprocess.run('wevtutil qe System /c:50 /rd:true /f:text', shell=True, capture_output=True, text=True, timeout=10, errors='replace')
    return jsonify({'logs': r.stdout[:10000]})

# ─── SCRIPTS ────────────────────────────────────────────────────

@app.route('/api/scripts/list')
@require_auth
def scripts_list():
    return jsonify(script_library)

@app.route('/api/scripts/save', methods=['POST'])
@require_auth
def scripts_save():
    data = request.get_json()
    script = {
        'id': str(int(time.time()*1000)),
        'name': data.get('name', 'Sem nome'),
        'code': data.get('code', ''),
        'created': datetime.now().strftime('%d/%m/%Y %H:%M')
    }
    script_library.append(script)
    return jsonify({'success': True, 'script': script})

@app.route('/api/scripts/run', methods=['POST'])
@require_auth
def scripts_run():
    data = request.get_json()
    code = data.get('code', '')
    try:
        r = subprocess.run(['python', '-c', code], capture_output=True, text=True, timeout=30, errors='replace')
        return jsonify({'stdout': r.stdout, 'stderr': r.stderr, 'returncode': r.returncode})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ─── WINDOWS LIST ───────────────────────────────────────────────

@app.route('/api/windows')
@require_auth
def list_windows():
    windows = []
    try:
        import pygetwindow as gw
        for w in gw.getAllWindows():
            if w.title:
                windows.append({'title': w.title, 'visible': w.visible, 'minimized': w.isMinimized})
    except:
        pass
    return jsonify(windows)

# ─── AI ASSISTANT ───────────────────────────────────────────────

@app.route('/api/ai/chat', methods=['POST'])
@require_auth
def ai_chat():
    data = request.get_json()
    message = data.get('message', '').lower().strip()
    
    responses = []
    
    if any(w in message for w in ['desligar', 'shutdown', 'desligar pc']):
        os.system('shutdown /s /t 60')
        responses.append({'action': 'power', 'result': 'Desligando em 60 segundos...'})
    elif any(w in message for w in ['reiniciar', 'restart']):
        os.system('shutdown /r /t 60')
        responses.append({'action': 'power', 'result': 'Reiniciando em 60 segundos...'})
    elif any(w in message for w in ['travar', 'bloquear', 'lock']):
        os.system('rundll32.exe user32.dll,LockWorkStation')
        responses.append({'action': 'power', 'result': 'Tela bloqueada!'})
    elif any(w in message for w in ['limpar', 'clean', 'temporário']):
        cleaned = 0
        for d in [os.environ.get('TEMP', ''), 'C:\\Windows\\Temp']:
            if d and os.path.exists(d):
                for f in os.listdir(d):
                    try:
                        p = os.path.join(d, f)
                        if os.path.isfile(p): os.remove(p); cleaned += 1
                        else: import shutil; shutil.rmtree(p, ignore_errors=True); cleaned += 1
                    except: pass
        responses.append({'action': 'cleanup', 'result': f'{cleaned} itens limpos!'})
    elif any(w in message for w in ['abrir', 'open']):
        apps = {'navegador': 'brave', 'chrome': 'brave', 'brave': 'brave', 'blocodenotas': 'notepad',
                'notepad': 'notepad', 'calculadora': 'calculator', 'explorador': 'explorer',
                'cmd': 'cmd', 'terminal': 'cmd', 'gerenciador': 'taskmgr', 'paint': 'paint'}
        for key, val in apps.items():
            if key in message:
                subprocess.Popen([val + ('.exe' if not val.endswith('.exe') else '')])
                responses.append({'action': 'open', 'result': f'{val} aberto!'})
                break
        if not responses:
            responses.append({'action': 'info', 'result': 'Não entendi qual app abrir. Tente: "abrir brave", "abrir notepad", etc.'})
    elif any(w in message for w in ['ip', 'endereço', 'rede']):
        ip = socket.gethostbyname(socket.gethostname())
        responses.append({'action': 'info', 'result': f'Seu IP local é: {ip}'})
    elif any(w in message for w in ['screenshot', 'tela', 'print', 'printscreen']):
        try:
            with mss.mss() as sct:
                img = sct.grab(sct.monitors[1])
                b64 = base64.b64encode(mss.tools.to_png(img.rgb, img.size)).decode()
                responses.append({'action': 'screenshot', 'image': b64})
        except:
            responses.append({'action': 'error', 'result': 'Não foi possível capturar a tela'})
    elif any(w in message for w in ['cpu', 'processador']):
        cpu = psutil.cpu_percent(interval=0.5)
        responses.append({'action': 'info', 'result': f'CPU: {cpu}% de uso'})
    elif any(w in message for w in ['ram', 'memória', 'memoria']):
        m = psutil.virtual_memory()
        responses.append({'action': 'info', 'result': f'RAM: {m.percent}% ({round(m.used/(1024**3),2)} / {round(m.total/(1024**3),2)} GB)'})
    elif any(w in message for w in ['disco', 'espaço', 'espaco']):
        d = psutil.disk_usage('/')
        responses.append({'action': 'info', 'result': f'Disco: {d.percent}% ({round(d.used/(1024**3),2)} / {round(d.total/(1024**3),2)} GB)'})
    elif any(w in message for w in ['obrigado', 'valeu', 'thanks']):
        responses.append({'action': 'chat', 'result': 'Por nada! Estou aqui para ajudar! 😊'})
    elif any(w in message for w in ['oi', 'olá', 'ola', 'hello', 'hi', 'eai']):
        responses.append({'action': 'chat', 'result': f'Olá! Sou seu assistente virtual. Meu hostname é {socket.gethostname()}. Como posso ajudar?'})
    elif any(w in message for w in ['comandos', 'ajuda', 'help', 'o que voce faz']):
        responses.append({'action': 'chat', 'result': '''Posso fazer muitas coisas! Tente:
• "desligar o pc" / "reiniciar"
• "abrir brave" / "abrir notepad"
• "limpar temporários"
• "screenshot" / "print da tela"
• "ip" / "cpu" / "ram" / "disco"
• "travar pc"
• Ou qualquer comando do Windows!'''})
    else:
        try:
            r = subprocess.run(message, shell=True, capture_output=True, text=True, timeout=15, errors='replace')
            if r.stdout.strip():
                responses.append({'action': 'command', 'result': r.stdout.strip()[:2000]})
            elif r.stderr.strip():
                responses.append({'action': 'command', 'result': f'[ERRO] {r.stderr.strip()[:1000]}'})
            else:
                responses.append({'action': 'chat', 'result': f'Comando executado. Não há saída.'})
        except:
            responses.append({'action': 'chat', 'result': 'Não entendi. Tente "ajuda" para ver o que posso fazer.'})
    
    return jsonify({'responses': responses})

# ─── MAIN ───────────────────────────────────────────────────────

if __name__ == '__main__':
    import time as _time
    for _attempt in range(10):
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
            break
        except Exception:
            _time.sleep(3)
    else:
        local_ip = '127.0.0.1'

    threading.Thread(target=hub_heartbeat, daemon=True).start()
    send_discord_webhook("start")

    print("=" * 60)
    print("   REMOTE CONTROL v3.0 - ULTIMATE EDITION")
    print("=" * 60)
    print(f"   URL:  http://{local_ip}:5000")
    print(f"   Pass: {AUTH_PASSWORD}")
    print(f"   ID:   {PANEL_ID}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False)
