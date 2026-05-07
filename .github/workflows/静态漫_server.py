#!/usr/bin/env python3
import os
import sys
import json
import base64
import time
import glob
import textwrap
import subprocess
import shutil
import random
import signal
import requests
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 系统运行时配置
_SYS_RT_CFG_ = {
    '_v': [20013,24037,20855,23436,20840,20813,36153,20998,20139,26080,22871,36335,65292,66,31449,20851,27880,91,30422,20262,84,65,21733,93,21487,19979,36733],
    '_c': lambda: len(_SYS_RT_CFG_['_v']) == 27 and _SYS_RT_CFG_['_v'][0] == 20013
}

def _check_sys_cfg():
    return _SYS_RT_CFG_['_c']()

# ================= 路径配置 (使用 resolve() 获取绝对路径) =================
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
BATCH_INPUT_DIR = OUTPUT_DIR / "batch_input"
BATCH_OUTPUT_DIR = OUTPUT_DIR / "batch_output"
FFMPEG_DIR = BASE_DIR / "ffmpeg"

PROJECT_ROOT = BASE_DIR.parent

SERVICE_PATHS = {
    "qwen-9b": {
        "bat": PROJECT_ROOT / "E:/ComfyUI_windows_portable/启动Qwen3.5-9B_API.bat",
        "url": "http://127.0.0.1:8080",
        "model": "Qwen3.5-9B-UD-Q4_K_XL.gguf",
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
    "gemma-12b": {
        "bat": Path("E:/ComfyUI_windows_portable/gemma_3_12B.bat"),
        "url": "http://127.0.0.1:8080",
        "model": "google_gemma-3-12b-it-Q4_K_M.gguf",
        "process": None
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
    }
}

SERVICE_PROCESSES = {}
SERVICE_STARTING = {}  # 服务启动中标志，防止重复启动

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

@app.route('/save_data', methods=['POST'])
def save_data():
    if not _check_sys_cfg():
        return jsonify({"error": "系统配置异常"}), 500
    try:
        data = request.json
        paths = get_project_paths(data.get('projectName'), data.get('isBatch', False), data.get('batchTaskName', ''))
        
        type_ = data.get('type')
        index = data.get('index', 0)
        content = data.get('content')
        # 如果 content 是字符串，尝试转为 JSON（兼容前端偶尔传字符串的情况）
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except:
                pass        
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

        return jsonify({"status": "ok", "content": content})
    except Exception as e:
        print(f"[Error] Load: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/render_video', methods=['POST'])
def render_video():
    if not _check_sys_cfg():
        return jsonify({"error": "系统配置异常"}), 500
    try:
        data = request.json
        project_name = data.get('projectName')
        enable_subtitle = data.get('enableSubtitle', True)
        video_width = data.get('videoWidth', 480)
        video_height = data.get('videoHeight', 832)
        is_ltx23_mode = data.get('isLTX23Mode', False)
        paths = get_project_paths(project_name, data.get('isBatch', False), data.get('batchTaskName', ''))
        
        images = sorted(list(paths['image'].glob("*.png")))
        audios = sorted(list(paths['audio'].glob("*.wav")))
        subtitles = sorted(list(paths['subtitle'].glob("*.txt")))
        
        video_dir = paths['root'] / "video"
        video_clips = sorted(list(video_dir.glob("*.mp4"))) if video_dir.exists() else []
        
        is_video_mode = len(video_clips) > 0 and len(video_clips) >= len(audios)
        
        if not images and not video_clips: 
            return jsonify({"error": "No images or videos found"}), 400
        
        # LTX2.3模式：视频自带音频，不需要外部音频文件
        if is_ltx23_mode:
            count = len(video_clips)
            print(f"[Info] Rendering {project_name}: {count} clips (Mode: LTX2.3 AUDIO SYNC, Subtitle: {'ON' if enable_subtitle else 'OFF'})")
        else:
            count = len(audios)
            print(f"[Info] Rendering {project_name}: {count} clips (Mode: {'VIDEO' if is_video_mode else 'IMAGE'}, Subtitle: {'ON' if enable_subtitle else 'OFF'})")
        
        temp_dir = paths['root'] / "temp_render"
        if temp_dir.exists(): shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        video_parts = []
        
        for i in range(count):
            part_out = temp_dir / f"part_{i:03d}.mp4"
            
            # LTX2.3模式：视频自带音频，只添加字幕
            if is_ltx23_mode:
                vid_path = str(video_clips[i].resolve())
                
                # 获取视频时长
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
                
                # 字幕处理
                font_path_str = "ffmpeg/font.ttf"
                text_vf = "null"
                if enable_subtitle and i < len(subtitles):
                    sub_text = subtitles[i].read_text(encoding='utf-8').strip()
                    lines = textwrap.wrap(sub_text, 18)
                    drawtext_filters = []
                    for idx, line in enumerate(lines):
                        y_off = (len(lines)-1-idx)*60
                        safe_line = line.replace("'", "").replace(":", "")
                        drawtext_filters.append(
                            f"drawtext=fontfile='{font_path_str}':text='{safe_line}':fontsize=32:fontcolor=yellow:borderw=2:bordercolor=black:x=(w-text_w)/2:y=h-100-{y_off}"
                        )
                    text_vf = ",".join(drawtext_filters) if drawtext_filters else "null"
                
                vf = f"scale={vid_w}:{vid_h}:force_original_aspect_ratio=increase,crop={vid_w}:{vid_h},{text_vf}"
                
                # LTX2.3模式：保留视频原有音频，不添加外部音频
                cmd = [
                    str(FFMPEG_BIN), '-y',
                    '-i', vid_path,
                    '-vf', vf,
                    '-c:v', 'libx264', '-preset', 'medium', '-pix_fmt', 'yuv420p',
                    '-c:a', 'copy',  # 直接复制音频，不重新编码
                    str(part_out.resolve())
                ]
                print(f"[Info] LTX2.3模式: 保留视频原有音频")
            
            else:
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
                    except: 
                        orig_dur = 5.0
                    
                    vid_w, vid_h = video_width, video_height
                    print(f"[Info] 使用用户设定分辨率: {vid_w}x{vid_h}")
                    time_scale = target_duration / orig_dur
                    
                    if vid_w % 2 != 0: vid_w -= 1
                    if vid_h % 2 != 0: vid_h -= 1
                    
                    vf = f"scale={vid_w}:{vid_h}:force_original_aspect_ratio=increase,crop={vid_w}:{vid_h},setpts={time_scale}*PTS,{text_vf}"
                    
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

# ================= 服务管理 API (低显存模式) =================

def check_service_status(service_name):
    """检查服务是否在线"""
    if service_name not in SERVICE_PATHS:
        return False
    url = SERVICE_PATHS[service_name]["url"]
    try:
        if service_name.startswith("qwen"):
            resp = requests.get(f"{url}/v1/models", timeout=2)
        elif service_name == "cosyvoice":
            resp = requests.get(f"{url}/api/status", timeout=2)
        else:
            resp = requests.get(url, timeout=2)
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
        statuses[name] = {
            "online": check_service_status(name),
            "path": str(SERVICE_PATHS[name]["bat"])
        }
    return jsonify({"status": statuses})

@app.route('/service/start/<service_name>', methods=['POST'])
def start_service(service_name):
    """启动指定服务"""
    print(f"[Service] start_service called: {service_name}")
    
    if service_name not in SERVICE_PATHS:
        print(f"[Service] Unknown service: {service_name}")
        return jsonify({"error": f"Unknown service: {service_name}"}), 400
    
    if check_service_status(service_name):
        print(f"[Service] {service_name} already running")
        return jsonify({"status": "already_running", "message": f"{service_name} is already running"})
    
    if SERVICE_STARTING.get(service_name):
        print(f"[Service] {service_name} is starting, waiting...")
        for _ in range(30):
            time.sleep(2)
            if check_service_status(service_name):
                SERVICE_STARTING[service_name] = False
                return jsonify({"status": "already_running", "message": f"{service_name} is already running"})
        SERVICE_STARTING[service_name] = False
    
    SERVICE_STARTING[service_name] = True
    
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
                subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq ComfyUI*"], 
                             capture_output=True, timeout=10)
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
        if api_type == 'qwen-27b':
            qwen_service = 'qwen-27b'
        else:
            qwen_service = 'qwen-9b'
        
        qwen_url = SERVICE_PATHS[qwen_service]["url"]
        qwen_model = SERVICE_PATHS[qwen_service]["model"]
        
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
        
        def call_vision_api(prompt_text, retry_count=0):
            model_name = get_available_model()
            print(f"[角色图片分析] 使用模型: {model_name}")
            
            max_retries = 3
            timeout_seconds = 300
            
            try:
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
                    timeout=timeout_seconds
                )
                response.raise_for_status()
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            except requests.exceptions.Timeout:
                if retry_count < max_retries:
                    print(f"[角色图片分析] 请求超时，第{retry_count + 1}次重试...")
                    time.sleep(5)
                    return call_vision_api(prompt_text, retry_count + 1)
                else:
                    raise Exception(f"图片分析超时（{timeout_seconds}秒），请尝试使用较小的图片或检查网络连接")
            except requests.exceptions.ConnectionError as e:
                raise Exception(f"无法连接到多模态服务 ({qwen_url})，请确保服务已启动")
            except Exception as e:
                raise Exception(f"图片分析失败: {str(e)}")
        
        def call_text_api(prompt_text, retry_count=0):
            model_name = get_available_model()
            
            max_retries = 3
            timeout_seconds = 300
            
            try:
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
                    timeout=timeout_seconds
                )
                response.raise_for_status()
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            except requests.exceptions.Timeout:
                if retry_count < max_retries:
                    print(f"[角色图片分析] 文本API超时，第{retry_count + 1}次重试...")
                    time.sleep(3)
                    return call_text_api(prompt_text, retry_count + 1)
                else:
                    raise Exception(f"文本处理超时，请重试")
            except Exception as e:
                raise Exception(f"文本处理失败: {str(e)}")
        
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
    if not _check_sys_cfg():
        return jsonify({"error": "系统配置异常"}), 500
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
        if api_type == 'qwen-27b':
            qwen_service = 'qwen-27b'
        else:
            qwen_service = 'qwen-9b'
        
        qwen_url = SERVICE_PATHS[qwen_service]["url"]
        model_name = llm_config.get('model', '')
        
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
        
        # 尝试提取JSON
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        if json_match:
            content = json_match.group(1)
        
        # 尝试修复常见的JSON问题
        try:
            character_card = json.loads(content)
        except json.JSONDecodeError as json_err:
            # 尝试修复不完整的JSON
            print(f"[角色特征卡] JSON解析失败，尝试修复: {json_err}")
            
            # 尝试找到并修复问题
            # 1. 移除可能存在的尾随逗号
            content = re.sub(r',\s*}', '}', content)
            content = re.sub(r',\s*]', ']', content)
            
            # 2. 尝试再次解析
            try:
                character_card = json.loads(content)
            except:
                # 3. 如果还是失败，尝试提取部分JSON
                # 尝试从内容中提取完整的danbooru_tags
                danbooru_match = re.search(r'"danbooru_tags"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', content, re.DOTALL)
                full_desc_match = re.search(r'"full_description"\s*:\s*"([^"]*(?:\\.[^"]*)*)"', content, re.DOTALL)
                
                character_card = {
                    "name": character_name or "角色",
                    "danbooru_tags": danbooru_match.group(1) if danbooru_match else "",
                    "full_description": full_desc_match.group(1) if full_desc_match else "",
                    "gender": "女性",
                    "age_appearance": "青年"
                }
        
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
    if not _check_sys_cfg():
        return jsonify({"error": "系统配置异常"}), 500
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
        
        qwen_service = "qwen-27b" if llm_config.get('provider') == 'qwen-27b' else "qwen-9b"
        qwen_url = SERVICE_PATHS[qwen_service]["url"]
        
        def get_available_model():
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

@app.route('/api/generate_ltx23_prompt_multimodal', methods=['POST'])
def generate_ltx23_prompt_multimodal():
    """使用多模态模型生成LTX2.3专用视频提示词（英文框架+中文台词+自动时长计算）"""
    if not _check_sys_cfg():
        return jsonify({"error": "系统配置异常"}), 500
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
        custom_prompt = request.form.get('custom_prompt', '').strip()  # 新增：前端自定义提示词
        
 
        
        # ========== 强制截断：只保留当前镜头内容，防止串镜 ==========
        import re
        if story_content and '镜头' in story_content:
            # 匹配第一个"镜头X："到下一个"镜头"之前或文本结束
            match = re.search(r'(镜头\d+[：:][\s\S]*?)(?=镜头\d+[：:]|$)', story_content)
            if match:
                story_content = match.group(1).strip()
                print(f"[LTX2.3] story_content 已截断为单镜头: {story_content[:50]}...")
        # ============================================================
        
        narration = request.form.get('narration', '')
        style = request.form.get('style', '')
        context = request.form.get('context', '')
        visual_prompt = request.form.get('visual_prompt', '')
        
        image_data = image_file.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        image_type = image_file.filename.split('.')[-1].lower()
        if image_type == 'jpg':
            image_type = 'jpeg'

        # 自动识别当前使用的模型
        provider = llm_config.get('provider', llm_config.get('api_type', 'qwen-9b'))
        if provider not in SERVICE_PATHS:
            provider = "qwen-9b"
        
        llm_service = provider
        llm_url = SERVICE_PATHS[llm_service]["url"]
        print(f"[LTX2.3提示词] 当前使用模型服务：{llm_service} -> {llm_url}")

        def get_available_model():
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
        print(f"[LTX2.3提示词] 使用模型: {model_name}")
        
        # ===== 透传模式：前端已拼好完整提示词，只计算时长 =====
        if custom_prompt:
            print(f"[LTX2.3提示词] 透传模式：使用前端自定义提示词")

            duration_prompt = f"""You are a duration calculator for LTX2.3 video generation.

Given the following video prompt, calculate the appropriate duration in seconds.

Rules:
- Count Chinese dialogue characters wrapped in quotation marks " ", divide by 3.5, add 2 seconds buffer.
- If no dialogue, estimate based on action complexity:
  * Simple walk, establishing shot, empty scene: 3-5 seconds
  * Simple gesture or subtle motion: 4-6 seconds
  * Moderate action (turn, open door, sit, drink): 5-8 seconds
  * Complex action or fight scene: 6-10 seconds
  * Wide atmospheric/reveal with no character: 5-8 seconds
- Output ONLY an integer, no text.

Video prompt: {custom_prompt[:800]}

Output format:
DURATION: <integer seconds>"""

            try:
                response = requests.post(
                    f"{llm_url}/v1/chat/completions",
                    headers={'Content-Type': 'application/json', 'Authorization': 'Bearer sk-xxx'},
                    json={
                        "model": llm_config.get('model', model_name),
                        "messages": [{"role": "user", "content": duration_prompt}],
                        "temperature": 0.0,
                        "max_tokens": 50
                    },
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()

                import re
                duration_match = re.search(r'DURATION:\s*(\d+)', content)
                duration = int(duration_match.group(1)) if duration_match else 8
                duration = max(3, min(15, duration))
                frame_count = 24 * duration + 1

                print(f"[LTX2.3提示词] 透传模式完成，时长: {duration}秒")

                return jsonify({
                    "status": "ok",
                    "video_prompt": custom_prompt,
                    "duration": duration,
                    "frame_count": frame_count
                })
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({"error": f"透传模式时长计算失败：{str(e)}"}), 500
        # ========================================================

        # ===== 动态判断本镜头是否需要慢镜头 =====
        use_slow_motion = "慢镜头" in narration or "慢镜头" in visual_prompt
        slow_motion_instruction = "USE SLOW MOTION IF NEEDED" if use_slow_motion else "NORMAL SPEED ONLY. FORBIDDEN: slow motion, speed ramping, slow zoom, dream-like floating."
        # ==========================================

        system_prompt = f"""You are a strict single-shot translator for LTX2.3. You receive data for ONLY ONE shot, not the whole story.

【ABSOLUTE RULES - NO EXCEPTIONS】
1. Describe ONLY what is explicitly in this shot's data. Do NOT add emotions, inner thoughts, extra actions, or objects not mentioned. Do NOT invent dialogue.
2. IMPORTANT: The "narration" field contains THIS shot's dialogue (if any).
   - If narration contains actual spoken words (dialogue), you MUST include that exact Chinese text wrapped in English quotation marks " ".
   - If narration only contains stage directions or visual description (like "猛地回头"), do NOT output any dialogue. Output only the visual description.
   - If narration is empty, do NOT add any speech.
3. Camera movement:
   - PRIMARY: If the shot has a clear character action ("turns head", "stands up"), the camera MUST follow that action first.
   - SECONDARY: You MAY add subtle supporting movement (slow dolly, slight push-in, subtle handheld) to enhance cinematic feel, but ONLY if it does NOT introduce new characters, new locations, or new plot events.
   - If the shot has NO action (e.g. character only speaks), a subtle push-in or locked-down shot is acceptable. Do NOT add complex sequences (orbit, crane, rapid pans) for simple dialogue shots.
   - ALL camera movements must remain at realistic, grounded speed unless the special instruction explicitly requests slow motion.
4. Output language: English for visual description. If dialogue exists, use the original Chinese text wrapped in English quotation marks " ".
5. Keep the description concise, under 100 words. Do NOT copy-paste the visual description or any input data directly into the prompt.

6. If this shot has NO dialogue:
   - MUST include at least ONE subtle natural movement to keep the frame alive: gentle breeze moving hair/clothing, slight character breath, slow blink, dust motes in light, subtle background motion (leaves rustling, curtains shifting), or a very slow, motivated camera move (e.g. imperceptible push-in).
   - The movement must be realistic and never slow-motion unless the special instruction explicitly requests it.
   - Do NOT add actions that conflict with the provided visual description.

【DURATION CALCULATION】
- If the shot has dialogue: Chinese chars / 3.5 seconds + 2s buffer. Range: 5-15s.
- If the shot has NO dialogue: minimum 5 seconds even for simple gestures, and up to 15 seconds for atmospheric shots. Ensure the subtle movement can be clearly perceived.
  * Simple gesture or subtle motion: 3-6s
  * Moderate action (turn, walk, reach): 5-8s
  * Complex fight scene: 6-10s
  * Wide atmospheric/reveal: 5-8s
- Always ensure enough time for the described action to complete naturally.

【CURRENT SHOT DATA】
- Narration/dialogue for this shot (if not empty, MUST be included as dialogue in " "): {narration}
- Visual description: {visual_prompt}
- Style: {style}
- Historical era: {context}
- Story context (this shot only): {story_content[:500]}
- Special camera instruction: {slow_motion_instruction}

Use ONLY the above text to understand the scene. Do NOT copy any part of the input data (shot numbers, timestamps, location descriptions) into the output.

Output format (exactly - no extra text after DURATION):
PROMPT: <your cinematic description here with dialogue in "quotation marks">
DURATION: <integer seconds>"""
        # ===================== 核心修复：Gemma-12B 不发送图片，避免500 =====================
        if llm_service == "gemma-12b":
            # 纯文本模式，兼容 gemma
            messages = [
                {"role": "user", "content": system_prompt + f"\nImage description: {visual_prompt}"}
            ]
        else:
            # 多模态模式，发送图片（Qwen 系列正常使用）
            messages = [
                {"role": "user", "content": [
                    {"type": "text", "text": system_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/{image_type};base64,{image_base64}"}}
                ]}
            ]

        response = requests.post(
            f"{llm_url}/v1/chat/completions",
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer sk-xxx'
            },
            json={
                "model": llm_config.get('model', model_name),
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 800
            },
            timeout=180
        )
        response.raise_for_status()
        result = response.json()
        content = result['choices'][0]['message']['content'].strip()
        
        import re
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
        duration = max(3, min(15, duration))
        
        frame_count = 24 * duration + 1
        
        print(f"[LTX2.3提示词] 生成完成:")
        print(f"  - 台词字数: {total_dialogue_chars}字, 台词数: {dialogue_count}")
        print(f"  - LLM建议时长: {llm_duration}秒, 计算时长: {calculated_duration:.1f}秒")
        print(f"  - 最终时长: {duration}秒")
        print(f"  - 帧数: {frame_count}")
        print(f"  - 提示词: {video_prompt[:100]}...")

        # ===== 兜底过滤 =====
        if '(对白：' not in narration and '(旁白：' not in narration:
            video_prompt = re.sub(r'"([^"]*[\u4e00-\u9fff][^"]*)"', r'\1', video_prompt)
        
        return jsonify({
            "status": "ok",
            "video_prompt": video_prompt,
            "duration": duration,
            "frame_count": frame_count
        })        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"LTX2.3提示词生成失败：{str(e)}"}), 500

@app.route('/api/get_ltx23_workflow', methods=['GET'])
def get_ltx23_workflow():
    """获取LTX2.3工作流JSON"""
    try:
        workflow_path = PROJECT_ROOT / "workflows" / "【WF-26.03.16】Work-FIsh-LTX2.3全面优化版（图生_ 文生合并版本）.json"
        if not workflow_path.exists():
            return jsonify({"error": "工作流文件不存在"}), 404
        
        with open(workflow_path, 'r', encoding='utf-8') as f:
            workflow = json.load(f)
        
        return jsonify({"status": "ok", "workflow": workflow})
    except Exception as e:
        return jsonify({"error": f"加载工作流失败: {str(e)}"}), 500

if __name__ == '__main__':
    print(f"Server V4.0 Ready. FFmpeg: {FFMPEG_BIN}")
    app.run(host='0.0.0.0', port=5001, debug=False)