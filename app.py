import os, subprocess, platform, psutil, json, threading, time, base64, io, re, socket, urllib.request
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

DISCORD_WEBHOOK = ""
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
        req = urllib.request.Request(DISCORD_WEBHOOK, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=5)
    except:
        pass

def register_with_hub():
    if not HUB_URL:
        return
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        payload = json.dumps({
            "panel_id": PANEL_ID,
            "hostname": HOSTNAME,
            "username": USERNAME,
            "ip": local_ip,
            "port": 5000
        }).encode()
        req = urllib.request.Request(f"{HUB_URL}/api/register", data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=5)
    except:
        pass

def hub_heartbeat():
    while True:
        try:
            register_with_hub()
        except:
            pass
        time.sleep(30)

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
    return render_template('index.html')

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
