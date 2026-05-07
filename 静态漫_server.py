#!/usr/bin/env python3
import os
import sys
import json
import base64
import time
import glob
import re
import textwrap
import subprocess
import shutil
import random
import signal
import io
import requests
import threading
import queue
import uuid
import numpy as np
from datetime import datetime

# ==================== 身份验证系统 ====================
_EA = [26475,23940,20766,23533,20796,20748,36222,26066,22887,36317,21040,20106,65325,5,31416,20762,27785,12356,30359,20321,102,113,21719,12327,21330,21454,20746,36184,20066,36636]
_EK = [71,97,105,97,84,65,71,50,48,50,54,33,33]
def _dz():
    r=''
    for i,v in enumerate(_EA):
        r+=chr(v^_EK[i%len(_EK)])
    return r
_BS = _dz()
_BH = sum(ord(c) for c in _BS)
def _vc():
    return True
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'creative-director-secret-key'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB 限制，支持大视频上传
CORS(app, resources={r"/*": {"origins": "*"}})

@app.after_request
def after_request_cors(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    return response
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ================= 路径配置 (使用 resolve() 获取绝对路径) =================
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
BATCH_INPUT_DIR = OUTPUT_DIR / "batch_input"
BATCH_OUTPUT_DIR = OUTPUT_DIR / "batch_output"
FFMPEG_DIR = BASE_DIR / "ffmpeg"

PROJECT_ROOT = BASE_DIR.parent

DEFAULT_BGM_PATH = PROJECT_ROOT / "音乐" / "权力的游戏.mp3"

SERVICE_PATHS = {
    "qwen-9b": {
        "bat": PROJECT_ROOT / "D:\my-video\启动Qwen3.5-9B_API.bat",
        "url": "http://127.0.0.1:8080",
        "model": "Qwen3.5-9B-UD-Q4_K_XL.gguf",
        "process": None
    },
    "qwen-0.8b": {
        "bat": PROJECT_ROOT / "启动Qwen3.5-0.8B_API.bat",
        "url": "http://127.0.0.1:8081",
        "model": "Qwen3.5-0.8B-UD-Q4_K_XL.gguf",
        "process": None,
        "keep_alive": True
    },
    "gemma-4-31b": {
        "bat": PROJECT_ROOT / "启动Gemma-4-31B_API.bat",
        "url": "http://127.0.0.1:8080",
        "model": "gemma-4-31B-it-UD-Q4_K_XL.gguf",
        "process": None
    },
    "gemma-4-e4b": {
        "bat": PROJECT_ROOT / "启动Gemma-4-E4B_API.bat",
        "url": "http://127.0.0.1:8082",
        "model": "gemma-4-E4B-it-UD-Q4_K_XL.gguf",
        "process": None,
        "keep_alive": True
    },
    "gemma-4-26b": {
        "bat": PROJECT_ROOT / "启动Gemma-4-26B_API.bat",
        "url": "http://127.0.0.1:8083",
        "model": "gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf",
        "process": None
    },
    "qwen-27b": {
        "bat": PROJECT_ROOT / "启动Qwen3.5-27B_API.bat",
        "url": "http://127.0.0.1:8080",
        "model": "Qwen3.5-27B-UD-Q4_K_XL.gguf",
        "process": None
    },
    "qwen-27b-q6": {
        "bat": PROJECT_ROOT / "启动Qwen3.5-27B-Q6_API.bat",
        "url": "http://127.0.0.1:8080",
        "model": "Qwen-3.5-27B-Derestricted.Q6_K.gguf",
        "process": None
    },
    "qwen-35b-a3b-q4": {
        "bat": PROJECT_ROOT / "启动Qwen3.5-35B-A3B-Q4_API.bat",
        "url": "http://127.0.0.1:8080",
        "model": "Qwen3.5-35B-A3B-UD-Q4_K_L.gguf",
        "process": None
    },
    "qwen-35b-a3b-q2": {
        "bat": PROJECT_ROOT / "启动Qwen3.5-35B-A3B-Q2_API.bat",
        "url": "http://127.0.0.1:8080",
        "model": "Qwen3.5-35B-A3B-UD-Q2_K_XL.gguf",
        "process": None
    },
    "qwen-4b": {
        "bat": PROJECT_ROOT / "启动Qwen3.5-4B_API.bat",
        "url": "http://127.0.0.1:8084",
        "model": "Qwen3.5-4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf",
        "process": None,
        "keep_alive": True
    },
    "comfyui": {
        "bat": PROJECT_ROOT / "ComfyUI_windows_portable" / "run_nvidia_gpu_fast_fp16_accumulation.bat",
        "url": "http://127.0.0.1:8188",
        "process": None
    },
    "cosyvoice": {
        "bat": PROJECT_ROOT / "CosyVoice3-App" / "run.bat",
        "url": "http://127.0.0.1:7860",
        "process": None
    },
    "doubao": {
        "bat": PROJECT_ROOT / "漫画" / "doubao_bridge" / "start_bridge.bat",
        "url": "http://127.0.0.1:8765",
        "process": None
    },
    "minimax-m2.7": {
        "url": "http://192.168.1.100:9001",
        "model": "minimax-m2.7-multimodal",
        "process": None,
        "is_remote": True
    },
    "qwen3.6-27b-fp8": {
        "url": "http://192.168.1.100:9005",
        "model": "qwen3.6-27b-fp8",
        "process": None,
        "is_remote": True
    }
}

SERVICE_PROCESSES = {}
SERVICE_STARTING = {}
MINIMAX_URL = "http://192.168.1.100:9001"
task_queue = queue.Queue()
active_tasks = {}
tasks_lock = threading.Lock()

# 聊天会话管理
chat_sessions = {}
session_lock = threading.Lock()

# WebSocket连接管理
connected_clients = set()
clients_lock = threading.Lock()

# 兼容 Windows/Linux
if sys.platform == "win32":
    FFMPEG_BIN = FFMPEG_DIR / "ffmpeg.exe"
    FFPROBE_BIN = FFMPEG_DIR / "ffprobe.exe"
else:
    FFMPEG_BIN = FFMPEG_DIR / "ffmpeg"
    FFPROBE_BIN = FFMPEG_DIR / "ffprobe"

FONT_PATH = FFMPEG_DIR / "font.ttf"

# 初始化目录
for p in [OUTPUT_DIR, BATCH_INPUT_DIR, BATCH_OUTPUT_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# ================= 辅助函数 =================

def get_qwen_service_from_api_type(api_type):
    """根据api_type获取对应的qwen服务名称"""
    mapping = {
        'qwen-9b': 'qwen-9b',
        'qwen-27b': 'qwen-27b',
        'qwen-27b-q6': 'qwen-27b-q6',
        'qwen-35b-a3b-q4': 'qwen-35b-a3b-q4',
        'qwen-35b-a3b-q2': 'qwen-35b-a3b-q2',
        'qwen-4b': 'qwen-4b',
        'qwen-0.8b': 'qwen-0.8b',
        'gemma-4-31b': 'gemma-4-31b',
        'gemma-4-26b': 'gemma-4-26b',
        'gemma-4-e4b': 'gemma-4-e4b',
        'minimax-m2.7': 'minimax-m2.7',
    }
    return mapping.get(api_type, 'qwen-9b')

def get_audio_duration(audio_path):
    try:
        cmd = [str(FFMPEG_BIN), '-i', str(audio_path)]
        # 必须使用 stderr 捕获输出，并设置 errors='ignore' 防止编码报错
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        import re
        match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d+)", result.stderr)
        if match:
            h, m, s = match.groups()
            return float(h)*3600 + float(m)*60 + float(s)
        return 5.0
    except Exception as e:
        print(f"[Warn] 获取时长失败: {e}")
        return 5.0

def get_image_size(image_path):
    try:
        cmd = [str(FFMPEG_BIN), '-i', str(image_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        import re
        match = re.search(r"Stream #\d+:\d+: Video: \w+.*? (\d+)x(\d+)", result.stderr)
        if match:
            w, h = match.groups()
            return int(w), int(h)
        return 1280, 720
    except Exception as e:
        print(f"[Warn] 获取图片尺寸失败: {e}")
        return 1280, 720

def get_project_paths(project_name, is_batch=False, batch_task_name=None):
    """统一路径管理：output/ProjectName/..."""
    if is_batch:
        root = BATCH_OUTPUT_DIR / batch_task_name / project_name
        role_dir = BATCH_OUTPUT_DIR / batch_task_name / "role"
        final_dir = BATCH_OUTPUT_DIR / batch_task_name
    else:
        root = OUTPUT_DIR / project_name
        role_dir = root / "role"
        final_dir = root

    paths = {
        "root": root,
        "image": root / "image",
        "audio": root / "audio",
        "subtitle": root / "subtitle",
        "role": role_dir,
        "final": final_dir
    }
    for k, p in paths.items():
        if k not in ['root', 'final']: p.mkdir(parents=True, exist_ok=True)
    paths['root'].mkdir(parents=True, exist_ok=True)
    paths['final'].mkdir(parents=True, exist_ok=True)
    return paths

def get_visual_effects(img_w, img_h, duration_sec, move_type):
    """
    生成复合滤镜链：运镜(Zoom/Pan/Shake) + 视觉特效(Vignette/Noise/Color)
    确保动画全程持续，绝不静止。
    """
    fps = 120
    total_frames = int(duration_sec * fps)
    d_param = total_frames + 60
    
    s_size = f"{img_w}x{img_h}"
    
    if move_type == "zoom_in":
        z = "1.0+(0.15*on/duration)"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
        
    elif move_type == "zoom_out":
        z = "1.15-(0.15*on/duration)" 
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
        
    elif move_type == "pan_right":
        z = "1.1"
        x = "(iw-iw/zoom)*(on/duration)"
        y = "ih/2-(ih/zoom/2)"
        
    elif move_type == "pan_left":
        z = "1.1"
        x = "(iw-iw/zoom)*(1-on/duration)"
        y = "ih/2-(ih/zoom/2)"
        
    elif move_type == "pan_up":
        z = "1.1"
        x = "iw/2-(iw/zoom/2)"
        y = "(ih-ih/zoom)*(1-on/duration)"
        
    elif move_type == "shake":
        z = "1.05+(0.05*on/duration)"
        x = "iw/2-(iw/zoom/2)+2*sin(on/2)"
        y = "ih/2-(ih/zoom/2)+2*cos(on/3)"
        
    else:
        z = "1.0+(0.1*on/duration)"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    base_vf = f"zoompan=z='{z}':x='{x}':y='{y}':d={d_param}:s={s_size}:fps={fps}"

    fx_options = ["none", "vignette", "grain", "warm", "cool", "pulse"]
    fx_weights = [0.2, 0.3, 0.3, 0.05, 0.05, 0.1]
    
    fx_type = random.choices(fx_options, weights=fx_weights, k=1)[0]
    fx_vf = ""
    
    if fx_type == "vignette":
        fx_vf = ",vignette=PI/4"
        
    elif fx_type == "grain":
        fx_vf = ",noise=alls=10:allf=t+u"
        
    elif fx_type == "warm":
        fx_vf = ",curves=r='0/0 1/1':g='0/0 1/0.9':b='0/0 1/0.8'"
        
    elif fx_type == "cool":
        fx_vf = ",curves=r='0/0 1/0.8':g='0/0 1/0.9':b='0/0 1/1'"
        
    elif fx_type == "pulse":
        fx_vf = ",eq=brightness=0.05*sin(t*2)"

    return base_vf + fx_vf

# ================= 接口 =================

@app.route('/')
def index():
    return send_file(str(BASE_DIR / '静态漫.html'))

@app.route('/<path:filename>')
def serve_static(filename):
    file_path = BASE_DIR / filename
    if file_path.exists() and file_path.is_file():
        return send_file(str(file_path))
    return jsonify({"error": "File not found"}), 404

@app.route('/health', methods=['GET'])
def health_check():
    ok = _BS and len(_BS) > 20 and _BH > 10000
    return jsonify({"status": "ok" if ok else "degraded", "service": "静态漫_server", "version": "2.0"})

# ==================== 图片资产 API ====================
ASSET_DIR = BASE_DIR / "图片资产"

@app.route('/api/list_assets', methods=['GET'])
def list_assets():
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(ASSET_DIR.glob('*.png')) + sorted(ASSET_DIR.glob('*.jpg')) + sorted(ASSET_DIR.glob('*.jpeg')) + sorted(ASSET_DIR.glob('*.webp'))
    assets = []
    for f in files:
        assets.append({
            "name": f.name,
            "url": f"/api/asset_file/{f.name}",
            "size": f.stat().st_size,
            "mtime": f.stat().st_mtime
        })
    return jsonify(assets)

@app.route('/api/save_asset', methods=['POST'])
def save_asset():
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    if 'image' not in request.files:
        return jsonify({"error": "未上传图片"}), 400
    file = request.files['image']
    filename = file.filename or f"asset_{int(time.time())}.png"
    filepath = ASSET_DIR / filename
    file.save(str(filepath))
    return jsonify({"status": "saved", "filename": filename, "url": f"/api/asset_file/{filename}"})

@app.route('/api/asset_file/<path:filename>', methods=['GET'])
def get_asset_file(filename):
    filepath = ASSET_DIR / filename
    if not filepath.exists():
        return jsonify({"error": "File not found"}), 404
    return send_file(str(filepath))

@app.route('/api/pep_poses', methods=['GET'])
def list_pep_poses():
    pep_dir = BASE_DIR / "POSE STUDIO" / "Library" / "PresetPose"
    if not pep_dir.exists():
        return jsonify({"error": "PEP directory not found"}), 404
    poses = []
    for f in sorted(pep_dir.glob('*.pep')):
        poses.append({"filename": f.name, "name": f.stem})
    return jsonify({"poses": poses, "count": len(poses)})

@app.route('/api/pep_pose/<path:filename>', methods=['GET'])
def get_pep_pose(filename):
    pep_dir = BASE_DIR / "POSE STUDIO" / "Library" / "PresetPose"
    filepath = pep_dir / filename
    if not filepath.exists():
        return jsonify({"error": "PEP file not found"}), 404
    return send_file(str(filepath), mimetype='application/xml')

@app.route('/scan_batch', methods=['GET'])
def scan_batch():
    files = sorted(glob.glob(str(BATCH_INPUT_DIR / "*.txt")))
    file_list = []
    for f in files:
        p = Path(f)
        try:
            content = p.read_text(encoding='utf-8')
        except:
            content = p.read_text(encoding='gbk', errors='ignore')
        file_list.append({"filename": p.stem, "content": content})
    return jsonify({"count": len(file_list), "files": file_list})

@app.route('/check_role', methods=['POST'])
def check_role():
    data = request.json
    paths = get_project_paths("temp", data.get('isBatch', False), data.get('batchTaskName', 'default'))
    role_file = paths['role'] / f"{data.get('name')}.txt"
    if role_file.exists():
        return jsonify({"exists": True, "description": role_file.read_text(encoding='utf-8')})
    return jsonify({"exists": False})

@app.route('/check_ref_image', methods=['POST'])
def check_ref_image():
    data = request.json
    ref_type = data.get('refType', 'role')
    name = data.get('name', '')
    batch_task_name = data.get('batchTaskName', 'default')
    
    if not name:
        return jsonify({"exists": False})
    
    safe_name = str(name).replace('/', '_').replace('\\', '_').replace(':', '_')
    
    if ref_type == 'role':
        ref_dir = BATCH_OUTPUT_DIR / batch_task_name / "reference_images" / "roles"
    else:
        ref_dir = BATCH_OUTPUT_DIR / batch_task_name / "reference_images" / "scenes"
    
    ref_file = ref_dir / f"{safe_name}.png"
    
    if ref_file.exists():
        import urllib.parse
        relative_path = str(ref_file.relative_to(BATCH_OUTPUT_DIR / batch_task_name))
        return jsonify({
            "exists": True, 
            "path": f"/batch_output/{batch_task_name}/{relative_path}",
            "filename": ref_file.name
        })
    
    return jsonify({"exists": False})

VOICE_LIB_DIR = BASE_DIR / "音色库"

@app.route('/scan_voice_library', methods=['GET'])
def scan_voice_library():
    result = {}
    if not VOICE_LIB_DIR.exists():
        return jsonify({"categories": {}, "error": "音色库目录不存在"})
    
    for category_dir in VOICE_LIB_DIR.iterdir():
        if not category_dir.is_dir():
            continue
        cat_name = category_dir.name
        result[cat_name] = {}
        for sub_dir in category_dir.iterdir():
            if not sub_dir.is_dir():
                continue
            sub_name = sub_dir.name
            voices = []
            for f in sorted(sub_dir.iterdir()):
                if f.is_file() and f.suffix.lower() in ['.wav', '.mp3', '.flac']:
                    voices.append({
                        "name": f.stem,
                        "filename": f.name,
                        "path": str(f.relative_to(VOICE_LIB_DIR)).replace('\\', '/'),
                        "category": cat_name,
                        "subcategory": sub_name
                    })
            if voices:
                result[cat_name][sub_name] = voices
    
    return jsonify({"categories": result})

@app.route('/voice_library/<path:filepath>')
def serve_voice_file(filepath):
    try:
        safe_path = (VOICE_LIB_DIR / filepath).resolve()
        if not str(safe_path).startswith(str(VOICE_LIB_DIR.resolve())):
            return jsonify({"error": "Invalid path"}), 403
        if safe_path.exists() and safe_path.is_file():
            return send_file(str(safe_path))
        return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/models3d/<path:filepath>')
def serve_models3d_file(filepath):
    try:
        models3d_dir = Path(__file__).parent / 'models3d'
        safe_path = (models3d_dir / filepath).resolve()
        if not str(safe_path).startswith(str(models3d_dir.resolve())):
            return jsonify({"error": "Invalid path"}), 403
        if safe_path.exists() and safe_path.is_file():
            return send_file(str(safe_path))
        return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/save_data', methods=['POST'])
def save_data():
    try:
        data = request.json
        print(f"[save_data] 收到请求: type={data.get('type')}, index={data.get('index')}, project={data.get('projectName')}")
        
        paths = get_project_paths(data.get('projectName'), data.get('isBatch', False), data.get('batchTaskName', ''))
        
        type_ = data.get('type')
        index = data.get('index', 0)
        content = data.get('content')
        
        filename = ""
        if type_ == 'role':
            f = paths['role'] / f"{content.get('name')}.txt"
            f.write_text(content.get('tags'), encoding='utf-8')
            filename = f.name
        elif type_ == 'image':
            f = paths['image'] / f"{index:03d}.png"
            if ',' in content: content = content.split(',')[1]
            f.write_bytes(base64.b64decode(content))
            filename = f.name
        elif type_ == 'role_ref_image':
            ref_dir = paths['root'] / "reference_images" / "roles"
            ref_dir.mkdir(parents=True, exist_ok=True)
            safe_name = str(index).replace('/', '_').replace('\\', '_').replace(':', '_')
            f = ref_dir / f"{safe_name}.png"
            if ',' in content: content = content.split(',')[1]
            f.write_bytes(base64.b64decode(content))
            filename = str(f.relative_to(paths['root']))
            print(f"[保存] 角色参考图: {filename}")
        elif type_ == 'scene_ref_image':
            ref_dir = paths['root'] / "reference_images" / "scenes"
            ref_dir.mkdir(parents=True, exist_ok=True)
            safe_name = str(index).replace('/', '_').replace('\\', '_').replace(':', '_')
            f = ref_dir / f"{safe_name}.png"
            if ',' in content: content = content.split(',')[1]
            f.write_bytes(base64.b64decode(content))
            filename = str(f.relative_to(paths['root']))
            print(f"[保存] 场景参考图: {filename}")
        elif type_ == 'audio':
            f = paths['audio'] / f"{index:03d}.wav"
            if ',' in content: content = content.split(',')[1]
            f.write_bytes(base64.b64decode(content))
            filename = f.name
        elif type_ == 'subtitle':
            f = paths['subtitle'] / f"{index:03d}.txt"
            f.write_text(content, encoding='utf-8')
            filename = f.name
        elif type_ == 'video_clip':
            video_dir = paths['root'] / "video"
            video_dir.mkdir(exist_ok=True)
            f = video_dir / f"{index:03d}.mp4"
            if ',' in content: content = content.split(',')[1]
            f.write_bytes(base64.b64decode(content))
            filename = f.name
        elif type_ == 'transition_video':
            trans_dir = paths['root'] / "video" / "transitions"
            trans_dir.mkdir(parents=True, exist_ok=True)
            f = trans_dir / f"{index}.mp4"
            if ',' in content: content = content.split(',')[1]
            f.write_bytes(base64.b64decode(content))
            filename = str(f.relative_to(paths['root']))
            print(f"[保存] 过渡视频: {filename}")
        elif type_ == 'variant_image':
            variant_dir = paths['root'] / "variants"
            variant_dir.mkdir(parents=True, exist_ok=True)
            # index 格式: "shotIndex_variantIndex" 如 "0_1", "2_3"
            f = variant_dir / f"{index}.png"
            if ',' in content: content = content.split(',')[1]
            f.write_bytes(base64.b64decode(content))
            filename = str(f.relative_to(paths['root']))
            print(f"[保存] 变体图片: {filename}, 完整路径: {f}")

        print(f"[保存数据] type={type_}, index={index}, filename={filename}")
        return jsonify({"status": "ok", "path": str(filename)})
    except Exception as e:
        print(f"[Error] Save: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/load_data', methods=['POST'])
def load_data():
    try:
        data = request.json
        paths = get_project_paths(data.get('projectName'), data.get('isBatch', False), data.get('batchTaskName', ''))
        
        type_ = data.get('type')
        index = data.get('index', 0)
        
        content = None
        if type_ == 'image':
            f = paths['image'] / f"{index:03d}.png"
            if f.exists():
                content = base64.b64encode(f.read_bytes()).decode('utf-8')
        elif type_ == 'role_ref_image':
            ref_dir = paths['root'] / "reference_images" / "roles"
            safe_name = str(index).replace('/', '_').replace('\\', '_').replace(':', '_')
            f = ref_dir / f"{safe_name}.png"
            if f.exists():
                content = base64.b64encode(f.read_bytes()).decode('utf-8')
        elif type_ == 'scene_ref_image':
            ref_dir = paths['root'] / "reference_images" / "scenes"
            safe_name = str(index).replace('/', '_').replace('\\', '_').replace(':', '_')
            f = ref_dir / f"{safe_name}.png"
            if f.exists():
                content = base64.b64encode(f.read_bytes()).decode('utf-8')
        elif type_ == 'audio':
            f = paths['audio'] / f"{index:03d}.wav"
            if f.exists():
                content = base64.b64encode(f.read_bytes()).decode('utf-8')
        elif type_ == 'subtitle':
            f = paths['subtitle'] / f"{index:03d}.txt"
            if f.exists():
                content = f.read_text(encoding='utf-8')
        elif type_ == 'video_clip':
            video_dir = paths['root'] / "video"
            f = video_dir / f"{index:03d}.mp4"
            if f.exists():
                content = base64.b64encode(f.read_bytes()).decode('utf-8')
        elif type_ == 'variant_image':
            variant_dir = paths['root'] / "variants"
            # index 格式: "shotIndex_variantIndex" 如 "0_1", "2_3"
            f = variant_dir / f"{index}.png"
            if f.exists():
                content = base64.b64encode(f.read_bytes()).decode('utf-8')
                print(f"[加载] 变体图片: {f}")

        return jsonify({"status": "ok", "content": content})
    except Exception as e:
        print(f"[Error] Load: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/list_ref_images', methods=['POST'])
def list_ref_images():
    try:
        data = request.json
        paths = get_project_paths(data.get('projectName'), data.get('isBatch', False), data.get('batchTaskName', ''))
        
        result = {"roles": [], "scenes": []}
        
        role_ref_dir = paths['root'] / "reference_images" / "roles"
        if role_ref_dir.exists():
            for f in role_ref_dir.glob("*.png"):
                result["roles"].append({
                    "name": f.stem,
                    "path": str(f.relative_to(paths['root']))
                })
        
        scene_ref_dir = paths['root'] / "reference_images" / "scenes"
        if scene_ref_dir.exists():
            scene_names = set()
            for f in scene_ref_dir.glob("*.png"):
                name = f.stem
                if '_' in name:
                    base_name = '_'.join(name.split('_')[:-1])
                    scene_names.add(base_name)
                else:
                    scene_names.add(name)
            
            for scene_name in scene_names:
                result["scenes"].append({
                    "name": scene_name
                })
        
        return jsonify({"status": "ok", "data": result})
    except Exception as e:
        print(f"[Error] List Ref Images: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/save_project_state', methods=['POST'])
def save_project_state():
    try:
        request.encoding = 'utf-8'
        data = request.json
        project_name = data.get('projectName')
        if not project_name:
            return jsonify({"error": "缺少项目名称"}), 400
        
        if not all(ord(c) < 128 for c in project_name):
            import urllib.parse
            safe_name = urllib.parse.quote(project_name, safe='')
            print(f"[Info] 中文项目名 '{project_name}' 转换为 '{safe_name}'")
            project_name = safe_name
        
        paths = get_project_paths(project_name, data.get('isBatch', False), data.get('batchTaskName', ''))
        
        state_file = paths['root'] / "project_state.json"
        
        state_data = {
            "projectName": project_name,
            "currentStep": data.get('currentStep', 0),
            "shots": data.get('shots', []),
            "characters": data.get('characters', []),
            "scenes": data.get('scenes', []),
            "storyContext": data.get('storyContext', {}),
            "config": data.get('config', {}),
            "storyText": data.get('storyText', ''),
            "timestamp": int(time.time() * 1000)
        }
        
        state_file.write_text(json.dumps(state_data, ensure_ascii=False, indent=2), encoding='utf-8')
        
        print(f"[保存项目状态] {project_name} - 步骤{state_data['currentStep']}")
        return jsonify({"status": "ok", "message": "项目状态已保存"})
    except Exception as e:
        print(f"[Error] Save Project State: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/load_project_state', methods=['POST'])
def load_project_state():
    try:
        data = request.json
        project_name = data.get('projectName')
        if not project_name:
            return jsonify({"error": "缺少项目名称"}), 400
        
        paths = get_project_paths(project_name, data.get('isBatch', False), data.get('batchTaskName', ''))
        
        state_file = paths['root'] / "project_state.json"
        
        if not state_file.exists():
            return jsonify({"status": "not_found", "message": "未找到项目状态文件"})
        
        state_data = json.loads(state_file.read_text(encoding='utf-8'))
        
        print(f"[加载项目状态] {project_name} - 步骤{state_data.get('currentStep', 0)}")
        return jsonify({"status": "ok", "data": state_data})
    except Exception as e:
        print(f"[Error] Load Project State: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/save_shot_image', methods=['POST'])
def save_shot_image():
    try:
        if 'image' not in request.files:
            return jsonify({"error": "未上传图片"}), 400
        
        project_name = request.form.get('projectName')
        shot_index = request.form.get('shotIndex', '0')
        image_type = request.form.get('imageType', 'main')
        
        if not project_name:
            return jsonify({"error": "缺少项目名称"}), 400
        
        paths = get_project_paths(project_name, False, '')
        
        file = request.files['image']
        image_data = file.read()
        
        if image_type == 'main':
            image_file = paths['image'] / f"{int(shot_index):03d}.png"
        elif image_type == 'additional':
            additional_dir = paths['root'] / "additional_images"
            additional_dir.mkdir(exist_ok=True)
            image_file = additional_dir / f"{int(shot_index):03d}_{int(request.form.get('variantIndex', 0)):02d}.png"
        elif image_type == 'video':
            video_dir = paths['root'] / "video"
            video_dir.mkdir(exist_ok=True)
            image_file = video_dir / f"{int(shot_index):03d}.mp4"
            image_file.write_bytes(image_data)
            return jsonify({"status": "ok", "path": str(image_file.name)})
        else:
            image_file = paths['image'] / f"{int(shot_index):03d}.png"
        
        image_file.write_bytes(image_data)
        
        return jsonify({"status": "ok", "path": str(image_file.name)})
    except Exception as e:
        print(f"[Error] Save Shot Image: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/save_audio', methods=['POST'])
def save_audio():
    try:
        if 'audio' not in request.files:
            return jsonify({"error": "未上传音频"}), 400
        
        project_name = request.form.get('projectName')
        shot_index = request.form.get('shotIndex', '0')
        
        if not project_name:
            return jsonify({"error": "缺少项目名称"}), 400
        
        paths = get_project_paths(project_name, False, '')
        
        file = request.files['audio']
        audio_data = file.read()
        
        audio_file = paths['audio'] / f"{int(shot_index):03d}.wav"
        audio_file.write_bytes(audio_data)
        
        return jsonify({"status": "ok", "path": str(audio_file.name)})
    except Exception as e:
        print(f"[Error] Save Audio: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/list_projects', methods=['GET'])
def list_projects():
    try:
        projects = []
        
        if OUTPUT_DIR.exists():
            for project_dir in OUTPUT_DIR.iterdir():
                if project_dir.is_dir():
                    state_file = project_dir / "project_state.json"
                    if state_file.exists():
                        try:
                            state = json.loads(state_file.read_text(encoding='utf-8'))
                            projects.append({
                                "name": project_dir.name,
                                "currentStep": state.get('currentStep', 0),
                                "shotCount": len(state.get('shots', [])),
                                "timestamp": state.get('timestamp', 0),
                                "storyText": state.get('storyText', '')[:100] + '...' if len(state.get('storyText', '')) > 100 else state.get('storyText', '')
                            })
                        except:
                            projects.append({
                                "name": project_dir.name,
                                "currentStep": 0,
                                "shotCount": 0,
                                "timestamp": 0,
                                "storyText": ""
                            })
        
        projects.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        return jsonify({"status": "ok", "projects": projects})
    except Exception as e:
        print(f"[Error] List Projects: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/delete_project', methods=['POST'])
def delete_project():
    try:
        data = request.json
        project_name = data.get('projectName')
        if not project_name:
            return jsonify({"error": "缺少项目名称"}), 400
        
        project_dir = OUTPUT_DIR / project_name
        
        if not project_dir.exists():
            return jsonify({"error": "项目不存在"}), 404
        
        if not str(project_dir.resolve()).startswith(str(OUTPUT_DIR.resolve())):
            return jsonify({"error": "无效的项目路径"}), 403
        
        shutil.rmtree(project_dir)
        
        print(f"[删除项目] {project_name}")
        return jsonify({"status": "ok", "message": "项目已删除"})
    except Exception as e:
        print(f"[Error] Delete Project: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/render_video', methods=['POST'])
def render_video():
    try:
        data = request.json
        project_name = data.get('projectName')
        enable_subtitle = data.get('enableSubtitle', True)
        video_width = data.get('videoWidth', 480)
        video_height = data.get('videoHeight', 832)
        
        # 完整性校验
        try:
            _ok = _BS and len(_BS) > 20 and _BH > 10000
            if not _ok:
                video_width = max(240, video_width // 3)
                video_height = max(240, video_height // 3)
        except:
            pass
        
        paths = get_project_paths(project_name, data.get('isBatch', False), data.get('batchTaskName', ''))
        
        images = sorted(list(paths['image'].glob("*.png")))
        audios = sorted(list(paths['audio'].glob("*.wav")))
        subtitles = sorted(list(paths['subtitle'].glob("*.txt")))
        
        video_dir = paths['root'] / "video"
        video_clips = sorted(list(video_dir.glob("*.mp4"))) if video_dir.exists() else []
        
        trans_dir = video_dir / "transitions"
        transition_clips = sorted(list(trans_dir.glob("*.mp4"))) if trans_dir.exists() else []
        
        is_video_mode = len(video_clips) > 0 and len(video_clips) >= len(audios)
        is_video_only_mode = is_video_mode and len(audios) == 0 and len(video_clips) > 0
        
        if not images and not video_clips: 
            return jsonify({"error": "No images or videos found"}), 400
        
        if is_video_only_mode:
            count = len(video_clips)
        else:
            count = len(audios)
        
        if count == 0:
            return jsonify({"error": "No audio or video clips to render"}), 400
        
        print(f"[Info] Rendering {project_name}: {count} clips (Mode: {'VIDEO_ONLY' if is_video_only_mode else 'VIDEO' if is_video_mode else 'IMAGE'}, Subtitle: {'ON' if enable_subtitle else 'OFF'})")
        
        temp_dir = paths['root'] / "temp_render"
        if temp_dir.exists(): shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        video_parts = []
        
        for i in range(count):
            part_out = temp_dir / f"part_{i:03d}.mp4"
            
            if is_video_only_mode:
                vid_path = str(video_clips[i].resolve())
                
                try:
                    res = subprocess.run([str(FFMPEG_BIN), '-i', vid_path], capture_output=True, text=True, encoding='utf-8', errors='ignore')
                    import re
                    m = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d+)", res.stderr)
                    orig_dur = float(m.group(1))*3600 + float(m.group(2))*60 + float(m.group(3)) if m else 5.0
                except: 
                    orig_dur = 5.0
                
                vid_w, vid_h = video_width, video_height
                if vid_w % 2 != 0: vid_w -= 1
                if vid_h % 2 != 0: vid_h -= 1
                
                vf = f"scale={vid_w}:{vid_h}:force_original_aspect_ratio=increase,crop={vid_w}:{vid_h}"
                
                cmd = [
                    str(FFMPEG_BIN), '-y',
                    '-i', vid_path,
                    '-vf', vf,
                    '-c:v', 'libx264', '-preset', 'medium', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac',
                    '-t', str(orig_dur),
                    str(part_out.resolve())
                ]
                
                print(f"[Info] Video-only mode: clip {i+1}/{count}, duration={orig_dur:.1f}s, size={vid_w}x{vid_h}")
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                video_parts.append(str(part_out.resolve()))
                continue
            
            aud_path = str(audios[i].resolve())
            sub_text = subtitles[i].read_text(encoding='utf-8').strip()
            
            font_path_str = "ffmpeg/font.ttf"
            text_vf = "null"
            if enable_subtitle:
                lines = textwrap.wrap(sub_text, 18)
                drawtext_filters = []
                for idx, line in enumerate(lines):
                    y_off = (len(lines)-1-idx)*60
                    safe_line = line.replace("'", "").replace(":", "")
                    drawtext_filters.append(
                        f"drawtext=fontfile='{font_path_str}':text='{safe_line}':fontsize=32:fontcolor=yellow:borderw=2:bordercolor=black:x=(w-text_w)/2:y=h-100-{y_off}"
                    )
                text_vf = ",".join(drawtext_filters) if drawtext_filters else "null"
            
            target_duration = get_audio_duration(aud_path)
            if target_duration < 2.0: target_duration = 2.0

            if is_video_mode:
                vid_path = str(video_clips[i].resolve())
                
                try:
                    res = subprocess.run([str(FFMPEG_BIN), '-i', vid_path], capture_output=True, text=True, encoding='utf-8', errors='ignore')
                    import re
                    m = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d+)", res.stderr)
                    orig_dur = float(m.group(1))*3600 + float(m.group(2))*60 + float(m.group(3)) if m else 5.0
                    has_audio = 'Audio:' in res.stderr
                except: 
                    orig_dur = 5.0
                    has_audio = False
                
                vid_w, vid_h = video_width, video_height
                print(f"[Info] 使用用户设定分辨率: {vid_w}x{vid_h}")
                time_scale = target_duration / orig_dur
                
                if vid_w % 2 != 0: vid_w -= 1
                if vid_h % 2 != 0: vid_h -= 1
                
                vf = f"scale={vid_w}:{vid_h}:force_original_aspect_ratio=increase,crop={vid_w}:{vid_h},setpts={time_scale}*PTS,{text_vf}"
                
                if has_audio:
                    # 视频自带音频（如LTX2.3配音），保留视频原始音频，不叠加外部音频
                    print(f"[Info] 视频{i+1}已有音频流，使用内嵌音频")
                    cmd = [
                        str(FFMPEG_BIN), '-y',
                        '-i', vid_path,
                        '-vf', vf,
                        '-c:v', 'libx264', '-preset', 'medium', '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac',
                        '-t', str(target_duration),
                        str(part_out.resolve())
                    ]
                else:
                    cmd = [
                        str(FFMPEG_BIN), '-y',
                        '-i', vid_path,
                        '-i', aud_path,
                        '-vf', vf,
                        '-c:v', 'libx264', '-preset', 'medium', '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac',
                        '-t', str(target_duration),
                        str(part_out.resolve())
                    ]
            else:
                img_path = str(images[i].resolve())
                img_w, img_h = get_image_size(img_path)
                if img_w % 2 != 0: img_w -= 1
                if img_h % 2 != 0: img_h -= 1
                
                move_types = ["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "shake"]
                move = random.choice(move_types)
                visual_vf = get_visual_effects(img_w, img_h, target_duration, move)
                vf = f"{visual_vf},{text_vf}"

                cmd = [
                    str(FFMPEG_BIN), '-y',
                    '-loop', '1', '-i', img_path,
                    '-i', aud_path,
                    '-vf', vf,
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac',
                    '-t', str(target_duration),
                    str(part_out.resolve())
                ]

            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            video_parts.append(str(part_out.resolve()))

        if transition_clips:
            print(f"[Info] 发现 {len(transition_clips)} 个过渡视频，正在插入...")
            new_parts = []
            for i, part in enumerate(video_parts):
                new_parts.append(part)
                if i < len(video_parts) - 1:
                    trans_name = f"{i:03d}_{i+1:03d}.mp4"
                    trans_path = trans_dir / trans_name
                    if trans_path.exists():
                        trans_out = temp_dir / f"trans_{i:03d}.mp4"
                        vid_w, vid_h = video_width, video_height
                        if vid_w % 2 != 0: vid_w -= 1
                        if vid_h % 2 != 0: vid_h -= 1
                        vf = f"scale={vid_w}:{vid_h}:force_original_aspect_ratio=increase,crop={vid_w}:{vid_h}"
                        cmd = [
                            str(FFMPEG_BIN), '-y',
                            '-i', str(trans_path.resolve()),
                            '-vf', vf,
                            '-c:v', 'libx264', '-preset', 'medium', '-pix_fmt', 'yuv420p',
                            '-c:a', 'aac',
                            str(trans_out.resolve())
                        ]
                        try:
                            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                            new_parts.append(str(trans_out.resolve()))
                            print(f"[Info] 过渡视频 {trans_name} 已插入到分镜{i}和{i+1}之间")
                        except Exception as te:
                            print(f"[Warn] 过渡视频 {trans_name} 处理失败: {te}")
                    else:
                        for tc in transition_clips:
                            tc_name = tc.stem
                            if f"{i:03d}" in tc_name and f"{i+1:03d}" in tc_name:
                                trans_out = temp_dir / f"trans_{i:03d}.mp4"
                                vid_w, vid_h = video_width, video_height
                                if vid_w % 2 != 0: vid_w -= 1
                                if vid_h % 2 != 0: vid_h -= 1
                                vf = f"scale={vid_w}:{vid_h}:force_original_aspect_ratio=increase,crop={vid_w}:{vid_h}"
                                cmd = [
                                    str(FFMPEG_BIN), '-y',
                                    '-i', str(tc.resolve()),
                                    '-vf', vf,
                                    '-c:v', 'libx264', '-preset', 'medium', '-pix_fmt', 'yuv420p',
                                    '-c:a', 'aac',
                                    str(trans_out.resolve())
                                ]
                                try:
                                    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                                    new_parts.append(str(trans_out.resolve()))
                                    print(f"[Info] 过渡视频 {tc.name} 已插入到分镜{i}和{i+1}之间")
                                except Exception as te:
                                    print(f"[Warn] 过渡视频 {tc.name} 处理失败: {te}")
                                break
            video_parts = new_parts

        # LTX2.3 截取机制已禁用（用户要求取消末尾1.5秒截取）
        # LTX23_TRIM_END_SECONDS = 1.5
        # trimmed_video_parts = []
        # for idx, v in enumerate(video_parts):
        #     try:
        #         res = subprocess.run(
        #             [str(FFMPEG_BIN), '-i', v],
        #             capture_output=True, text=True, encoding='utf-8', errors='ignore'
        #         )
        #         import re
        #         m = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d+)", res.stderr)
        #         orig_dur = float(m.group(1))*3600 + float(m.group(2))*60 + float(m.group(3)) if m else 5.0
        #         
        #         if orig_dur > LTX23_TRIM_END_SECONDS + 0.5:
        #             new_dur = orig_dur - LTX23_TRIM_END_SECONDS
        #             trimmed_path = temp_dir / f"trimmed_{idx:03d}.mp4"
        #             subprocess.run([
        #                 str(FFMPEG_BIN), '-y',
        #                 '-i', v,
        #                 '-t', str(new_dur),
        #                 '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
        #                 '-c:a', 'aac',
        #                 str(trimmed_path.resolve())
        #             ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        #             trimmed_video_parts.append(str(trimmed_path.resolve()))
        #             print(f"[LTX2.3修复] 片段{idx}: {orig_dur:.1f}s → {new_dur:.1f}s (截取末尾{LTX23_TRIM_END_SECONDS}s)")
        #         else:
        #             trimmed_video_parts.append(v)
        #             print(f"[LTX2.3修复] 片段{idx}: {orig_dur:.1f}s (过短，跳过截取)")
        #     except Exception as te:
        #         trimmed_video_parts.append(v)
        #         print(f"[Warn] LTX2.3截取失败，使用原始片段: {te}")
        # 
        # video_parts = trimmed_video_parts
        print(f"[Info] LTX2.3末尾截取已禁用，保留完整视频片段")

        concat_list = temp_dir / "concat.txt"
        with open(concat_list, 'w', encoding='utf-8') as f:
            for v in video_parts:
                f.write(f"file '{v.replace(os.sep, '/')}'\n")
        
        merged_mp4 = temp_dir / "merged.mp4"
        subprocess.run([
            str(FFMPEG_BIN), '-y', '-f', 'concat', '-safe', '0',
            '-i', str(concat_list.resolve()), '-c', 'copy', str(merged_mp4.resolve())
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        
        final_output = paths['final'] / f"{project_name}_final.mp4"
        bgm_base64 = data.get('bgm')
        
        if bgm_base64:
            bgm_path = temp_dir / "bgm.mp3"
            if ',' in bgm_base64: bgm_base64 = bgm_base64.split(',')[1]
            bgm_path.write_bytes(base64.b64decode(bgm_base64))
            
            subprocess.run([
                str(FFMPEG_BIN), '-y', '-i', str(merged_mp4.resolve()),
                '-stream_loop', '-1', '-i', str(bgm_path.resolve()),
                '-filter_complex', '[0:a]volume=1.0[v];[1:a]volume=0.2[b];[v][b]amix=inputs=2:duration=first',
                '-c:v', 'copy', '-c:a', 'aac', str(final_output.resolve())
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        else:
            shutil.move(str(merged_mp4), str(final_output))

        relative_path = final_output.relative_to(OUTPUT_DIR)
        url_path = str(relative_path).replace(os.sep, '/')

        return jsonify({"status": "ok", "url": url_path})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/output/<path:filename>')
def download_file(filename):
    try:
        safe_path = (OUTPUT_DIR / filename).resolve()
        if not str(safe_path).startswith(str(OUTPUT_DIR.resolve())):
            return jsonify({"error": "Invalid path"}), 403
        if safe_path.exists() and safe_path.is_file():
            return send_file(str(safe_path))
        return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/batch_output/<path:filename>')
def download_batch_file(filename):
    try:
        safe_path = (BATCH_OUTPUT_DIR / filename).resolve()
        if not str(safe_path).startswith(str(BATCH_OUTPUT_DIR.resolve())):
            return jsonify({"error": "Invalid path"}), 403
        if safe_path.exists() and safe_path.is_file():
            return send_file(str(safe_path))
        return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ================= 服务管理 API (低显存模式) =================

def check_service_status(service_name):
    """检查服务是否在线"""
    if service_name not in SERVICE_PATHS:
        return False
    
    # 远程服务（如 MiniMax-M2.7）通过健康检查端点验证
    if SERVICE_PATHS[service_name].get("is_remote"):
        url = SERVICE_PATHS[service_name]["url"]
        try:
            resp = requests.get(f"{url}/health", timeout=3)
            return resp.status_code == 200
        except Exception as e:
            print(f"[Service] Remote service {service_name} health check failed: {e}")
            return False
    
    url = SERVICE_PATHS[service_name]["url"]
    try:
        if service_name.startswith("qwen"):
            resp = requests.get(f"{url}/v1/models", timeout=5)
        elif service_name == "cosyvoice":
            resp = requests.get(f"{url}/api/status", timeout=5)
        elif service_name == "comfyui":
            resp = requests.get(f"{url}/system_stats", timeout=10)
        else:
            resp = requests.get(url, timeout=5)
        return resp.status_code == 200
    except:
        return False

def kill_process_tree(pid):
    """终止进程及其子进程"""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], 
                         capture_output=True, timeout=10)
        else:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
    except Exception as e:
        print(f"[Warn] Kill process failed: {e}")

@app.route('/service/status', methods=['GET'])
def get_service_status():
    """获取所有服务状态"""
    statuses = {}
    for name in SERVICE_PATHS:
        bat_path = SERVICE_PATHS[name].get("bat")
        statuses[name] = {
            "online": check_service_status(name),
            "path": str(bat_path) if bat_path else "remote"
        }
    return jsonify({"status": statuses})

@app.route('/default-bgm', methods=['GET'])
def get_default_bgm():
    """获取默认BGM文件"""
    if DEFAULT_BGM_PATH.exists():
        return send_file(str(DEFAULT_BGM_PATH), mimetype='audio/mpeg')
    else:
        return jsonify({"error": "Default BGM not found"}), 404

@app.route('/service/start/<service_name>', methods=['POST'])
def start_service(service_name):
    """启动指定服务"""
    print(f"[Service] start_service called: {service_name}")
    
    if service_name not in SERVICE_PATHS:
        print(f"[Service] Unknown service: {service_name}")
        return jsonify({"error": f"Unknown service: {service_name}"}), 400
    
    for retry in range(3):
        if check_service_status(service_name):
            print(f"[Service] {service_name} already running (check {retry + 1})")
            return jsonify({"status": "already_running", "message": f"{service_name} is already running"})
        if retry < 2:
            time.sleep(1)
    
    if SERVICE_STARTING.get(service_name):
        print(f"[Service] {service_name} is starting, waiting...")
        for _ in range(60):
            time.sleep(2)
            if check_service_status(service_name):
                SERVICE_STARTING[service_name] = False
                return jsonify({"status": "already_running", "message": f"{service_name} is already running"})
            if not SERVICE_STARTING.get(service_name):
                break
        SERVICE_STARTING[service_name] = False
    
    SERVICE_STARTING[service_name] = True
    
    # 检查是否为远程服务（如 MiniMax-M2.7）
    if SERVICE_PATHS[service_name].get("is_remote"):
        SERVICE_STARTING[service_name] = False
        print(f"[Service] {service_name} is remote service, no need to start locally")
        return jsonify({"status": "already_running", "message": f"{service_name} is remote service"})
    
    bat_path = SERVICE_PATHS[service_name].get("bat")
    if not bat_path:
        SERVICE_STARTING[service_name] = False
        print(f"[Service] No bat path for {service_name}")
        return jsonify({"error": f"No bat path configured for {service_name}"}), 500
    
    if not bat_path.exists():
        SERVICE_STARTING[service_name] = False
        print(f"[Service] Batch file not found: {bat_path}")
        return jsonify({"error": f"Batch file not found: {bat_path}"}), 404
    
    print(f"[Service] Starting {service_name} with bat: {bat_path}")
    
    try:
        work_dir = bat_path.parent
        if service_name == "comfyui":
            work_dir = PROJECT_ROOT / "ComfyUI_windows_portable"
            comfyui_cmd = [
                str(work_dir / "python_embeded" / "python.exe"), "-s",
                "ComfyUI/main.py",
                "--windows-standalone-build",
                "--fast", "fp16_accumulation",
                "--listen", "127.0.0.1",
                "--enable-cors-header", "*",
                "--disable-xformers",
                "--disable-auto-launch",
                "--reserve-vram", "2.0"
            ]
            proc = subprocess.Popen(
                comfyui_cmd,
                cwd=str(work_dir),
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
            )
        else:
            proc = subprocess.Popen(
                ["cmd", "/c", str(bat_path)],
                cwd=str(work_dir),
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
            )
        SERVICE_PROCESSES[service_name] = proc.pid
        print(f"[Service] Process started with PID: {proc.pid}")
        
        max_wait = 120
        waited = 0
        while waited < max_wait:
            time.sleep(2)
            waited += 2
            if check_service_status(service_name):
                SERVICE_STARTING[service_name] = False
                print(f"[Service] {service_name} started successfully")
                return jsonify({
                    "status": "started", 
                    "pid": proc.pid,
                    "message": f"{service_name} started successfully"
                })
        
        SERVICE_STARTING[service_name] = False
        print(f"[Service] {service_name} start timeout")
        return jsonify({"status": "timeout", "message": f"{service_name} start timeout"}), 408
        
    except Exception as e:
        SERVICE_STARTING[service_name] = False
        print(f"[Service] Error starting {service_name}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/service/stop/<service_name>', methods=['POST'])
def stop_service(service_name):
    """停止指定服务"""
    if service_name not in SERVICE_PATHS:
        return jsonify({"error": f"Unknown service: {service_name}"}), 400
    
    # 清除启动标志
    SERVICE_STARTING[service_name] = False
    
    stopped = False
    
    if service_name in SERVICE_PROCESSES:
        pid = SERVICE_PROCESSES[service_name]
        kill_process_tree(pid)
        del SERVICE_PROCESSES[service_name]
        stopped = True
    
    if sys.platform == "win32":
        try:
            if service_name.startswith("qwen"):
                subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"], 
                             capture_output=True, timeout=10)
            elif service_name == "comfyui":
                try:
                    result = subprocess.run(
                        ["wmic", "process", "where", "commandline like '%ComfyUI\\\\main.py%'", "call", "terminate"],
                        capture_output=True, timeout=10
                    )
                except:
                    pass
                time.sleep(1)
                try:
                    subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq ComfyUI*"], 
                                 capture_output=True, timeout=10)
                except:
                    pass
            elif service_name == "cosyvoice":
                subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq CosyVoice*"], 
                             capture_output=True, timeout=10)
        except:
            pass
    
    time.sleep(2)
    
    if not check_service_status(service_name):
        return jsonify({"status": "stopped", "message": f"{service_name} stopped"})
    else:
        return jsonify({"status": "failed", "message": f"{service_name} still running"}), 500

@app.route('/service/start_doubao', methods=['POST'])
def start_doubao_service():
    """启动豆包中间服务"""
    print("[Service] start_doubao_service called")
    
    doubao_url = "http://127.0.0.1:8765"
    
    # 检查是否已经运行
    try:
        resp = requests.get(f"{doubao_url}/health", timeout=3)
        if resp.ok:
            data = resp.json()
            print(f"[Service] Doubao already running, logged_in: {data.get('logged_in')}")
            return jsonify({
                "status": "already_running",
                "logged_in": data.get("logged_in", False),
                "message": "豆包服务已在运行"
            })
    except:
        pass
    
    # 启动服务
    doubao_config = SERVICE_PATHS.get("doubao")
    if not doubao_config:
        return jsonify({"error": "豆包服务配置未找到"}), 500
    
    bat_path = doubao_config.get("bat")
    if not bat_path or not bat_path.exists():
        return jsonify({"error": f"豆包启动脚本未找到: {bat_path}"}), 404
    
    print(f"[Service] Starting doubao with bat: {bat_path}")
    
    try:
        work_dir = bat_path.parent
        proc = subprocess.Popen(
            ["cmd", "/c", str(bat_path)],
            cwd=str(work_dir),
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
        )
        SERVICE_PROCESSES["doubao"] = proc.pid
        print(f"[Service] Doubao process started with PID: {proc.pid}")
        
        # 等待服务启动
        max_wait = 60
        waited = 0
        while waited < max_wait:
            time.sleep(3)
            waited += 3
            try:
                resp = requests.get(f"{doubao_url}/health", timeout=3)
                if resp.ok:
                    data = resp.json()
                    print(f"[Service] Doubao started, logged_in: {data.get('logged_in')}")
                    return jsonify({
                        "status": "started",
                        "pid": proc.pid,
                        "logged_in": data.get("logged_in", False),
                        "message": "豆包服务已启动"
                    })
            except:
                pass
        
        print("[Service] Doubao start timeout")
        return jsonify({"status": "timeout", "message": "豆包服务启动超时"}), 408
        
    except Exception as e:
        print(f"[Service] Error starting doubao: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/service/switch', methods=['POST'])
def switch_service():
    """切换服务：关闭当前服务，启动目标服务"""
    data = request.json
    stop_service_name = data.get("stop")
    start_service_name = data.get("start")
    
    print(f"[Service] switch_service: stop={stop_service_name}, start={start_service_name}")
    
    results = {}
    
    if stop_service_name:
        stop_result = stop_service(stop_service_name)
        if isinstance(stop_result, tuple):
            stop_resp, stop_code = stop_result
            results["stop"] = stop_resp.get_json() if hasattr(stop_resp, 'get_json') else {"status": "unknown", "code": stop_code}
        else:
            results["stop"] = stop_result.get_json() if hasattr(stop_result, 'get_json') else {"status": "unknown"}
        time.sleep(3)
    
    if start_service_name:
        start_result = start_service(start_service_name)
        print(f"[Service] start_result type: {type(start_result)}")
        if isinstance(start_result, tuple):
            start_resp, start_code = start_result
            print(f"[Service] start_result is tuple, code: {start_code}")
            results["start"] = start_resp.get_json() if hasattr(start_resp, 'get_json') else {"status": "unknown"}
            results["start"]["code"] = start_code
        else:
            print(f"[Service] start_result is not tuple")
            results["start"] = start_result.get_json() if hasattr(start_result, 'get_json') else {"status": "unknown"}
    
    print(f"[Service] switch_service results: {results}")
    return jsonify(results)

# ==================== 角色图片分析API ====================
@app.route('/api/analyze/character_image', methods=['POST'])
def analyze_character_image():
    """使用多模态模型分析图片中的角色特征，然后生成详细的Danbooru标签描述"""
    try:
        llm_config = request.form.get('llm_config')
        if llm_config:
            try:
                llm_config = json.loads(llm_config)
            except:
                llm_config = {}
        else:
            llm_config = {}
        
        if 'image' not in request.files:
            return jsonify({"error": "未上传图片"}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({"error": "未选择图片"}), 400
        
        image_data = file.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        filename = file.filename.lower()
        if filename.endswith('.png'):
            image_type = 'png'
        elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
            image_type = 'jpeg'
        elif filename.endswith('.webp'):
            image_type = 'webp'
        else:
            image_type = 'jpeg'
        
        print(f"[角色图片分析] 开始分析图片: {file.filename}")
        
        api_type = llm_config.get('api_type', 'qwen-9b')
        qwen_service = get_qwen_service_from_api_type(api_type)
        
        qwen_url = SERVICE_PATHS[qwen_service]["url"]
        qwen_model = SERVICE_PATHS[qwen_service]["model"]
        is_minimax = (api_type == 'minimax-m2.7')
        
        # 第一步：用多模态模型提取图片中的角色特征
        extract_prompt = """你是顶级原画设定师。请仔细分析这张图片，提取图片中**最主要的一个角色/人物**的所有可见外观特征。

【重要规则】
1. 只描述图片中最主要的那一个角色/人物，忽略背景中的其他人物
2. 忽略背景环境，只专注于角色的外观特征
3. 必须非常详细，尽可能捕捉所有可见细节
4. **绝对不要描述动作、姿态、姿势！** 图片中的动作只是参考图的动作，不是角色的固定特征
5. **绝对不要描述表情！** 表情会根据场景变化，不是固定特征
6. **必须首先明确性别！** 开头第一句必须说明是男性还是女性

【请详细描述以下内容】

0. **性别（最重要，必须首先说明）**：
   - 必须明确说明：男性 或 女性
   - 这是最重要的特征，必须放在描述的最开头

1. **发型发色**：
   - 发型具体样式（长发/中发/短发/马尾/双马尾/丸子头/散发/编发/刘海样式等）
   - 发色（纯黑/深棕/浅棕/金色/银白/红色/蓝色/挑染/渐变等）
   - 发质（直发/卷发/波浪/毛躁/柔顺等）

2. **面部特征**：
   - 瞳色（深黑/深棕/浅棕/琥珀/蓝色/绿色/灰色/异色瞳等）
   - 眼型（圆眼/杏眼/丹凤眼/下垂眼/上挑眼/大眼睛/小眼睛等）
   - 肤色（白皙/小麦色/古铜/苍白/粉嫩等）
   - 五官特点（如有特殊标记请描述）

3. **身材体型**：
   - 身高感（高挑/中等/娇小）
   - 体型（纤细/匀称/健壮/丰满/苗条）
   - 年龄感（儿童/少年/青年/中年/老年）

4. **服装细节（最重要，必须详细）**：
   - 上装款式和颜色（如：白色棉质衬衫、深蓝色西装外套等）
   - 下装款式和颜色
   - 鞋子款式和颜色
   - 服装材质（如可见）

5. **配饰细节**：
   - 首饰（项链/耳环/戒指/手镯/发饰等，描述样式和颜色）
   - 眼镜（有无/款式/颜色）
   - 其他（手表/腰带/帽子/围巾/包包/武器等）

6. **标志性特征**：
   - 痣/疤痕/纹身（位置和形状）
   - 特殊标记（如"左眼下一颗泪痣"等）

【禁止描述的内容】
- ❌ 动作/姿态（如"站立"、"坐着"、"举手"、"奔跑"等）
- ❌ 表情（如"微笑"、"严肃"、"哭泣"等）
- ❌ 手势（如"比V"、"握拳"等）
- ❌ 身体朝向（如"面向左侧"、"侧身"等）

【输出格式】
请直接输出一段完整的角色外观描述文字，只包含静态的外观特征，不要输出JSON格式，不要有任何开场白。
**第一句必须是性别！** 例如："这是一位女性角色..." 或 "这是一位男性角色..."
然后描述应该是一个连贯的段落，包含上述所有可见的细节。"""

        def get_available_model():
            """获取可用的模型名称"""
            try:
                resp = requests.get(f"{qwen_url}/v1/models", timeout=5)
                if resp.status_code == 200:
                    models = resp.json().get("data", [])
                    if models:
                        return models[0].get("id", qwen_model)
            except:
                pass
            return qwen_model
        
        def call_vision_api(prompt_text):
            if is_minimax:
                print(f"[角色图片分析] 使用MiniMax-M2.7多模态模型")
                response = requests.post(
                    f"{MINIMAX_URL}/v1/chat/completions",
                    headers={'Content-Type': 'application/json'},
                    json={
                        "model": "minimax-m2.7-multimodal",
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt_text},
                                    {"type": "image_url", "image_url": {"url": f"data:image/{image_type};base64,{image_base64}"}}
                                ]
                            }
                        ],
                        "temperature": 0.3,
                        "max_tokens": 1500
                    },
                    timeout=180
                )
                response.raise_for_status()
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            
            model_name = get_available_model()
            print(f"[角色图片分析] 使用模型: {model_name}")
            response = requests.post(
                f"{qwen_url}/v1/chat/completions",
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer sk-xxx'
                },
                json={
                    "model": llm_config.get('model', model_name),
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt_text},
                                {"type": "image_url", "image_url": {"url": f"data:image/{image_type};base64,{image_base64}"}}
                            ]
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1500
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        
        def call_text_api(prompt_text):
            if is_minimax:
                response = requests.post(
                    f"{MINIMAX_URL}/v1/chat/completions",
                    headers={'Content-Type': 'application/json'},
                    json={
                        "model": "minimax-m2.7-multimodal",
                        "messages": [{"role": "user", "content": prompt_text}],
                        "temperature": 0.3,
                        "max_tokens": 2000
                    },
                    timeout=180
                )
                response.raise_for_status()
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            
            model_name = get_available_model()
            response = requests.post(
                f"{qwen_url}/v1/chat/completions",
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer sk-xxx'
                },
                json={
                    "model": llm_config.get('model', model_name),
                    "messages": [
                        {"role": "user", "content": prompt_text}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        
        try:
            # 第一步：提取原始特征
            raw_features = call_vision_api(extract_prompt)
            print(f"[角色图片分析] 原始特征提取完成: {raw_features[:100]}...")
            
            # 第二步：将特征转换为详细的Danbooru标签格式
            danbooru_prompt = f"""你是Danbooru标签专家和角色设定师。请根据以下角色外观特征描述，生成详细的Danbooru标签格式描述。

【原始特征描述】
{raw_features}

【任务要求】
1. 将上述特征转换为标准的Danbooru英文标签格式
2. 标签必须非常详细，覆盖所有可见的外观特征
3. 输出长度约500-600字（标签数量要足够多，确保角色一致性）
4. 只输出标签，用逗号分隔，不要有任何解释

【必须包含的标签类别】
- 性别和焦点：1boy/1girl, male focus/female focus
- 年龄：young/teen/adult/mature/elderly
- 发型发色：long hair/short hair/black hair/blonde hair等
- 眼睛：brown eyes/blue eyes/round eyes等
- 体型：slender/athletic/curvy等
- 服装：shirt/dress/skirt/jacket等（包含颜色和材质）
- 配饰：earrings/necklace/glasses等
- 特殊标记：beauty mark/scar/tattoo等

【输出格式】
直接输出Danbooru标签，用逗号分隔，长度约500-600字。"""

            danbooru_tags = call_text_api(danbooru_prompt)
            print(f"[角色图片分析] Danbooru标签生成完成: {danbooru_tags[:100]}...")
            
            return jsonify({
                "status": "ok",
                "character_desc": danbooru_tags
            })
            
        except requests.exceptions.ConnectionError as e:
            print("[角色图片分析] 多模态服务未启动，尝试启动...")
            try:
                start_resp = requests.post(f"http://127.0.0.1:5001/service/start/{qwen_service}", timeout=120)
                if start_resp.status_code == 200:
                    start_data = start_resp.json()
                    print(f"[角色图片分析] 启动服务响应: {start_data}")
            except Exception as start_err:
                print(f"[角色图片分析] 启动服务异常: {start_err}")
            
            time.sleep(8)
            
            # 重试
            raw_features = call_vision_api(extract_prompt)
            danbooru_prompt = f"""你是Danbooru标签专家和角色设定师。请根据以下角色外观特征描述，生成详细的Danbooru标签格式描述。

【原始特征描述】
{raw_features}

【任务要求】
1. 将上述特征转换为标准的Danbooru英文标签格式
2. 标签必须非常详细，覆盖所有可见的外观特征
3. 输出长度约500-600字（标签数量要足够多，确保角色一致性）
4. 只输出标签，用逗号分隔，不要有任何解释

【必须包含的标签类别】
- 性别和焦点：1boy/1girl, male focus/female focus
- 年龄：young/teen/adult/mature/elderly
- 发型发色：long hair/short hair/black hair/blonde hair等
- 眼睛：brown eyes/blue eyes/round eyes等
- 体型：slender/athletic/curvy等
- 服装：shirt/dress/skirt/jacket等（包含颜色和材质）
- 配饰：earrings/necklace/glasses等
- 特殊标记：beauty mark/scar/tattoo等

【输出格式】
直接输出Danbooru标签，用逗号分隔，长度约500-600字。"""

            danbooru_tags = call_text_api(danbooru_prompt)
            
            return jsonify({
                "status": "ok",
                "character_desc": danbooru_tags
            })
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"分析失败: {str(e)}"}), 500

# ==================== 角色特征卡生成API ====================
@app.route('/api/generate_character_card', methods=['POST'])
def generate_character_card():
    """根据主题和图片特征生成结构化的角色特征卡（JSON格式）"""
    try:
        data = request.get_json() if request.is_json else {}
        
        theme = data.get('theme', '')
        character_name = data.get('character_name', '')
        user_input = data.get('user_input', '')
        image_features = data.get('image_features', '')
        llm_config = data.get('llm_config', {})
        
        print(f"[角色特征卡] 主题: {theme}, 角色名: {character_name}")
        print(f"[角色特征卡] 用户输入: {user_input[:50] if user_input else '无'}...")
        print(f"[角色特征卡] 图片特征: {image_features[:50] if image_features else '无'}...")
        
        user_context = ""
        if character_name:
            user_context += f"\n角色名称：{character_name}"
        if user_input:
            user_context += f"\n\n【用户提供的角色描述】\n{user_input}\n（请将这些特征包含在最终的角色卡中，并补充其他细节）"
        if image_features:
            user_context += f"\n\n【从图片识别的角色特征】\n{image_features}\n（这些是必须包含的核心特征，请完整保留并补充其他细节）"
        
        prompt = f"""你是顶级原画设定师。请根据以下主题，设计一个主角的详细外观特征卡。

主题：{theme}
{user_context}

【核心原则 - 必须严格遵守】
1. **图片特征优先级最高**：如果提供了图片特征，必须完整保留，一个字都不能改
2. **性别必须从图片特征确定**：如果提供了图片特征，性别（gender字段）必须根据图片中的角色来确定，绝对不能根据角色名称或主题来推断性别！
3. **用户描述次之**：用户提供的描述必须完整包含
4. **自动补全缺失字段**：对于用户未提供的字段，根据主题和已有信息合理推测，设计详细的默认值
5. **每个字段都必须填写**：不能为空，不能写"未知"、"不确定"等
6. **越详细越稳定**：描述越详细，AI生成时角色越稳定，所以要尽可能详细

【绝对禁止包含的内容】
- ❌ 动作/姿态（如"站立"、"坐着"、"举手"、"奔跑"等）- 这些会根据场景变化
- ❌ 表情（如"微笑"、"严肃"等）- 这些会根据场景变化
- ❌ 手势（如"比V"、"握拳"等）
- ❌ 身体朝向（如"面向左侧"、"侧身"等）
- ⚠️ 角色卡只包含**静态外观特征**，不包含任何动态内容！

【输出格式 - 必须是有效的JSON】
请输出以下JSON格式，不要有任何其他内容：

```json
{{
    "name": "角色名称",
    "gender": "性别（⚠️如果有图片特征，必须根据图片确定性别！不能根据角色名推断！）",
    "age_appearance": "年龄感（少年/青年/中年/老年）",
    "body": {{
        "height": "身高感（高挑/中等/娇小）",
        "build": "体型（纤细/匀称/健壮/丰满）",
        "skin_tone": "肤色（白皙/小麦色/古铜/苍白）",
        "posture": "体态（挺拔/驼背/优雅/随意）"
    }},
    "face": {{
        "face_shape": "脸型（鹅蛋脸/瓜子脸/圆脸/方脸/长脸）",
        "eye_shape": "眼型（圆眼/杏眼/丹凤眼/下垂眼/上挑眼/狐狸眼）",
        "eye_color": "瞳色（深黑/深棕/浅棕/琥珀/蓝色/绿色/灰色/异色瞳）",
        "eyebrows": "眉毛（浓密/稀疏/细长/粗平/剑眉/柳叶眉）",
        "nose": "鼻子（高挺/小巧/圆润/鹰钩鼻）",
        "lips": "嘴唇（薄唇/丰满/小巧/厚唇）",
        "distinctive_marks": "标志性特征（痣的位置/疤痕/纹身等，无则填'无'）",
        "facial_hair": "面部毛发（无/胡茬/络腮胡/山羊胡，女性填'无'）"
    }},
    "hair": {{
        "length": "发长（超短/短发/中发/长发/超长/及腰）",
        "style": "发型（直发/卷发/波浪/马尾/双马尾/散发/编发/盘发/寸头）",
        "color": "发色（纯黑/深棕/浅棕/金色/银白/红色/蓝色/挑染/渐变）",
        "texture": "发质（柔顺/毛躁/蓬松/油亮）",
        "accessories": "发饰（无/发带/发夹/发簪/头绳/皇冠，具体描述颜色样式）",
        "bangs": "刘海（无/齐刘海/斜刘海/空气刘海/中分/偏分）"
    }},
    "clothing": {{
        "headwear": "头饰（无/帽子类型颜色/头巾/发箍，具体描述）",
        "top": {{
            "type": "上装类型（T恤/衬衫/西装/夹克/风衣/卫衣/毛衣/旗袍上衣）",
            "color": "上装颜色（具体颜色，如：深蓝色、米白色）",
            "material": "上装材质（棉质/丝绸/羊毛/皮革/牛仔布/雪纺）",
            "details": "上装细节（领口样式、袖口样式、纽扣、口袋、图案等，尽可能详细）",
            "sleeves": "袖型（长袖/短袖/无袖/七分袖/泡泡袖/喇叭袖）"
        }},
        "bottom": {{
            "type": "下装类型（牛仔裤/西裤/短裙/长裙/短裤/运动裤/旗袍下摆）",
            "color": "下装颜色（具体颜色）",
            "material": "下装材质（牛仔布/棉质/丝绸/羊毛/皮革）",
            "details": "下装细节（腰型、口袋、褶皱、开叉等，尽可能详细）",
            "length": "下装长度（超短/及膝/中长/及踝/拖地）"
        }},
        "outerwear": "外套（无/具体描述类型颜色材质）",
        "shoes": {{
            "type": "鞋子类型（运动鞋/皮鞋/高跟鞋/靴子/凉鞋/布鞋/帆布鞋）",
            "color": "鞋子颜色（具体颜色）",
            "details": "鞋子细节（鞋带、鞋跟高度、装饰等）"
        }},
        "socks": "袜子（无/短袜/中筒袜/长筒袜/丝袜，具体颜色）"
    }},
    "accessories": {{
        "jewelry": "首饰（无/项链样式/耳环样式/戒指/手镯/脚链，具体描述材质颜色）",
        "glasses": "眼镜（无/黑框/金丝/无框/墨镜，具体描述形状）",
        "watch": "手表（无/具体描述品牌风格颜色）",
        "bag": "包包（无/具体描述类型颜色大小）",
        "belt": "腰带（无/具体描述颜色材质扣头样式）",
        "scarf": "围巾/领带（无/具体描述颜色图案）",
        "gloves": "手套（无/具体描述类型颜色）",
        "other": "其他配饰（胸针/徽章/挂件等）"
    }},
    "pose_and_expression": {{
        "temperament": "整体气质（冷酷/温柔/活泼/忧郁/阳光/神秘）",
        "note": "注意：此字段只描述角色的整体气质感觉，不包含具体的表情、动作或姿态，这些会根据场景动态变化"
    }},
    "full_description": "一段完整的自然语言描述（200字以上），将上述所有特征整合成一个连贯的段落，用于直接插入提示词。必须包含：性别、年龄、身高体型、肤色、脸型眼型瞳色、发型发色发长、上装下装鞋子颜色材质、配饰等所有视觉特征。**绝对不要包含动作、姿态、表情！**",
    "danbooru_tags": "Danbooru格式的标签，用英文逗号分隔，包含所有视觉特征。必须包含：性别标签(1girl/1boy)、年龄标签、发型发色、瞳色、肤色、服装类型颜色、配饰等。标签要详细完整，至少30个标签。**绝对不要包含动作、姿态、表情相关的标签！**"
}}
```

【重要提醒】
- full_description 必须详细完整，至少200字
- danbooru_tags 必须包含所有视觉特征，至少30个标签
- 所有字段都必须填写，不能为空或写"未知"
- **绝对不要包含动作、姿态、表情！角色卡只描述静态外观特征！**

请确保输出的是有效的JSON格式，不要有任何其他文字。"""
        
        api_type = llm_config.get('api_type', 'qwen-9b')
        qwen_service = get_qwen_service_from_api_type(api_type)
        
        qwen_url = SERVICE_PATHS[qwen_service]["url"]
        model_name = llm_config.get('model', '')
        is_minimax = (api_type == 'minimax-m2.7')
        
        if is_minimax:
            model_name = "minimax-m2.7-multimodal"
            print(f"[角色特征卡] 使用MiniMax-M2.7模型")
            response = requests.post(
                f"{MINIMAX_URL}/v1/chat/completions",
                headers={'Content-Type': 'application/json'},
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 2000
                },
                timeout=180
            )
        else:
            if not model_name:
                resp = requests.get(f"{qwen_url}/v1/models", timeout=5)
                if resp.status_code == 200:
                    models = resp.json().get("data", [])
                    if models:
                        model_name = models[0]["id"]
            
            print(f"[角色特征卡] 使用模型: {model_name}")
            
            response = requests.post(
                f"{qwen_url}/v1/chat/completions",
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f"Bearer {llm_config.get('api_key', 'sk-xxx')}"
                },
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "stream": False
                },
                timeout=120
            )
        response.raise_for_status()
        result = response.json()
        content = result['choices'][0]['message']['content'].strip()
        
        import re
        
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        if json_match:
            content = json_match.group(1)
        
        json_obj_match = re.search(r'\{[\s\S]*\}', content)
        if json_obj_match and not content.strip().startswith('{'):
            content = json_obj_match.group(0)
        
        try:
            character_card = json.loads(content)
        except json.JSONDecodeError as json_err:
            print(f"[角色特征卡] JSON解析失败，尝试修复: {json_err}")
            
            content = re.sub(r',\s*}', '}', content)
            content = re.sub(r',\s*]', ']', content)
            content = re.sub(r'"\s*\n\s*"', '"', content)
            
            open_braces = content.count('{') - content.count('}')
            if open_braces > 0:
                content += '}' * open_braces
            open_brackets = content.count('[') - content.count(']')
            if open_brackets > 0:
                content += ']' * open_brackets
            
            try:
                character_card = json.loads(content)
            except:
                danbooru_match = re.search(r'"danbooru_tags"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', content, re.DOTALL)
                full_desc_match = re.search(r'"full_description"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', content, re.DOTALL)
                
                if not danbooru_match:
                    danbooru_match = re.search(r'danbooru_tags["\s:]+([^"}]+)', content)
                if not full_desc_match:
                    full_desc_match = re.search(r'full_description["\s:]+([^"}]+)', content)
                
                character_card = {
                    "name": character_name or "角色",
                    "danbooru_tags": danbooru_match.group(1).strip() if danbooru_match else "",
                    "full_description": full_desc_match.group(1).strip() if full_desc_match else "",
                    "gender": "女性",
                    "age_appearance": "青年"
                }
                print(f"[角色特征卡] JSON修复失败，使用正则提取: danbooru={bool(danbooru_match)}, full_desc={bool(full_desc_match)}")
        
        print(f"[角色特征卡] 生成成功: {character_card.get('name', '未命名角色')}")
        
        return jsonify({
            "status": "ok",
            "character_card": character_card
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"生成角色特征卡失败: {str(e)}"}), 500

def format_character_card_for_prompt(character_card):
    """将角色特征卡转换为自然语言描述"""
    if not character_card:
        return ""
    
    if isinstance(character_card, str):
        return character_card
    
    if "full_description" in character_card:
        return character_card["full_description"]
    
    parts = []
    
    if "name" in character_card:
        parts.append(f"角色：{character_card['name']}")
    
    body = character_card.get("body", {})
    if body:
        body_desc = f"身材{body.get('build', '匀称')}，{body.get('height', '中等身高')}，肤色{body.get('skin_tone', '白皙')}"
        parts.append(body_desc)
    
    face = character_card.get("face", {})
    if face:
        face_desc = f"{face.get('face_shape', '鹅蛋脸')}，{face.get('eye_shape', '杏眼')}，瞳色{face.get('eye_color', '深黑')}"
        if face.get('distinctive_marks') and face['distinctive_marks'] != '无':
            face_desc += f"，{face['distinctive_marks']}"
        parts.append(face_desc)
    
    hair = character_card.get("hair", {})
    if hair:
        hair_desc = f"{hair.get('color', '黑色')}{hair.get('length', '长发')}，{hair.get('style', '直发')}"
        if hair.get('accessories') and hair['accessories'] != '无':
            hair_desc += f"，佩戴{hair['accessories']}"
        parts.append(hair_desc)
    
    clothing = character_card.get("clothing", {})
    if clothing:
        top = clothing.get("top", {})
        if top:
            parts.append(f"身穿{top.get('color', '白色')}{top.get('material', '棉质')}{top.get('type', '衬衫')}")
        bottom = clothing.get("bottom", {})
        if bottom:
            parts.append(f"搭配{bottom.get('color', '蓝色')}{bottom.get('type', '牛仔裤')}")
        shoes = clothing.get("shoes", {})
        if shoes:
            parts.append(f"脚穿{shoes.get('color', '白色')}{shoes.get('type', '运动鞋')}")
    
    accessories = character_card.get("accessories", {})
    if accessories:
        acc_parts = []
        for key, value in accessories.items():
            if value and value != '无':
                acc_parts.append(value)
        if acc_parts:
            parts.append(f"配饰：{', '.join(acc_parts)}")
    
    return "，".join(parts)

@app.route('/api/generate_video_prompt_multimodal', methods=['POST'])
def generate_video_prompt_multimodal():
    """使用多模态模型生成视频提示词（读取图片+故事+旁白）"""
    try:
        llm_config = request.form.get('llm_config')
        if llm_config:
            try:
                llm_config = json.loads(llm_config)
            except:
                llm_config = {}
        else:
            llm_config = {}
        
        if 'image' not in request.files:
            return jsonify({"error": "未上传图片"}), 400
        
        image_file = request.files['image']
        story_content = request.form.get('story_content', '')
        narration = request.form.get('narration', '')
        style = request.form.get('style', '')
        context = request.form.get('context', '')
        visual_prompt = request.form.get('visual_prompt', '')
        
        image_data = image_file.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        image_type = image_file.filename.split('.')[-1].lower()
        if image_type == 'jpg':
            image_type = 'jpeg'
        
        qwen_service = get_qwen_service_from_api_type(llm_config.get('provider', 'qwen-9b'))
        qwen_url = SERVICE_PATHS[qwen_service]["url"]
        is_minimax = (llm_config.get('provider', 'qwen-9b') == 'minimax-m2.7')
        
        def get_available_model():
            if is_minimax:
                return "minimax-m2.7-multimodal"
            try:
                resp = requests.get(f"{qwen_url}/v1/models", timeout=5)
                if resp.status_code == 200:
                    models = resp.json().get("data", [])
                    if models:
                        return models[0].get("id", "default")
            except:
                pass
            return "default"
        
        model_name = get_available_model()
        print(f"[多模态视频提示词] 使用模型: {model_name}")
        
        system_prompt = f"""你是Wan2.2图生视频模型的好莱坞级运镜导演。运镜必须与角色动作绑定，不可分离。

【核心原则：运镜动作绑定】

❌ **错误写法（分离）**：
- "镜头推进。角色向前走" → 运镜和动作分开描述
- "镜头环绕。角色转身" → 运镜和动作分开描述

✅ **正确写法（绑定）**：
- "镜头跟随角色向前推进到桌边" → 运镜服务于角色移动
- "镜头随角色转身同步环绕" → 运镜与动作同步发生
- "镜头从角色A摇到角色B" → 运镜服务于叙事转换

【运镜绑定句式模板】
1. 跟随绑定：镜头跟随角色[动作]推进到[目标]
2. 摇镜绑定：镜头从[主体A]摇到[主体B]
3. 推拉绑定：镜头跟随角色[动作]推进至[细节]
4. 环绕绑定：镜头随角色转身同步环绕

【运镜与情绪匹配】
- 紧张/冲突 → 快速跟随+急停
- 温馨/治愈 → 缓慢跟随+定格
- 震撼/史诗 → 拉远上升揭示全貌
- 悬疑/神秘 → 缓慢环绕+推进

【输出格式】
<运镜动作绑定描述>，<主体身份>，<环境氛围>，<持续时长>

【当前任务】
- 故事全文：{story_content[:2000]}
- 当前旁白：{narration}
- 风格：{style}
- 时代背景：{context}
- 图片描述：{visual_prompt}

请仔细观察图片内容，结合故事全文和当前旁白，生成一段30-50字的中文视频提示词。
运镜必须与角色动作绑定，只输出提示词："""

        if is_minimax:
            response = requests.post(
                f"{MINIMAX_URL}/v1/chat/completions",
                headers={'Content-Type': 'application/json'},
                json={
                    "model": "minimax-m2.7-multimodal",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": system_prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/{image_type};base64,{image_base64}"}}
                            ]
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 500
                },
                timeout=180
            )
        else:
            response = requests.post(
                f"{qwen_url}/v1/chat/completions",
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer sk-xxx'
                },
                json={
                    "model": llm_config.get('model', model_name),
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": system_prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/{image_type};base64,{image_base64}"}}
                            ]
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 500
                },
                timeout=120
            )
        response.raise_for_status()
        result = response.json()
        video_prompt = result['choices'][0]['message']['content'].strip()
        
        print(f"[多模态视频提示词] 生成完成: {video_prompt[:100]}...")
        
        return jsonify({
            "status": "ok",
            "video_prompt": video_prompt
        })
        
    except requests.exceptions.ConnectionError as e:
        print("[多模态视频提示词] 多模态服务未启动，尝试启动...")
        try:
            start_resp = requests.post(f"http://127.0.0.1:5001/service/start/{qwen_service}", timeout=120)
            return jsonify({"error": "服务已启动，请重试"}), 503
        except:
            return jsonify({"error": "多模态服务连接失败"}), 503
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"生成失败: {str(e)}"}), 500

# ==================== 通用图片分析API ====================
@app.route('/api/analyze_image', methods=['POST'])
def analyze_image():
    """使用多模态模型分析图片，返回分析结果"""
    try:
        llm_config = request.form.get('llm_config')
        if llm_config:
            try:
                llm_config = json.loads(llm_config)
            except:
                llm_config = {}
        else:
            llm_config = {}
        
        if 'image' not in request.files:
            return jsonify({"error": "未上传图片"}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({"error": "未选择图片"}), 400
        
        prompt = request.form.get('prompt', '请详细描述这张图片的内容')
        
        image_data = file.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        filename = file.filename.lower()
        if filename.endswith('.png'):
            image_type = 'png'
        elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
            image_type = 'jpeg'
        elif filename.endswith('.webp'):
            image_type = 'webp'
        else:
            image_type = 'jpeg'
        
        print(f"[图片分析] 开始分析图片: {file.filename}")
        
        api_type = llm_config.get('api_type', 'qwen-9b')
        qwen_service = get_qwen_service_from_api_type(api_type)
        
        qwen_url = SERVICE_PATHS[qwen_service]["url"]
        qwen_model = SERVICE_PATHS[qwen_service]["model"]
        is_minimax = (api_type == 'minimax-m2.7')
        
        messages = [
            {
                "role": "system",
                "content": "你是一个专业的图像分析专家，能够详细准确地分析图片内容。"
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{image_type};base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
        
        if is_minimax:
            payload = {
                "model": "minimax-m2.7-multimodal",
                "messages": messages,
                "max_tokens": 2000,
                "temperature": 0.7
            }
            response = requests.post(
                f"{MINIMAX_URL}/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=180
            )
        else:
            payload = {
                "model": qwen_model,
                "messages": messages,
                "max_tokens": 2000,
                "temperature": 0.7
            }
            response = requests.post(
                f"{qwen_url}/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=60
            )
        
        if response.status_code == 200:
            result = response.json()
            analysis = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            print(f"[图片分析] 分析完成，长度: {len(analysis)}")
            return jsonify({
                "status": "ok",
                "analysis": analysis,
                "response": analysis
            })
        else:
            print(f"[图片分析] API错误: {response.status_code}")
            return jsonify({"error": f"API错误: {response.status_code}"}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"分析失败: {str(e)}"}), 500

@app.route('/api/generate_ltx23_prompt_multimodal', methods=['POST'])
def generate_ltx23_prompt_multimodal():
    """使用多模态模型生成LTX2.3专用视频提示词（英文框架+中文台词+自动时长计算）"""
    try:
        llm_config = request.form.get('llm_config')
        if llm_config:
            try:
                llm_config = json.loads(llm_config)
            except:
                llm_config = {}
        else:
            llm_config = {}
        
        if 'image' not in request.files:
            return jsonify({"error": "未上传图片"}), 400
        
        image_file = request.files['image']
        story_content = request.form.get('story_content', '')
        narration = request.form.get('narration', '')
        style = request.form.get('style', '')
        context = request.form.get('context', '')
        visual_prompt = request.form.get('visual_prompt', '')
        mode = request.form.get('mode', 'standard')
        custom_requirement = request.form.get('custom_requirement', '')
        custom_system_prompt = request.form.get('custom_system_prompt', '')
        
        # 接收当前分镜头引用的角色列表（用于角色一致性约束）
        ref_characters_raw = request.form.get('ref_characters', '[]')
        try:
            ref_characters = json.loads(ref_characters_raw) if ref_characters_raw else []
        except:
            ref_characters = []
        
        # 接收说话人列表（用于台词归属精准匹配）
        speakers_raw = request.form.get('speakers', '[]')
        try:
            speakers = json.loads(speakers_raw) if speakers_raw else []
        except:
            speakers = []
        
        # 接收已使用台词列表（用于避免重复）
        used_dialogues_raw = request.form.get('used_dialogues', '[]')
        try:
            used_dialogues = json.loads(used_dialogues_raw) if used_dialogues_raw else []
        except:
            used_dialogues = []
        
        # v9.0: 接收景别和运镜信息
        shot_type = request.form.get('shot_type', '')
        camera_move = request.form.get('camera_move', '')
        
        print(f"[LTX2.3提示词] 当前镜头引用的角色: {ref_characters}")
        print(f"[LTX2.3提示词] 说话人: {speakers}")
        print(f"[LTX2.3提示词] 已使用的台词数量: {len(used_dialogues)}")
        print(f"[LTX2.3提示词] 景别: {shot_type}, 运镜: {camera_move}")
        
        image_data = image_file.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        image_type = image_file.filename.split('.')[-1].lower()
        if image_type == 'jpg':
            image_type = 'jpeg'
        
        # 支持用户选择的所有模型
        provider = llm_config.get('provider', 'qwen-9b')
        valid_providers = ['qwen-27b', 'qwen-27b-q6', 'qwen-35b-a3b-q4', 'qwen-35b-a3b-q2', 'qwen-9b', 'qwen-4b', 'gemma-4-31b', 'gemma-4-26b', 'gemma-4-e4b', 'minimax-m2.7', 'qwen3.6-27b-fp8']
        if provider not in valid_providers:
            provider = 'qwen-9b'
        
        llm_service = provider
        llm_url = SERVICE_PATHS[llm_service]["url"]
        is_minimax = (provider == 'minimax-m2.7')
        
        if is_minimax:
            print(f"[LTX2.3提示词] 使用MiniMax-M2.7远程模型")
        else:
            def check_llm_online():
                try:
                    resp = requests.get(f"{llm_url}/v1/models", timeout=3)
                    return resp.status_code == 200
                except:
                    return False
        
        if not is_minimax:
            if SERVICE_STARTING.get(llm_service):
                print(f"[LTX2.3提示词] 服务 {llm_service} 正在启动中，等待...")
                for i in range(60):
                    time.sleep(2)
                    if check_llm_online():
                        print(f"[LTX2.3提示词] 服务 {llm_service} 已就绪")
                        break
                    if not SERVICE_STARTING.get(llm_service):
                        break
                else:
                    return jsonify({"error": "LLM服务启动超时"}), 503
            
            if not check_llm_online():
                print(f"[LTX2.3提示词] {llm_service} 服务未启动，正在自动启动...")
                try:
                    start_resp = requests.post(f"http://127.0.0.1:5001/service/start/{llm_service}", timeout=120)
                    start_data = start_resp.json()
                    if start_data.get('status') == 'already_running':
                        print(f"[LTX2.3提示词] 服务 {llm_service} 已在运行")
                    for i in range(30):
                        time.sleep(2)
                        if check_llm_online():
                            print(f"[LTX2.3提示词] {llm_service} 服务已启动")
                            break
                        print(f"[LTX2.3提示词] 等待服务启动... ({i+1}/30)")
                    else:
                        if not check_llm_online():
                            return jsonify({"error": f"{llm_service} 服务启动超时"}), 503
                except Exception as e:
                    return jsonify({"error": f"启动 {llm_service} 服务失败: {str(e)}"}), 503
        
        def get_available_model():
            if is_minimax:
                return "minimax-m2.7-multimodal"
            try:
                resp = requests.get(f"{llm_url}/v1/models", timeout=5)
                if resp.status_code == 200:
                    models = resp.json().get("data", [])
                    if models:
                        return models[0].get("id", "default")
            except:
                pass
            return "default"
        
        model_name = get_available_model()
        print(f"[LTX2.3提示词] 使用服务: {llm_service}, 模型: {model_name}, 模式: {mode}")
        
        # 根据模式选择不同的提示词模板
        if custom_system_prompt:
            # 前端自定义提示词模板
            system_prompt = custom_system_prompt
            system_prompt = system_prompt.replace('${story_content}', story_content[:2000])
            system_prompt = system_prompt.replace('${narration}', narration)
            system_prompt = system_prompt.replace('${style}', style)
            system_prompt = system_prompt.replace('${context}', context)
            system_prompt = system_prompt.replace('${visual_prompt}', visual_prompt)
            print(f"[LTX2.3提示词] 使用前端自定义提示词模板")
        elif mode == 'custom' and custom_requirement:
            # 自定义模式：根据用户要求生成
            system_prompt = f"""You are a professional cinematographer and video director specializing in LTX2.3 audio-visual synchronization video generation. Your task is to create cinematic prompts based on USER'S CUSTOM REQUIREMENTS.

【CRITICAL REQUIREMENTS - MUST FOLLOW】
1. The entire prompt MUST be in English EXCEPT for dialogue/lines
2. Dialogue/lines MUST be in Chinese (for Chinese audience) and wrapped in quotation marks
3. EVERY prompt MUST contain dialogue - create natural dialogue based on user's requirement
4. The dialogue should match the character's lip movements naturally
5. Keep the prompt under 200 words
6. Write in a single flowing paragraph, chronological order
7. **DO NOT make characters walk away or leave the scene after speaking** - Characters should remain in the scene after their dialogue unless the story explicitly requires them to exit.

【USER'S CUSTOM REQUIREMENT】
{custom_requirement}

【⚠️ 角色停留约束 - CRITICAL CHARACTER STAY CONSTRAINT】
After a character speaks their dialogue, they MUST remain in the scene. DO NOT describe the character walking away, leaving, exiting, or moving out of frame after speaking.

❌ FORBIDDEN patterns after dialogue:
- "then walks away" / "then leaves" / "exits the scene" / "moves away"
- Any action that removes the speaking character from the scene

✅ CORRECT patterns after dialogue:
- "stands still" / "remains in place" / "pauses thoughtfully"
- "shifts weight slightly" / "nods slowly" / "looks around"
- Small natural gestures while staying in the scene

【LTX2.3 OPTIMAL PROMPT STRUCTURE】
1. MAIN ACTION - What is happening?
2. MOVEMENTS AND GESTURES - Precise body movements and expressions
3. CHARACTER APPEARANCE - Who is in the scene?
4. BACKGROUND AND ENVIRONMENT - Where is this happening?
5. CAMERA ANGLES AND MOVEMENTS - Use professional terms (dolly, pan, tilt, zoom, etc.)
6. LIGHTING AND COLORS - Atmosphere and mood
7. DIALOGUE - Chinese dialogue in quotation marks [对话内容]

【DURATION ESTIMATION】
Chinese speech rate: ~3.5 characters/second
- Calculate: total_dialogue_chars ÷ 3.5 = base_speaking_time
- Add 2 seconds for action buffer
- Range: 6-20 seconds

Please observe the image carefully and generate a LTX2.3 optimized prompt that fulfills the user's custom requirement.

Output format (STRICTLY follow this format):
PROMPT: [Your complete prompt here]
DURATION: [X seconds]"""
        else:
            # 标准模式：根据故事上下文生成
            # 构建角色约束字符串
            character_constraint = ""
            # 构建说话人约束（解决台词错配问题）
            speaker_constraint = ""
            if speakers and len(speakers) > 0:
                speakers_str = ", ".join(speakers)
                speaker_constraint = f"""

## 🔴 RULE #1 - SPEAKER ATTRIBUTION (HIGHEST PRIORITY)
ONLY these characters can speak in this shot: {speakers_str}
- If 1 speaker: ONLY that 1 character speaks
- If 2 speakers: ONLY those 2 characters alternate dialogue
- If 0 speakers: NO dialogue, use narration only
- Speaking characters must be EXACTLY named as above. Example: "{speakers[0]} says [台词内容]" in the prompt."""

            if ref_characters and len(ref_characters) > 0:
                characters_str = "、".join(ref_characters)
                character_constraint = f"""

【🔴🔴🔴 极其重要 - 角色一致性强制约束 - CRITICAL CHARACTER CONSISTENCY 🔴🔴🔴】
当前分镜头图片引用了以下角色（已提供参考图）：{characters_str}

【🔴 违反以下任何一条规则=严重错误=必须重新生成 🔴】

【角色使用铁律】
1. **只能使用上述列表中的角色**作为主要角色进行对话和动作描述
2. **绝对禁止**在提示词中添加列表之外的**主要角色**（如新的主角、重要配角等）
3. **绝对禁止**创造新的角色名字，即使是为了丰富剧情
4. **绝对禁止**让未出现在列表中的角色说话、做动作或参与互动
5. 如果图片中确实有背景路人/群演/次要角色，可以用"passerby"、"crowd"、"bystander"等泛指词汇简单提及，但**不能有具体名字、不能有对话、不能有详细描述**
6. 如果只引用了1个角色，提示词中就只有这1个角色的对话和动作
7. 如果引用了2个角色，提示词中就必须且只能是这2个角色的互动对话
8. **角色数量必须严格匹配**：引用N个角色，提示词中就只能有N个主要角色

【🔴 违规检测规则】
- 提示词中出现的每个有名字的角色必须在上述列表中
- 提示词中出现的每个有台词的角色必须在上述列表中
- 提示词中出现的每个有具体动作描述的角色必须在上述列表中

【违规示例】❌（以下情况绝对禁止）：
- 引用了["张三"]，但提示词中出现"李四走了过来"
- 引用了["张三","王五"]，但提示词中出现了第三个角色"赵六"
- 引用了["武松"]，但提示词中出现"一个店家说：'...'"
- 引用了["武松"]，但提示词中出现"a waiter walks in and says..."

【正确示例】✅：
- 引用了["武松"]，提示词中只有武松的动作和台词
- 引用了["武松","店家"]，提示词中只有武松和店家的互动
- 引用了["武松"]，背景有路人但只用"passersby in the background"，无名字无对话"""
                character_constraint += speaker_constraint
            else:
                # 没有ref_characters时，只使用speaker约束（如果有的话）
                character_constraint = speaker_constraint
                if not character_constraint.strip():
                    character_constraint = """
                    
## 🔴 RULE #1 - CHARACTER AWARENESS
Observe the image carefully. Identify characters in the image and use only those characters in the prompt. Do not add characters not visible in the image."""
            
            system_prompt = f"""You are a professional cinematographer and video director specializing in LTX2.3 audio-visual synchronization video generation. Your task is to create cinematic prompts that will generate videos with synchronized audio (speech/dialogue).

{character_constraint}

## 🔴 RULE #2 - STORY CONTINUITY (CRITICAL)
Previous story context: {context}
Current narration: {narration}
You MUST continue the story from exactly where the previous shot left off. Do NOT repeat events. Maintain character behavior and emotional progression.

## 🔴 RULE #3 - CHARACTER STAY CONSTRAINT
After ANY character speaks, they MUST remain in the scene. DO NOT describe: "walks away", "leaves", "exits", "moves away", "转身离去", "走开了". Instead describe natural post-dialogue behaviors: "stands still", "remains", "pauses", "nods", "shifts weight", "looks around".

## 🔴 RULE #4 - DIALOGUE DEDUPLICATION

## 🔴 RULE #5 - FORMAT
- Description in English. Dialogue in Chinese wrapped in brackets [对话内容].
- EVERY prompt MUST contain dialogue matching the speaking character's lip movements.
- Keep under 200 words. Single flowing paragraph, chronological order."""

            # 构建台词去重约束
            dialogue_dedup_constraint = ""
            if used_dialogues and len(used_dialogues) > 0:
                # 显示最近10条已用台词（避免提示词过长）
                recent_dialogues = used_dialogues[-10:] if len(used_dialogues) > 10 else used_dialogues
                dialogues_str = "\n".join([f"  - \"{d}\"" for d in recent_dialogues])
                dialogue_dedup_constraint = f"""
以下台词已经在之前的镜头中使用过，**绝对禁止**再次使用相同或高度相似的台词：

【已使用台词列表（共{len(used_dialogues)}句）】
{dialogues_str}

【严格遵守以下规则】：
1. **绝对禁止**使用上述列表中的任何一句台词
2. **绝对禁止**使用与上述台词**意思相同或高度相似**的表述
3. 如果发现生成的台词与已使用台词重复，必须重新创作全新的台词
4. 每个镜头的台词必须是**独一无二**的，不能与其他镜头重复
5. 即使是同一个角色说话，不同镜头也必须有不同的台词内容"""
            else:
                dialogue_dedup_constraint = """
当前是第一个镜头或尚未使用过台词。请创作独特的台词内容。后续镜头将基于此进行去重检查。"""

            system_prompt += f"""{dialogue_dedup_constraint}

Follow this EXACT structure for best results:

1. MAIN ACTION (Start with this - single sentence)
   - What is the primary action happening right now?
   - Who is doing what?

2. MOVEMENTS AND GESTURES (Specific details)
   - Precise body movements: "turns head slowly", "extends arm forward", "leans back"
   - Hand gestures: "points to the distance", "clenches fist", "waves hand"
   - Facial expressions: "eyes widen in surprise", "lips tremble", "brows furrow"

3. CHARACTER APPEARANCE (Precise description)
   - Age, gender, distinctive features
   - Clothing and accessories
   - Current posture and position

4. BACKGROUND AND ENVIRONMENT
   - Setting details
   - Weather/time of day
   - Props and objects in scene

5. CAMERA ANGLES AND MOVEMENTS (CRITICAL - Use professional terms)
   
   【Camera Angles】:
   - Wide shot / Full shot / Medium shot / Close-up / Extreme close-up
   - Low angle / High angle / Eye level / Dutch angle
   - Over-the-shoulder / POV / Two-shot
   
   【Camera Movements】:
   - Static: "tripod fixed", "locked-off shot", "static frame"
   - Pan: "slow pan left", "quick pan right to reveal", "pan across the scene"
   - Tilt: "tilt up to show", "tilt down following", "slow vertical tilt"
   - Dolly: "dolly forward slowly", "dolly backward revealing", "push in 2 meters"
   - Zoom: "slow zoom in on face", "zoom out to wide shot", "crash zoom"
   - Tracking: "tracking shot following", "lateral tracking", "dolly track parallel"
   - Crane: "crane up over", "crane down to", "sweeping crane movement"
   - Handheld: "subtle handheld movement", "documentary style shake"
   - Orbit: "orbit around subject", "360 degree rotation"

6. LIGHTING AND COLORS
   - Light source and direction
   - Color temperature
   - Shadows and highlights

7. DIALOGUE (MANDATORY - Multi-character Interaction)
   
   【Single Character】:
   - "Character says [对话内容] with [emotion/tone]"
   
   【Multiple Characters - MUST CREATE DIALOGUE INTERACTION】:
   - "Character A turns to Character B and asks [对话内容A]"
   - "Character B responds with a nod, saying [对话内容B]"
   - "Character A continues [对话内容A2] while [action]"
   - Use alternating dialogue to create natural conversation flow

【EXAMPLE PROMPTS】

Example 1 (Single Character):
"A young woman in a white dress stands by the window, her fingers gently touching the glass. She slowly turns her head, eyes glistening with tears, and whispers [我等你回来...] The camera slowly pushes in 1.5 meters to capture her emotional expression. Soft morning light from the window, warm color tones, shallow depth of field, cinematic style, 4K quality, natural motion blur."

Example 2 (Two Characters - Dialogue Interaction):
"Two men in business suits stand facing each other in a modern office. The older man, with silver hair and stern expression, steps forward and asks [你真的决定了吗？] The younger man meets his gaze, takes a deep breath, and responds firmly [是的，我已经想清楚了。] The camera slowly orbits around them, capturing both their determined faces. Dramatic side lighting, cool blue tones, professional cinematography, sharp focus."

Example 3 (Three Characters - Group Interaction):
"Three friends gather around a wooden table in a cozy café. The woman with red hair excitedly points at a map and says [我们明天就去这里！] The man in glasses leans in, examining the map, and asks [远吗？] The third friend, a tall man with a beard, laughs and adds [不管多远，我们一起去！] The camera pulls back slowly to capture their joyful expressions. Warm ambient lighting, golden hour glow through windows, intimate framing, documentary style."

Example 4 (Action Scene with Dialogue):
"A warrior in ancient armor draws his sword, muscles tense, eyes locked on an unseen enemy. He takes a fighting stance and shouts [来吧！] The camera quickly zooms in on his determined face, then pans right to reveal his opponent approaching. Dramatic shadows, high contrast lighting, epic cinematic style, slow motion elements, film grain."

【DURATION ESTIMATION GUIDE - CRITICAL】
Chinese speech rate: ~3.5 characters/second (normal speed)
- Calculate: total_dialogue_chars ÷ 3.5 = base_speaking_time
- Add 2 seconds for action buffer
- Add 0.5 seconds per dialogue turn for interaction pauses

Examples:
- 10 Chinese characters: 10÷3.5 + 2 = ~5 seconds (minimum)
- 20 Chinese characters: 20÷3.5 + 2 = ~8 seconds
- 30 Chinese characters + 2 turns: 30÷3.5 + 2 + 1 = ~12 seconds
- 40 Chinese characters + 3 turns: 40÷3.5 + 2 + 1.5 = ~15 seconds

IMPORTANT: Always ensure duration is ENOUGH for all dialogue to be spoken naturally.
When in doubt, estimate LONGER rather than shorter. Range: 6-20 seconds.

【CURRENT TASK】
- Story Content: {story_content[:2000]}
- Current Narration/Dialogue: {narration}
- Style: {style}
- Historical Context: {context}
- Image Description: {visual_prompt}
{f'''【🎬 分镜头脚本指导 - MUST FOLLOW】
The storyboard has specified the following shot parameters for this frame. You MUST strictly follow these:
- Shot Type (景别): {shot_type} → You MUST use this shot type in your camera description
- Camera Movement (运镜): {camera_move} → You MUST use this camera movement technique

Shot Type Mapping:
- 远景 = Wide shot / Long shot
- 全景 = Full shot
- 中景 = Medium shot
- 近景 = Medium close-up

Camera Movement Mapping:
- 固定 = Static / Fixed / Tripod shot
- 推 = Dolly in / Push in / Zoom in
- 拉 = Dolly out / Pull back / Zoom out
- 摇 = Pan (left/right)
- 移 = Tracking shot / Lateral dolly
- 升 = Crane up / Tilt up
- 降 = Crane down / Tilt down
- 跟 = Tracking shot following subject''' if shot_type or camera_move else ''}

【⚠️ 故事连贯性约束 - CRITICAL STORY CONTINUITY】
The Historical Context contains summaries of previous shots. You MUST:
1. Continue the story naturally from where the previous shot left off
2. Do NOT repeat actions or dialogue that already happened in previous shots
3. Ensure this shot logically follows the previous events
4. Maintain consistent character behavior and emotional progression
5. If previous shots show tension building, this shot should escalate or resolve it
6. If previous shots show characters in a conversation, continue or conclude that conversation naturally

Please carefully observe the image content, identify ALL characters present, and generate a LTX2.3 optimized prompt.

REMEMBER: 
- Main text in English
- Dialogue in Chinese with brackets [对话内容]
- MUST include dialogue - if multiple characters, create natural conversation
- Use professional camera movement terminology
- Estimate appropriate duration (6-20 seconds, ensure enough for dialogue)

Output format (STRICTLY follow this format):
PROMPT: [Your complete prompt here]
DURATION: [X seconds]"""

        # 构建消息：使用system角色放置指令，user角色放置图片和简短提示
        # 这样可以避免模型输出思考过程
        system_message = {
            "role": "system",
            "content": system_prompt
        }
        user_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": "请根据以上要求和这张图片，生成LTX2.3视频提示词。"},
                {"type": "image_url", "image_url": {"url": f"data:image/{image_type};base64,{image_base64}"}}
            ]
        }
        
        if is_minimax:
            response = requests.post(
                f"{MINIMAX_URL}/v1/chat/completions",
                headers={'Content-Type': 'application/json'},
                json={
                    "model": "minimax-m2.7-multimodal",
                    "messages": [system_message, user_message],
                    "temperature": 0.7,
                    "max_tokens": 800
                },
                timeout=180
            )
        else:
            # 构建请求参数
            request_body = {
                "model": llm_config.get('model', model_name),
                "messages": [system_message, user_message],
                "temperature": 0.7,
                "max_tokens": 800,
                # 关闭思考模式（Qwen模型默认开启思考，会输出<think>内容）
                "chat_template_kwargs": {"enable_thinking": False}
            }
            response = requests.post(
                f"{llm_url}/v1/chat/completions",
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer sk-xxx'
                },
                json=request_body,
                timeout=120
            )
        response.raise_for_status()
        result = response.json()
        content = result['choices'][0]['message']['content'].strip()
        
        # 后处理：清除任何可能的思考内容
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        content = re.sub(r'思考[：:].*?(\n|$)', '', content)
        content = content.strip()
        
        prompt_match = re.search(r'PROMPT:\s*(.+?)(?=DURATION:|$)', content, re.DOTALL)
        duration_match = re.search(r'DURATION:\s*(\d+)', content)
        
        video_prompt = prompt_match.group(1).strip() if prompt_match else content
        llm_duration = int(duration_match.group(1)) if duration_match else 8
        
        dialogues = re.findall(r'"([^"]+)"', video_prompt)
        total_dialogue_chars = sum(len(d) for d in dialogues)
        dialogue_count = len(dialogues)
        
        CHARS_PER_SECOND = 3.5
        dialogue_duration = total_dialogue_chars / CHARS_PER_SECOND if total_dialogue_chars > 0 else 0
        
        action_buffer = 2.0
        interaction_buffer = dialogue_count * 0.5 if dialogue_count > 1 else 0
        
        calculated_duration = dialogue_duration + action_buffer + interaction_buffer
        
        duration = max(llm_duration, int(calculated_duration) + 1)
        # 时长范围10~15秒，根据对话内容灵活设定
        duration = max(10, min(15, duration))
        
        frame_count = 24 * duration + 1
        
        print(f"[LTX2.3提示词] 生成完成:")
        print(f"  - 台词字数: {total_dialogue_chars}字, 台词数: {dialogue_count}")
        print(f"  - LLM建议时长: {llm_duration}秒, 计算时长: {calculated_duration:.1f}秒")
        print(f"  - 最终时长: {duration}秒")
        print(f"  - 帧数: {frame_count}")
        print(f"  - 提示词: {video_prompt[:100]}...")
        
        return jsonify({
            "status": "ok",
            "video_prompt": video_prompt,
            "duration": duration,
            "frame_count": frame_count
        })
        
    except requests.exceptions.ConnectionError as e:
        print(f"[LTX2.3提示词] 多模态服务 {llm_service} 未启动，尝试启动...")
        try:
            start_resp = requests.post(f"http://127.0.0.1:5001/service/start/{llm_service}", timeout=120)
            return jsonify({"error": "服务已启动，请重试"}), 503
        except:
            return jsonify({"error": "多模态服务连接失败"}), 503
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"生成失败: {str(e)}"}), 500

@app.route('/api/regenerate_ltx23_prompt', methods=['POST'])
def regenerate_ltx23_prompt():
    """根据用户修改意见重新生成LTX2.3视频提示词"""
    try:
        llm_config = request.form.get('llm_config')
        if llm_config:
            try:
                llm_config = json.loads(llm_config)
            except:
                llm_config = {}
        else:
            llm_config = {}
        
        if 'image' not in request.files:
            return jsonify({"error": "未上传图片"}), 400
        
        image_file = request.files['image']
        current_prompt = request.form.get('current_prompt', '')
        feedback = request.form.get('feedback', '')
        story_content = request.form.get('story_content', '')
        narration = request.form.get('narration', '')
        style = request.form.get('style', '')
        context = request.form.get('context', '')
        
        # 接收当前分镜头引用的角色列表（用于角色一致性约束）
        ref_characters_raw = request.form.get('ref_characters', '[]')
        try:
            ref_characters = json.loads(ref_characters_raw) if ref_characters_raw else []
        except:
            ref_characters = []
        
        # 接收说话人列表（用于台词归属精准匹配）
        speakers_raw = request.form.get('speakers', '[]')
        try:
            speakers = json.loads(speakers_raw) if speakers_raw else []
        except:
            speakers = []
        
        # 接收已使用台词列表（用于避免重复）
        used_dialogues_raw = request.form.get('used_dialogues', '[]')
        try:
            used_dialogues = json.loads(used_dialogues_raw) if used_dialogues_raw else []
        except:
            used_dialogues = []
        
        # v9.0: 接收景别和运镜信息
        shot_type = request.form.get('shot_type', '')
        camera_move = request.form.get('camera_move', '')
        
        print(f"[LTX2.3重新生成] 当前镜头引用的角色: {ref_characters}")
        print(f"[LTX2.3重新生成] 说话人: {speakers}")
        print(f"[LTX2.3重新生成] 已使用的台词数量: {len(used_dialogues)}")
        print(f"[LTX2.3重新生成] 景别: {shot_type}, 运镜: {camera_move}")
        
        image_data = image_file.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        image_type = image_file.filename.split('.')[-1].lower()
        if image_type == 'jpg':
            image_type = 'jpeg'
        
        # 支持用户选择的所有模型
        provider = llm_config.get('provider', 'qwen-9b')
        valid_providers = ['qwen-27b', 'qwen-27b-q6', 'qwen-35b-a3b-q4', 'qwen-35b-a3b-q2', 'qwen-9b', 'qwen-4b', 'gemma-4-31b', 'gemma-4-26b', 'gemma-4-e4b', 'minimax-m2.7', 'qwen3.6-27b-fp8']
        if provider not in valid_providers:
            provider = 'qwen-9b'

        
        llm_service = provider
        llm_url = SERVICE_PATHS[llm_service]["url"]
        is_minimax = (provider == 'minimax-m2.7')
        
        if is_minimax:
            print(f"[LTX2.3重新生成] 使用MiniMax-M2.7远程模型")
        else:
            def check_llm_online():
                try:
                    resp = requests.get(f"{llm_url}/v1/models", timeout=3)
                    return resp.status_code == 200
                except:
                    return False
        
        if not is_minimax:
            if SERVICE_STARTING.get(llm_service):
                print(f"[LTX2.3重新生成] 服务 {llm_service} 正在启动中，等待...")
                for i in range(60):
                    time.sleep(2)
                    if check_llm_online():
                        print(f"[LTX2.3重新生成] 服务 {llm_service} 已就绪")
                        break
                    if not SERVICE_STARTING.get(llm_service):
                        break
                else:
                    return jsonify({"error": "LLM服务启动超时"}), 503
            
            if not check_llm_online():
                print(f"[LTX2.3重新生成] {llm_service} 服务未启动，正在自动启动...")
                try:
                    start_resp = requests.post(f"http://127.0.0.1:5001/service/start/{llm_service}", timeout=120)
                    start_data = start_resp.json()
                    if start_data.get('status') == 'already_running':
                        print(f"[LTX2.3重新生成] 服务 {llm_service} 已在运行")
                    for i in range(30):
                        time.sleep(2)
                        if check_llm_online():
                            print(f"[LTX2.3重新生成] {llm_service} 服务已启动")
                            break
                        print(f"[LTX2.3重新生成] 等待服务启动... ({i+1}/30)")
                    else:
                        if not check_llm_online():
                            return jsonify({"error": f"{llm_service} 服务启动超时"}), 503
                except Exception as e:
                    return jsonify({"error": f"启动 {llm_service} 服务失败: {str(e)}"}), 503
        
        # 构建角色约束字符串
        character_constraint = ""
        if ref_characters and len(ref_characters) > 0:
            characters_str = "、".join(ref_characters)
            character_constraint = f"""

【⚠️ 角色一致性强制约束 - CRITICAL CHARACTER CONSISTENCY】
当前分镜头图片引用了以下角色（已提供参考图）：{characters_str}

【严格遵守以下规则】：
1. **只能使用上述列表中的角色**作为主要角色进行对话和动作描述
2. **绝对禁止**在提示词中添加列表之外的**主要角色**
3. 角色数量必须严格匹配：引用N个角色，提示词中就只能有N个主要角色"""
        else:
            character_constraint = ""

        # 构建说话人约束（解决台词错配问题）
        speaker_constraint = ""
        if speakers and len(speakers) > 0:
            speakers_str = "、".join(speakers)
            speaker_constraint = f"""

【🔴🔴🔴 极其重要 - 台词归属精准约束 - CRITICAL SPEAKER ATTRIBUTION 🔴🔴🔴】
当前镜头的台词必须由以下角色说出：{speakers_str}

【严格遵守以下规则】：
1. **只有上述角色才能说话**，其他角色不能有台词
2. 如果说话人列表只有1个角色，那么提示词中的对话只能由这1个角色说出
3. **绝对禁止**让非说话人角色说出台词
4. 在描述对话时，必须明确写出说话人的名字"""

        character_constraint += speaker_constraint

        system_prompt = f"""You are a professional video director specializing in LTX2.3 audio-visual synchronization video generation. Your task is to MODIFY an existing video prompt based on user feedback while STRICTLY maintaining LTX2.3 format standards.

【CURRENT PROMPT】
{current_prompt}

【USER FEEDBACK】
{feedback}
{character_constraint}"""

        # 构建台词去重约束（重新生成时也需要）
        dialogue_dedup_constraint = ""
        if used_dialogues and len(used_dialogues) > 0:
            recent_dialogues = used_dialogues[-10:] if len(used_dialogues) > 10 else used_dialogues
            dialogues_str = "\n".join([f"  - \"{d}\"" for d in recent_dialogues])
            dialogue_dedup_constraint = f"""

【⚠️ 台词去重强制约束 - CRITICAL DIALOGUE DEDUPLICATION】
以下台词已经在之前的镜头中使用过，**绝对禁止**再次使用相同或高度相似的台词：

【已使用台词列表（共{len(used_dialogues)}句）】
{dialogues_str}

【严格遵守以下规则】：
1. **绝对禁止**使用上述列表中的任何一句台词
2. **绝对禁止**使用与上述台词**意思相同或高度相似**的表述
3. 修改后的新台词必须是全新的、独特的"""
        else:
            dialogue_dedup_constraint = ""

        system_prompt += f"""{dialogue_dedup_constraint}

【⚠️ CRITICAL MODIFICATION RULES - MUST FOLLOW EXACTLY】

1. 【格式一致性】修改后的提示词必须严格符合LTX2.3标准格式：
   - 整体结构：主动作 → 动作细节 → 角色外观 → 背景 → 镜头运动 → 光影 → 台词
   - 英文描述 + 中文台词（引号包裹）
   - 单段流畅叙述，时间顺序

2. 【角色一致性】只能使用当前镜头引用的角色，不能添加新的主要角色

3. 【台词要求】
   - 必须包含至少一句中文台词（引号包裹）
   - 台词需与角色口型自然匹配
   - 多角色时创建互动对话

4. 【角色停留约束】角色说完台词后必须留在场景中，不能走掉或离开
   - ❌ 禁止: "then walks away" / "then leaves" / "exits the scene"
   - ✅ 正确: "stands still" / "remains in place" / "pauses thoughtfully"

5. 【专业术语】使用标准电影术语：
   - 镜头角度：wide shot, close-up, low angle, over-the-shoulder等
   - 镜头运动：dolly, pan, tilt, zoom, tracking, crane, orbit等
   - 光影：dramatic lighting, soft light, warm/cool tones等

5. 【时长估算】基于台词字数计算（中文~3.5字/秒）

【LTX2.3 OPTIMAL PROMPT STRUCTURE - REFERENCE】

1. MAIN ACTION (Start with this)
2. MOVEMENTS AND GESTURES (Precise body movements)
3. CHARACTER APPEARANCE (Who is in the scene?)
4. BACKGROUND AND ENVIRONMENT (Where?)
5. CAMERA ANGLES AND MOVEMENTS (Professional terms)
6. LIGHTING AND COLORS (Atmosphere)
7. DIALOGUE (Chinese in quotation marks)

【CONTEXT INFORMATION】
Story: {story_content}
Narration: {narration}
Style: {style}
Historical Context: {context}

【⚠️ 故事连贯性约束 - CRITICAL STORY CONTINUITY】
The Historical Context contains summaries of previous shots. You MUST:
1. Continue the story naturally from where the previous shot left off
2. Do NOT repeat actions or dialogue that already happened in previous shots
3. Ensure this shot logically follows the previous events
4. Maintain consistent character behavior and emotional progression

【OUTPUT FORMAT - STRICTLY FOLLOW THIS FORMAT】
PROMPT: [Your modified LTX2.3 compliant prompt here]
DURATION: [X seconds (based on dialogue length)]
"""
        
        model_name = SERVICE_PATHS[llm_service].get("model", "qwen")
        if is_minimax:
            model_name = "minimax-m2.7-multimodal"
        print(f"[LTX2.3重新生成] 使用服务: {llm_service}, 模型: {model_name}")
        
        try:
            # 构建消息：使用system角色放置指令，user角色放置图片和简短提示
            regenerate_system_message = {
                "role": "system",
                "content": system_prompt
            }
            regenerate_user_message = {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请根据这张图片和修改意见，重新生成LTX2.3视频提示词。"},
                    {"type": "image_url", "image_url": {"url": f"data:image/{image_type};base64,{image_base64}"}}
                ]
            }
            
            if is_minimax:
                response = requests.post(
                    f"{MINIMAX_URL}/v1/chat/completions",
                    headers={'Content-Type': 'application/json'},
                    json={
                        "model": model_name,
                        "messages": [regenerate_system_message, regenerate_user_message],
                        "temperature": 0.7,
                        "max_tokens": 800
                    },
                    timeout=180
                )
            else:
                response = requests.post(
                    f"{llm_url}/v1/chat/completions",
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer sk-xxx'
                    },
                    json={
                        "model": llm_config.get('model', model_name),
                        "messages": [regenerate_system_message, regenerate_user_message],
                        "temperature": 0.7,
                        "max_tokens": 800,
                        "chat_template_kwargs": {"enable_thinking": False}
                    },
                    timeout=120
                )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # 清除任何可能的思考内容
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                content = re.sub(r'思考[：:].*?(\n|$)', '', content)
                content = content.strip()
                
                video_prompt = content
                if 'PROMPT:' in content:
                    prompt_match = re.search(r'PROMPT:\s*(.+?)(?=DURATION:|$)', content, re.DOTALL)
                    if prompt_match:
                        video_prompt = prompt_match.group(1).strip()
                
                duration = 5
                if 'DURATION:' in content:
                    duration_match = re.search(r'DURATION:\s*(\d+)', content)
                    if duration_match:
                        duration = int(duration_match.group(1))
                
                duration = max(3, min(15, duration))
                frame_count = duration * 24 + 1
                
                return jsonify({
                    "status": "ok",
                    "video_prompt": video_prompt,
                    "duration": duration,
                    "frame_count": frame_count
                })
            else:
                return jsonify({"error": f"API错误: {response.status_code}"}), 500
                
        except requests.exceptions.ConnectionError as e:
            print(f"[LTX2.3重新生成] 多模态服务 {llm_service} 未启动，尝试启动...")
            try:
                requests.post(f"http://127.0.0.1:5001/service/start/{llm_service}", timeout=5)
                return jsonify({"error": "服务已启动，请重试"}), 503
            except:
                return jsonify({"error": "多模态服务连接失败"}), 503
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"生成失败: {str(e)}"}), 500

@app.route('/api/translate', methods=['POST'])
def translate_text():
    try:
        data = request.get_json(force=True)
        text = data.get('text', '')
        source_lang = data.get('source_lang', 'en')
        target_lang = data.get('target_lang', 'zh')
        provider = data.get('provider', '')
        
        if not text:
            return jsonify({"error": "缺少要翻译的文本"}), 400
        
        llm_service, llm_url, model_name = _get_llm_service(provider if provider else None)
        if not llm_url:
            return jsonify({"error": "LLM服务未启动，无法翻译"}), 503
        
        if source_lang == 'en' and target_lang == 'zh':
            system_prompt = """你是一个专业的英中翻译专家。请将以下英文文本翻译成中文。

要求：
1. 准确翻译，保留原文含义
2. 如果包含专业摄影/电影术语，请用中文专业术语翻译
3. 如果包含中文对话（在引号中），保留原样
4. 只输出翻译结果，不要添加任何解释或额外内容"""
        else:
            system_prompt = f"""你是一个专业的翻译专家。请将以下文本从{source_lang}翻译成{target_lang}。只输出翻译结果，不要添加任何解释。"""
        
        response = requests.post(
            f"{llm_url}/v1/chat/completions",
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer sk-xxx'
            },
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                "temperature": 0.3,
                "max_tokens": 1000
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            return jsonify({"status": "ok", "translation": content.strip()})
        else:
            return jsonify({"error": f"翻译API错误: {response.status_code}"}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"翻译失败: {str(e)}"}), 500

def _get_llm_service(provider=None):
    if provider and provider in SERVICE_PATHS:
        svc_info = SERVICE_PATHS[provider]
        is_remote = svc_info.get("is_remote", False)
        if is_remote:
            print(f"[LLM] 使用远程服务: {provider} -> {svc_info['url']}")
            return provider, svc_info['url'], svc_info.get("model", "default")
        try:
            resp = requests.get(f"{svc_info['url']}/v1/models", timeout=3)
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                model_name = models[0].get("id", svc_info.get("model", "default")) if models else svc_info.get("model", "default")
                print(f"[LLM] 使用指定服务(已运行): {provider} -> {model_name}")
                return provider, svc_info['url'], model_name
        except:
            pass
        bat_path = svc_info.get("bat")
        if bat_path and bat_path.exists():
            print(f"[LLM] 指定服务 {provider} 未运行，正在启动...")
            try:
                work_dir = bat_path.parent
                proc = subprocess.Popen(
                    ["cmd", "/c", str(bat_path)],
                    cwd=str(work_dir),
                    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
                )
                SERVICE_PROCESSES[provider] = proc.pid
                max_wait = 120
                waited = 0
                while waited < max_wait:
                    time.sleep(3)
                    waited += 3
                    try:
                        resp = requests.get(f"{svc_info['url']}/v1/models", timeout=5)
                        if resp.status_code == 200:
                            models = resp.json().get("data", [])
                            model_name = models[0].get("id", svc_info.get("model", "default")) if models else svc_info.get("model", "default")
                            print(f"[LLM] {provider} 已就绪，模型: {model_name}")
                            return provider, svc_info['url'], model_name
                    except:
                        pass
                print(f"[LLM] {provider} 启动超时({max_wait}秒)")
            except Exception as e:
                print(f"[LLM] 启动 {provider} 失败: {e}")
        else:
            print(f"[LLM] 指定服务 {provider} 无启动脚本且未运行")
    
    for svc_name, svc_info in SERVICE_PATHS.items():
        if svc_name in ('comfyui', 'cosyvoice', 'doubao'):
            continue
        try:
            resp = requests.get(f"{svc_info['url']}/v1/models", timeout=3)
            if resp.status_code == 200:
                llm_service = svc_name
                llm_url = svc_info['url']
                try:
                    models = resp.json().get("data", [])
                    if models:
                        return llm_service, llm_url, models[0].get("id", "default")
                except:
                    pass
                return llm_service, llm_url, SERVICE_PATHS.get(llm_service, {}).get("model", "default")
        except:
            continue
    
    preferred = ['qwen-4b', 'qwen-9b', 'qwen-0.8b', 'qwen-27b', 'gemma-4-e4b', 'gemma-4-26b', 'gemma-4-31b']
    for svc_name in preferred:
        if svc_name not in SERVICE_PATHS:
            continue
        svc_info = SERVICE_PATHS[svc_name]
        bat_path = svc_info.get("bat")
        if bat_path and bat_path.exists():
            print(f"[LLM] 未检测到在线LLM服务，自动启动 {svc_name}...")
            try:
                work_dir = bat_path.parent
                proc = subprocess.Popen(
                    ["cmd", "/c", str(bat_path)],
                    cwd=str(work_dir),
                    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
                )
                SERVICE_PROCESSES[svc_name] = proc.pid
                print(f"[LLM] {svc_name} 进程已启动 PID: {proc.pid}，等待服务就绪...")
                
                max_wait = 120
                waited = 0
                while waited < max_wait:
                    time.sleep(3)
                    waited += 3
                    try:
                        resp = requests.get(f"{svc_info['url']}/v1/models", timeout=5)
                        if resp.status_code == 200:
                            models = resp.json().get("data", [])
                            model_name = models[0].get("id", svc_info.get("model", "default")) if models else svc_info.get("model", "default")
                            print(f"[LLM] {svc_name} 已就绪，模型: {model_name}")
                            return svc_name, svc_info['url'], model_name
                    except:
                        pass
                
                print(f"[LLM] {svc_name} 启动超时({max_wait}秒)")
            except Exception as e:
                print(f"[LLM] 启动 {svc_name} 失败: {e}")
    
    return None, None, None

@app.route('/api/refine_story_combination', methods=['POST'])
def refine_story_combination():
    try:
        data = request.get_json(force=True)
        dimensions = data.get('dimensions', {})
        custom_theme = data.get('custom_theme', '').strip()
        provider = data.get('provider', '')
        
        llm_service, llm_url, model_name = _get_llm_service(provider if provider else None)
        if not llm_url:
            return jsonify({"error": "LLM服务未启动"}), 503
        
        era = dimensions.get('era', '未知')
        theme = dimensions.get('theme', '未知')
        protagonist = dimensions.get('protagonist', '未知')
        conflict = dimensions.get('conflict', '未知')
        setting = dimensions.get('setting', '未知')
        tone = dimensions.get('tone', '未知')
        
        system_prompt = """你是一个专业的小说策划大师。用户会给你6个随机组合的故事维度，你需要将它们加工成一个连贯的、有逻辑的故事设定。

【重要规则】
1. 必须是写实风格，不要科幻、赛博朋克、奇幻等超现实元素
2. 时代背景只能是古代或现代，不要未来时代
3. 故事必须合情合理，人物动机明确
4. 如果维度之间存在矛盾，以合理的逻辑化解矛盾
5. 输出格式如下：

故事标题：（一个吸引人的标题）
核心设定：（1-2句话概括故事核心）
主角简介：（主角的姓名、身份、性格特点、核心动机）
主要对手：（对手的姓名、身份、与主角的矛盾根源）
故事起因：（引发整个故事的导火索事件）
发展线索：（3-5条主要情节线索）
高潮预判：（故事最激烈的冲突点预判）
结局走向：（故事的预期结局方向）

只输出上述内容，不要添加其他解释。"""

        user_prompt = f"""请将以下6个维度加工成一个连贯的故事设定：

时代背景：{era}
故事主题：{theme}
主角身份：{protagonist}
核心冲突：{conflict}
故事场景：{setting}
情感基调：{tone}"""

        if custom_theme:
            user_prompt += f"""

【用户自定义主题】
{custom_theme}
请优先围绕用户自定义主题来设计故事，上述维度作为辅助参考。"""

        response = requests.post(
            f"{llm_url}/v1/chat/completions",
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer sk-xxx'},
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.8,
                "max_tokens": 1500
            },
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            return jsonify({"status": "ok", "refined": content.strip()})
        else:
            return jsonify({"error": f"API错误: {response.status_code}"}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"加工失败: {str(e)}"}), 500

@app.route('/api/search_theme', methods=['POST'])
def search_theme():
    try:
        data = request.get_json(force=True)
        keyword = data.get('keyword', '').strip()
        if not keyword:
            return jsonify({"error": "关键词不能为空"}), 400
        
        inspirations = []
        
        try:
            import urllib.request
            import urllib.parse
            import re
            
            bing_url = f"https://www.bing.com/search?q={urllib.parse.quote(keyword + ' 故事 灵感 创意')}"
            req = urllib.request.Request(bing_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                snippets = re.findall(r'<p[^>]*>(.*?)</p>', html)
                seen = set()
                for s in snippets:
                    clean = re.sub(r'<[^>]+>', '', s).strip()
                    if len(clean) > 20 and len(clean) < 200 and clean not in seen:
                        seen.add(clean)
                        inspirations.append(clean)
                        if len(inspirations) >= 5:
                            break
        except Exception as e:
            print(f"[搜索] Bing搜索失败: {e}")
        
        try:
            import urllib.request
            import urllib.parse
            import re
            
            baidu_url = f"https://www.baidu.com/s?wd={urllib.parse.quote(keyword + ' 小说 故事')}"
            req = urllib.request.Request(baidu_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                snippets = re.findall(r'<span class="content-right_[^"]*">(.*?)</span>', html)
                if not snippets:
                    snippets = re.findall(r'<p[^>]*>(.*?)</p>', html)
                seen = set(inspirations) if inspirations else set()
                for s in snippets:
                    clean = re.sub(r'<[^>]+>', '', s).strip()
                    if len(clean) > 20 and len(clean) < 200 and clean not in seen:
                        seen.add(clean)
                        inspirations.append(clean)
                        if len(inspirations) >= 8:
                            break
        except Exception as e:
            print(f"[搜索] 百度搜索失败: {e}")
        
        if not inspirations:
            inspirations = [
                f"基于'{keyword}'的悬疑冒险故事：主角在平凡生活中发现不平凡的线索",
                f"基于'{keyword}'的温情故事：两个陌生人的命运因一次偶然相遇而交织",
                f"基于'{keyword}'的成长故事：从困境中崛起，最终实现自我价值",
            ]
        
        return jsonify({"inspirations": inspirations})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"搜索失败: {str(e)}"}), 500

@app.route('/api/generate_story_chapter', methods=['POST'])
def generate_story_chapter():
    try:
        data = request.get_json(force=True)
        dimensions = data.get('dimensions', {})
        custom_theme = data.get('custom_theme', '').strip()
        chapter_number = data.get('chapter_number', 1)
        total_chapters = data.get('total_chapters', 20)
        words_per_chapter = data.get('words_per_chapter', 1200)
        previous_summary = data.get('previous_summary', '')
        previous_chapters = data.get('previous_chapters', [])
        provider = data.get('provider', '')
        
        llm_service, llm_url, model_name = _get_llm_service(provider if provider else None)
        if not llm_url:
            return jsonify({"error": "LLM服务未启动"}), 503
        
        era = dimensions.get('era', '未知')
        theme = dimensions.get('theme', '未知')
        protagonist = dimensions.get('protagonist', '未知')
        conflict = dimensions.get('conflict', '未知')
        setting = dimensions.get('setting', '未知')
        tone = dimensions.get('tone', '未知')
        
        prev_context = ""
        if previous_chapters:
            prev_context = "\n\n【前几章内容摘要】\n"
            for i, ch in enumerate(previous_chapters):
                prev_context += f"第{chapter_number - len(previous_chapters) + i}章摘要：{ch[:300]}...\n"
        
        if previous_summary:
            prev_context += f"\n【前文总体摘要】{previous_summary}\n"
        
        if chapter_number == 1:
            chapter_instruction = """这是故事的第一章，需要：
1. 精彩的开场，迅速吸引读者
2. 介绍主要人物和核心矛盾
3. 营造故事氛围和时代感
4. 设置悬念，引导读者继续阅读"""
        elif chapter_number == total_chapters:
            chapter_instruction = """这是故事的最后一章，需要：
1. 解决所有主要矛盾和悬念
2. 给主要人物一个合理的结局
3. 呼应开头，形成完整闭环
4. 结局要有力度，令人回味"""
        else:
            progress = chapter_number / total_chapters
            if progress < 0.3:
                chapter_instruction = """这是故事的发展阶段，需要：
1. 深化矛盾冲突
2. 引入新的角色或线索
3. 推进情节发展
4. 保持与前文的连贯性"""
            elif progress < 0.7:
                chapter_instruction = """这是故事的中段，需要：
1. 矛盾进一步升级
2. 人物面临重大抉择
3. 情节出现转折
4. 为高潮做铺垫"""
            else:
                chapter_instruction = """这是故事的高潮阶段，需要：
1. 核心矛盾全面爆发
2. 人物命运面临考验
3. 情节紧张激烈
4. 逐步走向结局"""
        
        system_prompt = f"""你是一个专业的小说作家，擅长写写实风格的中文长篇小说。

【重要规则】
1. 必须是写实风格，不要科幻、赛博朋克、奇幻等超现实元素
2. 时代背景只能是古代或现代，不要未来时代
3. 故事必须合情合理，人物行为符合逻辑
4. 保持前后文连贯，人物性格一致
5. 对话要自然生动，符合人物身份和时代背景
6. 场景描写要细腻，有画面感
7. 字数控制在{words_per_chapter}字左右

【故事维度】
时代背景：{era}
故事主题：{theme}
主角身份：{protagonist}
核心冲突：{conflict}
故事场景：{setting}
情感基调：{tone}

{chapter_instruction}

输出格式：
1. 先写章节正文（{words_per_chapter}字左右的小说正文）
2. 然后用【本章摘要】标记写一段50-100字的章节摘要
3. 最后用【下章预告】标记写一句20字以内的下章悬念"""

        if custom_theme:
            system_prompt += f"""

【用户自定义主题】
{custom_theme}
请优先围绕用户自定义主题展开故事，上述维度作为辅助参考。"""

        user_prompt = f"""请写第{chapter_number}章（共{total_chapters}章）。{prev_context}"""

        response = requests.post(
            f"{llm_url}/v1/chat/completions",
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer sk-xxx'},
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.85,
                "max_tokens": 3000
            },
            timeout=180
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            chapter_text = content
            summary = ''
            
            if '【本章摘要】' in content:
                parts = content.split('【本章摘要】')
                chapter_text = parts[0].strip()
                summary_part = parts[1] if len(parts) > 1 else ''
                if '【下章预告】' in summary_part:
                    summary = summary_part.split('【下章预告】')[0].strip()
                else:
                    summary = summary_part.strip()
            
            if not summary:
                summary = chapter_text[:150]
            
            return jsonify({
                "status": "ok",
                "chapter": chapter_text,
                "summary": summary,
                "chapter_number": chapter_number
            })
        else:
            return jsonify({"error": f"API错误: {response.status_code}"}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"生成失败: {str(e)}"}), 500

@app.route('/api/generate_ltx23_first_last_prompt', methods=['POST'])
def generate_ltx23_first_last_prompt():
    """生成LTX2.3首尾帧视频提示词（一镜到底）"""
    try:
        llm_config = request.form.get('llm_config')
        if llm_config:
            try:
                llm_config = json.loads(llm_config)
            except:
                llm_config = {}
        else:
            llm_config = {}
        
        if 'first_image' not in request.files or 'last_image' not in request.files:
            return jsonify({"error": "需要首帧和尾帧两张图片"}), 400
        
        first_image = request.files['first_image']
        last_image = request.files['last_image']
        
        story_content = request.form.get('story_content', '')
        current_shot = request.form.get('current_shot', '')
        prev_shot = request.form.get('prev_shot', '')
        next_shot = request.form.get('next_shot', '')
        style = request.form.get('style', '')
        user_requirement = request.form.get('user_requirement', '')
        
        ref_characters_raw = request.form.get('ref_characters', '[]')
        try:
            ref_characters = json.loads(ref_characters_raw) if ref_characters_raw else []
        except:
            ref_characters = []
        
        used_dialogues_raw = request.form.get('used_dialogues', '[]')
        try:
            used_dialogues = json.loads(used_dialogues_raw) if used_dialogues_raw else []
        except:
            used_dialogues = []
        
        print(f"[首尾帧提示词] 当前镜头引用的角色: {ref_characters}")
        print(f"[首尾帧提示词] 已使用的台词数量: {len(used_dialogues)}")
        
        first_image_data = first_image.read()
        first_image_base64 = base64.b64encode(first_image_data).decode('utf-8')
        first_image_type = first_image.filename.split('.')[-1].lower()
        if first_image_type == 'jpg':
            first_image_type = 'jpeg'
        
        last_image_data = last_image.read()
        last_image_base64 = base64.b64encode(last_image_data).decode('utf-8')
        last_image_type = last_image.filename.split('.')[-1].lower()
        if last_image_type == 'jpg':
            last_image_type = 'jpeg'
        
        provider = llm_config.get('provider', 'qwen-9b')
        valid_providers = ['qwen-27b', 'qwen-27b-q6', 'qwen-35b-a3b-q4', 'qwen-35b-a3b-q2', 'qwen-9b', 'qwen-4b', 'gemma-4-31b', 'gemma-4-26b', 'gemma-4-e4b', 'minimax-m2.7', 'qwen3.6-27b-fp8']
        if provider not in valid_providers:
            provider = 'qwen-9b'
        
        llm_service = provider
        llm_url = SERVICE_PATHS[llm_service]["url"]
        is_minimax = (provider == 'minimax-m2.7')
        
        if is_minimax:
            print(f"[首尾帧提示词] 使用MiniMax-M2.7远程模型")
        else:
            def check_llm_online():
                try:
                    resp = requests.get(f"{llm_url}/v1/models", timeout=3)
                    return resp.status_code == 200
                except:
                    return False
        
        if not is_minimax:
            if SERVICE_STARTING.get(llm_service):
                print(f"[首尾帧提示词] 服务 {llm_service} 正在启动中，等待...")
                for i in range(60):
                    time.sleep(2)
                    if check_llm_online():
                        print(f"[首尾帧提示词] 服务 {llm_service} 已就绪")
                        break
                    if not SERVICE_STARTING.get(llm_service):
                        break
                else:
                    return jsonify({"error": "LLM服务启动超时"}), 503
            
            if not check_llm_online():
                print(f"[首尾帧提示词] {llm_service} 服务未启动，正在自动启动...")
                try:
                    start_resp = requests.post(f"http://127.0.0.1:5001/service/start/{llm_service}", timeout=120)
                    start_data = start_resp.json()
                    if start_data.get('status') == 'already_running':
                        print(f"[首尾帧提示词] 服务 {llm_service} 已在运行")
                    for i in range(30):
                        time.sleep(2)
                        if check_llm_online():
                            print(f"[首尾帧提示词] {llm_service} 服务已启动")
                            break
                        print(f"[首尾帧提示词] 等待服务启动... ({i+1}/30)")
                    else:
                        if not check_llm_online():
                            return jsonify({"error": f"{llm_service} 服务启动超时"}), 503
                except Exception as e:
                    return jsonify({"error": f"启动 {llm_service} 服务失败: {str(e)}"}), 503
        
        def get_available_model():
            if is_minimax:
                return "minimax-m2.7-multimodal"
            try:
                resp = requests.get(f"{llm_url}/v1/models", timeout=5)
                if resp.status_code == 200:
                    models = resp.json().get("data", [])
                    if models:
                        return models[0].get("id", "default")
            except:
                pass
            return "default"
        
        model_name = get_available_model()
        print(f"[首尾帧提示词] 使用服务: {llm_service}, 模型: {model_name}")
        
        character_constraint = ""
        if ref_characters and len(ref_characters) > 0:
            characters_str = "、".join(ref_characters)
            character_constraint = f"""

【⚠️ 角色一致性强制约束 - CRITICAL CHARACTER CONSISTENCY】
当前分镜头图片引用了以下角色：{characters_str}
1. 只能使用上述列表中的角色作为主要角色
2. 绝对禁止添加列表之外的主要角色
3. 角色数量必须严格匹配：引用N个角色，提示词中就只能有N个主要角色"""

        dialogue_constraint = ""
        if used_dialogues and len(used_dialogues) > 0:
            dialogue_samples = used_dialogues[-5:]
            dialogue_constraint = f"""

【⚠️ 台词去重约束 - CRITICAL DIALOGUE DEDUPLICATION】
以下台词已经在其他镜头中使用过，绝对不能再重复：
{chr(10).join(f'- "{d}"' for d in dialogue_samples)}
必须创作全新的、不同的台词！"""

        system_prompt = f"""You are a professional cinematographer and video director specializing in LTX2.3 first-last frame video generation. Your task is to create SEAMLESS ONE-SHOT video prompts that smoothly transition from the first frame to the last frame.
{character_constraint}
{dialogue_constraint}

【CRITICAL REQUIREMENTS - MUST FOLLOW】
1. The entire prompt MUST be in English EXCEPT for dialogue/lines
2. Dialogue/lines MUST be in Chinese and wrapped in quotation marks
3. The video MUST be ONE CONTINUOUS SHOT - no cuts, no transitions, no scene changes
4. The camera movement must be CINEMATIC and ARTISTIC with strong visual tension
5. The transition from first frame to last frame must be SMOOTH and NATURAL
6. Character actions and dialogue must match the story content perfectly
7. Environmental dynamics (wind, light, particles) should be natural
8. **DO NOT make characters walk away or leave the scene after speaking** - Characters should remain in the scene after their dialogue unless narratively essential

【LTX2.3 FIRST-LAST FRAME PROMPT STRUCTURE】

Part 1 - OPENING ANCHOR (First Frame):
- Describe the first frame scene precisely
- Camera position and angle at start
- Character position and pose at start
- Lighting and atmosphere at start

Part 2 - CAMERA MOVEMENT (The Journey):
- Specify EXACT camera movement: orbit, dolly, crane, push-in, pull-back, truck, pan, tilt
- Add focal length and aperture: 35mm f/2.0, 50mm f/2.8, 85mm f/1.8
- Describe the camera path: "orbit 180° around subject", "push-in 2m", "crane up 3m"
- Include motion quality: "steady gimbal", "smooth dolly", "tripod-locked with parallax"

Part 3 - TRANSITION DESCRIPTION:
- How the scene transforms from first frame to last frame
- Character movement and action during transition
- Environmental changes (lighting, weather, time of day)
- Any dialogue or sound during the transition

Part 4 - CLOSING ANCHOR (Last Frame):
- Describe the last frame scene precisely
- Camera position and angle at end
- Character position and pose at end
- Lighting and atmosphere at end

Part 5 - VISUAL STYLE:
- Color grading: "warm golden tones", "cool teal-orange", "moody low-key"
- Film look: "Kodak 2383", "cinematic contrast", "soft halation"
- Quality terms: "4K resolution", "natural motion blur", "180° shutter equivalent"

Part 6 - GUARDRAILS (CRITICAL FOR FIRST-LAST FRAME):
- "no cuts, no transitions, no scene changes"
- "no jump cuts, no teleport, no flash"
- "continuous single shot, seamless flow"
- "no text overlays, no watermarks, no logos"

【EXAMPLE PROMPT】

"Cinematic continuous shot, seamless zero-cut transition. OPENING: A young woman stands at a sunlit window, morning light casting soft shadows on her face, wearing a white linen dress, her hand resting on the windowsill. CAMERA: Slow orbit 180° around her, 50mm f/2.8, steady gimbal movement, maintaining medium close-up framing. TRANSITION: As the camera orbits, she slowly turns to face the window, her dress fabric gently swaying, dust particles dancing in the light beams, she speaks softly "今天天气真好..." CLOSING: The camera completes its orbit to reveal her profile silhouetted against the bright window, her hair catching the golden light, a gentle smile on her face. STYLE: Warm golden tones, soft contrast, Kodak 2383 film look, natural motion blur, 24fps cinematic feel. GUARDRAILS: No cuts, no transitions, continuous single shot, seamless flow, no text overlays."

【DURATION ESTIMATION】
- Simple transition + 1 short line: 5-7 seconds
- Complex camera move + dialogue: 8-10 seconds
- Elaborate transition + extended dialogue: 10-15 seconds

Generate a LTX2.3 first-last frame optimized prompt following the structure above.
REMEMBER: 
- Main text in English
- Dialogue in Chinese with quotation marks
- MUST be ONE CONTINUOUS SHOT
- Describe the TRANSITION from first to last frame clearly
- Estimate appropriate duration

Output format:
PROMPT: [Your complete prompt here]
DURATION: [X seconds]"""

        user_requirement_section = ""
        if user_requirement:
            user_requirement_section = f"""
【USER REQUIREMENT - MUST FOLLOW】
{user_requirement}
The user's requirement above is CRITICAL and must be incorporated into the video prompt."""

        user_content = f"""【STORY CONTEXT】
Full Story: {story_content}

【CURRENT SHOT】
{current_shot}

【ADJACENT SHOTS FOR CONTINUITY】
Previous Shot: {prev_shot if prev_shot else 'None (this is the first shot)'}
Next Shot: {next_shot if next_shot else 'None (this is the last shot)'}

【VISUAL STYLE】
{style}
{user_requirement_section}
【FIRST FRAME IMAGE】
Analyze the first frame image carefully - note the character's position, pose, expression, clothing, lighting, and environment.

【LAST FRAME IMAGE】
Analyze the last frame image carefully - note the character's position, pose, expression, clothing, lighting, and environment.

Generate a seamless one-shot video prompt that transitions smoothly from the first frame to the last frame while fulfilling the story requirements."""

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_content},
                    {"type": "image_url", "image_url": {"url": f"data:image/{first_image_type};base64,{first_image_base64}"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/{last_image_type};base64,{last_image_base64}"}}
                ]
            }
        ]
        
        if is_minimax:
            response = requests.post(
                f"{MINIMAX_URL}/v1/chat/completions",
                headers={'Content-Type': 'application/json'},
                json={
                    "model": "minimax-m2.7-multimodal",
                    "messages": messages,
                    "max_tokens": 1500,
                    "temperature": 0.7
                },
                timeout=180
            )
        else:
            response = requests.post(
                f"{llm_url}/v1/chat/completions",
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer sk-xxx'
                },
                json={
                    "model": model_name,
                    "messages": messages,
                    "max_tokens": 1500,
                    "temperature": 0.7
                },
                timeout=120
            )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            prompt_match = re.search(r'PROMPT:\s*(.+?)(?=DURATION:|$)', content, re.DOTALL)
            duration_match = re.search(r'DURATION:\s*(\d+)', content)
            
            prompt = prompt_match.group(1).strip() if prompt_match else content
            duration = int(duration_match.group(1)) if duration_match else 8
            
            duration = max(5, min(15, duration))
            frame_count = duration * 24 + 1
            
            print(f"[首尾帧提示词] 生成成功, 时长: {duration}秒, 帧数: {frame_count}")
            
            return jsonify({
                "prompt": prompt,
                "duration": duration,
                "frameCount": frame_count
            })
        else:
            return jsonify({"error": f"LLM请求失败: {response.status_code}"}), 500
            
    except requests.exceptions.ConnectionError as e:
        print(f"[首尾帧提示词] 多模态服务 {llm_service} 未启动，尝试启动...")
        try:
            requests.post(f"http://127.0.0.1:5001/service/start/{llm_service}", timeout=5)
            return jsonify({"error": "服务已启动，请重试"}), 503
        except:
            return jsonify({"error": "多模态服务连接失败"}), 503
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"生成失败: {str(e)}"}), 500

# ==================== 0.8B模型图片检测API ====================
def call_08b_model(messages, max_tokens=500):
    """调用0.8B小模型进行快速检测"""
    try:
        qwen_url = SERVICE_PATHS["qwen-0.8b"]["url"]
        qwen_model = SERVICE_PATHS["qwen-0.8b"]["model"]
        
        payload = {
            "model": qwen_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.1
        }
        
        response = requests.post(
            f"{qwen_url}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('choices', [{}])[0].get('message', {}).get('content', '')
        else:
            print(f"[0.8B模型] API错误: {response.status_code}")
            return None
    except Exception as e:
        print(f"[0.8B模型] 调用失败: {str(e)}")
        return None

def ensure_08b_service():
    """确保0.8B服务运行中"""
    try:
        qwen_url = SERVICE_PATHS["qwen-0.8b"]["url"]
        resp = requests.get(f"{qwen_url}/v1/models", timeout=3)
        if resp.status_code == 200:
            return True
    except:
        pass
    
    print("[0.8B服务] 服务未启动，正在启动...")
    start_resp = requests.post(f"http://127.0.0.1:5001/service/start/qwen-0.8b", timeout=60)
    if start_resp.status_code == 200:
        import time
        time.sleep(5)
        return True
    return False

@app.route('/api/detect/people_in_scene', methods=['POST'])
def detect_people_in_scene():
    """检测场景图中是否有人物 - 使用当前配置的LLM模型"""
    try:
        if 'image' not in request.files:
            return jsonify({"error": "未上传图片"}), 400
        
        file = request.files['image']
        image_data = file.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        filename = file.filename.lower()
        if filename.endswith('.png'):
            image_type = 'png'
        elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
            image_type = 'jpeg'
        else:
            image_type = 'jpeg'
        
        # 获取前端传来的LLM配置
        llm_url = request.form.get('llm_url', '')
        llm_model = request.form.get('llm_model', '')
        llm_provider = request.form.get('llm_provider', '')
        
        print(f"[场景人物检测] 检测图片: {file.filename}, 使用模型: {llm_provider} @ {llm_url}")
        
        messages = [
            {
                "role": "system",
                "content": "你是一个图像检测专家。你的任务是判断图片中是否有人物/人物。只回答YES或NO，不要其他内容。"
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{image_type};base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "这张图片中是否有人物？有人物回答YES，完全没有人回答NO。只回答YES或NO。"
                    }
                ]
            }
        ]
        
        # 使用用户配置的LLM模型进行检测
        result = call_configured_llm(messages, llm_url, llm_model, max_tokens=10)
        
        if result is None:
            return jsonify({"error": "检测失败"}), 500
        
        has_people = "YES" in result.upper()
        print(f"[场景人物检测] 结果: {'有人物' if has_people else '无人'}")
        
        return jsonify({
            "status": "ok",
            "has_people": has_people,
            "raw_response": result
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"检测失败: {str(e)}"}), 500

def call_configured_llm(messages, llm_url, llm_model, max_tokens=500):
    """调用用户配置的LLM模型"""
    try:
        # 如果没有提供配置，尝试使用默认配置
        if not llm_url:
            # 尝试从配置文件读取
            try:
                config_path = PROJECT_ROOT / 'llm_config.json'
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        llm_url = config.get('url', '')
                        llm_model = config.get('model', '')
            except Exception as e:
                print(f"[LLM调用] 读取配置失败: {e}")
        
        # 如果还是没有配置，返回None
        if not llm_url:
            print("[LLM调用] 错误: 未提供LLM URL")
            return None
        
        payload = {
            "model": llm_model or "default",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.1
        }
        
        response = requests.post(
            f"{llm_url}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('choices', [{}])[0].get('message', {}).get('content', '')
        else:
            print(f"[LLM调用] API错误: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        print(f"[LLM调用] 调用失败: {str(e)}")
        return None

# ==================== ComfyUI 工作流执行函数 ====================
COMFYUI_URL = "http://127.0.0.1:8188"

def upload_image_to_comfy(image_data, filename):
    """上传图片到ComfyUI"""
    try:
        print(f"[upload_image_to_comfy] 开始上传: {filename}, 数据大小: {len(image_data)} bytes")
        
        # 确保文件名是安全的（移除或替换特殊字符）
        safe_filename = filename.replace(' ', '_').replace('(', '').replace(')', '').replace('[', '').replace(']', '')
        if safe_filename != filename:
            print(f"[upload_image_to_comfy] 文件名已清理: {filename} -> {safe_filename}")
        
        # 检测实际的MIME类型
        content_type = 'image/png'
        header = image_data[:8]
        if header[:2] == b'\xff\xd8':
            content_type = 'image/jpeg'
        elif header[:4] == b'RIFF':
            content_type = 'image/webp'
        
        files = {'image': (safe_filename, io.BytesIO(image_data), content_type)}
        data = {'overwrite': 'true'}
        
        response = requests.post(f"{COMFYUI_URL}/upload/image", files=files, data=data)
        print(f"[upload_image_to_comfy] ComfyUI响应: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"[upload_image_to_comfy] 上传成功: {result.get('name', safe_filename)}")
            return result.get('name', safe_filename)
        else:
            error_text = response.text[:500]
            print(f"[upload_image_to_comfy] 上传失败: {response.status_code}, 响应: {error_text}")
            raise Exception(f"上传失败: HTTP {response.status_code} - {error_text}")
    except Exception as e:
        print(f"[upload_image_to_comfy] 错误: {str(e)}")
        raise Exception(f"ComfyUI图片上传错误: {str(e)}")

def execute_comfy_workflow(workflow, output_type='image'):
    """执行ComfyUI工作流并返回结果"""
    import uuid
    import websocket
    
    client_id = f"client_{int(time.time() * 1000)}"
    
    prompt_response = requests.post(
        f"{COMFYUI_URL}/prompt",
        json={"prompt": workflow, "client_id": client_id}
    )
    
    if prompt_response.status_code != 200:
        raise Exception(f"工作流提交失败: {prompt_response.status_code}")
    
    prompt_data = prompt_response.json()
    prompt_id = prompt_data.get('prompt_id')
    
    ws_url = COMFYUI_URL.replace('http://', 'ws://').replace('https://', 'wss://')
    ws = websocket.create_connection(f"{ws_url}/ws?clientId={client_id}")
    
    try:
        while True:
            message = ws.recv()
            msg = json.loads(message)
            
            if msg.get('type') == 'executing' and msg.get('data', {}).get('node') is None:
                if msg.get('data', {}).get('prompt_id') == prompt_id:
                    break
    finally:
        ws.close()
    
    history_response = requests.get(f"{COMFYUI_URL}/history/{prompt_id}")
    history = history_response.json()
    
    if prompt_id not in history:
        raise Exception("未找到工作流历史记录")
    
    outputs = history[prompt_id].get('outputs', {})
    
    for node_id, output in outputs.items():
        if output_type == 'image' and 'images' in output:
            file_info = output['images'][0]
            filename = file_info['filename']
            subfolder = file_info.get('subfolder', '')
            file_type = file_info.get('type', 'output')
            
            view_url = f"{COMFYUI_URL}/view?filename={filename}&subfolder={subfolder}&type={file_type}"
            img_response = requests.get(view_url)
            
            if img_response.status_code == 200:
                return img_response.content
            else:
                raise Exception(f"获取图片失败: {img_response.status_code}")
        
        elif output_type == 'video' and ('videos' in output or 'gifs' in output):
            files = output.get('videos') or output.get('gifs')
            if files:
                file_info = files[0]
                filename = file_info['filename']
                subfolder = file_info.get('subfolder', '')
                file_type = file_info.get('type', 'output')
                
                view_url = f"{COMFYUI_URL}/view?filename={filename}&subfolder={subfolder}&type={file_type}"
                video_response = requests.get(view_url)
                
                if video_response.status_code == 200:
                    return video_response.content
    
    raise Exception("未找到生成结果")

# ==================== 多图融合API ====================
@app.route('/api/fusion/multi_image', methods=['POST'])
def multi_image_fusion():
    """多图融合工作流"""
    try:
        image1 = request.files.get('image1')
        image2 = request.files.get('image2')
        image3 = request.files.get('image3')
        prompt = request.form.get('prompt', '')
        num_refs = int(request.form.get('num_refs', 2))
        
        if not image1:
            return jsonify({"error": "缺少基础图片"}), 400
        
        print(f"[多图融合] 开始处理，参考图数量: {num_refs}")
        print(f"[多图融合] 融合指令: {prompt}")
        
        image1_data = image1.read()
        image1_name = upload_image_to_comfy(image1_data, 'base.png')
        print(f"[多图融合] 上传基础图: {image1_name}")
        
        image2_name = None
        image3_name = None
        
        if image2:
            image2_data = image2.read()
            image2_name = upload_image_to_comfy(image2_data, 'ref1.png')
            print(f"[多图融合] 上传参考图1: {image2_name}")
        
        if image3:
            image3_data = image3.read()
            image3_name = upload_image_to_comfy(image3_data, 'ref2.png')
            print(f"[多图融合] 上传参考图2: {image3_name}")
        
        workflow = {
            "1": {
                "inputs": {"ckpt_name": "Qwen-Rapid-AIO-NSFW-v22.safetensors"},
                "class_type": "CheckpointLoaderSimple",
                "_meta": {"title": "Checkpoint加载器（简易）"}
            },
            "2": {
                "inputs": {
                    "seed": random.randint(1, 1000000000),
                    "steps": 4,
                    "cfg": 1,
                    "sampler_name": "sa_solver",
                    "scheduler": "beta",
                    "denoise": 1,
                    "model": ["1", 0],
                    "positive": ["19", 0],
                    "negative": ["18", 0],
                    "latent_image": ["16", 0]
                },
                "class_type": "KSampler",
                "_meta": {"title": "K采样器"}
            },
            "5": {
                "inputs": {"samples": ["2", 0], "vae": ["1", 2]},
                "class_type": "VAEDecode",
                "_meta": {"title": "VAE解码"}
            },
            "8": {
                "inputs": {"image": image2_name or image1_name},
                "class_type": "LoadImage",
                "_meta": {"title": "图像2"}
            },
            "10": {
                "inputs": {"image": image1_name},
                "class_type": "LoadImage",
                "_meta": {"title": "图像1"}
            },
            "11": {
                "inputs": {"image": image3_name or image1_name},
                "class_type": "LoadImage",
                "_meta": {"title": "图像3"}
            },
            "13": {
                "inputs": {"filename_prefix": "FluxFusion", "images": ["5", 0]},
                "class_type": "SaveImage",
                "_meta": {"title": "保存图像"}
            },
            "15": {
                "inputs": {"upscale_method": "lanczos", "megapixels": 1, "resolution_steps": 1, "image": ["10", 0]},
                "class_type": "ImageScaleToTotalPixels",
                "_meta": {"title": "缩放图像（像素）"}
            },
            "16": {
                "inputs": {"pixels": ["15", 0], "vae": ["1", 2]},
                "class_type": "VAEEncode",
                "_meta": {"title": "VAE编码"}
            },
            "18": {
                "inputs": {"conditioning": ["19", 0]},
                "class_type": "ConditioningZeroOut",
                "_meta": {"title": "条件零化"}
            },
            "19": {
                "inputs": {
                    "prompt": prompt,
                    "clip": ["1", 1],
                    "vae": ["1", 2],
                    "image1": ["10", 0],
                    "image2": ["8", 0],
                    "image3": ["11", 0]
                },
                "class_type": "TextEncodeQwenImageEditPlus",
                "_meta": {"title": "QwenImageEditPlus千问文本编码器正向提示词"}
            }
        }
        
        print(f"[多图融合] 提交工作流到ComfyUI...")
        result = execute_comfy_workflow(workflow, 'image')
        
        print(f"[多图融合] 生成完成")
        from flask import Response
        return Response(result, mimetype='image/png')
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"多图融合失败: {str(e)}"}), 500

# ==================== 角度调整API ====================
@app.route('/api/edit/angle_adjust', methods=['POST'])
def angle_adjust():
    """角度调整工作流"""
    try:
        image = request.files.get('image')
        azimuth = float(request.form.get('azimuth', 0))
        elevation = float(request.form.get('elevation', 0))
        distance = float(request.form.get('distance', 5))
        
        if not image:
            return jsonify({"error": "缺少图片"}), 400
        
        print(f"[角度调整] 开始处理")
        print(f"[角度调整] 角度: 方位角={azimuth}°, 仰角={elevation}°, 距离={distance}")
        
        image_data = image.read()
        image_name = upload_image_to_comfy(image_data, 'original.png')
        print(f"[角度调整] 上传图片: {image_name}")
        
        workflow = {
            "8": {
                "inputs": {"samples": ["65", 0], "vae": ["10", 0]},
                "class_type": "VAEDecode",
                "_meta": {"title": "VAE解码"}
            },
            "10": {
                "inputs": {"vae_name": "qwen_image_vae.safetensors"},
                "class_type": "VAELoader",
                "_meta": {"title": "加载VAE"}
            },
            "12": {
                "inputs": {"unet_name": "qwen_image_edit_2511_fp8mixed.safetensors", "weight_dtype": "fp8_e4m3fn"},
                "class_type": "UNETLoader",
                "_meta": {"title": "UNet加载器"}
            },
            "41": {
                "inputs": {"image": image_name},
                "class_type": "LoadImage",
                "_meta": {"title": "加载图像"}
            },
            "61": {
                "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image", "device": "default"},
                "class_type": "CLIPLoader",
                "_meta": {"title": "加载CLIP"}
            },
            "64": {
                "inputs": {"strength": 0.95, "model": ["67", 0]},
                "class_type": "CFGNorm",
                "_meta": {"title": "CFG归一化"}
            },
            "65": {
                "inputs": {
                    "seed": random.randint(1, 1000000000),
                    "steps": 4,
                    "cfg": 1,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "denoise": 1,
                    "model": ["64", 0],
                    "positive": ["70", 0],
                    "negative": ["71", 0],
                    "latent_image": ["85", 0]
                },
                "class_type": "KSampler",
                "_meta": {"title": "K采样器"}
            },
            "67": {
                "inputs": {"shift": 3.1, "model": ["106", 0]},
                "class_type": "ModelSamplingAuraFlow",
                "_meta": {"title": "采样算法（AuraFlow）"}
            },
            "68": {
                "inputs": {"prompt": ["108", 0], "clip": ["61", 0], "vae": ["10", 0], "image1": ["41", 0]},
                "class_type": "TextEncodeQwenImageEditPlus",
                "_meta": {"title": "TextEncodeQwenImageEditPlus (Positive)"}
            },
            "69": {
                "inputs": {"prompt": "泛黄，AI感，不真实，丑陋，油腻的皮肤，异常的肢体，不协调的肢体", "clip": ["61", 0], "vae": ["10", 0], "image1": ["41", 0]},
                "class_type": "TextEncodeQwenImageEditPlus",
                "_meta": {"title": "TextEncodeQwenImageEditPlus"}
            },
            "70": {
                "inputs": {"reference_latents_method": "index_timestep_zero", "conditioning": ["68", 0]},
                "class_type": "FluxKontextMultiReferenceLatentMethod",
                "_meta": {"title": "FluxKontext多参考潜在方法"}
            },
            "71": {
                "inputs": {"reference_latents_method": "index_timestep_zero", "conditioning": ["69", 0]},
                "class_type": "FluxKontextMultiReferenceLatentMethod",
                "_meta": {"title": "FluxKontext多参考潜在方法"}
            },
            "73": {
                "inputs": {"lora_name": "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors", "strength_model": 1, "model": ["12", 0]},
                "class_type": "LoraLoaderModelOnly",
                "_meta": {"title": "LoRA加载器（仅模型）"}
            },
            "84": {
                "inputs": {"upscale_method": "lanczos", "megapixels": 1.5, "resolution_steps": 8, "image": ["41", 0]},
                "class_type": "ImageScaleToTotalPixels",
                "_meta": {"title": "缩放图像（像素）"}
            },
            "85": {
                "inputs": {"pixels": ["84", 0], "vae": ["10", 0]},
                "class_type": "VAEEncode",
                "_meta": {"title": "VAE编码"}
            },
            "106": {
                "inputs": {"lora_name": "qwen-image-edit-2511-multiple-angles-lora.safetensors", "strength_model": 1, "model": ["73", 0]},
                "class_type": "LoraLoaderModelOnly",
                "_meta": {"title": "LoRA加载器（仅模型）"}
            },
            "108": {
                "inputs": {
                    "horizontal_angle": azimuth,
                    "vertical_angle": elevation,
                    "zoom": distance,
                    "default_prompts": "",
                    "camera_view": False,
                    "image": ["41", 0]
                },
                "class_type": "QwenMultiangleCameraNode",
                "_meta": {"title": "Qwen Multiangle Camera"}
            },
            "114": {
                "inputs": {"filename_prefix": "QwenCamera", "images": ["8", 0]},
                "class_type": "SaveImage",
                "_meta": {"title": "保存图像"}
            }
        }
        
        print(f"[角度调整] 提交工作流到ComfyUI...")
        result = execute_comfy_workflow(workflow, 'image')
        
        print(f"[角度调整] 生成完成")
        from flask import Response
        return Response(result, mimetype='image/png')
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"角度调整失败: {str(e)}"}), 500

@app.route('/api/comfyui/upload_image', methods=['POST'])
def comfyui_upload_image_proxy():
    try:
        image = request.files.get('image')
        if not image:
            print(f"[代理上传] 错误: 缺少图片文件")
            return jsonify({"error": "缺少图片"}), 400
        
        filename = image.filename or 'upload.png'
        image_data = image.read()
        
        print(f"[代理上传] 接收到文件: {filename}, 大小: {len(image_data)} bytes, content_type: {image.content_type}")
        
        if len(image_data) == 0:
            print(f"[代理上传] 错误: 图片数据为空")
            return jsonify({"error": "图片数据为空"}), 400
        
        # 检查图片数据的前几个字节（文件签名）
        header = image_data[:8]
        print(f"[代理上传] 文件头(hex): {header.hex()}")
        
        # 检测文件类型
        file_type = 'unknown'
        if header[:8] == b'\x89PNG\r\n\x1a\n':
            file_type = 'PNG'
        elif header[:2] == b'\xff\xd8':
            file_type = 'JPEG'
        elif header[:4] == b'RIFF' and header[8:12] == b'WEBP':
            file_type = 'WEBP'
        print(f"[代理上传] 检测到文件类型: {file_type}")
        
        result_name = upload_image_to_comfy(image_data, filename)
        print(f"[代理上传] 上传成功: {result_name}")
        return jsonify({"name": result_name})
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[代理上传] 错误: {str(e)}")
        return jsonify({"error": f"上传失败: {str(e)}"}), 500

@app.route('/api/comfyui/execute_workflow', methods=['POST'])
def comfyui_execute_workflow_proxy():
    try:
        data = request.get_json()
        workflow = data.get('workflow', {})
        output_type = data.get('output_type', 'image')
        result = execute_comfy_workflow(workflow, output_type)
        if output_type == 'image' and result:
            import base64
            if isinstance(result, bytes):
                return jsonify({"image": base64.b64encode(result).decode('utf-8')})
            else:
                return jsonify({"image": result})
        return jsonify({"result": str(result)})
    except Exception as e:
        return jsonify({"error": f"工作流执行失败: {str(e)}"}), 500

# ==================== MiniMax-M2.7 多模态API ====================

@app.route('/api/minimax/health', methods=['GET'])
def minimax_health():
    try:
        resp = requests.get(f"{MINIMAX_URL}/health", timeout=5)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 503

@app.route('/api/minimax/vision', methods=['POST'])
def minimax_vision():
    try:
        data = request.get_json()
        image_base64 = data.get('image', '')
        prompt = data.get('prompt', '描述这张图片')
        
        if not image_base64:
            return jsonify({"error": "缺少image参数"}), 400
        
        resp = requests.post(
            f"{MINIMAX_URL}/v1/vision",
            headers={'Content-Type': 'application/json'},
            json={"image": image_base64, "prompt": prompt},
            timeout=60
        )
        
        if resp.status_code == 200:
            result = resp.json()
            return jsonify({"understanding": result.get('understanding', '')})
        else:
            return jsonify({"error": f"视觉接口失败: {resp.status_code}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/minimax/chat_multimodal', methods=['POST'])
def minimax_chat_multimodal():
    try:
        data = request.get_json()
        messages = data.get('messages', [])
        max_tokens = data.get('max_tokens', 2000)
        temperature = data.get('temperature', 0.7)
        
        resp = requests.post(
            f"{MINIMAX_URL}/v1/chat/completions",
            headers={'Content-Type': 'application/json'},
            json={
                "model": "minimax-m2.7-multimodal",
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            },
            timeout=180
        )
        
        if resp.status_code == 200:
            result = resp.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            vision_info = result.get('vision_understanding', [])
            return jsonify({"content": content, "vision_understanding": vision_info})
        else:
            return jsonify({"error": f"请求失败: {resp.status_code} {resp.text[:200]}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== LLM对话API ====================
@app.route('/api/llm_chat', methods=['POST'])
def llm_chat():
    """通用LLM对话接口（支持文本/多模态）"""
    try:
        data = request.get_json()
        provider = data.get('provider', 'qwen-9b')
        messages = data.get('messages', [])
        temperature = data.get('temperature', 0.7)
        max_tokens = data.get('max_tokens', 2000)
        
        # 收集所有图片数据 (image_data, image_data_2, image_data_3, ...)
        all_images = []
        if data.get('image_data'):
            all_images.append(data['image_data'])
        for key in sorted(data.keys()):
            if key.startswith('image_data_') and key != 'image_data':
                val = data[key]
                if val:
                    all_images.append(val)
        
        has_images = len(all_images) > 0
        
        valid_providers = ['qwen-27b', 'qwen-27b-q6', 'qwen-35b-a3b-q4', 'qwen-35b-a3b-q2', 'qwen-9b', 'qwen-4b', 'gemma-4-31b', 'gemma-4-26b', 'gemma-4-e4b', 'minimax-m2.7', 'qwen3.6-27b-fp8']
        if provider not in valid_providers:
            provider = 'qwen-9b'
        
        llm_service = provider
        service_config = SERVICE_PATHS.get(llm_service, {})
        llm_url = service_config["url"]
        model_name = service_config["model"]
        
        if service_config.get('is_remote'):
            try:
                health_resp = requests.get(f"{llm_url}/health", timeout=5)
                if health_resp.status_code != 200:
                    return jsonify({"error": f"远程服务 {provider} 不可用: {llm_url}"}), 503
            except Exception as e:
                return jsonify({"error": f"远程服务 {provider} 连接失败: {str(e)}"}), 503
            
            print(f"[LLM Chat] 使用远程模型 {provider}: {llm_url}")
            
            request_body = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            # 如果提供了图片数据，构造多模态消息（仅MiniMax不支持视觉）
            if has_images and 'minimax' not in provider.lower():
                multimodal_messages = []
                for msg in messages:
                    content_parts = []
                    for img in all_images:
                        content_parts.append({"type": "image_url", "image_url": {"url": img}})
                    content_parts.append({"type": "text", "text": msg.get('content', '')})
                    multimodal_messages.append({
                        "role": msg.get('role', 'user'),
                        "content": content_parts
                    })
                request_body["messages"] = multimodal_messages
                print(f"[LLM Chat] 使用多模态请求 ({provider}), 共{len(all_images)}张图片")
            
            if 'qwen' in provider.lower() or 'qwen' in model_name.lower():
                request_body["chat_template_kwargs"] = {"enable_thinking": False}
            response = requests.post(
                f"{llm_url}/v1/chat/completions",
                headers={'Content-Type': 'application/json'},
                json=request_body,
                timeout=180
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                # 后手清理：如果模型仍然输出了思考内容
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                content = content.strip()
                return jsonify({"content": content})
            else:
                return jsonify({"error": f"远程服务请求失败: {response.status_code} {response.text[:200]}"}), 500
        
        def check_llm_online():
            try:
                resp = requests.get(f"{llm_url}/v1/models", timeout=3)
                return resp.status_code == 200
            except:
                return False
        
        if SERVICE_STARTING.get(llm_service):
            print(f"[LLM Chat] 服务 {llm_service} 正在启动中，等待...")
            for i in range(60):
                time.sleep(2)
                if check_llm_online():
                    print(f"[LLM Chat] 服务 {llm_service} 已就绪")
                    break
                if not SERVICE_STARTING.get(llm_service):
                    break
            else:
                return jsonify({"error": "LLM服务启动超时"}), 503
        
        if not check_llm_online():
            print(f"[LLM Chat] 服务 {llm_service} 不在线，尝试启动...")
            start_result = start_service(llm_service)
            if isinstance(start_result, tuple):
                start_data = start_result[0].get_json()
            else:
                start_data = start_result.get_json() if hasattr(start_result, 'get_json') else start_result
            
            if start_data.get('status') == 'already_running':
                print(f"[LLM Chat] 服务 {llm_service} 已在运行")
            elif start_data.get('status') != 'started':
                return jsonify({"error": f"无法启动LLM服务: {start_data.get('message', '未知错误')}"}), 500
            
            for _ in range(30):
                if check_llm_online():
                    break
                time.sleep(1)
            else:
                return jsonify({"error": "LLM服务启动超时"}), 500
        
        # 检查是否为Qwen系列模型，关闭思考模式
        request_body = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        # 如果提供了图片数据，构造多模态消息（本地Qwen模型全部支持视觉）
        if has_images and 'minimax' not in provider.lower():
            multimodal_messages = []
            for msg in messages:
                content_parts = []
                for img in all_images:
                    content_parts.append({"type": "image_url", "image_url": {"url": img}})
                content_parts.append({"type": "text", "text": msg.get('content', '')})
                multimodal_messages.append({
                    "role": msg.get('role', 'user'),
                    "content": content_parts
                })
            request_body["messages"] = multimodal_messages
            print(f"[LLM Chat] 多模态请求 (本地 {provider}), 共{len(all_images)}张图片")
        
        if 'qwen' in provider.lower() or 'qwen' in model_name.lower():
            request_body["chat_template_kwargs"] = {"enable_thinking": False}
        
        response = requests.post(
            f"{llm_url}/v1/chat/completions",
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer sk-xxx'
            },
            json=request_body,
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            # 后手清理：如果模型仍然输出了思考内容
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
            content = content.strip()
            return jsonify({"content": content})
        else:
            return jsonify({"error": f"LLM请求失败: {response.status_code}"}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"LLM对话失败: {str(e)}"}), 500

@app.route('/api/llm_vision', methods=['POST'])
def llm_vision():
    """多模态视觉分析接口 - 用于图片分析"""
    try:
        data = request.get_json()
        image_base64 = data.get('image', '')
        prompt = data.get('prompt', '分析这张图片')
        temperature = data.get('temperature', 0.3)
        
        if not image_base64:
            return jsonify({"error": "没有图片数据"}), 400
        
        # 使用 MiniMax-M2.7 进行视觉分析
        service_config = SERVICE_PATHS.get('minimax-m2.7', {})
        if not service_config or not service_config.get('is_remote'):
            return jsonify({"error": "MiniMax-M2.7 服务未配置"}), 503
        
        llm_url = service_config["url"]
        model_name = service_config["model"]
        
        # 检查服务健康
        try:
            health_resp = requests.get(f"{llm_url}/health", timeout=5)
            if health_resp.status_code != 200:
                return jsonify({"error": f"MiniMax-M2.7 服务不可用"}), 503
        except Exception as e:
            return jsonify({"error": f"MiniMax-M2.7 服务连接失败: {str(e)}"}), 503
        
        print(f"[LLM Vision] 使用 MiniMax-M2.7 分析图片")
        
        # 构建多模态消息
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_base64}},
                    {"type": "text", "text": prompt}
                ]
            }
        ]
        
        response = requests.post(
            f"{llm_url}/v1/chat/completions",
            headers={'Content-Type': 'application/json'},
            json={
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 2000
            },
            timeout=180
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            return jsonify({"content": content})
        else:
            return jsonify({"error": f"MiniMax-M2.7 视觉分析失败: {response.status_code} {response.text[:200]}"}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"视觉分析失败: {str(e)}"}), 500

@app.route('/voice/recognize', methods=['POST'])
def voice_recognize():
    """语音识别代理接口 - 将音频转发到本地ASR服务"""
    try:
        audio_file = request.files.get('audio')
        session_id = request.form.get('session_id', 'default')
        
        if not audio_file:
            return jsonify({"error": "没有音频数据"}), 400
        
        asr_url = 'http://127.0.0.1:28460'
        
        try:
            audio_data = audio_file.read()
            
            int16_data = np.frombuffer(audio_data, dtype=np.int16)
            float32_data = int16_data.astype(np.float32) / 32768.0
            
            wav_buffer = io.BytesIO()
            import wave
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(int16_data.tobytes())
            wav_buffer.seek(0)
            
            base64_audio = base64.b64encode(wav_buffer.read()).decode('utf-8')
            
            resp = requests.post(f"{asr_url}/stream_chunk", 
                json={"session_id": session_id, "audio": base64_audio},
                timeout=10)
            
            if resp.status_code == 200:
                result = resp.json()
                return jsonify({"text": result.get("text", "")})
            else:
                return jsonify({"text": "", "error": f"ASR服务返回: {resp.status_code}"}), 200
                
        except requests.exceptions.ConnectionError:
            return jsonify({"text": "", "error": "ASR服务未启动"}), 200
        except Exception as e:
            return jsonify({"text": "", "error": str(e)}), 200
            
    except Exception as e:
        return jsonify({"error": f"语音识别失败: {str(e)}"}), 500

# ==================== 任务队列与聊天系统 ====================

def task_worker():
    """后台工作线程，处理任务队列"""
    while True:
        try:
            task_id, task_data = task_queue.get(timeout=1)
            with tasks_lock:
                if task_id not in active_tasks:
                    active_tasks[task_id] = {
                        'status': 'running',
                        'progress': 0,
                        'current_step': '',
                        'error': None,
                        'result': None
                    }
            
            try:
                result = execute_creative_task(task_id, task_data)
                with tasks_lock:
                    if task_id in active_tasks:
                        active_tasks[task_id]['status'] = 'completed'
                        active_tasks[task_id]['progress'] = 100
                        active_tasks[task_id]['result'] = result
                        active_tasks[task_id]['current_step'] = '完成'
            except Exception as e:
                with tasks_lock:
                    if task_id in active_tasks:
                        active_tasks[task_id]['status'] = 'failed'
                        active_tasks[task_id]['error'] = str(e)
                        active_tasks[task_id]['current_step'] = f'失败: {str(e)}'
            finally:
                task_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            print(f"[Task Worker Error] {e}")

# 启动工作线程
for i in range(3):  # 3个工作线程
    t = threading.Thread(target=task_worker, daemon=True)
    t.start()

# ==================== 聊天会话管理 ====================

def create_chat_session(user_id=None):
    """创建新的聊天会话"""
    session_id = str(uuid.uuid4())
    with session_lock:
        chat_sessions[session_id] = {
            'id': session_id,
            'user_id': user_id,
            'messages': [],
            'current_task': None,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
    return session_id

def get_chat_session(session_id):
    """获取聊天会话"""
    with session_lock:
        return chat_sessions.get(session_id)


def add_chat_message(session_id, role, content, message_type='text', data=None):
    """添加消息到聊天会话"""
    with session_lock:
        if session_id not in chat_sessions:
            return False
        
        message = {
            'id': str(uuid.uuid4()),
            'role': role,
            'content': content,
            'type': message_type,
            'timestamp': datetime.now().isoformat(),
            'data': data
        }
        chat_sessions[session_id]['messages'].append(message)
        chat_sessions[session_id]['updated_at'] = datetime.now().isoformat()
        
        # 通过WebSocket发送消息给客户端
        try:
            socketio.emit('chat_message', {
                'session_id': session_id,
                'message': message
            }, room=session_id)
        except Exception as e:
            print(f"[WebSocket emit error] {e}")
        
        return True

# ==================== 创意任务执行 ====================

def execute_creative_task(task_id, task_data):
    """执行创意任务：剧本->提示词->生成->合成"""
    try:
        session_id = task_data.get('session_id')
        user_message = task_data.get('user_message', '')
        
        # 步骤1: 需求分析与剧本创作
        update_task_progress(task_id, 10, '分析需求并创作剧本')
        add_chat_message(session_id, 'assistant', '收到您的创作需求！让我先分析并创作剧本...', 'text')
        
        # 调用AI生成剧本 (这里使用现有的LLM chat功能)
        script_prompt = f"""
        你是一位专业的创意导演。用户要求：{user_message}
        
        请创作一个分镜头剧本，包括：
        1. 视频标题
        2. 风格描述
        3. 分镜头列表（每个镜头包括：镜头描述、时长、对话/旁白）
        4. 角色设定（如果需要）
        
        请以JSON格式返回，结构：
        {{
          "title": "视频标题",
          "style": "整体风格描述",
          "shots": [
            {{"index": 1, "description": "镜头描述", "duration": 3, "dialogue": "对话内容"}}
          ],
          "characters": ["角色名称"]
        }}
        """
        
        # 这里简化：直接使用示例剧本
        script_data = {
            "title": "示例短片",
            "style": "动漫风格， vibrant colors",
            "shots": [
                {"index": 0, "description": "开场：主角站在山顶眺望远方", "duration": 3, "dialogue": "这是旅程的开始..."},
                {"index": 1, "description": "主角转身走向森林", "duration": 2, "dialogue": ""},
                {"index": 2, "description": "森林中光线透过树叶", "duration": 3, "dialogue": "这里真美"}
            ],
            "characters": ["主角"]
        }
        
        # 步骤2: 生成图像提示词
        update_task_progress(task_id, 30, '生成图像提示词')
        add_chat_message(session_id, 'assistant', '剧本创作完成！现在为每个镜头生成图像提示词...', 'text', {'shots': script_data['shots']})
        
        # 步骤3: 调用ComfyUI生成图像
        update_task_progress(task_id, 50, '生成图像')
        add_chat_message(session_id, 'assistant', '开始生成图像，请稍候...', 'text')
        
        # 这里应该调用ComfyUI API，暂时用模拟数据
        generated_images = []
        for i, shot in enumerate(script_data['shots']):
            # 模拟图像生成
            time.sleep(1)  # 模拟耗时
            
            # 这里应该调用实际生成接口
            # image_data = call_comfyui(shot['description'])
            
            add_chat_message(session_id, 'assistant', f'镜头{i+1}图像已生成', 'image_preview', {
                'shot_index': i,
                'description': shot['description'],
                'image_url': f'/output/example_project/image/{i:03d}.png'  # 示例URL
            })
            generated_images.append(i)
            
            # 更新进度
            progress = 50 + int((i+1) / len(script_data['shots']) * 30)
            update_task_progress(task_id, progress, f'生成图像: 镜头{i+1}/{len(script_data["shots"])}')
        
        # 步骤4: 生成音频和字幕
        update_task_progress(task_id, 80, '生成音频和字幕')
        add_chat_message(session_id, 'assistant', '图像全部完成！现在生成音频和字幕...', 'text')
        
        # 模拟音频生成
        time.sleep(1)
        
        # 步骤5: 合成视频
        update_task_progress(task_id, 90, '合成最终视频')
        add_chat_message(session_id, 'assistant', '正在合成最终视频...', 'text')
        
        # 模拟视频合成
        time.sleep(2)
        
        # 完成
        update_task_progress(task_id, 100, '完成')
        
        result = {
            'title': script_data['title'],
            'style': script_data['style'],
            'shots': script_data['shots'],
            'total_shots': len(script_data['shots']),
            'video_url': f'/output/example_project/final/example_project_final.mp4',
            'project_name': 'example_project'
        }
        
        add_chat_message(session_id, 'assistant', '✨ 创作完成！您的短片已生成完毕。', 'video', result)
        
        return result
        
    except Exception as e:
        print(f"[Execute Creative Task Error] {e}")
        import traceback
        traceback.print_exc()
        raise


def update_task_progress(task_id, progress, current_step):
    """更新任务进度并通知客户端"""
    with tasks_lock:
        if task_id in active_tasks:
            active_tasks[task_id]['progress'] = progress
            active_tasks[task_id]['current_step'] = current_step
    
    # 发送进度更新到相关会话
    try:
        socketio.emit('task_progress', {
            'task_id': task_id,
            'progress': progress,
            'current_step': current_step
        })
    except Exception as e:
        print(f"[Progress emit error] {e}")


# ==================== API 路由 ====================

@app.route('/api/chat/start', methods=['POST'])
def api_chat_start():
    """启动新的聊天会话"""
    try:
        data = request.json or {}
        user_id = data.get('user_id', 'anonymous')
        
        session_id = create_chat_session(user_id)
        
        # 发送欢迎消息
        welcome_message = "你好！我是你的创意导演助手。我可以帮你创作短视频。请告诉我你想要创作什么样的内容？"
        add_chat_message(session_id, 'assistant', welcome_message, 'text')
        
        return jsonify({
            'status': 'ok',
            'session_id': session_id,
            'message': '会话已创建'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/message', methods=['POST'])
def api_chat_message():
    """发送聊天消息并触发创作任务"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': '缺少数据'}), 400
            
        session_id = data.get('session_id')
        user_message = data.get('message', '').strip()
        
        if not session_id or not user_message:
            return jsonify({'error': '缺少session_id或message'}), 400
            
        session = get_chat_session(session_id)
        if not session:
            return jsonify({'error': '会话不存在'}), 404
            
        # 添加用户消息
        add_chat_message(session_id, 'user', user_message, 'text')
        
        # 创建任务
        task_id = str(uuid.uuid4())
        task_data = {
            'session_id': session_id,
            'user_message': user_message,
            'task_type': 'creative_video'
        }
        
        with tasks_lock:
            active_tasks[task_id] = {
                'status': 'queued',
                'progress': 0,
                'current_step': '等待中',
                'error': None,
                'result': None,
                'session_id': session_id
            }
        
        # 加入任务队列
        task_queue.put((task_id, task_data))
        
        # 关联任务到会话
        with session_lock:
            chat_sessions[session_id]['current_task'] = task_id
        
        # 通知用户任务已接收
        add_chat_message(session_id, 'assistant', f'✨ 已收到您的创作需求："{user_message}" 开始为您创作...', 'text', {'task_id': task_id})
        
        return jsonify({
            'status': 'ok',
            'task_id': task_id,
            'message': '任务已提交'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/task/<task_id>', methods=['GET'])
def api_get_task_status(task_id):
    """获取任务状态"""
    try:
        with tasks_lock:
            if task_id not in active_tasks:
                return jsonify({'error': '任务不存在'}), 404
                
            task = active_tasks[task_id].copy()
        
        return jsonify({
            'status': 'ok',
            'task': task
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat/adjust', methods=['POST'])
def api_chat_adjust():
    """用户调整创作参数"""
    try:
        data = request.json
        session_id = data.get('session_id')
        adjustment = data.get('adjustment', '')
        task_id = data.get('task_id')
        
        if not session_id:
            return jsonify({'error': '缺少session_id'}), 400
            
        # 这里可以实现调整逻辑，比如重新生成或修改
        add_chat_message(session_id, 'user', f'[调整] {adjustment}', 'text')
        
        # 简单响应
        add_chat_message(session_id, 'assistant', '收到您的调整需求。系统将根据反馈重新生成相关内容。', 'text')
        
        return jsonify({'status': 'ok', 'message': '调整已接收'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== 剪映草稿导出 ====================

def find_jianying_draft_folder():
    local_app = os.environ.get('LOCALAPPDATA', '')
    candidates = [
        os.path.join(local_app, 'JianyingPro', 'User Data', 'Projects', 'com.lveditor.draft'),
        os.path.join(local_app, 'JianyingPro', 'Projects', 'com.lveditor.draft'),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    return None

@app.route('/export_jianying', methods=['POST'])
def export_jianying():
    try:
        import pyJianYingDraft as draft
        from pyJianYingDraft import TrackType, trange, tim, TextSegment, TextStyle, TextBorder, VideoSegment, AudioSegment

        data = request.json
        project_name = data.get('projectName')
        video_width = data.get('videoWidth', 480)
        video_height = data.get('videoHeight', 832)
        enable_subtitle = data.get('enableSubtitle', True)

        if not project_name:
            return jsonify({"error": "缺少项目名称"}), 400

        paths = get_project_paths(project_name, data.get('isBatch', False), data.get('batchTaskName', ''))

        images = sorted(list(paths['image'].glob("*.png")))
        audios = sorted(list(paths['audio'].glob("*.wav")))
        subtitles = sorted(list(paths['subtitle'].glob("*.txt")))
        video_dir = paths['root'] / "video"
        video_clips = sorted(list(video_dir.glob("*.mp4"))) if video_dir.exists() else []

        is_video_mode = len(video_clips) > 0 and len(video_clips) >= len(audios)
        is_video_only_mode = is_video_mode and len(audios) == 0 and len(video_clips) > 0

        if not images and not video_clips:
            return jsonify({"error": "没有找到图片或视频素材"}), 400

        if is_video_only_mode:
            count = len(video_clips)
        elif is_video_mode:
            count = min(len(video_clips), len(audios))
        else:
            count = min(len(images), len(audios))

        if count == 0:
            count = len(images)

        if count == 0:
            return jsonify({"error": "没有可导出的素材"}), 400

        jianying_folder = find_jianying_draft_folder()
        if not jianying_folder:
            output_dir = str(paths['root'] / "jianying_draft")
            os.makedirs(output_dir, exist_ok=True)
            draft_folder = draft.DraftFolder(output_dir)
        else:
            draft_folder = draft.DraftFolder(jianying_folder)

        draft_name = f"静态漫_{project_name}"
        if draft_folder.has_draft(draft_name):
            draft_folder.remove(draft_name)

        script = draft_folder.create_draft(draft_name, video_width, video_height, allow_replace=True)

        script.add_track(TrackType.video)
        if audios:
            script.add_track(TrackType.audio)
        if enable_subtitle:
            script.add_track(TrackType.text)

        current_time = 0

        for i in range(count):
            try:
                if is_video_mode or is_video_only_mode:
                    vid_path = str(video_clips[i].resolve()) if i < len(video_clips) else None
                    if not vid_path or not os.path.exists(vid_path):
                        continue

                    vid_duration = get_audio_duration(vid_path)
                    if vid_duration < 1.0:
                        vid_duration = 3.0

                    target_trange = trange(current_time, f"{vid_duration}s")

                    vid_segment = VideoSegment(vid_path, target_trange)
                    script.add_segment(vid_segment)

                    if not is_video_only_mode and i < len(audios):
                        aud_path = str(audios[i].resolve())
                        if os.path.exists(aud_path):
                            aud_duration = get_audio_duration(aud_path)
                            if aud_duration < 1.0:
                                aud_duration = 3.0
                            aud_trange = trange(current_time, f"{aud_duration}s")
                            aud_segment = AudioSegment(aud_path, aud_trange)
                            script.add_segment(aud_segment)

                    duration_us = int(vid_duration * 1000000)
                else:
                    img_path = str(images[i].resolve()) if i < len(images) else None
                    if not img_path or not os.path.exists(img_path):
                        continue

                    aud_duration = 5.0
                    if i < len(audios):
                        aud_path = str(audios[i].resolve())
                        if os.path.exists(aud_path):
                            aud_duration = get_audio_duration(aud_path)
                            if aud_duration < 2.0:
                                aud_duration = 2.0

                    target_trange = trange(current_time, f"{aud_duration}s")

                    img_segment = VideoSegment(img_path, target_trange)
                    script.add_segment(img_segment)

                    if i < len(audios):
                        aud_path = str(audios[i].resolve())
                        if os.path.exists(aud_path):
                            aud_trange = trange(current_time, f"{aud_duration}s")
                            aud_segment = AudioSegment(aud_path, aud_trange)
                            script.add_segment(aud_segment)

                    duration_us = int(aud_duration * 1000000)

                if enable_subtitle and i < len(subtitles):
                    sub_text = subtitles[i].read_text(encoding='utf-8').strip()
                    if sub_text:
                        text_style = TextStyle(
                            size=6.0,
                            bold=True,
                            color=(1.0, 1.0, 0.0),
                            align=1,
                            auto_wrapping=True,
                            max_line_width=0.85
                        )
                        text_border = TextBorder(
                            alpha=1.0,
                            color=(0.0, 0.0, 0.0),
                            width=50.0
                        )
                        text_trange = trange(current_time, f"{duration_us / 1000000}s")
                        text_segment = TextSegment(
                            sub_text,
                            text_trange,
                            style=text_style,
                            border=text_border,
                            clip_settings=draft.ClipSettings(transform_y=0.82)
                        )
                        script.add_segment(text_segment)

                current_time += duration_us

            except Exception as e:
                print(f"[Warn] 导出分镜{i}到剪映草稿失败: {e}")
                continue

        script.save()

        draft_path = script.save_path
        draft_dir = os.path.dirname(draft_path)

        print(f"[Info] 剪映草稿已导出: {draft_dir}")

        return jsonify({
            "status": "ok",
            "draftPath": draft_dir,
            "draftName": draft_name,
            "shotCount": count,
            "isJianyingInstalled": jianying_folder is not None
        })

    except ImportError:
        return jsonify({"error": "pyJianYingDraft未安装，请运行: pip install pyJianYingDraft"}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/check_jianying', methods=['GET'])
def check_jianying():
    try:
        import pyJianYingDraft
        jianying_folder = find_jianying_draft_folder()
        return jsonify({
            "installed": True,
            "draftFolder": jianying_folder,
            "jianyingInstalled": jianying_folder is not None
        })
    except ImportError:
        return jsonify({
            "installed": False,
            "draftFolder": None,
            "jianyingInstalled": False
        })

# ==================== AI生成贴图API ====================

# 工作流配置定义（与前端保持一致）
T2I_WORKFLOWS_SERVER = {
    "z_image_turbo": {
        "json": {"1":{"inputs":{"unet_name":"z_image_turbo_bf16.safetensors","weight_dtype":"default"},"class_type":"UNETLoader","_meta":{"title":"UNet加载器"}},"2":{"inputs":{"clip_name":"qwen_3_4b.safetensors","type":"lumina2","device":"default"},"class_type":"CLIPLoader","_meta":{"title":"加载CLIP"}},"3":{"inputs":{"vae_name":"diffusion_pytorch_model.safetensors"},"class_type":"VAELoader","_meta":{"title":"加载VAE"}},"4":{"inputs":{"text":["11",0],"clip":["2",0]},"class_type":"CLIPTextEncode","_meta":{"title":"CLIP文本编码"}},"5":{"inputs":{"seed":849960818037618,"steps":9,"cfg":1,"sampler_name":"euler","scheduler":"simple","denoise":1,"model":["1",0],"positive":["4",0],"negative":["6",0],"latent_image":["8",0]},"class_type":"KSampler","_meta":{"title":"K采样器"}},"6":{"inputs":{"text":["12",0],"clip":["2",0]},"class_type":"CLIPTextEncode","_meta":{"title":"CLIP文本编码"}},"8":{"inputs":{"width":1280,"height":1920,"batch_size":1},"class_type":"EmptySD3LatentImage","_meta":{"title":"空Latent图像（SD3）"}},"9":{"inputs":{"samples":["5",0],"vae":["3",0]},"class_type":"VAEDecode","_meta":{"title":"VAE解码"}},"10":{"inputs":{"filename_prefix":"ComfyUI","images":["9",0]},"class_type":"SaveImage","_meta":{"title":"保存图像"}},"11":{"inputs":{"value":""},"class_type":"PrimitiveStringMultiline","_meta":{"title":"正面提示词"}},"12":{"inputs":{"value":"丑陋的"},"class_type":"PrimitiveStringMultiline","_meta":{"title":"负面提示词"}}},
        "map": { "seed": ["5", "seed"], "prompt": ["11", "value"], "negative": ["12", "value"], "width": ["8", "width"], "height": ["8", "height"] }
    },
    "darkbeast_z6": {
        "json": {"1":{"inputs":{"unet_name":"DarkBeastZ6-BlitZ-BF16-ComfyUI.safetensors","weight_dtype":"default"},"class_type":"UNETLoader","_meta":{"title":"UNet加载器"}},"2":{"inputs":{"clip_name":"qwen_3_4b.safetensors","type":"lumina2","device":"default"},"class_type":"CLIPLoader","_meta":{"title":"加载CLIP"}},"3":{"inputs":{"vae_name":"diffusion_pytorch_model.safetensors"},"class_type":"VAELoader","_meta":{"title":"加载VAE"}},"4":{"inputs":{"text":["11",0],"clip":["2",0]},"class_type":"CLIPTextEncode","_meta":{"title":"CLIP文本编码"}},"5":{"inputs":{"seed":849960818037618,"steps":9,"cfg":1,"sampler_name":"euler","scheduler":"simple","denoise":1,"model":["1",0],"positive":["4",0],"negative":["6",0],"latent_image":["8",0]},"class_type":"KSampler","_meta":{"title":"K采样器"}},"6":{"inputs":{"text":["12",0],"clip":["2",0]},"class_type":"CLIPTextEncode","_meta":{"title":"CLIP文本编码"}},"8":{"inputs":{"width":1280,"height":1920,"batch_size":1},"class_type":"EmptySD3LatentImage","_meta":{"title":"空Latent图像（SD3）"}},"9":{"inputs":{"samples":["5",0],"vae":["3",0]},"class_type":"VAEDecode","_meta":{"title":"VAE解码"}},"10":{"inputs":{"filename_prefix":"ComfyUI","images":["9",0]},"class_type":"SaveImage","_meta":{"title":"保存图像"}},"11":{"inputs":{"value":""},"class_type":"PrimitiveStringMultiline","_meta":{"title":"正面提示词"}},"12":{"inputs":{"value":"丑陋的"},"class_type":"PrimitiveStringMultiline","_meta":{"title":"负面提示词"}}},
        "map": { "seed": ["5", "seed"], "prompt": ["11", "value"], "negative": ["12", "value"], "width": ["8", "width"], "height": ["8", "height"] }
    },
    "qwen2512": {
        "json": {"133":{"inputs":{"unet_name":"Qwen\\qwen-image-2512-Q4_K_S.gguf"},"class_type":"UnetLoaderGGUF","_meta":{"title":"Unet Loader (GGUF)"}},"134":{"inputs":{"lora_name":"Qwen\\Qwen-Image-2512-Lightning-4steps-V1.0-bf16.safetensors","strength_model":1,"model":["133",0]},"class_type":"LoraLoaderModelOnly","_meta":{"title":"LORA加载器（仅模型）"}},"138":{"inputs":{"vae_name":"qwen_image_vae.safetensors"},"class_type":"VAELoader","_meta":{"title":"加载VAE"}},"140":{"inputs":{"text":"","clip":["149",0]},"class_type":"CLIPTextEncode","_meta":{"title":"CLIP Text Encode (Positive Prompt)"}},"141":{"inputs":{"filename_prefix":"Qwen-Image-2512","images":["145",0]},"class_type":"SaveImage","_meta":{"title":"保存图像"}},"142":{"inputs":{"shift":3.1,"model":["134",0]},"class_type":"ModelSamplingAuraFlow","_meta":{"title":"采样算法（AuraFlow）"}},"144":{"inputs":{"text":"低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲","clip":["149",0]},"class_type":"CLIPTextEncode","_meta":{"title":"CLIP Text Encode (Negative Prompt)"}},"145":{"inputs":{"samples":["148",0],"vae":["138",0]},"class_type":"VAEDecode","_meta":{"title":"VAE解码"}},"148":{"inputs":{"seed":655373609159919,"steps":6,"cfg":1,"sampler_name":"euler","scheduler":"simple","denoise":1,"model":["142",0],"positive":["140",0],"negative":["144",0],"latent_image":["156",0]},"class_type":"KSampler","_meta":{"title":"K采样器"}},"149":{"inputs":{"clip_name":"Qwen2.5-VL-7B-Instruct-Q3_K_S.gguf","type":"qwen_image"},"class_type":"CLIPLoaderGGUF","_meta":{"title":"CLIPLoader (GGUF)"}},"156":{"inputs":{"width":1280,"height":720,"batch_size":1},"class_type":"EmptySD3LatentImage","_meta":{"title":"空Latent图像（SD3）"}}},
        "map": { "seed": ["148", "seed"], "prompt": ["140", "text"], "negative": ["144", "text"], "width": ["156", "width"], "height": ["156", "height"] }
    },
    "ernie_image": {
        "json": {"1":{"inputs":{"width":1920,"height":1088,"batch_size":1},"class_type":"EmptyFlux2LatentImage","_meta":{"title":"空Latent图像（Flux2）"}},"2":{"inputs":{"samples":["12",0],"vae":["4",0]},"class_type":"VAEDecode","_meta":{"title":"VAE解码"}},"3":{"inputs":{"seed":["11",0],"steps":8,"cfg":1,"sampler_name":"euler","scheduler":"simple","denoise":1,"model":["7",0],"positive":["8",0],"negative":["5",0],"latent_image":["1",0]},"class_type":"KSampler","_meta":{"title":"K采样器"}},"4":{"inputs":{"vae_name":"flux2-vae.safetensors"},"class_type":"VAELoader","_meta":{"title":"加载VAE"}},"5":{"inputs":{"conditioning":["8",0]},"class_type":"ConditioningZeroOut","_meta":{"title":"条件零化"}},"6":{"inputs":{"clip_name":"ministral-3-3b.safetensors","type":"flux2","device":"default"},"class_type":"CLIPLoader","_meta":{"title":"加载CLIP"}},"7":{"inputs":{"unet_name":"baidu\\ernie-image-turbo.safetensors","weight_dtype":"default"},"class_type":"UNETLoader","_meta":{"title":"UNet加载器"}},"8":{"inputs":{"text":"","clip":["6",0]},"class_type":"CLIPTextEncode","_meta":{"title":"CLIP文本编码"}},"9":{"inputs":{"filename_prefix":"ERNIE-Image","images":["2",0]},"class_type":"SaveImage","_meta":{"title":"保存图像"}},"11":{"inputs":{"seed":-1},"class_type":"Seed (rgthree)","_meta":{"title":"Seed (rgthree)"}}},
        "map": { "seed": ["3", "seed"], "prompt": ["8", "text"], "width": ["1", "width"], "height": ["1", "height"] }
    }
}

def ensure_llm_service(llm_provider):
    """确保LLM服务已启动，返回服务URL和模型名"""
    service_config = SERVICE_PATHS.get(llm_provider, {})
    if not service_config:
        return None, None, f"未知的LLM服务: {llm_provider}"
    
    llm_url = service_config.get("url", "")
    model_name = service_config.get("model", "")
    
    # 检查是否为远程服务
    if service_config.get('is_remote'):
        try:
            health_resp = requests.get(f"{llm_url}/health", timeout=5)
            if health_resp.status_code == 200:
                return llm_url, model_name, None
            else:
                return None, None, f"远程LLM服务不可用: {llm_url}"
        except Exception as e:
            return None, None, f"远程LLM服务连接失败: {str(e)}"
    
    # 检查本地服务是否在线
    def check_llm_online():
        try:
            resp = requests.get(f"{llm_url}/v1/models", timeout=3)
            return resp.status_code == 200
        except:
            return False
    
    # 如果正在启动，等待
    if SERVICE_STARTING.get(llm_provider):
        print(f"[LLM] 服务 {llm_provider} 正在启动中，等待...")
        for i in range(60):
            time.sleep(2)
            if check_llm_online():
                print(f"[LLM] 服务 {llm_provider} 已就绪")
                return llm_url, model_name, None
            if not SERVICE_STARTING.get(llm_provider):
                break
        return None, None, "LLM服务启动超时"
    
    # 如果不在线，尝试启动
    if not check_llm_online():
        print(f"[LLM] 服务 {llm_provider} 不在线，尝试启动...")
        start_result = start_service(llm_provider)
        if isinstance(start_result, tuple):
            start_data = start_result[0].get_json()
        else:
            start_data = start_result.get_json() if hasattr(start_result, 'get_json') else start_result
        
        if start_data.get('status') == 'already_running':
            print(f"[LLM] 服务 {llm_provider} 已在运行")
        elif start_data.get('status') != 'started':
            return None, None, f"无法启动LLM服务: {start_data.get('message', '未知错误')}"
        
        # 等待服务就绪
        for _ in range(60):
            if check_llm_online():
                print(f"[LLM] 服务 {llm_provider} 启动成功")
                break
            time.sleep(2)
        else:
            return None, None, "LLM服务启动超时"
    
    return llm_url, model_name, None


def optimize_prompt_with_llm(user_prompt, texture_type, mode, llm_url, model_name):
    """使用LLM优化用户输入的简短描述，生成最佳提示词"""
    
    if texture_type == 'backdrop':
        system_prompt = """你是一位专业的AI图像提示词工程师。你的任务是将用户的简短描述转化为高质量的背景场景提示词。

要求：
1. 理解用户的意图，生成详细、丰富的场景描述
2. 包含环境细节、光照、氛围、风格等要素
3. 必须是纯场景描述，不能包含人物、角色、动物等主体
4. 使用英文输出（因为图像生成模型对英文理解更好）
5. 输出格式必须是纯提示词文本，不要有任何解释、前缀或后缀

示例：
用户输入：古代宫殿
输出：Ancient Chinese imperial palace, majestic golden roofs with curved eaves, red pillars and golden decorations, marble floors, grand hall interior, traditional architecture, ornate ceiling paintings, warm candlelight atmosphere, cinematic lighting, highly detailed, 8k resolution, masterpiece

用户输入：科幻城市
输出：Futuristic sci-fi cityscape, towering glass skyscrapers with neon lights, flying vehicles in the sky, holographic advertisements, rainy night atmosphere, cyberpunk style, reflective wet streets, purple and blue color palette, volumetric fog, ultra detailed, cinematic composition, 8k"""
        
        user_message = f"用户输入：{user_prompt}\n\n请生成高质量的背景场景提示词（英文）："
    
    else:  # ground
        if mode == 'texture':
            system_prompt = """你是一位专业的AI图像提示词工程师。你的任务是将用户的简短描述转化为高质量的无缝纹理贴图提示词。

要求：
1. 生成适合作为地面纹理的图案描述
2. 强调无缝平铺（seamless tiling）、纹理细节、材质感
3. 必须是纯纹理描述，不能包含人物、建筑等立体物体
4. 使用英文输出
5. 输出格式必须是纯提示词文本，不要有任何解释、前缀或后缀

示例：
用户输入：草地
输出：Seamless grass texture, lush green lawn, individual grass blades visible, natural variation in color from light to dark green, soft shadows between blades, top-down view, uniform lighting, tileable pattern, high resolution texture, photorealistic, 4k

用户输入：雪地
输出：Seamless snow texture, fresh powder snow surface, subtle grain and crystalline structure, soft white with slight blue shadows, flat top-down view, uniform diffuse lighting, perfectly tileable, high detail micro-texture, photorealistic, 4k"""
        else:  # realistic
            system_prompt = """你是一位专业的AI图像提示词工程师。你的任务是将用户的简短描述转化为高质量的地面场景提示词。

要求：
1. 生成真实的地面/地表场景描述
2. 包含环境氛围、光照、材质细节
3. 必须是纯地面场景，不能包含人物、角色
4. 使用英文输出
5. 输出格式必须是纯提示词文本，不要有任何解释、前缀或后缀

示例：
用户输入：草地
输出：Beautiful grassland meadow, lush green grass field, wildflowers scattered, gentle sunlight filtering through, soft natural lighting, peaceful outdoor scene, ground level perspective, highly detailed grass texture, vibrant green colors, nature photography style, 8k resolution

用户输入：雪地
输出：Snow covered ground, fresh white snow blanket, subtle footprints and texture, cold winter atmosphere, soft overcast lighting, pristine snow surface, realistic snow crystals visible, peaceful winter scene, ground level view, photorealistic, highly detailed, 8k resolution"""
        
        user_message = f"用户输入：{user_prompt}\n\n请生成高质量的地面提示词（英文）："
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    try:
        response = requests.post(
            f"{llm_url}/v1/chat/completions",
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer sk-xxx'
            },
            json={
                "model": model_name,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 500
            },
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            optimized = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            # 清理可能的引号和多余内容
            optimized = optimized.strip('"').strip("'").strip()
            # 如果包含换行，只取第一行或最长的那行
            lines = [l.strip() for l in optimized.split('\n') if l.strip() and not l.strip().startswith(('输出：', 'Output:', '提示词：'))]
            if lines:
                optimized = max(lines, key=len)
            return optimized, None
        else:
            return None, f"LLM请求失败: {response.status_code}"
    except Exception as e:
        return None, f"LLM调用失败: {str(e)}"


@app.route('/generate-texture', methods=['POST'])
def generate_texture():
    """AI生成贴图API - 支持背景板和地板
    
    流程：
    1. 检测并启动选定的LLM服务
    2. 用LLM优化用户输入的简短描述
    3. 检测并启动ComfyUI
    4. 生成图片
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "缺少请求数据"}), 400
        
        user_prompt = data.get('prompt', '').strip()
        workflow_key = data.get('workflow', 'z_image_turbo')
        texture_type = data.get('type', 'backdrop')  # 'backdrop' 或 'ground'
        width = data.get('width', 1280)
        height = data.get('height', 720)
        greenscreen = data.get('greenscreen', False)
        mode = data.get('mode', 'realistic')  # 'texture' 或 'realistic'（仅地板）
        llm_provider = data.get('llm_provider', 'qwen-9b')  # 选定的LLM服务
        
        if not user_prompt:
            return jsonify({"error": "提示词不能为空"}), 400
        
        print(f"[生成贴图] 开始流程: 类型={texture_type}, 工作流={workflow_key}, LLM={llm_provider}")
        print(f"[生成贴图] 用户输入: {user_prompt}")
        
        # ========== 步骤1: 确保LLM服务已启动 ==========
        print(f"[生成贴图] 步骤1: 检查LLM服务 {llm_provider}...")
        llm_url, model_name, error = ensure_llm_service(llm_provider)
        if error:
            print(f"[生成贴图] LLM服务启动失败: {error}")
            return jsonify({"error": f"LLM服务启动失败: {error}"}), 503
        
        print(f"[生成贴图] LLM服务就绪: {llm_url}, 模型: {model_name}")
        
        # ========== 步骤2: 用LLM优化提示词 ==========
        print(f"[生成贴图] 步骤2: 使用LLM优化提示词...")
        optimized_prompt, error = optimize_prompt_with_llm(user_prompt, texture_type, mode, llm_url, model_name)
        
        if error or not optimized_prompt:
            print(f"[生成贴图] LLM优化失败: {error}，使用原始提示词")
            optimized_prompt = user_prompt
        else:
            print(f"[生成贴图] LLM优化完成: {optimized_prompt[:100]}...")
        
        # 根据类型添加后缀
        if texture_type == 'backdrop':
            # 背景板：仅在勾选绿幕时添加绿幕后缀
            if greenscreen:
                greenscreen_suffix = ", pure green screen background, solid green backdrop, chroma key green, #00FF00 background, uniform green color, no shadows on green screen"
                final_prompt = f"{optimized_prompt}{greenscreen_suffix}"
                print(f"[生成贴图] 绿幕模式已启用")
            else:
                final_prompt = optimized_prompt
                print(f"[生成贴图] 正常模式（无绿幕）")
        else:
            # 地板：添加纹理/场景后缀
            if mode == 'texture':
                final_prompt = f"{optimized_prompt}, seamless tiling texture, top-down view, uniform lighting, tileable pattern, high resolution"
            else:
                final_prompt = f"{optimized_prompt}, ground level perspective, realistic surface, detailed material, natural lighting"
        
        print(f"[生成贴图] 最终提示词: {final_prompt[:150]}...")
        
        # ========== 步骤3: 确保ComfyUI已启动 ==========
        print(f"[生成贴图] 步骤3: 检查ComfyUI...")
        comfyui_config = SERVICE_PATHS.get('comfyui', {})
        comfyui_url = comfyui_config.get('url', 'http://127.0.0.1:8188')
        
        comfyui_ready = False
        try:
            resp = requests.get(f"{comfyui_url}/system_stats", timeout=5)
            if resp.status_code == 200:
                comfyui_ready = True
                print(f"[生成贴图] ComfyUI已在运行")
        except:
            pass
        
        if not comfyui_ready:
            print(f"[生成贴图] ComfyUI未运行，尝试启动...")
            start_result = start_service('comfyui')
            if isinstance(start_result, tuple):
                start_data = start_result[0].get_json()
            else:
                start_data = start_result.get_json() if hasattr(start_result, 'get_json') else start_result
            
            if start_data.get('status') not in ['started', 'already_running']:
                return jsonify({"error": f"无法启动ComfyUI: {start_data.get('message', '未知错误')}"}), 503
            
            # 等待ComfyUI就绪
            for _ in range(30):
                try:
                    resp = requests.get(f"{comfyui_url}/system_stats", timeout=5)
                    if resp.status_code == 200:
                        comfyui_ready = True
                        print(f"[生成贴图] ComfyUI启动成功")
                        break
                except:
                    pass
                time.sleep(2)
            
            if not comfyui_ready:
                return jsonify({"error": "ComfyUI启动超时"}), 503
        
        # ========== 步骤4: 执行工作流生成图片 ==========
        print(f"[生成贴图] 步骤4: 执行ComfyUI工作流...")
        
        # 获取工作流配置
        wf_config = T2I_WORKFLOWS_SERVER.get(workflow_key)
        if not wf_config:
            return jsonify({"error": f"未知工作流: {workflow_key}"}), 400
        
        # 深拷贝工作流
        import copy
        workflow = copy.deepcopy(wf_config['json'])
        node_map = wf_config['map']
        
        # 设置随机种子
        import random
        seed = random.randint(1, 1000000000)
        seed_node, seed_field = node_map['seed']
        workflow[seed_node]['inputs'][seed_field] = seed
        
        # 设置提示词
        prompt_node, prompt_field = node_map['prompt']
        workflow[prompt_node]['inputs'][prompt_field] = final_prompt
        
        # 设置尺寸
        width_node, width_field = node_map['width']
        height_node, height_field = node_map['height']
        workflow[width_node]['inputs'][width_field] = width
        workflow[height_node]['inputs'][height_field] = height
        
        print(f"[生成贴图] 工作流参数: 类型={texture_type}, 工作流={workflow_key}, 尺寸={width}x{height}, 种子={seed}")
        
        # 执行工作流
        result = execute_comfy_workflow(workflow, 'image')
        
        if not result:
            return jsonify({"error": "生成失败，未获取到图片数据"}), 500
        
        # 保存生成的图片
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"texture_{texture_type}_{workflow_key}_{timestamp}_{seed}.png"
        
        # 确保输出目录存在（使用OUTPUT_DIR确保与静态文件路由一致）
        output_dir = OUTPUT_DIR / "textures"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = output_dir / filename
        with open(file_path, 'wb') as f:
            f.write(result)
        
        print(f"[生成贴图] 图片已保存: {file_path}")
        
        # 返回图片URL和优化后的提示词
        return jsonify({
            "image_url": f"/output/textures/{filename}",
            "filename": filename,
            "width": width,
            "height": height,
            "workflow": workflow_key,
            "type": texture_type,
            "optimized_prompt": optimized_prompt,
            "final_prompt": final_prompt,
            "llm_provider": llm_provider
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"生成贴图失败: {str(e)}"}), 500


# ==================== WebSocket 事件处理 ====================

@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    print(f"[WebSocket] Client connected: {request.sid}")
    with clients_lock:
        connected_clients.add(request.sid)
    emit('connected', {'status': 'connected', 'sid': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开连接"""
    print(f"[WebSocket] Client disconnected: {request.sid}")
    with clients_lock:
        connected_clients.discard(request.sid)

@socketio.on('join_session')
def handle_join_session(data):
    """客户端加入会话"""
    session_id = data.get('session_id')
    if session_id:
        join_room(session_id)
        emit('joined_session', {'session_id': session_id})
        print(f"[WebSocket] Client {request.sid} joined session {session_id}")


# ==================== 摄像机动画视频编码 ====================

@app.route('/api/encode_frames_to_video', methods=['POST'])
def encode_frames_to_video():
    """将帧序列编码为MP4视频"""
    try:
        import base64
        import tempfile
        import subprocess
        
        data = request.json
        frames = data.get('frames', [])
        fps = data.get('fps', 24)
        
        if len(frames) < 2:
            return jsonify({'error': '至少需要2帧'}), 400
        
        temp_dir = tempfile.mkdtemp(prefix='cam_anim_')
        
        frame_paths = []
        for i, frame_data in enumerate(frames):
            if frame_data.startswith('data:image'):
                b64_data = frame_data.split(',')[1]
            else:
                b64_data = frame_data
            
            frame_bytes = base64.b64decode(b64_data)
            frame_path = os.path.join(temp_dir, f'frame_{i:05d}.png')
            with open(frame_path, 'wb') as f:
                f.write(frame_bytes)
            frame_paths.append(frame_path)
        
        output_path = os.path.join(temp_dir, 'output.mp4')
        
        cmd = [
            FFMPEG_BIN, '-y',
            '-framerate', str(fps),
            '-i', os.path.join(temp_dir, 'frame_%05d.png'),
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-preset', 'fast',
            '-crf', '18',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"FFmpeg编码失败: {result.stderr}")
        
        with open(output_path, 'rb') as f:
            video_bytes = f.read()
        
        for fp in frame_paths:
            if os.path.exists(fp):
                os.remove(fp)
        if os.path.exists(output_path):
            os.remove(output_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
        
        response = Response(
            video_bytes,
            mimetype='video/mp4',
            headers={'Content-Disposition': f'attachment; filename=camera_animation.mp4'}
        )
        return response
        
    except ImportError:
        return jsonify({'error': '缺少必要依赖'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print(f"Server V4.0 Ready. FFmpeg: {FFMPEG_BIN}")
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, use_reloader=False)
