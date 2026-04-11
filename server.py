r"""
鈺斺晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晽
鈺? ./server.py  鈥? AI Canvas V2 鐙珛鏈嶅姟鍣?              鈺?
鈺犫晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨暎
鈺? 鍚姩鏂瑰紡锛?                                             鈺?
鈺?   cd v2                                                 鈺?
鈺?   venv\Scripts\python server.py                        鈺?
鈺? 娴忚鍣ㄨ闂細http://localhost:8777                        鈺?
鈺犫晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨暎
鈺? 鐩綍缁撴瀯锛堝潎鍦?v2/ 鍐咃級锛?                              鈺?
鈺?   user/Canvas Project/  鈥?鐢诲竷椤圭洰鏂囦欢                  鈺?
鈺?   user/shortcuts.json   鈥?蹇嵎閿缃?                   鈺?
鈺?   user/settings.json    鈥?涓婚绛夎缃?                   鈺?
鈺?   user/config.json      鈥?API Key 閰嶇疆                  鈺?
鈺?   data/uploads/         鈥?涓婁紶鏂囦欢缂撳瓨                  鈺?
鈺氣晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨暆
"""

import http.server
import socketserver
import os
import json
import threading
import subprocess
import time
import mimetypes
import sys
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import unquote
import base64
import re
import random
import hashlib
import datetime
from collections import OrderedDict

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from services.subscription_client import SubscriptionRemoteClient

mimetypes.add_type("text/javascript; charset=utf-8", ".js")
mimetypes.add_type("text/javascript; charset=utf-8", ".mjs")
mimetypes.add_type("text/css; charset=utf-8", ".css")

def _get_int_env(name, default, min_value=None):
    try:
        value = int(str(os.environ.get(name, default)).strip())
    except Exception:
        return default
    if min_value is not None and value < min_value:
        return default
    return value

PORT      = _get_int_env("AICANVAS_PORT", 8777, 1)
BIND_HOST = (os.environ.get("AIC_BIND_HOST", "0.0.0.0") or "").strip() or "0.0.0.0"
DIRECTORY = os.path.abspath(os.path.dirname(__file__))   # v2/ 缁濆璺緞
# 鈹€鈹€ 鑷姩鏇存柊 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# 浠?index.html 璇诲彇鐗堟湰鍙?
import re

def get_version_from_index_html():
    """浠?index.html 涓鍙栫増鏈彿"""
    index_path = os.path.join(DIRECTORY, "index.html")
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # 鍖归厤 <meta name="app-version" content="V0.0.7">
        match = re.search(r'<meta name="app-version" content="([^"]+)"', content)
        if match:
            return match.group(1)
    except Exception:
        pass
    return "V0.0.7"  # 榛樿鐗堟湰鍙?

LOCAL_VERSION   = get_version_from_index_html()  # 浠?index.html 璇诲彇鐗堟湰鍙?
UPDATE_INTERVAL = 30 * 60          # 妫€鏌ラ棿闅旓紙绉掞級锛岄粯璁?30 鍒嗛挓
_update_info    = None              # None=鏃犳洿鏂帮紱dict=鏈夋洿鏂颁俊鎭?
_update_lock    = threading.Lock()
_gen_seq_lock   = threading.Lock()
_smart_clip_jobs = {}
_smart_clip_lock = threading.Lock()

# 鈹€鈹€ 鏁版嵁鐩綍锛堝叏閮ㄥ湪 v2/ 鍐咃級鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
USER_DIR       = os.path.join(DIRECTORY, "user")
CANVAS_DIR     = os.path.join(USER_DIR,  "Canvas Project")
ASSETS_DIR     = os.path.join(DIRECTORY, "data", "assets")
ASSET_THUMBS_DIR = os.path.join(ASSETS_DIR, "thumbs")
UPLOADS_DIR    = os.path.join(DIRECTORY, "data", "uploads")
OUTPUT_DIR     = os.path.join(DIRECTORY, "output")
CONFIG_FILE    = os.path.join(USER_DIR, "config.json")
GEN_SEQ_STATE_FILE = os.path.join(OUTPUT_DIR, ".gen_seq_state.json")
MAX_UPLOAD_BYTES = _get_int_env("AIC_UPLOAD_MAX_BYTES", 100 * 1024 * 1024, 1)

V54_VIP_MODEL_ID = "runninghub/2041741496667348994"
V54_VIP_WORKFLOW_ID = "2041741496667348994"
VIDEO_VIP_MODEL_IDS = (
    "runninghub/2041741496667348994",
)
VIDEO_VIP_WORKFLOW_IDS = set(
    mid.split("/", 1)[1]
    for mid in VIDEO_VIP_MODEL_IDS
    if "/" in mid
)
VIDEO_VIP_MODEL_NAME_MAP = {
    "runninghub/2041741496667348994": "视频编辑V5.4",
}
SUB_STATUS_NONE = "none"
SUB_STATUS_ACTIVE = "active"
SUB_STATUS_EXPIRED = "expired"
SUB_ERROR_INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
SUB_ERROR_INVALID_CDKEY = "INVALID_CDKEY"
SUB_ERROR_CDKEY_ALREADY_USED = "CDKEY_ALREADY_USED"
SUB_ERROR_REQUIRED = "SUBSCRIPTION_REQUIRED"
SUB_ERROR_MODEL_NOT_ENTITLED = "SUBSCRIPTION_MODEL_NOT_ENTITLED"
SUB_MESSAGE_V54_REQUIRED = "该模型为 VIP 模型，请先激活 CDKEY/订阅"
DEFAULT_SUB_CONTACT_TEXT = os.environ.get(
    "AIC_SUB_CONTACT_TEXT",
    "联系管理员获取授权码",
).strip() or "联系管理员获取授权码"
DEFAULT_SUB_CONTACT_URL = os.environ.get("AIC_SUB_CONTACT_URL", "").strip()
_raw_sub_api_base = (os.environ.get("AIC_SUBSCRIPTION_API_BASE", "") or "").strip()
SUBSCRIPTION_API_BASE = (_raw_sub_api_base or "https://api.ashuoai.com").rstrip("/")
try:
    SUBSCRIPTION_TIMEOUT_SECONDS = int(
        (os.environ.get("AIC_SUBSCRIPTION_TIMEOUT_SEC", "5") or "5").strip()
    )
except Exception:
    SUBSCRIPTION_TIMEOUT_SECONDS = 5

SUBSCRIPTION_CLIENT = SubscriptionRemoteClient(
    api_base_url=SUBSCRIPTION_API_BASE,
    timeout_seconds=SUBSCRIPTION_TIMEOUT_SECONDS,
    status_active=SUB_STATUS_ACTIVE,
    err_required=SUB_ERROR_REQUIRED,
    required_message=SUB_MESSAGE_V54_REQUIRED,
    contact_text=DEFAULT_SUB_CONTACT_TEXT,
    contact_url=DEFAULT_SUB_CONTACT_URL,
)
_VIP_GATE_ALLOW_CACHE = {}
_VIP_GATE_CACHE_LOCK = threading.Lock()
_VIP_GATE_CACHE_MAX = 2048

# 纭繚鐩綍瀛樺湪
os.makedirs(CANVAS_DIR,  exist_ok=True)
os.makedirs(ASSETS_DIR,  exist_ok=True)
os.makedirs(ASSET_THUMBS_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR,  exist_ok=True)
os.makedirs(USER_DIR,    exist_ok=True)

SAM3_ONNX_DIR = os.path.join(DIRECTORY, "models", "sam3_onnx")
_sam3_lock = threading.Lock()
_sam3_infer_lock = threading.Lock()
_sam3_sessions = None
_sam3_tokenizer = None
_sam3_lang_cache_lock = threading.Lock()
_sam3_lang_cache = {}
_sam3_image_cache_lock = threading.Lock()
_sam3_image_cache = OrderedDict()
_sam3_image_cache_max = 6
_sam3_last_use_lock = threading.Lock()
_sam3_last_use_ts = 0.0

def _sam3_enabled():
    try:
        v = (os.environ.get("SAM3_ENABLED", "0") or "0").strip().lower()
        return v in ("1", "true", "yes", "on")
    except Exception:
        return False

def _sam3_touch():
    global _sam3_last_use_ts
    try:
        now = time.time()
    except Exception:
        now = 0.0
    with _sam3_last_use_lock:
        _sam3_last_use_ts = now

def _sam3_get_idle_sec():
    with _sam3_last_use_lock:
        ts = float(_sam3_last_use_ts or 0.0)
    try:
        now = time.time()
    except Exception:
        now = ts
    if ts <= 0:
        return None
    return max(0.0, now - ts)

def _sam3_clear_caches():
    with _sam3_lang_cache_lock:
        _sam3_lang_cache.clear()
    with _sam3_image_cache_lock:
        _sam3_image_cache.clear()

def _sam3_unload():
    global _sam3_sessions, _sam3_tokenizer
    with _sam3_lock:
        sess = _sam3_sessions
        _sam3_sessions = None
        _sam3_tokenizer = None
    with _sam3_last_use_lock:
        global _sam3_last_use_ts
        _sam3_last_use_ts = 0.0
    _sam3_clear_caches()
    try:
        import gc
        del sess
        gc.collect()
    except Exception:
        pass

def _sam3_get_np():
    import numpy as np
    return np

def _sam3_get_pil_image():
    from PIL import Image
    return Image

def _sam3_get_ort():
    import onnxruntime as ort
    return ort

def _sam3_has_tensorrt_runtime():
    try:
        path_env = os.environ.get("PATH", "") or ""
        parts = [p for p in path_env.split(os.pathsep) if p]
        for p in parts:
            p = p.strip().strip('"')
            if not p:
                continue
            cand = os.path.join(p, "nvinfer_10.dll")
            if os.path.isfile(cand):
                return True
            try:
                for fn in os.listdir(p):
                    if fn.lower().startswith("nvinfer_") and fn.lower().endswith(".dll"):
                        if os.path.isfile(os.path.join(p, fn)):
                            return True
            except Exception:
                continue
    except Exception:
        return False
    return False

def _sam3_get_tokenizer():
    global _sam3_tokenizer
    if _sam3_tokenizer is not None:
        return _sam3_tokenizer
    import os
    os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "true"
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
    from transformers import CLIPTokenizerFast
    local_dir = os.path.join(SAM3_ONNX_DIR, "clip_tokenizer")
    if os.path.isdir(local_dir):
        _sam3_tokenizer = CLIPTokenizerFast.from_pretrained(local_dir, local_files_only=True)
    else:
        _sam3_tokenizer = CLIPTokenizerFast.from_pretrained("openai/clip-vit-large-patch14")
    return _sam3_tokenizer

def _sam3_load_sessions():
    global _sam3_sessions
    if not _sam3_enabled():
        raise RuntimeError("SAM3 disabled")
    if _sam3_sessions is not None:
        return _sam3_sessions
    with _sam3_lock:
        if _sam3_sessions is not None:
            return _sam3_sessions
        ort = _sam3_get_ort()
        encoder_path = os.path.join(SAM3_ONNX_DIR, "sam3_image_encoder.onnx")
        language_path = os.path.join(SAM3_ONNX_DIR, "sam3_language_encoder.onnx")
        decoder_path = os.path.join(SAM3_ONNX_DIR, "sam3_decoder.onnx")
        missing = []
        if not os.path.exists(encoder_path):
            missing.append("sam3_image_encoder.onnx")
        if not os.path.exists(language_path):
            missing.append("sam3_language_encoder.onnx")
        if not os.path.exists(decoder_path):
            missing.append("sam3_decoder.onnx")
        if missing:
            raise RuntimeError("Missing model files: " + ", ".join(missing))

        providers = []
        try:
            avail = ort.get_available_providers()
            use_trt = (os.environ.get("SAM3_ENABLE_TRT", "0") or "0").strip() in ("1", "true", "True", "YES", "yes")
            if use_trt and "TensorrtExecutionProvider" in avail and _sam3_has_tensorrt_runtime():
                cache_dir = os.path.join(OUTPUT_DIR, "sam3_trt_cache")
                try:
                    os.makedirs(cache_dir, exist_ok=True)
                except Exception:
                    pass
                trt_opts = {
                    "trt_engine_cache_enable": True,
                    "trt_engine_cache_path": cache_dir,
                    "trt_fp16_enable": True,
                }
                providers = [
                    ("TensorrtExecutionProvider", trt_opts),
                    "CUDAExecutionProvider",
                    "CPUExecutionProvider",
                ]
            elif "CUDAExecutionProvider" in avail:
                try:
                    mem_gb = float(os.environ.get("SAM3_CUDA_MEM_LIMIT_GB", "12") or "12")
                except Exception:
                    mem_gb = 12.0
                mem_limit = int(mem_gb * 1024 * 1024 * 1024) if mem_gb > 0 else 0
                cuda_opts = {
                    "arena_extend_strategy": "kSameAsRequested",
                    "cudnn_conv_algo_search": "DEFAULT",
                    "gpu_mem_limit": mem_limit,
                }
                providers = [("CUDAExecutionProvider", cuda_opts), "CPUExecutionProvider"]
            elif "CoreMLExecutionProvider" in avail:
                providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
            elif "DmlExecutionProvider" in avail:
                providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
            else:
                providers = ["CPUExecutionProvider"]
        except Exception:
            providers = ["CPUExecutionProvider"]

        so = ort.SessionOptions()
        try:
            th = int(os.environ.get("SAM3_ORT_THREADS", "0") or "0")
        except Exception:
            th = 0
        cpu_n = int(os.cpu_count() or 4)
        th = th if th > 0 else max(2, cpu_n // 2)
        if th > 8:
            th = 8
        so.intra_op_num_threads = max(1, th)
        try:
            so.inter_op_num_threads = 1
        except Exception:
            pass
        try:
            so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        except Exception:
            pass
        try:
            so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        except Exception:
            pass

        def _fallback_providers():
            try:
                avail2 = ort.get_available_providers()
                if "CUDAExecutionProvider" in avail2:
                    return ["CUDAExecutionProvider", "CPUExecutionProvider"]
                if "CoreMLExecutionProvider" in avail2:
                    return ["CoreMLExecutionProvider", "CPUExecutionProvider"]
                if "DmlExecutionProvider" in avail2:
                    return ["DmlExecutionProvider", "CPUExecutionProvider"]
            except Exception:
                pass
            return ["CPUExecutionProvider"]

        try:
            sess_image = ort.InferenceSession(encoder_path, sess_options=so, providers=providers)
            sess_language = ort.InferenceSession(language_path, sess_options=so, providers=providers)
            sess_decode = ort.InferenceSession(decoder_path, sess_options=so, providers=providers)
        except Exception as e:
            msg = str(e)
            if "TensorrtExecutionProvider" in msg or "TensorRT" in msg or "nvinfer" in msg:
                fb = _fallback_providers()
                sess_image = ort.InferenceSession(encoder_path, sess_options=so, providers=fb)
                sess_language = ort.InferenceSession(language_path, sess_options=so, providers=fb)
                sess_decode = ort.InferenceSession(decoder_path, sess_options=so, providers=fb)
            else:
                raise
        _sam3_sessions = {"image": sess_image, "language": sess_language, "decode": sess_decode}
        return _sam3_sessions

def _sam3_safe_resolve_image_path(p):
    if not isinstance(p, str):
        return None
    p = p.strip().lstrip("/")
    if not p:
        return None
    if p.startswith("data/uploads/") or p.startswith("data/assets/") or p.startswith("output/"):
        abs_path = os.path.abspath(os.path.join(DIRECTORY, p))
        allow1 = os.path.abspath(UPLOADS_DIR)
        allow2 = os.path.abspath(ASSETS_DIR)
        allow3 = os.path.abspath(OUTPUT_DIR)
        if abs_path.startswith(allow1) or abs_path.startswith(allow2) or abs_path.startswith(allow3):
            if os.path.isfile(abs_path):
                return abs_path
    return None

def _sam3_get_language_features(prompt=None):
    np = _sam3_get_np()
    sess = _sam3_load_sessions()
    prompt = (prompt or "visual").strip() or "visual"
    with _sam3_lang_cache_lock:
        cached = _sam3_lang_cache.get(prompt)
    if cached is not None:
        return cached
    tok = _sam3_get_tokenizer()
    ids = tok([prompt], padding="max_length", max_length=32, truncation=True, return_tensors="np")["input_ids"]
    ids = np.asarray(ids, dtype=np.int64)
    lang_out_vals = sess["language"].run(None, {sess["language"].get_inputs()[0].name: ids})
    language_mask = lang_out_vals[0]
    language_features = lang_out_vals[1]
    with _sam3_lang_cache_lock:
        _sam3_lang_cache[prompt] = (language_mask, language_features)
    return language_mask, language_features

def _sam3_get_image_embedding(abs_path=None, b64_data=None):
    np = _sam3_get_np()
    Image = _sam3_get_pil_image()
    sess = _sam3_load_sessions()

    raw_bytes = None
    image_cache_key = None
    if b64_data:
        if isinstance(b64_data, str) and "," in b64_data:
            b64_data = b64_data.split(",", 1)[1]
        raw_bytes = base64.b64decode(b64_data)
        import io
        img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    else:
        img = Image.open(abs_path).convert("RGB")

    orig_w, orig_h = img.size
    if abs_path:
        try:
            st = os.stat(abs_path)
            image_cache_key = f"p|{os.path.abspath(abs_path)}|{int(st.st_mtime_ns)}|{int(st.st_size)}"
        except Exception:
            image_cache_key = f"p|{os.path.abspath(abs_path)}"
    else:
        try:
            h = hashlib.md5(raw_bytes or b"").hexdigest()
            image_cache_key = f"b|{h}|{len(raw_bytes or b'')}"
        except Exception:
            image_cache_key = "b|0"

    enc_out = None
    if image_cache_key:
        with _sam3_image_cache_lock:
            enc_out = _sam3_image_cache.get(image_cache_key)
            if enc_out is not None:
                _sam3_image_cache.move_to_end(image_cache_key, last=True)

    if enc_out is None:
        img_resized = img.resize((1008, 1008))
        chw = np.asarray(img_resized, dtype=np.uint8).transpose(2, 0, 1)
        enc_in_name = sess["image"].get_inputs()[0].name
        enc_out_vals = sess["image"].run(None, {enc_in_name: chw})
        enc_out_names = [o.name for o in sess["image"].get_outputs()]
        enc_out_full = {k: v for k, v in zip(enc_out_names, enc_out_vals)}
        keep_keys = ("backbone_fpn_0", "backbone_fpn_1", "backbone_fpn_2", "vision_pos_enc_2")
        enc_out = {k: enc_out_full[k] for k in keep_keys if k in enc_out_full}
        if image_cache_key and enc_out:
            with _sam3_image_cache_lock:
                _sam3_image_cache[image_cache_key] = enc_out
                _sam3_image_cache.move_to_end(image_cache_key, last=True)
                while len(_sam3_image_cache) > _sam3_image_cache_max:
                    _sam3_image_cache.popitem(last=False)

    return enc_out or {}, orig_w, orig_h

def _sam3_run_segment(abs_path=None, b64_data=None, points=None, prompt=None, single_point_box_px=None, multi_point_pad_ratio=None):
    np = _sam3_get_np()
    sess = _sam3_load_sessions()
    enc_out, orig_w, orig_h = _sam3_get_image_embedding(abs_path=abs_path, b64_data=b64_data)
    language_mask, language_features = _sam3_get_language_features(prompt=prompt)

    fg = []
    bg = []
    for pt in points or []:
        try:
            x = float(pt.get("x"))
            y = float(pt.get("y"))
            label = int(pt.get("label"))
        except Exception:
            continue
        if label == 1:
            fg.append((x, y))
        else:
            bg.append((x, y))

    if not fg:
        raise RuntimeError("Missing foreground point")

    def _clamp(v, lo, hi):
        return lo if v < lo else (hi if v > hi else v)

    fg2 = []
    for (x, y) in fg:
        xx = _clamp(float(x), 0.0, float(max(0, orig_w - 1)))
        yy = _clamp(float(y), 0.0, float(max(0, orig_h - 1)))
        fg2.append((xx, yy))

    if len(fg2) == 1:
        try:
            sp = float(single_point_box_px) if single_point_box_px is not None else 160.0
        except Exception:
            sp = 160.0
        sp = 32.0 if sp < 32.0 else (2048.0 if sp > 2048.0 else sp)
        x, y = fg2[0]
        cx = _clamp(x / float(orig_w), 0.0, 1.0)
        cy = _clamp(y / float(orig_h), 0.0, 1.0)
        bw = _clamp(sp / float(orig_w), 0.02, 0.98)
        bh = _clamp(sp / float(orig_h), 0.02, 0.98)
    else:
        xs = [p[0] for p in fg2]
        ys = [p[1] for p in fg2]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span = max(max_x - min_x, max_y - min_y)
        try:
            pr = float(multi_point_pad_ratio) if multi_point_pad_ratio is not None else 0.35
        except Exception:
            pr = 0.35
        pr = 0.05 if pr < 0.05 else (1.2 if pr > 1.2 else pr)
        pad = max(24.0, span * pr)
        x0 = _clamp(min_x - pad, 0.0, float(orig_w))
        x1 = _clamp(max_x + pad, 0.0, float(orig_w))
        y0 = _clamp(min_y - pad, 0.0, float(orig_h))
        y1 = _clamp(max_y + pad, 0.0, float(orig_h))
        if x1 - x0 < 2.0:
            cx0 = (min_x + max_x) * 0.5
            x0 = _clamp(cx0 - 1.0, 0.0, float(orig_w))
            x1 = _clamp(cx0 + 1.0, 0.0, float(orig_w))
        if y1 - y0 < 2.0:
            cy0 = (min_y + max_y) * 0.5
            y0 = _clamp(cy0 - 1.0, 0.0, float(orig_h))
            y1 = _clamp(cy0 + 1.0, 0.0, float(orig_h))
        bw = _clamp((x1 - x0) / float(orig_w), 0.02, 0.98)
        bh = _clamp((y1 - y0) / float(orig_h), 0.02, 0.98)
        cx = _clamp(((x0 + x1) * 0.5) / float(orig_w), 0.0, 1.0)
        cy = _clamp(((y0 + y1) * 0.5) / float(orig_h), 0.0, 1.0)
    box_coords = np.array([[[cx, cy, bw, bh]]], dtype=np.float32)
    box_labels = np.array([[1]], dtype=np.int64)
    box_masks = np.array([[False]], dtype=np.bool_)

    feeds = {
        "original_height": np.array(orig_h, dtype=np.int64),
        "original_width": np.array(orig_w, dtype=np.int64),
        "language_mask": language_mask,
        "language_features": language_features,
        "box_coords": box_coords,
        "box_labels": box_labels,
        "box_masks": box_masks,
    }
    for k in ("backbone_fpn_0", "backbone_fpn_1", "backbone_fpn_2", "vision_pos_enc_2"):
        if k in enc_out:
            feeds[k] = enc_out[k]
    out_vals = sess["decode"].run(None, feeds)
    masks = out_vals[-1]
    m = np.asarray(masks)
    if m.size == 0:
        mask_u8 = np.zeros((1008, 1008), dtype=np.uint8)
        return mask_u8, 1008, 1008
    if m.ndim == 4 and m.shape[1] == 1:
        m = m[:, 0, :, :]
    if m.ndim == 4 and m.shape[0] == 1:
        m = m[0]
    if m.ndim == 3:
        m = m[0]
    if m.dtype != np.bool_:
        m = m > 0
    mask_u8 = (m.astype(np.uint8) * 255)
    if bg:
        mh = int(mask_u8.shape[0])
        mw = int(mask_u8.shape[1])
        rr = int(max(2, min(mw, mh) * 0.02))
        yy, xx = np.ogrid[:mh, :mw]
        for bx, by in bg:
            try:
                mx = int(round(float(bx) / float(orig_w) * float(mw)))
                my = int(round(float(by) / float(orig_h) * float(mh)))
            except Exception:
                continue
            if mx < 0:
                mx = 0
            elif mx > mw - 1:
                mx = mw - 1
            if my < 0:
                my = 0
            elif my > mh - 1:
                my = mh - 1
            dist2 = (xx - mx) ** 2 + (yy - my) ** 2
            mask_u8[dist2 <= rr * rr] = 0
    return mask_u8, int(mask_u8.shape[1]), int(mask_u8.shape[0])
# 鈹€鈹€ 鑷畾涔?AI 鍏ㄥ眬閰嶇疆锛堢幆澧冨彉閲?> config.json锛夆攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# 鏀寔鐨勭幆澧冨彉閲忥細CUSTOM_AI_URL, CUSTOM_AI_KEY
def _get_custom_ai_config():
    """浼樺厛璇诲彇鐜鍙橀噺锛屽叾娆?config.json 涓?custom_ai 鍧楋紝鍐嶅叾娆℃牴鑺傜偣閰嶇疆"""
    env_url = os.environ.get("CUSTOM_AI_URL", "").strip()
    env_key = os.environ.get("CUSTOM_AI_KEY", "").strip()
    
    cfg_url = ""
    cfg_key = ""
    try:
        with open(CONFIG_FILE, encoding="utf-8-sig") as f:
            cfg = json.load(f)
        ca = cfg.get("custom_ai", {})
        cfg_url = ca.get("apiUrl") or cfg.get("apiUrl", "")
        cfg_key = ca.get("apiKey") or cfg.get("apiKey", "")
    except Exception:
        pass

    final_url = env_url if env_url else cfg_url
    final_key = env_key if env_key else cfg_key
    
    source = "env" if (env_url or env_key) else "config"
    return {"apiUrl": final_url, "apiKey": final_key, "source": source}


def _is_install_entitled_for_model(install_id, model_id):
    return SUBSCRIPTION_CLIENT.is_install_entitled_for_model(install_id, model_id)


def _extract_install_id_from_request(handler, payload=None):
    return SUBSCRIPTION_CLIENT.extract_install_id_from_request(handler, payload)


def _normalize_runninghub_model_id(value):
    s = str(value or "").strip()
    if not s:
        return ""
    if s.startswith("runninghub/"):
        return s
    if re.match(r"^\d+$", s):
        return f"runninghub/{s}"
    return ""


def _extract_entitled_model_ids(payload):
    if not isinstance(payload, dict):
        return []
    base = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    raw = None
    if isinstance(base, dict):
        raw = base.get("entitledModelIds")
        if not isinstance(raw, list):
            raw = base.get("entitled_model_ids")
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _extract_expires_at(payload):
    if not isinstance(payload, dict):
        return 0
    base = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(base, dict):
        return 0
    raw = (
        base.get("expiresAt")
        or base.get("expires_at")
        or base.get("expireAt")
        or base.get("expire_at")
        or 0
    )
    try:
        n = int(raw or 0)
    except Exception:
        n = 0
    if n > 10**11:
        n = int(n / 1000)
    return n if n > 0 else 0


def _get_cached_vip_allow_decision(install_id, model_id):
    install = str(install_id or "").strip()
    model = str(model_id or "").strip()
    if not install or not model:
        return None
    with _VIP_GATE_CACHE_LOCK:
        cached = _VIP_GATE_ALLOW_CACHE.get(install)
    if not isinstance(cached, dict):
        return None

    status = str(cached.get("status") or "").strip().lower()
    if status != SUB_STATUS_ACTIVE:
        return None

    now_ts = int(time.time())
    expires_at = int(cached.get("expiresAt") or 0)
    if expires_at > 0 and expires_at <= now_ts:
        with _VIP_GATE_CACHE_LOCK:
            _VIP_GATE_ALLOW_CACHE.pop(install, None)
        return None

    entitled_ids = _extract_entitled_model_ids(cached)
    if entitled_ids and model not in entitled_ids:
        return None

    return {
        "allowed": True,
        "installId": install,
        "status": SUB_STATUS_ACTIVE,
        "reasonCode": "ACTIVE_CACHE_HIT",
        "reasonMessage": "",
        "requiredModelId": model,
        "payload": {
            "status": SUB_STATUS_ACTIVE,
            "expiresAt": expires_at,
            "entitledModelIds": entitled_ids,
        },
    }


def _cache_vip_allow_decision(install_id, *, payload, entitled_ids):
    install = str(install_id or "").strip()
    if not install:
        return
    entry = {
        "status": SUB_STATUS_ACTIVE,
        "expiresAt": _extract_expires_at(payload),
        "entitledModelIds": list(entitled_ids or []),
        "cachedAt": int(time.time()),
    }
    with _VIP_GATE_CACHE_LOCK:
        _VIP_GATE_ALLOW_CACHE.pop(install, None)
        _VIP_GATE_ALLOW_CACHE[install] = entry
        while len(_VIP_GATE_ALLOW_CACHE) > _VIP_GATE_CACHE_MAX:
            oldest_key = next(iter(_VIP_GATE_ALLOW_CACHE))
            _VIP_GATE_ALLOW_CACHE.pop(oldest_key, None)


def _clear_vip_allow_cache(install_id):
    install = str(install_id or "").strip()
    if not install:
        return
    with _VIP_GATE_CACHE_LOCK:
        _VIP_GATE_ALLOW_CACHE.pop(install, None)


def _check_v54_subscription_gate(handler, payload=None, required_model_id=""):
    install_id = _extract_install_id_from_request(handler, payload)
    model_id = _normalize_runninghub_model_id(required_model_id)
    cached_decision = _get_cached_vip_allow_decision(install_id, model_id)
    if isinstance(cached_decision, dict):
        return cached_decision

    decision = SUBSCRIPTION_CLIENT.evaluate_install_active(install_id)
    decision = dict(decision) if isinstance(decision, dict) else {}
    decision["requiredModelId"] = model_id
    if bool(decision.get("allowed")) and model_id:
        entitled_ids = _extract_entitled_model_ids(decision.get("payload"))
        entitled = (model_id in entitled_ids) if entitled_ids else _is_install_entitled_for_model(
            install_id,
            model_id,
        )
        if not entitled:
            decision["allowed"] = False
            decision["reasonCode"] = SUB_ERROR_MODEL_NOT_ENTITLED
            model_name = VIDEO_VIP_MODEL_NAME_MAP.get(model_id) or model_id
            decision["reasonMessage"] = f"当前订阅未包含 {model_name}"
            _clear_vip_allow_cache(install_id)
        else:
            if not entitled_ids:
                entitled_ids = [model_id]
            _cache_vip_allow_decision(
                install_id,
                payload=decision.get("payload"),
                entitled_ids=entitled_ids,
            )
    elif install_id:
        _clear_vip_allow_cache(install_id)
    try:
        print(
            "[subscription][v54_gate] "
            f"installId={decision.get('installId') or '-'} "
            f"modelId={model_id or '-'} "
            f"status={decision.get('status') or SUB_STATUS_NONE} "
            f"allowed={bool(decision.get('allowed'))} "
            f"reason={decision.get('reasonCode') or ''}"
        )
    except Exception:
        pass
    return decision


# 鈹€鈹€ 鑷姩鏇存柊锛氬悗鍙扮嚎绋?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
def _parse_remote_info():
    """浠?git remote origin URL 瑙ｆ瀽鍑?platform/owner/repo/branch
    鏀寔 GitHub / Gitee / 閫氱敤 HTTPS 鍜?SSH 鏍煎紡
    """
    try:
        raw = subprocess.check_output(
            ['git', 'remote', 'get-url', 'origin'],
            cwd=DIRECTORY, stderr=subprocess.DEVNULL
        ).decode().strip()
        # 瑙ｆ瀽 owner/repo
        if raw.startswith('https://'):
            parts = raw.rstrip('/').split('/')
            if parts[-1].endswith('.git'):
                parts[-1] = parts[-1][:-4]
            owner, repo = parts[-2], parts[-1]
            host = parts[2]  # e.g. github.com or gitee.com
        else:
            # SSH: git@github.com:owner/repo.git  鎴?git@gitee.com:owner/repo.git
            host = raw.split('@')[-1].split(':')[0]
            path_part = raw.split(':')[-1]
            if path_part.endswith('.git'):
                path_part = path_part[:-4]
            owner, repo = path_part.split('/')
        branch = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=DIRECTORY, stderr=subprocess.DEVNULL
        ).decode().strip() or 'master'
        # 璇嗗埆骞冲彴
        if 'gitee.com' in host:
            platform = 'gitee'
        elif 'github.com' in host:
            platform = 'github'
        else:
            platform = 'unknown'
        return platform, owner, repo, branch, host
    except Exception:
        return None, None, None, 'master', None
def _do_update_check():
    """瀵规瘮鏈湴涓庤繙绔渶鏂?commit hash锛涘彂鐜版洿鏂板啓鍏?_update_info锛岀敱鐢ㄦ埛鎵嬪姩瑙﹀彂鏇存柊銆傛敮鎸?GitHub 鍜?Gitee"""
    global _update_info
    
    # 濡傛灉瀛樺湪 .dev 鏍囪鏂囦欢锛岃鏄庢槸鏈湴寮€鍙戠幆澧冿紝璺宠繃鏇存柊妫€鏌?
    if os.path.exists(os.path.join(DIRECTORY, ".dev")):
        return

    try:
        local_hash = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            cwd=DIRECTORY, stderr=subprocess.DEVNULL
        ).decode().strip()
        
        # 纭紪鐮佷粨搴?B 鐨勪俊鎭紝涓嶅啀鍔ㄦ€佽鍙栨湰鍦扮殑 git remote
        platform = 'github'
        owner = 'ashuoAI'
        repo = 'AI-CanvasPro'
        branch = 'master'  # 鍋囪鍙戝竷浠撳簱鐨勪富鍒嗘敮鏄?master锛屽鏋滄槸 main 璇疯嚜琛屼慨鏀?
        
        if platform == 'gitee':
            api_url = f"https://gitee.com/api/v5/repos/{owner}/{repo}/commits?sha={branch}&limit=1"
            headers = {'User-Agent': 'TapNow-AutoUpdate/1.0'}
            download_url = f"https://gitee.com/{owner}/{repo}"
            def get_sha(data): return data[0].get('sha', '') if isinstance(data, list) and data else ''
            def get_msg(data): return (data[0].get('commit', {}).get('message', '') if isinstance(data, list) and data else '').split('\n')[0][:80]
        elif platform == 'github':
            api_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
            headers = {'User-Agent': 'TapNow-AutoUpdate/1.0', 'Accept': 'application/vnd.github.v3+json'}
            download_url = f"https://github.com/{owner}/{repo}/releases/latest"
            def get_sha(data): return data.get('sha', '')
            def get_msg(data): return data.get('commit', {}).get('message', '').split('\n')[0][:80]
        else:
            # print(f"[AutoUpdate] 涓嶆敮鎸佺殑骞冲彴: {host}")
            return
        # print(f"[AutoUpdate] 妫€鏌ヤ腑 ({platform}) {owner}/{repo}@{branch}")
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        remote_sha = get_sha(data)
        if not remote_sha or remote_sha == local_hash:
            with _update_lock:
                _update_info = None
            return
        commit_msg = get_msg(data)
        with _update_lock:
            _update_info = {
                'hasUpdate': True,
                'localHash': local_hash[:7], 'remoteHash': remote_sha[:7],
                'message': commit_msg, 'downloadUrl': download_url
            }
    except Exception as e:
        # print(f"[AutoUpdate] 妫€鏌ュけ璐? {e}")
        pass


def _update_check_loop():
    """后台守护线程：启动后先等待 10 秒，再按固定间隔执行更新检查。"""
    time.sleep(10)
    while True:
        _do_update_check()
        time.sleep(UPDATE_INTERVAL)


def _json_ok(handler, data):
    body = json.dumps(data, ensure_ascii=False, indent=2).encode()
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError):
        pass

def _json_err(handler, code, msg):
    body = json.dumps({"error": msg}, ensure_ascii=False, indent=2).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError):
        pass

def _read_body(handler, max_bytes=None):
    te = (handler.headers.get("Transfer-Encoding", "") or "").lower()
    if "chunked" in te:
        chunks = []
        total = 0
        while True:
            line = handler.rfile.readline()
            if not line:
                break
            size_hex = line.split(b";", 1)[0].strip()
            try:
                size = int(size_hex, 16)
            except Exception:
                break
            if size == 0:
                handler.rfile.readline()
                break
            chunk = handler.rfile.read(size)
            total += len(chunk)
            if max_bytes is not None and total > max_bytes:
                raise ValueError("REQUEST_BODY_TOO_LARGE")
            chunks.append(chunk)
            handler.rfile.read(2)
        return b"".join(chunks)
    length = int(handler.headers.get("Content-Length", 0))
    if max_bytes is not None and length > max_bytes:
        raise ValueError("REQUEST_BODY_TOO_LARGE")
    return handler.rfile.read(length) if length > 0 else b""

def _smart_clip_new_job_id():
    ts = int(time.time() * 1000)
    return f"smartclip_{ts}_{random.randint(1000, 9999)}"

def _smart_clip_cleanup(max_age_sec=2 * 60 * 60):
    try:
        now = time.time()
    except Exception:
        now = 0.0
    with _smart_clip_lock:
        expired = []
        for jid, job in list(_smart_clip_jobs.items()):
            try:
                created = float(job.get("createdAt") or 0.0)
            except Exception:
                created = 0.0
            if now - created > max_age_sec:
                expired.append(jid)
        for jid in expired:
            _smart_clip_jobs.pop(jid, None)

def _smart_clip_update(job_id, **kwargs):
    with _smart_clip_lock:
        job = _smart_clip_jobs.get(job_id)
        if not job:
            return
        for k, v in kwargs.items():
            job[k] = v

def _run_smart_clip_job(job_id, local_src, options):
    try:
        try:
            from scenedetect import open_video, SceneManager
            from scenedetect.detectors import ContentDetector
        except Exception as e:
            _smart_clip_update(
                job_id,
                status="error",
                stage="import",
                error=f"缺少依赖 scenedetect/opencv: {str(e)}。请在 venv 中执行 pip install -r requirements.txt",
                progress=0.0,
            )
            return

        opt = options if isinstance(options, dict) else {}
        raw_mode = str(opt.get("mode") or "stable").strip().lower()
        mode_map = {"stable": "stable", "balanced": "balanced", "sensitive": "sensitive"}
        mode = mode_map.get(raw_mode, raw_mode)
        if mode not in ("stable", "balanced", "sensitive"):
            mode = "stable"
        try:
            max_segments = int(opt.get("maxSegments", 20))
        except Exception:
            max_segments = 20
        max_segments = max(2, min(200, max_segments))

        try:
            black_luma_thr = float(opt.get("blackLuma", 16.0))
        except Exception:
            black_luma_thr = 16.0
        black_luma_thr = max(0.0, min(60.0, black_luma_thr))
        try:
            min_black_sec = float(opt.get("minBlackSec", 0.5))
        except Exception:
            min_black_sec = 0.5
        min_black_sec = max(0.1, min(10.0, min_black_sec))

        _smart_clip_update(job_id, status="running", stage="detect", progress=0.01)

        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        def _ffprobe_duration_sec(p):
            try:
                cmd = [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=nw=1:nk=1",
                    p,
                ]
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo,
                )
                stdout, _ = process.communicate(timeout=20)
                if process.returncode != 0:
                    return 0.0
                txt = (stdout or b"").decode("utf-8", errors="ignore").strip()
                return float(txt) if txt else 0.0
            except Exception:
                return 0.0

        def _ffprobe_video_fps_str(p):
            try:
                cmd = [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=avg_frame_rate,r_frame_rate",
                    "-of",
                    "json",
                    p,
                ]
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo,
                )
                stdout, _ = process.communicate(timeout=20)
                if process.returncode != 0:
                    return None
                txt = (stdout or b"").decode("utf-8", errors="ignore").strip()
                if not txt:
                    return None
                j = json.loads(txt)
                streams = j.get("streams") or []
                if not streams:
                    return None
                s0 = streams[0] if isinstance(streams[0], dict) else {}
                avg = (s0.get("avg_frame_rate") or "").strip()
                rr = (s0.get("r_frame_rate") or "").strip()
                cand = None
                if avg and avg not in ("0/0", "0"):
                    cand = avg
                elif rr and rr not in ("0/0", "0"):
                    cand = rr
                if not cand:
                    return None

                def _to_float(x):
                    raw = (x or "").strip()
                    if not raw:
                        return 0.0
                    if "/" in raw:
                        a, b = raw.split("/", 1)
                        na = float(a)
                        nb = float(b)
                        if nb == 0:
                            return 0.0
                        return na / nb
                    return float(raw)

                fps_v = _to_float(cand)
                if not fps_v or fps_v <= 0:
                    return None
                buckets = (24, 25, 30, 50, 60)
                closest = None
                closest_d = 999.0
                for b in buckets:
                    d = abs(fps_v - float(b))
                    if d < closest_d:
                        closest_d = d
                        closest = b
                fps_i = int(closest) if closest is not None and closest_d <= 0.2 else int(round(fps_v))
                if fps_i <= 0:
                    return None
                return str(fps_i)
            except Exception:
                return None

        duration_sec = _ffprobe_duration_sec(local_src)
        if not duration_sec or duration_sec <= 0:
            duration_sec = 0.0
        fps_str = _ffprobe_video_fps_str(local_src)

        def _run_detect_content_boundaries(threshold, min_scene_sec):
            try:
                scene_manager = SceneManager()
                video = open_video(local_src)
                try:
                    fps = float(getattr(video, "frame_rate", 0.0) or 0.0)
                except Exception:
                    fps = 0.0
                if not fps or fps <= 0:
                    fps = 30.0
                min_scene_len = max(1, int(round(float(min_scene_sec) * fps)))
                scene_manager.add_detector(
                    ContentDetector(
                        threshold=float(threshold), min_scene_len=int(min_scene_len)
                    )
                )
                scene_manager.detect_scenes(video, show_progress=False)
                scene_list = scene_manager.get_scene_list() or []
                boundaries = []
                for i, (start_tc, _end_tc) in enumerate(scene_list):
                    if i == 0:
                        continue
                    try:
                        t = float(start_tc.get_seconds())
                    except Exception:
                        continue
                    if t and t > 0:
                        boundaries.append(t)
                dur = duration_sec
                if not dur or dur <= 0:
                    try:
                        if scene_list:
                            dur = float(scene_list[-1][1].get_seconds())
                    except Exception:
                        dur = 0.0
                return boundaries, dur
            except Exception:
                return [], duration_sec

        black_intervals = []
        try:
            import cv2

            if duration_sec and duration_sec > 0:
                sample_fps = 2.0 if duration_sec <= 900 else 1.0
                step = 1.0 / sample_fps
                cap = cv2.VideoCapture(local_src)
                t = 0.0
                blk_start = None
                margin = 0.15
                while t <= duration_sec:
                    cap.set(cv2.CAP_PROP_POS_MSEC, int(round(t * 1000)))
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        t += step
                        continue
                    try:
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        mean_luma = float(gray.mean())
                    except Exception:
                        mean_luma = 999.0
                    is_black = mean_luma <= black_luma_thr
                    if is_black:
                        if blk_start is None:
                            blk_start = t
                    else:
                        if blk_start is not None:
                            blk_end = t
                            if blk_end - blk_start >= min_black_sec:
                                s = max(0.0, blk_start - margin)
                                e = min(duration_sec, blk_end + margin)
                                if e > s:
                                    black_intervals.append((s, e))
                            blk_start = None
                    t += step
                if blk_start is not None:
                    blk_end = duration_sec
                    if blk_end - blk_start >= min_black_sec:
                        s = max(0.0, blk_start - margin)
                        e = min(duration_sec, blk_end)
                        if e > s:
                            black_intervals.append((s, e))
                try:
                    cap.release()
                except Exception:
                    pass
        except Exception:
            black_intervals = []

        def _is_in_black(mid_t):
            for s, e in black_intervals:
                if mid_t >= s and mid_t <= e:
                    return True
            return False

        def _postprocess(boundaries, min_scene_sec, debounce_sec, strip_black):
            bds = []
            for t in boundaries or []:
                try:
                    bds.append(float(t))
                except Exception:
                    pass
            for s, e in black_intervals:
                bds.append(float(s))
                bds.append(float(e))
            bds = [t for t in bds if duration_sec and t > 0.0 and t < duration_sec]
            bds.sort()

            debounced = []
            prev = None
            for t in bds:
                if prev is None:
                    debounced.append(t)
                    prev = t
                    continue
                if t - prev < float(debounce_sec):
                    continue
                debounced.append(t)
                prev = t
            bds = debounced

            raw_segments = []
            cur = 0.0
            for t in bds:
                if t - cur >= 0.05:
                    raw_segments.append((cur, t))
                cur = t
            if duration_sec and duration_sec - cur >= 0.05:
                raw_segments.append((cur, duration_sec))

            segments2 = []
            for s, e in raw_segments:
                if not (e > s):
                    continue
                mid = (s + e) / 2.0
                if strip_black and _is_in_black(mid):
                    continue
                segments2.append([float(s), float(e)])

            i = 0
            while i < len(segments2):
                s, e = segments2[i]
                dur = e - s
                if dur < float(min_scene_sec) and len(segments2) > 1:
                    if i == 0:
                        ns, ne = segments2[i + 1]
                        segments2[i + 1] = [s, ne]
                        segments2.pop(i)
                        continue
                    ps, pe = segments2[i - 1]
                    segments2[i - 1] = [ps, e]
                    segments2.pop(i)
                    i = max(0, i - 1)
                    continue
                i += 1

            segments2 = [seg for seg in segments2 if (seg[1] - seg[0]) >= 0.2]

            def _merge_to_limit(segs, limit):
                out = [list(x) for x in (segs or [])]
                if limit <= 1:
                    return out
                while len(out) > int(limit):
                    shortest_i = 0
                    shortest_d = 999999.0
                    for i, (s, e) in enumerate(out):
                        d = float(e) - float(s)
                        if d < shortest_d:
                            shortest_d = d
                            shortest_i = i
                    if len(out) <= 1:
                        break
                    if shortest_i == 0:
                        out[1] = [out[0][0], out[1][1]]
                        out.pop(0)
                        continue
                    if shortest_i == len(out) - 1:
                        out[-2] = [out[-2][0], out[-1][1]]
                        out.pop(-1)
                        continue
                    left_d = out[shortest_i - 1][1] - out[shortest_i - 1][0]
                    right_d = out[shortest_i + 1][1] - out[shortest_i + 1][0]
                    if left_d <= right_d:
                        out[shortest_i - 1] = [out[shortest_i - 1][0], out[shortest_i][1]]
                        out.pop(shortest_i)
                    else:
                        out[shortest_i + 1] = [out[shortest_i][0], out[shortest_i + 1][1]]
                        out.pop(shortest_i)
                return out

            segments2 = _merge_to_limit(segments2, max_segments)
            return segments2

        def _equal_split(duration_sec, max_segments):
            if not duration_sec or duration_sec <= 0:
                return []
            desired = int(round(duration_sec / 3.0))
            desired = max(2, desired)
            desired = min(int(max_segments), desired)
            step = float(duration_sec) / float(desired)
            if step < 0.2:
                desired = max(2, min(int(max_segments), int(duration_sec / 0.2)))
                if desired <= 1:
                    return []
                step = float(duration_sec) / float(desired)
            out = []
            t = 0.0
            for i in range(desired):
                s = t
                e = float(duration_sec) if i == desired - 1 else min(float(duration_sec), s + step)
                if e - s >= 0.2:
                    out.append([s, e])
                t = e
                if t >= duration_sec:
                    break
            return out

        profiles = {
            "stable": {"threshold": 27.0, "min_scene_sec": 1.0, "debounce_sec": 0.3, "strip_black": True},
            "balanced": {"threshold": 23.0, "min_scene_sec": 0.6, "debounce_sec": 0.2, "strip_black": True},
            "sensitive": {"threshold": 18.0, "min_scene_sec": 0.25, "debounce_sec": 0.1, "strip_black": False},
        }
        chain = ["stable", "balanced", "sensitive"] if mode == "stable" else (["balanced", "sensitive"] if mode == "balanced" else ["sensitive"])

        segments2 = []
        for key in chain:
            prof = profiles[key]
            content_boundaries, dur2 = _run_detect_content_boundaries(prof["threshold"], prof["min_scene_sec"])
            if dur2 and dur2 > 0 and (not duration_sec or duration_sec <= 0):
                duration_sec = dur2
            segments2 = _postprocess(content_boundaries, prof["min_scene_sec"], prof["debounce_sec"], prof["strip_black"])
            if len(segments2) >= 2:
                break

        if len(segments2) <= 1:
            segments2 = _equal_split(duration_sec, max_segments)

        if len(segments2) <= 1:
            _smart_clip_update(job_id, status="done", stage="done", progress=1.0, segments=[])
            return

        segments = []
        for i, (s, e) in enumerate(segments2):
            segments.append({"index": i + 1, "start": s, "end": e, "duration": e - s})

        _smart_clip_update(job_id, stage="cut", progress=0.05, total=len(segments))

        out_dir = os.path.join(OUTPUT_DIR, "SceneCuts", job_id)
        os.makedirs(out_dir, exist_ok=True)

        out_segments = []
        total = len(segments)
        for idx, seg in enumerate(segments):
            s = float(seg["start"])
            e = float(seg["end"])
            dur = max(0.01, e - s)
            ms_s = int(round(s * 1000))
            ms_e = int(round(e * 1000))
            filename = f"scene_{idx+1:03d}_{ms_s}-{ms_e}.mp4"
            out_path = os.path.join(out_dir, filename)

            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                local_src,
                "-ss",
                str(s),
                "-t",
                str(dur),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-c:a",
                "aac",
                out_path,
            ]
            if fps_str:
                cmd.insert(-1, "-r")
                cmd.insert(-1, fps_str)

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
            )
            try:
                _, stderr = process.communicate(timeout=300)
            except subprocess.TimeoutExpired:
                process.kill()
                _smart_clip_update(job_id, status="error", stage="cut", error="FFmpeg process timeout")
                return
            if process.returncode != 0:
                try:
                    err_text = (stderr or b"").decode("utf-8", errors="ignore").strip()
                except Exception:
                    err_text = ""
                _smart_clip_update(job_id, status="error", stage="cut", error=f"FFmpeg processing failed: {err_text or 'unknown error'}")
                return

            rel = f"output/SceneCuts/{job_id}/{filename}"
            out_segments.append(
                {
                    "index": idx + 1,
                    "start": s,
                    "end": e,
                    "duration": dur,
                    "path": rel,
                    "localPath": rel,
                    "url": f"/{rel}",
                }
            )

            p = 0.05 + 0.95 * float(idx + 1) / float(total)
            _smart_clip_update(job_id, stage="cut", progress=min(0.999, p), doneCount=idx + 1, total=total)

        _smart_clip_update(job_id, status="done", stage="done", progress=1.0, segments=out_segments)
    except Exception as e:
        _smart_clip_update(job_id, status="error", stage="error", error=str(e))

def _load_json_file(p):
    try:
        if not os.path.exists(p):
            return {}
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _atomic_write_json(p, data):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)

def _scan_max_gen_seq_for_date(date_str):
    try:
        pat = re.compile(r"^gen_" + re.escape(date_str) + r"_(\d+)\.[a-z0-9]{1,5}$")
        max_n = 0
        for root, _, files in os.walk(OUTPUT_DIR):
            for fn in files:
                m = pat.match(fn)
                if not m:
                    continue
                try:
                    n = int(m.group(1))
                    if n > max_n:
                        max_n = n
                except Exception:
                    continue
        return max_n
    except Exception:
        return 0

def _next_gen_output_filename(ext):
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    with _gen_seq_lock:
        state = _load_json_file(GEN_SEQ_STATE_FILE)
        last = 0
        try:
            last = int(state.get(date_str) or 0)
        except Exception:
            last = 0
        if last <= 0:
            scanned = _scan_max_gen_seq_for_date(date_str)
            if scanned > last:
                last = scanned
        n = last + 1
        state[date_str] = n
        try:
            _atomic_write_json(GEN_SEQ_STATE_FILE, state)
        except Exception:
            pass
    seq = str(n).zfill(4)
    return f"gen_{date_str}_{seq}.{ext}"

class Handler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    # 灞忚斀鏃ュ織鍣煶锛堟寜闇€娉ㄩ噴鎺夛級
    def log_message(self, fmt, *args):
        pass

    def send_head(self):
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            parts = urllib.parse.urlsplit(self.path)
            if not parts.path.endswith('/'):
                self.send_response(301)
                new_parts = (parts[0], parts[1], parts[2] + '/', parts[3], parts[4])
                new_url = urllib.parse.urlunsplit(new_parts)
                self.send_header("Location", new_url)
                self.end_headers()
                return None
            for index in ("index.html", "index.htm"):
                index_path = os.path.join(path, index)
                if os.path.exists(index_path):
                    path = index_path
                    break
            else:
                return self.list_directory(path)
        ctype = self.guess_type(path)
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(404, "File not found")
            return None

        fs = os.fstat(f.fileno())
        size = fs.st_size
        range_header = self.headers.get("Range", "")
        self._range = None

        if range_header.startswith("bytes="):
            spec = range_header[6:].strip()
            if "," not in spec:
                start_s, dash, end_s = spec.partition("-")
                try:
                    if start_s == "":
                        suffix_len = int(end_s)
                        if suffix_len <= 0:
                            raise ValueError()
                        start = max(0, size - suffix_len)
                        end = size - 1
                    else:
                        start = int(start_s)
                        end = int(end_s) if end_s else size - 1
                    if start < 0 or start >= size:
                        raise ValueError()
                    end = min(end, size - 1)
                    if end < start:
                        raise ValueError()
                    self._range = (start, end)
                except Exception:
                    f.close()
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return None

        if self._range:
            start, end = self._range
            self.send_response(206)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()
            f.seek(start)
            return f

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(size))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        return f

    def copyfile(self, source, outputfile):
        rng = getattr(self, "_range", None)
        if not rng:
            return super().copyfile(source, outputfile)
        start, end = rng
        remaining = end - start + 1
        bufsize = 64 * 1024
        while remaining > 0:
            chunk = source.read(min(bufsize, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)

    # 鈹€鈹€ OPTIONS 棰勬锛圕ORS锛夆攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, PATCH, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, X-AIC-Install-Id",
        )
        self.end_headers()

    # 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲
    #  DELETE  /api/v2/projects/{filename}
    # 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲
    def do_DELETE(self):
        path = self.path.split("?")[0]
        if path.startswith("/api/v2/projects/"):
            fn = unquote(path[len("/api/v2/projects/"):])
            if fn and ".." not in fn and fn.endswith(".json"):
                fp = os.path.join(CANVAS_DIR, fn)
                if os.path.exists(fp):
                    os.remove(fp)
                    _json_ok(self, {"success": True})
                else:
                    _json_err(self, 404, "Project not found")
                return
                
        if path.startswith("/api/v2/assets/"):
            fn = unquote(path[len("/api/v2/assets/"):])
            if fn and ".." not in fn and fn.endswith(".json"):
                fp = os.path.join(ASSETS_DIR, fn)
                if os.path.exists(fp):
                    os.remove(fp)
                    _json_ok(self, {"success": True})
                else:
                    _json_err(self, 404, "Asset not found")
                return
                
        _json_err(self, 400, "Invalid request")

    # 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲
    #  PATCH  /api/v2/projects/{filename}  鈫?rename
    # 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲
    def do_PATCH(self):
        import re
        path = self.path.split("?")[0]
        if path.startswith("/api/v2/projects/"):
            fn = unquote(path[len("/api/v2/projects/"):])
            if fn and ".." not in fn and fn.endswith(".json"):
                fp = os.path.join(CANVAS_DIR, fn)
                if not os.path.exists(fp):
                    _json_err(self, 404, "Project not found"); return
                body = _read_body(self)
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    _json_err(self, 400, "Invalid JSON"); return
                new_name = data.get("name", "").strip()
                if not new_name:
                    _json_err(self, 400, "Name required"); return
                safe = re.sub(r'[\\/:*?"<>|]', "_", new_name)
                new_fn = safe + ".json"
                new_fp = os.path.join(CANVAS_DIR, new_fn)
                os.rename(fp, new_fp)
                _json_ok(self, {"success": True, "filename": new_fn})
                return
        _json_err(self, 400, "Invalid request")

    # 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲
    #  GET
    # 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲
    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/api/v2/subscription/status":
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(
                parsed.query,
                keep_blank_values=True,
                max_num_fields=20,
            )
            install_id_qs = (qs.get("installId") or [""])[0]
            install_id = SUBSCRIPTION_CLIENT.normalize_install_id(install_id_qs)
            if not install_id:
                install_id = _extract_install_id_from_request(self)
            if not install_id:
                _json_ok(
                    self,
                    {
                        "success": False,
                        "status": SUB_STATUS_NONE,
                        "errorCode": SUB_ERROR_INVALID_ARGUMENTS,
                        "message": "Missing installId",
                        "contactText": DEFAULT_SUB_CONTACT_TEXT,
                        "contactUrl": DEFAULT_SUB_CONTACT_URL,
                    },
                )
                return
            payload = SUBSCRIPTION_CLIENT.fetch_subscription_status(install_id)
            if isinstance(payload, dict):
                _json_ok(self, payload)
                return
            _json_ok(
                self,
                {
                    "success": False,
                    "status": SUB_STATUS_NONE,
                    "errorCode": "SUBSCRIPTION_SERVICE_UNAVAILABLE",
                    "message": "授权服务不可用",
                    "contactText": DEFAULT_SUB_CONTACT_TEXT,
                    "contactUrl": DEFAULT_SUB_CONTACT_URL,
                },
            )
            return

        # 鈹€鈹€ SSE 蹇冭烦闀胯繛鎺?鈹€鈹€
        if path == "/api/v2/heartbeat_stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                while True:
                    self.wfile.write(b"data: ping\n\n")
                    self.wfile.flush()
                    time.sleep(5)
            except Exception:
                # 瀹㈡埛绔柇寮€杩炴帴锛堝埛鏂扮綉椤垫垨鍏抽棴缃戦〉锛?
                pass
            return

        # 鈹€鈹€ 閫氱敤浠诲姟鐘舵€佷唬鐞?(GET) 鈹€鈹€
        if path == "/api/v2/proxy/task":
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            # 浣跨敤 keep_blank_values=False 鍜?max_num_fields=10 閬垮厤瑙ｆ瀽闂
            qs = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=10)
            api_url = qs.get("apiUrl", [""])[0].strip() if "apiUrl" in qs else ""
            api_key = qs.get("apiKey", [""])[0].strip() if "apiKey" in qs else ""
            # 鍘婚櫎鍙兘鐨勯€楀彿
            api_url = api_url.rstrip(',')
            api_key = api_key.rstrip(',')
            if not api_url or not api_key:
                _json_err(self, 400, "Missing apiUrl or apiKey"); return
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0"
            }
            try:
                # 灏濊瘯浣跨敤 requests (濡傛灉瀹夎浜?
                try:
                    import requests
                    resp = requests.get(api_url, headers=headers, timeout=30)
                    self.send_response(resp.status_code)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(resp.content)
                    return
                except ImportError:
                    pass
                except Exception:
                    pass

                # 鍏滃簳浣跨敤 urllib锛堜娇鐢ㄦā鍧楅《灞傚鍏ワ紝閬垮厤鍑芥暟灞€閮ㄤ綔鐢ㄥ煙姹℃煋锛?
                req = urllib.request.Request(api_url, headers=headers, method="GET")
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        resp_data = resp.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(resp_data)
                except urllib.error.HTTPError as e:
                    self.send_response(e.code)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(e.read())
                except Exception as e:
                    _json_err(self, 500, f"Urllib polling error: {str(e)}")
            except Exception as e:
                _json_err(self, 500, f"Task proxy global error: {repr(e)}")
            return

        # 鈹€鈹€ 鑷姩鏇存柊锛氭鏌ユ帴鍙?鈹€鈹€
        if path == "/api/v2/update/check":
            with _update_lock:
                info = _update_info
            if info:
                _json_ok(self, info)
            else:
                _json_ok(self, {'hasUpdate': False, 'localVersion': LOCAL_VERSION})
            return

        if path == "/api/v2/video/smart_clip/status":
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=10)
            job_id = qs.get("jobId", [""])[0].strip() if "jobId" in qs else ""
            if not job_id:
                _json_err(self, 400, "Missing jobId")
                return
            _smart_clip_cleanup()
            with _smart_clip_lock:
                job = _smart_clip_jobs.get(job_id)
            if not job:
                _json_err(self, 404, "Job not found")
                return
            _json_ok(self, job)
            return

        if path == "/api/v2/matting/sam3/info":
            info = {
                "success": True,
                "ortProviders": [],
                "ortVersion": "",
                "sam3EnableTrt": False,
                "tensorrtRuntimeFound": False,
                "sam3IdleSec": None,
                "sam3IdleUnloadSec": None,
                "sam3Enabled": False,
                "sam3SessionsLoaded": False,
                "sessions": None,
            }
            try:
                info["sam3Enabled"] = _sam3_enabled()
            except Exception:
                info["sam3Enabled"] = False
            try:
                info["sam3EnableTrt"] = (os.environ.get("SAM3_ENABLE_TRT", "0") or "0").strip() in ("1", "true", "True", "YES", "yes")
            except Exception:
                info["sam3EnableTrt"] = False
            try:
                info["tensorrtRuntimeFound"] = _sam3_has_tensorrt_runtime()
            except Exception:
                info["tensorrtRuntimeFound"] = False
            try:
                ort = _sam3_get_ort()
                info["ortVersion"] = getattr(ort, "__version__", "") or ""
                try:
                    info["ortProviders"] = ort.get_available_providers()
                except Exception:
                    info["ortProviders"] = []
            except Exception:
                pass
            try:
                try:
                    unload_sec = float(os.environ.get("SAM3_IDLE_UNLOAD_SEC", "300") or "300")
                except Exception:
                    unload_sec = 300.0
                info["sam3IdleUnloadSec"] = unload_sec
                info["sam3IdleSec"] = _sam3_get_idle_sec()
            except Exception:
                pass
            try:
                info["sam3SessionsLoaded"] = _sam3_sessions is not None
            except Exception:
                info["sam3SessionsLoaded"] = False
            if info.get("sam3Enabled") and info.get("sam3SessionsLoaded"):
                try:
                    sess = _sam3_sessions
                    info["sessions"] = {
                        "image": sess["image"].get_providers() if sess and sess.get("image") else [],
                        "language": sess["language"].get_providers() if sess and sess.get("language") else [],
                        "decode": sess["decode"].get_providers() if sess and sess.get("decode") else [],
                    }
                except Exception as e:
                    info["success"] = False
                    info["error"] = str(e)
            _json_ok(self, info)
            return

        if path == "/api/config":
            cfg = {}
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                    try:
                        cfg = json.load(f)
                    except json.JSONDecodeError:
                        pass
            
            # 馃敟 GRSAI API Key 鐜鍙橀噺鏅鸿兘淇濆簳閫昏緫 馃敟
            env_grsai_key = os.environ.get("GRSAI_API_KEY", "").strip()
            if env_grsai_key:
                old_key = cfg.get("apiKey") or cfg.get("apiKeyInput")
                prov_grsai = cfg.get("providers", {}).get("grsai", {})
                new_key = prov_grsai.get("apiKey")
                
                # 褰撲笖浠呭綋瀛?GRSAI key 鐨勪綅缃兘涓虹┖鏃讹紝鎵嶇敤鐜鍙橀噺娉ㄥ叆鍐呭瓨閰嶇疆锛屼笅鍙戠粰鍓嶇
                if not old_key and not new_key:
                    if "providers" not in cfg:
                        cfg["providers"] = {}
                    if "grsai" not in cfg["providers"]:
                        cfg["providers"]["grsai"] = {}
                    cfg["providers"]["grsai"]["apiKey"] = env_grsai_key

            # 馃敟 PPIO API Key 鐜鍙橀噺鏅鸿兘淇濆簳閫昏緫 馃敟
            env_ppio_key = os.environ.get("PPIO_API_KEY", "").strip()
            if env_ppio_key:
                prov_ppio = cfg.get("providers", {}).get("ppio", {})
                new_key = prov_ppio.get("apiKey")
                
                # 褰撳瓨 PPIO key 涓虹┖鏃讹紝鎵嶇敤鐜鍙橀噺娉ㄥ叆鍐呭瓨閰嶇疆
                if not new_key:
                    if "providers" not in cfg:
                        cfg["providers"] = {}
                    if "ppio" not in cfg["providers"]:
                        cfg["providers"]["ppio"] = {}
                    cfg["providers"]["ppio"]["apiKey"] = env_ppio_key

            _json_ok(self, cfg)
            return

        # 鈹€鈹€ 鑷畾涔?AI 鍏ㄥ眬閰嶇疆锛圙ET锛夆攢鈹€
        if path == "/api/v2/config/custom-ai":
            cfg = _get_custom_ai_config()
            # apiKey 杩斿洖鍓嶄袱浣?+ 鏄熷彿鎵撶爜锛岄槻姝㈡硠闇?
            key = cfg["apiKey"]
            masked = key[:4] + "*" * (len(key) - 4) if len(key) > 4 else ("*" * len(key) if key else "")
            _json_ok(self, {"apiUrl": cfg["apiUrl"], "apiKeyMasked": masked, "hasKey": bool(key), "source": cfg["source"]})
            return

        # 鈹€鈹€ 鍒楀嚭鐢诲竷椤圭洰 鈹€鈹€
        if path == "/api/v2/projects":
            files = []
            for fn in os.listdir(CANVAS_DIR):
                if not fn.endswith(".json"):
                    continue
                fp = os.path.join(CANVAS_DIR, fn)
                files.append({
                    "filename": fn,
                    "name":     fn[:-5],
                    "mtime":    os.path.getmtime(fp),
                })
            files.sort(key=lambda x: x["mtime"], reverse=True)
            _json_ok(self, files)
            return

        # 鈹€鈹€ 鍔犺浇鎸囧畾鐢诲竷椤圭洰 鈹€鈹€
        if path.startswith("/api/v2/projects/") and not path.endswith("/save"):
            fn = unquote(path[len("/api/v2/projects/"):])
            if fn and ".." not in fn:
                fp = os.path.join(CANVAS_DIR, fn)
                if os.path.exists(fp):
                    with open(fp, "r", encoding="utf-8-sig") as f:
                        _json_ok(self, json.load(f))
                else:
                    _json_err(self, 404, "Project not found")
                return

        # 鈹€鈹€ 璧勪骇鏁版嵁鎺ュ彛 鈹€鈹€
        if path == "/api/v2/assets":
            files = []
            if os.path.exists(ASSETS_DIR):
                for fn in os.listdir(ASSETS_DIR):
                    if not fn.endswith(".json"): continue
                    fp = os.path.join(ASSETS_DIR, fn)
                    try:
                        with open(fp, "r", encoding="utf-8-sig") as f:
                            data = json.load(f)
                            if isinstance(data, dict) and not data.get("id"):
                                data["id"] = fn[:-5]
                            files.append(data)
                    except Exception:
                        pass
            _json_ok(self, files)
            return

        # 鈹€鈹€ 璇诲彇鐢ㄦ埛閰嶇疆鏂囦欢 鈹€鈹€
        if path.startswith("/api/v2/user/") and not path.startswith("/api/v2/user/presets"):
            fn = path[len("/api/v2/user/"):]
            if fn and fn.endswith(".json") and "/" not in fn and ".." not in fn:
                fp = os.path.join(USER_DIR, fn)
                if os.path.exists(fp):
                    with open(fp, "r", encoding="utf-8-sig") as f:
                        _json_ok(self, json.load(f))
                else:
                    _json_ok(self, {})   # 棣栨璁块棶杩斿洖绌哄璞?
                return

        # 鈹€鈹€ 鑾峰彇鍩轰簬鏂囦欢澶筎XT鐨勮嚜瀹氫箟鎻愮ず璇嶉璁?鈹€鈹€
        if path == "/api/v2/user/presets":
            prompt_dir = os.path.join(USER_DIR, "prompt")
            # 纭繚鍒濆鐨勫洓涓垎绫绘枃浠跺す瀛樺湪锛屽苟鐢熸垚绀轰緥
            default_types = ["ai-image", "ai-text", "ai-video", "ai-audio"]
            for t in default_types:
                t_dir = os.path.join(prompt_dir, t)
                if not os.path.exists(t_dir):
                    os.makedirs(t_dir, exist_ok=True)

            # 閬嶅巻缁撴瀯鏋勫缓棰勮瀛楀吀
            result = {}
            if os.path.exists(prompt_dir):
                for node_type in os.listdir(prompt_dir):
                    t_dir = os.path.join(prompt_dir, node_type)
                    if os.path.isdir(t_dir):
                        result[node_type] = []
                        for fn in os.listdir(t_dir):
                            if fn.endswith(".txt"):
                                fp = os.path.join(t_dir, fn)
                                try:
                                    with open(fp, "r", encoding="utf-8") as f:
                                        content = f.read().strip()
                                        if content:
                                            result[node_type].append({
                                                "title": fn[:-4], # 鍘婚櫎 .txt 鎵╁睍鍚?
                                                "template": content
                                            })
                                except Exception as e:
                                    print(f"Error reading preset {fp}: {e}")
            _json_ok(self, result)
            return

        # 鈹€鈹€ 鍏朵綑闈欐€佹枃浠讹紙鐢?SimpleHTTPRequestHandler 澶勭悊锛夆攢鈹€
        try:
            super().do_GET()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def end_headers(self):
        # 避免重复响应头导致浏览器 CORS 拒绝（例如 "*, *"）
        header_buf = getattr(self, "_headers_buffer", []) or []
        has_cache_control = any(b"Cache-Control:" in h for h in header_buf)
        has_cors = any(b"Access-Control-Allow-Origin:" in h for h in header_buf)
        if not has_cache_control:
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        if not has_cors:
            self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    # 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲
    #  POST
    # 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲
    def do_POST(self):
        path = self.path.split("?")[0]

        if path == "/api/v2/subscription/activate":
            body = _read_body(self)
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                _json_err(self, 400, "Invalid JSON")
                return
            if not isinstance(data, dict):
                _json_err(self, 400, "Invalid JSON")
                return
            install_id = _extract_install_id_from_request(self, data)
            cdkey = str(data.get("cdkey") or "").strip()
            if not install_id or not cdkey:
                _json_ok(
                    self,
                    {
                        "success": False,
                        "errorCode": SUB_ERROR_INVALID_ARGUMENTS,
                        "message": "Missing installId or cdkey",
                        "contactText": DEFAULT_SUB_CONTACT_TEXT,
                        "contactUrl": DEFAULT_SUB_CONTACT_URL,
                    },
                )
                return
            payload = SUBSCRIPTION_CLIENT.activate_cdkey(install_id, cdkey)
            _clear_vip_allow_cache(install_id)
            if isinstance(payload, dict):
                _json_ok(self, payload)
                return
            _json_ok(
                self,
                {
                    "success": False,
                    "errorCode": "SUBSCRIPTION_SERVICE_UNAVAILABLE",
                    "message": "授权服务不可用",
                    "contactText": DEFAULT_SUB_CONTACT_TEXT,
                    "contactUrl": DEFAULT_SUB_CONTACT_URL,
                },
            )
            return

        # 鈹€鈹€ 淇濆瓨 API Key 閰嶇疆 鈹€鈹€
        if path == "/api/config":
            body = _read_body(self)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                _json_err(self, 400, "Invalid JSON")
                return
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            _json_ok(self, {"success": True})
            return

        # 鈹€鈹€ 淇濆瓨鐢诲竷椤圭洰 鈹€鈹€
        if path == "/api/v2/projects/save":
            body = _read_body(self)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                _json_err(self, 400, "Invalid JSON")
                return

            name = data.get("projectName", "未命名画布").strip() or "未命名画布"
            # 鏂囦欢鍚嶅畨鍏ㄥ寲锛氬彧淇濈暀涓枃銆佸瓧姣嶃€佹暟瀛椼€佺┖鏍笺€佹í鏉?
            safe = re.sub(r'[\\/:*?"<>|]', "_", name)
            fname = safe + ".json"
            fpath = os.path.join(CANVAS_DIR, fname)

            # 鍏煎 V1 鍜?V2 鏍煎紡锛歏2 浼氫紶鏉?canvases 鍜?activeCanvasId锛孷1 鍘熺敓浼犳潵 nodes 鍜?edges
            payload = {}
            if "canvases" in data:
                payload["canvases"] = data["canvases"]
                payload["activeCanvasId"] = data.get("activeCanvasId", "canvas_1")
            else:
                payload["nodes"] = data.get("nodes", {})
                payload["edges"] = data.get("edges", {})
                payload["viewport"] = data.get("viewport", {})
                
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            _json_ok(self, {"success": True, "filename": fname})
            return

        # 鈹€鈹€ 淇濆瓨鍗曚釜璧勪骇 鈹€鈹€
        if path == "/api/v2/assets/save":
            body = _read_body(self)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                _json_err(self, 400, "Invalid JSON")
                return
            
            asset_id = data.get("id")
            if not asset_id:
                _json_err(self, 400, "Asset ID required")
                return
                
            safe_id = re.sub(r'[\\/:*?"<>|]', "_", str(asset_id))
            fname = safe_id + ".json"
            fpath = os.path.join(ASSETS_DIR, fname)
            
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            _json_ok(self, {"success": True, "id": asset_id})
            return

        # 鈹€鈹€ 淇濆瓨璧勪骇缂╃暐鍥撅紙data/assets/thumbs锛?鈹€鈹€
        if path == "/api/v2/assets/thumb/save":
            body = _read_body(self)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                _json_err(self, 400, "Invalid JSON")
                return

            asset_id = data.get("assetId") or data.get("id")
            key = data.get("key") or data.get("idx") or "0"
            data_url = data.get("dataUrl") or ""

            if not asset_id:
                _json_err(self, 400, "Asset ID required")
                return
            if not isinstance(data_url, str) or not data_url.startswith("data:image/"):
                _json_err(self, 400, "Invalid dataUrl")
                return

            try:
                header, b64 = data_url.split(",", 1)
            except Exception:
                _json_err(self, 400, "Invalid dataUrl")
                return

            mime = "image/jpeg"
            try:
                mime = header[5:].split(";", 1)[0]
            except Exception:
                pass

            ext = ".jpg"
            if mime.endswith("png"):
                ext = ".png"
            elif mime.endswith("webp"):
                ext = ".webp"

            safe_id = re.sub(r'[\\/:*?"<>|]', "_", str(asset_id))
            safe_key = re.sub(r'[\\/:*?"<>|]', "_", str(key))
            fname = f"{safe_id}_{safe_key}{ext}"
            fpath = os.path.join(ASSET_THUMBS_DIR, fname)

            try:
                raw = base64.b64decode(b64)
            except Exception:
                _json_err(self, 400, "Invalid base64")
                return

            with open(fpath, "wb") as f:
                f.write(raw)

            rel_url = f"/data/assets/thumbs/{fname}"
            _json_ok(self, {"success": True, "url": rel_url, "localPath": f"data/assets/thumbs/{fname}", "filename": fname})
            return

        # 鈹€鈹€ 鍐欏叆鐢ㄦ埛閰嶇疆鏂囦欢 鈹€鈹€
        if path.startswith("/api/v2/user/"):
            fn = path[len("/api/v2/user/"):]
            if not fn or not fn.endswith(".json") or "/" in fn or ".." in fn:
                _json_err(self, 400, "Invalid filename")
                return
            body = _read_body(self)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                _json_err(self, 400, "Invalid JSON")
                return
            fp = os.path.join(USER_DIR, fn)
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            _json_ok(self, {"success": True})
            return

        # 鈹€鈹€ 鏂囦欢涓婁紶 鈹€鈹€
        if path == "/api/upload":
            try:
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                content_type = self.headers.get("Content-Type", "") or ""
                try:
                    body = _read_body(self, MAX_UPLOAD_BYTES)
                except ValueError as e:
                    if str(e) == "REQUEST_BODY_TOO_LARGE":
                        _json_err(self, 413, "Upload file too large")
                        return
                    raise

                filename = (qs.get("filename", [""])[0] or "").strip()
                file_bytes = body

                if content_type.startswith("multipart/form-data") and b"\r\n" in body:
                    m = re.search(r'boundary=([^;]+)', content_type)
                    boundary = (m.group(1).strip().strip('"') if m else "")
                    if boundary:
                        boundary_bytes = ("--" + boundary).encode("utf-8", "ignore")
                        parts = body.split(boundary_bytes)
                        for part in parts:
                            if b'Content-Disposition:' not in part:
                                continue
                            if b'name="file"' not in part and b"name='file'" not in part:
                                continue
                            header_end = part.find(b"\r\n\r\n")
                            if header_end == -1:
                                continue
                            header_blob = part[:header_end].decode("utf-8", "ignore")
                            data_blob = part[header_end + 4 :]
                            if data_blob.endswith(b"\r\n"):
                                data_blob = data_blob[:-2]
                            if data_blob.endswith(b"--"):
                                data_blob = data_blob[:-2]
                            if not filename:
                                mf = re.search(r'filename="([^"]+)"', header_blob)
                                if mf:
                                    filename = mf.group(1).strip()
                            file_bytes = data_blob
                            break

                if len(file_bytes) > MAX_UPLOAD_BYTES:
                    _json_err(self, 413, "Upload file too large")
                    return

                if not filename:
                    filename = "upload"

                safe_fn = re.sub(r'[\\/:*?"<>|]', "_", os.path.basename(filename))
                fpath = os.path.join(UPLOADS_DIR, safe_fn)
                with open(fpath, "wb") as f:
                    f.write(file_bytes)
                rel_url = f"/data/uploads/{safe_fn}"
                _json_ok(self, {"url": rel_url, "localPath": f"data/uploads/{safe_fn}", "filename": safe_fn})
            except Exception as e:
                try:
                    _json_err(self, 500, f"Upload failed: {str(e)}")
                except Exception:
                    pass
            return

        # 鈹€鈹€ 闈欓粯鏈湴纭浠?(鍓嶇鐢熸垚鍚庤皟鐢ㄤ繚瀛樺埌 output) 鈹€鈹€
        if path == "/api/v2/save_output":
            try:
                from urllib.parse import urlparse, parse_qs

                qs = parse_qs(urlparse(self.path).query)
                ext = (qs.get("ext", ["png"])[0] or "png").strip().lower()
                if not re.match(r"^[a-z0-9]{1,5}$", ext):
                    ext = "png"

                sub_dir = (qs.get("subDir", [""])[0] or "").strip()
                kind = (qs.get("kind", [""])[0] or "").strip()
                if kind and not re.match(r"^[a-zA-Z0-9_-]+$", kind):
                    kind = ""
                if sub_dir and re.match(r"^[a-zA-Z0-9_-]+$", sub_dir):
                    target_dir = os.path.join(OUTPUT_DIR, sub_dir)
                    os.makedirs(target_dir, exist_ok=True)
                    filename = _next_gen_output_filename(ext)
                    fpath = os.path.join(target_dir, filename)
                    rel_path = f"output/{sub_dir}/{filename}"
                else:
                    filename = _next_gen_output_filename(ext)
                    fpath = os.path.join(OUTPUT_DIR, filename)
                    rel_path = f"output/{filename}"

                body = _read_body(self)
                if body:
                    with open(fpath, "wb") as f:
                        f.write(body)
                    if kind:
                        meta_file = os.path.join(OUTPUT_DIR, ".output_meta.json")
                        meta = _load_json_file(meta_file)
                        items = meta.get("items") if isinstance(meta.get("items"), list) else []
                        items.append(
                            {
                                "kind": kind,
                                "localPath": rel_path,
                                "ts": int(time.time()),
                            }
                        )
                        if len(items) > 2000:
                            items = items[-2000:]
                        meta["items"] = items
                        try:
                            _atomic_write_json(meta_file, meta)
                        except Exception:
                            pass
                    _json_ok(
                        self,
                        {
                            "success": True,
                            "filename": filename,
                            "path": rel_path,
                            "localPath": rel_path,
                            "url": f"/{rel_path}",
                        },
                    )
                else:
                    _json_err(self, 400, "Empty payload")
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception as e:
                try:
                    _json_err(self, 500, f"save_output failed: {str(e)}")
                except Exception:
                    pass
            return

        if path == "/api/v2/matting/sam3/segment":
            body = _read_body(self)
            try:
                data = json.loads(body or b"{}")
            except Exception:
                _json_err(self, 400, "Invalid JSON")
                return
            if not _sam3_enabled():
                _json_err(self, 503, "SAM3 disabled")
                return
            _sam3_touch()

            image_local_path = data.get("imageLocalPath") or data.get("localPath") or ""
            image_base64 = data.get("imageBase64") or ""
            points = data.get("points") or []
            if not isinstance(points, list):
                _json_err(self, 400, "Invalid points")
                return

            abs_path = None
            if not image_base64:
                abs_path = _sam3_safe_resolve_image_path(image_local_path)
                if not abs_path:
                    _json_err(self, 400, "Invalid imageLocalPath or imageBase64")
                    return

            try:
                with _sam3_infer_lock:
                    mask_u8, mw, mh = _sam3_run_segment(
                        abs_path=abs_path,
                        b64_data=image_base64,
                        points=points,
                        prompt=data.get("textPrompt") or data.get("prompt") or "visual",
                        single_point_box_px=data.get("singlePointBoxPx"),
                        multi_point_pad_ratio=data.get("multiPointPadRatio"),
                    )
                from PIL import Image
                import io
                im = Image.fromarray(mask_u8, mode="L")
                buf = io.BytesIO()
                im.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                _json_ok(self, {"success": True, "maskPngBase64": b64, "maskWidth": mw, "maskHeight": mh})
            except Exception as e:
                _json_err(self, 500, str(e))
            return

        if path == "/api/v2/matting/sam3/segment_raw":
            body = _read_body(self)
            try:
                data = json.loads(body or b"{}")
            except Exception:
                _json_err(self, 400, "Invalid JSON")
                return
            if not _sam3_enabled():
                _json_err(self, 503, "SAM3 disabled")
                return
            _sam3_touch()

            image_local_path = data.get("imageLocalPath") or data.get("localPath") or ""
            image_base64 = data.get("imageBase64") or ""
            points = data.get("points") or []
            if not isinstance(points, list):
                _json_err(self, 400, "Invalid points")
                return

            abs_path = None
            if not image_base64:
                abs_path = _sam3_safe_resolve_image_path(image_local_path)
                if not abs_path:
                    _json_err(self, 400, "Invalid imageLocalPath or imageBase64")
                    return

            try:
                with _sam3_infer_lock:
                    mask_u8, mw, mh = _sam3_run_segment(
                        abs_path=abs_path,
                        b64_data=image_base64,
                        points=points,
                        prompt=data.get("textPrompt") or data.get("prompt") or "visual",
                    )
                buf = bytes(mask_u8.tobytes())
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("X-Mask-Width", str(int(mw)))
                self.send_header("X-Mask-Height", str(int(mh)))
                self.send_header("Content-Length", str(len(buf)))
                self.end_headers()
                self.wfile.write(buf)
            except Exception as e:
                _json_err(self, 500, str(e))
            return

        if path == "/api/v2/matting/sam3/prepare":
            body = _read_body(self)
            try:
                data = json.loads(body or b"{}")
            except Exception:
                _json_err(self, 400, "Invalid JSON")
                return
            if not _sam3_enabled():
                _json_err(self, 503, "SAM3 disabled")
                return
            _sam3_touch()

            image_local_path = data.get("imageLocalPath") or data.get("localPath") or ""
            image_base64 = data.get("imageBase64") or ""

            abs_path = None
            if not image_base64:
                abs_path = _sam3_safe_resolve_image_path(image_local_path)
                if not abs_path:
                    _json_err(self, 400, "Invalid imageLocalPath or imageBase64")
                    return

            try:
                with _sam3_infer_lock:
                    _sam3_get_image_embedding(abs_path=abs_path, b64_data=image_base64)
                    _sam3_get_language_features(prompt=data.get("textPrompt") or data.get("prompt") or "visual")
                _json_ok(self, {"success": True})
            except Exception as e:
                _json_err(self, 500, str(e))
            return

        # 鈹€鈹€ 瑙嗛瑁佸壀 (渚濊禆 FFmpeg) 鈹€鈹€
        if path.rstrip("/") == "/api/v2/video/cut":
            body = _read_body(self)
            try:
                data = json.loads(body or b"{}")
            except Exception:
                _json_err(self, 400, "Invalid JSON")
                return
            
            src_path = (data.get("src") or "").strip()
            start_sec = float(data.get("start", 0))
            end_sec = float(data.get("end", 0))
            
            if not src_path or end_sec <= start_sec:
                _json_err(self, 400, "Invalid parameters")
                return
            
            # 瀹夊叏澶勭悊婧愯矾寰勶細鍘婚櫎鍓嶅鏂滄潬锛岃浆鎹负鏈湴缁濆璺緞锛堝熀浜?DIRECTORY锛?
            safe_src = src_path.lstrip("/")
            norm_src = os.path.normpath(safe_src)
            if norm_src.startswith("..") or norm_src.startswith("../") or norm_src.startswith("..\\"):
                _json_err(self, 400, "Invalid src path")
                return
            local_src = os.path.join(DIRECTORY, norm_src)
            
            if not os.path.exists(local_src):
                _json_err(self, 404, "Source video not found")
                return
                
            # 鍑嗗杈撳嚭鐩綍
            cut_dir = os.path.join(OUTPUT_DIR, "CutVideo")
            os.makedirs(cut_dir, exist_ok=True)
            
            ts = int(time.time() * 1000)
            rand_str = f"{random.randint(100,999)}"
            filename = f"cut_{ts}_{rand_str}.mp4"
            out_path = os.path.join(cut_dir, filename)
            
            try:
                def _ffprobe_video_fps_str(p, startupinfo):
                    try:
                        cmd = [
                            "ffprobe",
                            "-v",
                            "error",
                            "-select_streams",
                            "v:0",
                            "-show_entries",
                            "stream=avg_frame_rate,r_frame_rate",
                            "-of",
                            "json",
                            p,
                        ]
                        process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            startupinfo=startupinfo,
                        )
                        stdout, _ = process.communicate(timeout=20)
                        if process.returncode != 0:
                            return None
                        txt = (stdout or b"").decode("utf-8", errors="ignore").strip()
                        if not txt:
                            return None
                        j = json.loads(txt)
                        streams = j.get("streams") or []
                        if not streams:
                            return None
                        s0 = streams[0] if isinstance(streams[0], dict) else {}
                        avg = (s0.get("avg_frame_rate") or "").strip()
                        rr = (s0.get("r_frame_rate") or "").strip()
                        cand = None
                        if avg and avg not in ("0/0", "0"):
                            cand = avg
                        elif rr and rr not in ("0/0", "0"):
                            cand = rr
                        if not cand:
                            return None

                        def _to_float(x):
                            raw = (x or "").strip()
                            if not raw:
                                return 0.0
                            if "/" in raw:
                                a, b = raw.split("/", 1)
                                na = float(a)
                                nb = float(b)
                                if nb == 0:
                                    return 0.0
                                return na / nb
                            return float(raw)

                        fps_v = _to_float(cand)
                        if not fps_v or fps_v <= 0:
                            return None
                        buckets = (24, 25, 30, 50, 60)
                        closest = None
                        closest_d = 999.0
                        for b in buckets:
                            d = abs(fps_v - float(b))
                            if d < closest_d:
                                closest_d = d
                                closest = b
                        fps_i = int(closest) if closest is not None and closest_d <= 0.2 else int(round(fps_v))
                        if fps_i <= 0:
                            return None
                        return str(fps_i)
                        return None
                    except Exception:
                        return None

                # 浣跨敤 FFmpeg 杩涜绮惧噯瑁佸壀 (-ss 鏀惧湪杈撳叆鍓嶅彲浠ュ姞閫燂紝鏀惧湪杈撳叆鍚庡彲浠ユ洿绮惧噯锛岃繖閲岀敤绮剧‘妯″紡)
                # 閲嶆柊缂栫爜浠ヤ繚璇佸吋瀹规€у拰绮惧噯鍒囩偣锛屾垨鑰呬娇鐢?copy 蹇€熷垏锛堝彲鑳戒笉鍑嗭級
                # 杩欓噷涓轰簡绋冲畾锛屾垜浠娇鐢ㄩ噸鏂扮紪鐮?
                cmd = [
                    "ffmpeg", "-y",
                    "-i", local_src,
                    "-ss", str(start_sec),
                    "-t", str(end_sec - start_sec),
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-c:a", "aac",
                    out_path
                ]
                
                # 闅愯棌鎺у埗鍙扮獥鍙?(Windows)
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                fps_str = _ffprobe_video_fps_str(local_src, startupinfo)
                if fps_str:
                    cmd.insert(-1, "-r")
                    cmd.insert(-1, fps_str)
                    
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo
                )
                stdout, stderr = process.communicate(timeout=120)
                
                if process.returncode != 0:
                    print(f"FFmpeg error: {stderr.decode('utf-8', errors='ignore')}")
                    _json_err(self, 500, "FFmpeg processing failed")
                    return
                    
                _json_ok(self, {
                    "success": True, 
                    "filename": filename, 
                    "path": f"output/CutVideo/{filename}",
                    "localPath": f"output/CutVideo/{filename}",
                    "url": f"/output/CutVideo/{filename}",
                })
            except subprocess.TimeoutExpired:
                process.kill()
                _json_err(self, 504, "FFmpeg process timeout")
            except Exception as e:
                _json_err(self, 500, f"Error processing video: {str(e)}")
            return

        # 鈹€鈹€ 闊抽瑁佸壀 (渚濊禆 FFmpeg) 鈹€鈹€
        if path.rstrip("/") == "/api/v2/audio/cut":
            body = _read_body(self)
            try:
                data = json.loads(body or b"{}")
            except Exception:
                _json_err(self, 400, "Invalid JSON")
                return

            src_path = (data.get("src") or "").strip()
            start_sec = float(data.get("start", 0))
            end_sec = float(data.get("end", 0))

            if not src_path or end_sec <= start_sec:
                _json_err(self, 400, "Invalid parameters")
                return

            safe_src = src_path.lstrip("/")
            norm_src = os.path.normpath(safe_src)
            if norm_src.startswith("..") or norm_src.startswith("../") or norm_src.startswith("..\\"):
                _json_err(self, 400, "Invalid src path")
                return
            local_src = os.path.join(DIRECTORY, norm_src)

            if not os.path.exists(local_src):
                _json_err(self, 404, "Source audio not found")
                return

            cut_dir = os.path.join(OUTPUT_DIR, "CutAudio")
            os.makedirs(cut_dir, exist_ok=True)

            ts = int(time.time() * 1000)
            rand_str = f"{random.randint(100,999)}"
            filename = f"cut_{ts}_{rand_str}.mp3"
            out_path = os.path.join(cut_dir, filename)

            try:
                cmd = [
                    "ffmpeg", "-y",
                    "-i", local_src,
                    "-ss", str(start_sec),
                    "-t", str(end_sec - start_sec),
                    "-vn",
                    "-c:a", "libmp3lame",
                    "-b:a", "192k",
                    out_path
                ]

                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo
                )
                stdout, stderr = process.communicate(timeout=120)

                if process.returncode != 0:
                    print(f"FFmpeg error: {stderr.decode('utf-8', errors='ignore')}")
                    _json_err(self, 500, "FFmpeg processing failed")
                    return

                _json_ok(self, {
                    "success": True,
                    "filename": filename,
                    "path": f"output/CutAudio/{filename}",
                    "localPath": f"output/CutAudio/{filename}",
                    "url": f"/output/CutAudio/{filename}",
                })
            except subprocess.TimeoutExpired:
                process.kill()
                _json_err(self, 504, "FFmpeg process timeout")
            except Exception as e:
                _json_err(self, 500, f"Error processing audio: {str(e)}")
            return

        if path.rstrip("/") == "/api/v2/video/compose":
            body = _read_body(self)
            try:
                data = json.loads(body or b"{}")
            except Exception:
                _json_err(self, 400, "Invalid JSON")
                return

            srcs = data.get("srcs") or data.get("sources") or []
            if not isinstance(srcs, list) or len(srcs) < 2:
                _json_err(self, 400, "Invalid srcs")
                return

            abs_srcs = []
            for s in srcs:
                try:
                    sp = (s or "").strip()
                except Exception:
                    sp = ""
                if not sp:
                    _json_err(self, 400, "Invalid srcs")
                    return
                safe_src = sp.lstrip("/")
                norm_src = os.path.normpath(safe_src)
                if norm_src.startswith("..") or norm_src.startswith("../") or norm_src.startswith("..\\"):
                    _json_err(self, 400, "Invalid src path")
                    return
                local_src = os.path.join(DIRECTORY, norm_src)
                if not os.path.exists(local_src):
                    _json_err(self, 404, "Source video not found")
                    return
                abs_srcs.append(local_src)

            out_dir = os.path.join(OUTPUT_DIR, "ComposeVideo")
            os.makedirs(out_dir, exist_ok=True)

            ts = int(time.time() * 1000)
            rand_str = f"{random.randint(100,999)}"
            filename = f"compose_{ts}_{rand_str}.mp4"
            out_path = os.path.join(out_dir, filename)
            try:
                if len(abs_srcs) > 80:
                    _json_err(self, 400, "Too many clips")
                    return

                startupinfo = None
                if os.name == "nt":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                def _ffprobe_video_fps_int(path0):
                    try:
                        cmd = [
                            "ffprobe",
                            "-v",
                            "error",
                            "-select_streams",
                            "v:0",
                            "-show_entries",
                            "stream=avg_frame_rate,r_frame_rate",
                            "-of",
                            "json",
                            path0,
                        ]
                        px = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            startupinfo=startupinfo,
                        )
                        stdout, _ = px.communicate(timeout=20)
                        if px.returncode != 0:
                            return None
                        txt = (stdout or b"").decode("utf-8", errors="ignore").strip()
                        if not txt:
                            return None
                        j = json.loads(txt)
                        streams = j.get("streams") or []
                        if not streams:
                            return None
                        s0 = streams[0] if isinstance(streams[0], dict) else {}
                        avg = (s0.get("avg_frame_rate") or "").strip()
                        rr = (s0.get("r_frame_rate") or "").strip()
                        cand = None
                        if avg and avg not in ("0/0", "0"):
                            cand = avg
                        elif rr and rr not in ("0/0", "0"):
                            cand = rr
                        if not cand:
                            return None

                        def _to_float(x):
                            raw = (x or "").strip()
                            if not raw:
                                return 0.0
                            if "/" in raw:
                                a, b = raw.split("/", 1)
                                na = float(a)
                                nb = float(b)
                                if nb == 0:
                                    return 0.0
                                return na / nb
                            return float(raw)

                        fps_v = _to_float(cand)
                        if not fps_v or fps_v <= 0:
                            return None
                        buckets = (24, 25, 30, 50, 60)
                        closest = None
                        closest_d = 999.0
                        for b in buckets:
                            d = abs(fps_v - float(b))
                            if d < closest_d:
                                closest_d = d
                                closest = b
                        fps_i = int(closest) if closest is not None and closest_d <= 0.2 else int(round(fps_v))
                        return fps_i if fps_i > 0 else None
                    except Exception:
                        return None

                def _ffprobe_has_audio(path0):
                    try:
                        cmd = [
                            "ffprobe",
                            "-v",
                            "error",
                            "-select_streams",
                            "a:0",
                            "-show_entries",
                            "stream=codec_type",
                            "-of",
                            "default=nw=1:nk=1",
                            path0,
                        ]
                        px = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            startupinfo=startupinfo,
                        )
                        stdout, _ = px.communicate(timeout=15)
                        if px.returncode != 0:
                            return False
                        txt = (stdout or b"").decode("utf-8", errors="ignore").strip().lower()
                        return "audio" in txt
                    except Exception:
                        return False

                def _ffprobe_video_wh(path0):
                    try:
                        cmd = [
                            "ffprobe",
                            "-v",
                            "error",
                            "-select_streams",
                            "v:0",
                            "-show_entries",
                            "stream=width,height",
                            "-of",
                            "json",
                            path0,
                        ]
                        px = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            startupinfo=startupinfo,
                        )
                        stdout, _ = px.communicate(timeout=20)
                        if px.returncode != 0:
                            return None
                        txt = (stdout or b"").decode("utf-8", errors="ignore").strip()
                        if not txt:
                            return None
                        j = json.loads(txt)
                        streams = j.get("streams") or []
                        if not streams:
                            return None
                        s0 = streams[0] if isinstance(streams[0], dict) else {}
                        try:
                            w = int(s0.get("width") or 0)
                            h = int(s0.get("height") or 0)
                        except Exception:
                            w = 0
                            h = 0
                        if w <= 0 or h <= 0:
                            return None
                        return (w, h)
                    except Exception:
                        return None

                fps_i = _ffprobe_video_fps_int(abs_srcs[0]) or 30
                wh = _ffprobe_video_wh(abs_srcs[0])
                if not wh:
                    _json_err(self, 500, "FFprobe failed: missing width/height")
                    return
                target_w, target_h = wh
                has_audio = True
                for p in abs_srcs:
                    if not _ffprobe_has_audio(p):
                        has_audio = False
                        break

                cmd = ["ffmpeg", "-y"]
                for p in abs_srcs:
                    cmd.extend(["-i", p])

                parts = []
                for i in range(len(abs_srcs)):
                    parts.append(
                        f"[{i}:v]"
                        f"scale={int(target_w)}:{int(target_h)}:force_original_aspect_ratio=decrease,"
                        f"pad={int(target_w)}:{int(target_h)}:(ow-iw)/2:(oh-ih)/2,"
                        f"setsar=1,"
                        f"fps={int(fps_i)},"
                        f"format=yuv420p,"
                        f"setpts=PTS-STARTPTS[v{i}]"
                    )
                    if has_audio:
                        parts.append(
                            f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}]"
                        )
                if has_audio:
                    join = "".join([f"[v{i}][a{i}]" for i in range(len(abs_srcs))])
                    parts.append(f"{join}concat=n={len(abs_srcs)}:v=1:a=1[v][a]")
                else:
                    join = "".join([f"[v{i}]" for i in range(len(abs_srcs))])
                    parts.append(f"{join}concat=n={len(abs_srcs)}:v=1:a=0[v]")

                filter_complex = ";".join(parts)
                cmd.extend(["-filter_complex", filter_complex, "-map", "[v]"])
                if has_audio:
                    cmd.extend(["-map", "[a]"])
                cmd.extend(
                    [
                        "-c:v",
                        "libx264",
                        "-preset",
                        "fast",
                        "-c:a",
                        "aac",
                        "-movflags",
                        "+faststart",
                        out_path,
                    ]
                )

                p0 = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo,
                )
                _, err0 = p0.communicate(timeout=900)
                if p0.returncode != 0:
                    err_text = (err0 or b"").decode("utf-8", errors="ignore").strip()
                    _json_err(self, 500, f"FFmpeg compose failed: {err_text or 'unknown error'}")
                    return

                rel = f"output/ComposeVideo/{filename}"
                _json_ok(self, {
                    "success": True,
                    "filename": filename,
                    "path": rel,
                    "localPath": rel,
                    "url": f"/{rel}",
                })
            except subprocess.TimeoutExpired:
                _json_err(self, 504, "FFmpeg process timeout")
            except Exception as e:
                _json_err(self, 500, f"Error composing video: {str(e)}")
            return

        if path.rstrip("/") == "/api/v2/video/smart_clip":
            body = _read_body(self)
            try:
                data = json.loads(body or b"{}")
            except Exception:
                _json_err(self, 400, "Invalid JSON")
                return

            src_path = (data.get("src") or "").strip()
            options = data.get("options") or {}
            if not isinstance(options, dict):
                options = {}

            if not src_path:
                _json_err(self, 400, "Missing src")
                return

            safe_src = src_path.lstrip("/")
            norm_src = os.path.normpath(safe_src)
            if norm_src.startswith("..") or norm_src.startswith("../") or norm_src.startswith("..\\"):
                _json_err(self, 400, "Invalid src path")
                return
            local_src = os.path.join(DIRECTORY, norm_src)

            if not os.path.exists(local_src):
                _json_err(self, 404, "Source video not found")
                return

            job_id = _smart_clip_new_job_id()
            try:
                created_at = time.time()
            except Exception:
                created_at = 0.0

            with _smart_clip_lock:
                _smart_clip_jobs[job_id] = {
                    "success": True,
                    "jobId": job_id,
                    "status": "running",
                    "stage": "queued",
                    "progress": 0.0,
                    "segments": None,
                    "error": None,
                    "createdAt": created_at,
                }

            t = threading.Thread(
                target=_run_smart_clip_job,
                args=(job_id, local_src, options),
                daemon=True,
            )
            t.start()

            _json_ok(self, {"success": True, "jobId": job_id})
            return

        # 鈹€鈹€ 瑙嗛鍏冩暟鎹?(渚濊禆 FFprobe/FFmpeg) 鈹€鈹€
        if path.rstrip("/") == "/api/v2/video/meta":
            body = _read_body(self)
            try:
                data = json.loads(body or b"{}")
            except Exception:
                _json_err(self, 400, "Invalid JSON")
                return

            src_path = (data.get("src") or "").strip()
            if not src_path:
                _json_err(self, 400, "Missing src")
                return

            safe_src = src_path.lstrip("/")
            norm_src = os.path.normpath(safe_src)
            if norm_src.startswith("..") or norm_src.startswith("../") or norm_src.startswith("..\\"):
                _json_err(self, 400, "Invalid src path")
                return
            local_src = os.path.join(DIRECTORY, norm_src)

            if not os.path.exists(local_src):
                _json_err(self, 404, "Source video not found")
                return

            def _parse_ratio(s):
                try:
                    raw = (s or "").strip()
                    if not raw:
                        return 0.0
                    if "/" in raw:
                        a, b = raw.split("/", 1)
                        na = float(a)
                        nb = float(b)
                        if nb == 0:
                            return 0.0
                        return na / nb
                    return float(raw)
                except Exception:
                    return 0.0

            try:
                cmd = [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "format=duration:stream=avg_frame_rate,r_frame_rate,nb_frames,duration,width,height",
                    "-of",
                    "json",
                    local_src,
                ]

                startupinfo = None
                if os.name == "nt":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo,
                )
                stdout, stderr = process.communicate(timeout=20)
                if process.returncode != 0:
                    err_text = (stderr or b"").decode("utf-8", errors="ignore").strip()
                    _json_err(self, 500, f"FFprobe failed: {err_text or 'unknown error'}")
                    return

                try:
                    meta = json.loads(stdout.decode("utf-8", errors="ignore") or "{}")
                except Exception:
                    meta = {}

                streams = meta.get("streams") or []
                s0 = streams[0] if streams else {}
                fmt = meta.get("format") or {}

                duration = 0.0
                for k in ("duration",):
                    v = fmt.get(k)
                    try:
                        dv = float(v)
                        if dv > 0:
                            duration = dv
                            break
                    except Exception:
                        pass
                if duration <= 0:
                    try:
                        dv = float(s0.get("duration") or 0)
                        if dv > 0:
                            duration = dv
                    except Exception:
                        pass

                fps = _parse_ratio(s0.get("avg_frame_rate") or "") or _parse_ratio(
                    s0.get("r_frame_rate") or "",
                )
                if fps <= 0:
                    fps = 0.0

                frame_count = 0
                nb_frames = s0.get("nb_frames")
                try:
                    if nb_frames is not None:
                        frame_count = int(float(nb_frames))
                except Exception:
                    frame_count = 0
                if frame_count <= 0 and fps > 0 and duration > 0:
                    frame_count = int(round(duration * fps))

                width = 0
                height = 0
                try:
                    width = int(float(s0.get("width") or 0))
                except Exception:
                    width = 0
                try:
                    height = int(float(s0.get("height") or 0))
                except Exception:
                    height = 0

                _json_ok(
                    self,
                    {
                        "success": True,
                        "fps": fps if fps > 0 else None,
                        "frameCount": frame_count if frame_count > 0 else None,
                        "duration": duration if duration > 0 else None,
                        "width": width if width > 0 else None,
                        "height": height if height > 0 else None,
                    },
                )
            except subprocess.TimeoutExpired:
                process.kill()
                _json_err(self, 504, "FFprobe process timeout")
            except Exception as e:
                _json_err(self, 500, f"Error reading video meta: {str(e)}")
            return

        # 鈹€鈹€ 瑙嗛棣栧抚缂╃暐鍥撅紙渚濊禆 FFmpeg锛屼骇鐗╄惤鐩樺埌 output/VideoThumbs锛?鈹€鈹€
        if path.rstrip("/") == "/api/v2/video/first_frame":
            body = _read_body(self)
            try:
                data = json.loads(body or b"{}")
            except Exception:
                _json_err(self, 400, "Invalid JSON")
                return

            src_path = (data.get("src") or "").strip()
            if not src_path:
                _json_err(self, 400, "Missing src")
                return

            # 瀹夊叏澶勭悊婧愯矾寰勶細鍘婚櫎鍓嶅鏂滄潬锛岃浆鎹负鏈湴缁濆璺緞锛堝熀浜?DIRECTORY锛?
            safe_src = src_path.lstrip("/")
            norm_src = os.path.normpath(safe_src)
            if norm_src.startswith("..") or norm_src.startswith("../") or norm_src.startswith("..\\"):
                _json_err(self, 400, "Invalid src path")
                return
            local_src = os.path.join(DIRECTORY, norm_src)

            if not os.path.exists(local_src):
                _json_err(self, 404, "Source video not found")
                return

            try:
                st = os.stat(local_src)
            except Exception:
                _json_err(self, 500, "Cannot stat source video")
                return

            # 鐢ㄢ€滄簮璺緞 + mtime + size鈥濈敓鎴愮ǔ瀹氭枃浠跺悕锛岄伩鍏嶉噸澶嶇敓鎴愬鑷?output 鑶ㄨ儉
            sig = f"{norm_src}|{getattr(st, 'st_mtime_ns', int(st.st_mtime * 1e9))}|{st.st_size}"
            h = hashlib.sha1(sig.encode("utf-8", errors="ignore")).hexdigest()[:12]

            thumb_dir = os.path.join(OUTPUT_DIR, "VideoThumbs")
            os.makedirs(thumb_dir, exist_ok=True)
            filename = f"vthumb_{h}.jpg"
            out_path = os.path.join(thumb_dir, filename)

            if not os.path.exists(out_path):
                try:
                    # 鍙?0 绉掑棣栧抚骞剁缉鏀惧埌 320px 瀹斤紙绛夋瘮锛夛紝鐢熸垚 jpg 浠ユ帶鍒舵枃浠朵綋绉?
                    cmd = [
                        "ffmpeg",
                        "-y",
                        "-ss",
                        "0",
                        "-i",
                        local_src,
                        "-frames:v",
                        "1",
                        "-vf",
                        "scale=320:-1",
                        "-q:v",
                        "4",
                        "-an",
                        out_path,
                    ]

                    startupinfo = None
                    if os.name == "nt":
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        startupinfo=startupinfo,
                    )
                    stdout, stderr = process.communicate(timeout=30)
                    if process.returncode != 0:
                        print(
                            f"FFmpeg first_frame error: {(stderr or b'').decode('utf-8', errors='ignore')}"
                        )
                        _json_err(self, 500, "FFmpeg processing failed")
                        return
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                    except Exception:
                        pass
                    _json_err(self, 504, "FFmpeg process timeout")
                    return
                except Exception as e:
                    _json_err(self, 500, f"Error extracting first frame: {str(e)}")
                    return

            rel_path = f"output/VideoThumbs/{filename}"
            _json_ok(self, {"success": True, "url": "/" + rel_path, "localPath": rel_path})
            return

        # 鈹€鈹€ 浠庤繙绔?URL 涓嬭浇骞朵繚瀛樺埌 output锛堢敤浜庤棰戠瓑浜岃繘鍒朵骇鐗╄惤鐩橈級 鈹€鈹€
        if path == "/api/v2/save_output_from_url":
            import socket
            import ipaddress
            import urllib.parse
            import urllib.request
            import urllib.error
            body = _read_body(self)
            try:
                data = json.loads(body or b"{}")
            except Exception:
                _json_err(self, 400, "Invalid JSON")
                return
            url = (data.get("url") or "").strip()
            if not url:
                _json_err(self, 400, "Missing url")
                return
            if url.startswith("//"):
                url = "https:" + url
            elif not re.match(r"^https?://", url, flags=re.I):
                url = "https://" + url.lstrip("/")
            try:
                parsed = urllib.parse.urlparse(url)
            except Exception:
                _json_err(self, 400, "Invalid url")
                return
            if parsed.scheme not in ("http", "https"):
                _json_err(self, 400, "Only http/https url allowed")
                return
            host = parsed.hostname
            if not host:
                _json_err(self, 400, "Invalid host")
                return

            def _is_allowlisted_download_host(h):
                try:
                    hh = (h or "").strip().lower().strip(".")
                except Exception:
                    return False
                if not hh:
                    return False
                if hh in ("localhost", "127.0.0.1", "0.0.0.0"):
                    return True
                if hh == "runninghub.cn" or hh.endswith(".runninghub.cn"):
                    return True
                if hh.endswith(".myqcloud.com") or hh.endswith(".qcloud.com"):
                    return True
                if hh.endswith(".volces.com") or hh.endswith(".aliyuncs.com") or hh.endswith(".bcebos.com"):
                    return True
                return False

            def _is_private_ip(ip_str):
                try:
                    ip = ipaddress.ip_address(ip_str)
                except Exception:
                    return True
                return (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_multicast
                    or ip.is_reserved
                    or ip.is_unspecified
                )

            try:
                allow_private = _is_allowlisted_download_host(host)
                if not allow_private:
                    infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
                    for info in infos:
                        ip_str = info[4][0]
                        if _is_private_ip(ip_str):
                            _json_err(self, 400, "Blocked private/reserved address")
                            return
            except Exception:
                _json_err(self, 400, "DNS resolve failed")
                return

            max_bytes = int(data.get("maxBytes") or 1024 * 1024 * 300)

            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "AI-Canvas/1.0")
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    ct = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                    ext = (data.get("ext") or "").strip().lower()
                    if not re.match(r"^[a-z0-9]{1,5}$", ext):
                        ext = ""
                    if not ext:
                        if ct == "image/png":
                            ext = "png"
                        elif ct in ("image/jpeg", "image/jpg"):
                            ext = "jpg"
                        elif ct == "image/webp":
                            ext = "webp"
                        elif ct == "image/gif":
                            ext = "gif"
                        elif ct == "video/mp4":
                            ext = "mp4"
                        elif ct in ("video/webm", "audio/webm"):
                            ext = "webm"
                        else:
                            ext = "bin"
                    filename = _next_gen_output_filename(ext)
                    fpath = os.path.join(OUTPUT_DIR, filename)
                    total = 0
                    with open(fpath, "wb") as f:
                        while True:
                            chunk = resp.read(1024 * 256)
                            if not chunk:
                                break
                            total += len(chunk)
                            if total > max_bytes:
                                try:
                                    os.remove(fpath)
                                except Exception:
                                    pass
                                _json_err(self, 413, "File too large")
                                return
                            f.write(chunk)
            except urllib.error.HTTPError as e:
                _json_err(self, 502, f"Download HTTPError: {e.code}")
                return
            except Exception as e:
                _json_err(self, 502, f"Download failed: {str(e)}")
                return

            rel_path = f"output/{filename}"
            _json_ok(
                self,
                {
                    "success": True,
                    "filename": filename,
                    "path": rel_path,
                    "localPath": rel_path,
                    "url": f"/{rel_path}",
                },
            )
            return

        # 鈹€鈹€ 鑷畾涔?AI 鍏ㄥ眬閰嶇疆锛圥OST锛夆攢鈹€
        if path == "/api/v2/config/custom-ai":
            body = _read_body(self)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                _json_err(self, 400, "Invalid JSON"); return
            # 濡傛灉褰撳墠鏄幆澧冨彉閲忔潵婧愶紝鎷掔粷瑕嗙洊
            conf = _get_custom_ai_config()
            if conf["source"] == "env":
                _json_err(self, 403, "Config is locked by environment variables (CUSTOM_AI_URL / CUSTOM_AI_KEY)"); return
            # 鍐欏叆 config.json
            try:
                existing = {}
                if os.path.exists(CONFIG_FILE):
                    with open(CONFIG_FILE, encoding="utf-8-sig") as f:
                        existing = json.load(f)
                existing["custom_ai"] = {"apiUrl": data.get("apiUrl", "").strip(), "apiKey": data.get("apiKey", "").strip()}
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)
                _json_ok(self, {"success": True})
            except Exception as e:
                _json_err(self, 500, str(e))
            return

        # 鈹€鈹€ 鏂囦欢涓婁紶浠ｇ悊锛圧unningHUB 绛夛級鈹€鈹€
        if path == "/api/v2/proxy/upload":
            try:
                import urllib.request
                import urllib.error
                
                # 浠庢煡璇㈠弬鏁拌幏鍙?apiUrl 鍜?apiKey
                from urllib.parse import parse_qs, urlparse
                qs = parse_qs(urlparse(self.path).query)
                api_url = qs.get("apiUrl", [""])[0].strip()
                api_key = qs.get("apiKey", [""])[0].strip()
                
                if not api_url or not api_key:
                    _json_err(self, 400, "Missing apiUrl or apiKey"); return
                
                # 璇诲彇鍘熷璇锋眰浣擄紙multipart/form-data锛?
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                content_type = self.headers.get('Content-Type', '')
                
                # 鐩存帴杞彂鍒?RunningHUB
                req = urllib.request.Request(api_url, data=body, method="POST")
                req.add_header("Authorization", f"Bearer {api_key}")
                req.add_header("Content-Type", content_type)
                req.add_header("Content-Length", str(len(body)))
                
                with urllib.request.urlopen(req, timeout=60) as resp:
                    resp_body = resp.read()
                    self.send_response(resp.status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(resp_body)
                return
            except urllib.error.HTTPError as e:
                self.send_response(e.code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(e.read())
                return
            except Exception as e:
                _json_err(self, 500, f"Upload proxy error: {str(e)}")
                return

        if path == "/api/v2/video/matting/run":
            body = _read_body(self)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                _json_err(self, 400, "Invalid JSON"); return

            api_key = (data.get("apiKey") or "").strip()
            node_info_list = data.get("nodeInfoList")
            if not api_key or not isinstance(node_info_list, list):
                _json_err(self, 400, "Missing apiKey or nodeInfoList"); return

            app_id = str(data.get("appId") or "2042569732972355585").strip() or "2042569732972355585"
            instance_type = data.get("instanceType") or data.get("rhInstanceType") or ""
            instance_type = str(instance_type).strip().lower()
            if instance_type in ("24g", "default", "basic"):
                instance_type = "default"
            elif instance_type in ("48g", "plus", "pro"):
                instance_type = "plus"
            else:
                instance_type = "default"

            def _resolve_local_file(url_or_path: str):
                s = (url_or_path or "").strip()
                if not s:
                    return None
                s2 = s.lstrip("/")
                if s2.startswith("output/"):
                    fp = os.path.abspath(os.path.join(DIRECTORY, s2))
                    if fp.startswith(os.path.abspath(OUTPUT_DIR)) and os.path.isfile(fp):
                        return fp
                if s2.startswith("data/uploads/"):
                    fp = os.path.abspath(os.path.join(DIRECTORY, s2))
                    if fp.startswith(os.path.abspath(UPLOADS_DIR)) and os.path.isfile(fp):
                        return fp
                if os.path.isabs(s) and os.path.isfile(s):
                    return s
                return None

            def _guess_filename(raw: str, fallback_name: str):
                path_name = ""
                try:
                    path_name = os.path.basename(urllib.parse.urlparse(raw).path or "")
                except Exception:
                    path_name = ""
                candidate = path_name or fallback_name
                if "." not in os.path.basename(candidate):
                    fallback_ext = os.path.splitext(fallback_name)[1] or ".bin"
                    candidate = f"{candidate}{fallback_ext}"
                return candidate

            def _download_remote_bytes(url: str):
                try:
                    import requests as _req
                    resp = _req.get(url, timeout=120)
                    resp.raise_for_status()
                    return resp.content
                except ImportError:
                    with urllib.request.urlopen(url, timeout=120) as resp:
                        return resp.read()

            def _upload_to_runninghub(file_bytes: bytes, filename: str, content_type: str = "application/octet-stream"):
                upload_api_url = "https://www.runninghub.cn/openapi/v2/media/upload/binary"
                try:
                    import requests as _req
                    files = {"file": (filename, file_bytes, content_type or "application/octet-stream")}
                    resp = _req.post(
                        upload_api_url,
                        files=files,
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=120,
                    )
                    resp.raise_for_status()
                    js = resp.json()
                    if js.get("code") != 0:
                        raise RuntimeError(js.get("message") or js.get("msg") or "upload failed")
                    u = (js.get("data") or {}).get("download_url") or ""
                    if not u:
                        raise RuntimeError("upload missing download_url")
                    return u
                except ImportError:
                    import uuid
                    import urllib.request
                    import urllib.error
                    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
                    head = (
                        f"--{boundary}\r\n"
                        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                        f"Content-Type: {content_type or 'application/octet-stream'}\r\n\r\n"
                    ).encode("utf-8")
                    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
                    payload = head + file_bytes + tail
                    req = urllib.request.Request(upload_api_url, data=payload, method="POST")
                    req.add_header("Authorization", f"Bearer {api_key}")
                    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
                    req.add_header("Content-Length", str(len(payload)))
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        rb = resp.read()
                    js = json.loads(rb.decode("utf-8", errors="replace"))
                    if js.get("code") != 0:
                        raise RuntimeError(js.get("message") or js.get("msg") or "upload failed")
                    u = (js.get("data") or {}).get("download_url") or ""
                    if not u:
                        raise RuntimeError("upload missing download_url")
                    return u

            def _materialize_media_url(raw_value: str, fallback_name: str, fallback_content_type: str):
                raw = str(raw_value or "").strip()
                if not raw:
                    raise RuntimeError("missing media fieldValue")
                if "runninghub.cn" in raw:
                    return raw

                local_file = _resolve_local_file(raw)
                if local_file:
                    with open(local_file, "rb") as f:
                        file_bytes = f.read()
                    filename = os.path.basename(local_file) or fallback_name
                    content_type = mimetypes.guess_type(filename)[0] or fallback_content_type
                    return _upload_to_runninghub(file_bytes, filename, content_type)

                if raw.startswith("data:"):
                    match = re.match(r"^data:([^;,]+)?;base64,(.*)$", raw, re.DOTALL)
                    if not match:
                        raise RuntimeError("invalid data url")
                    mime_type = (match.group(1) or fallback_content_type or "application/octet-stream").strip()
                    ext = mimetypes.guess_extension(mime_type) or os.path.splitext(fallback_name)[1] or ".bin"
                    filename_root = os.path.splitext(fallback_name)[0] or "upload"
                    filename = f"{filename_root}{ext}"
                    try:
                        file_bytes = base64.b64decode(match.group(2))
                    except Exception as exc:
                        raise RuntimeError("invalid base64 media payload") from exc
                    return _upload_to_runninghub(file_bytes, filename, mime_type)

                if raw.startswith("http://") or raw.startswith("https://"):
                    file_bytes = _download_remote_bytes(raw)
                    filename = _guess_filename(raw, fallback_name)
                    content_type = mimetypes.guess_type(filename)[0] or fallback_content_type
                    return _upload_to_runninghub(file_bytes, filename, content_type)

                raise RuntimeError("unsupported media url")

            try:
                source_video_item = None
                mask_item = None
                for item in node_info_list:
                    if not isinstance(item, dict):
                        continue
                    node_id = str(item.get("nodeId") or "")
                    field_name = str(item.get("fieldName") or "")
                    if node_id == "117" and field_name == "video":
                        source_video_item = item
                    elif node_id == "63" and field_name == "image":
                        mask_item = item

                if not source_video_item:
                    _json_err(self, 400, "Missing source video node 117/video"); return
                if not mask_item:
                    _json_err(self, 400, "Missing erase mask node 63/image"); return

                source_video_item["fieldValue"] = _materialize_media_url(
                    source_video_item.get("fieldValue"),
                    "input.mp4",
                    "video/mp4",
                )
                mask_item["fieldValue"] = _materialize_media_url(
                    mask_item.get("fieldValue"),
                    "erase-mask.png",
                    "image/png",
                )

                api_url = f"https://www.runninghub.cn/openapi/v2/run/ai-app/{app_id}"
                payload = {
                    "nodeInfoList": node_info_list,
                    "instanceType": instance_type,
                    "usePersonalQueue": "false",
                }
                request_headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }

                try:
                    import requests as _req
                    resp = _req.post(
                        api_url,
                        json=payload,
                        headers=request_headers,
                        timeout=900,
                    )
                    self.send_response(resp.status_code)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(resp.content)
                except ImportError:
                    import urllib.request, urllib.error
                    req_body = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(api_url, data=req_body, method="POST")
                    req.add_header("Authorization", f"Bearer {api_key}")
                    req.add_header("Content-Type", "application/json")
                    req.add_header("User-Agent", "Mozilla/5.0")
                    try:
                        with urllib.request.urlopen(req, timeout=900) as resp:
                            resp_data = resp.read()
                        self.send_response(resp.status)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        self.wfile.write(resp_data)
                    except urllib.error.HTTPError as e:
                        self.send_response(e.code)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        self.wfile.write(e.read())
            except Exception as e:
                _json_err(self, 500, f"Video matting proxy error: {repr(e)}")
            return

        if path == "/api/v2/runninghubwf/run":
            body = _read_body(self)
            try:
                data = json.loads(body)
                api_key = (data.get("apiKey") or "").strip()
                workflow_id = str(data.get("workflowId") or "").strip()
                node_info_list = data.get("nodeInfoList")
            except json.JSONDecodeError:
                _json_err(self, 400, "Invalid JSON"); return
            if not api_key or not workflow_id or not isinstance(node_info_list, list):
                _json_err(self, 400, "Missing apiKey or workflowId or nodeInfoList"); return
            if workflow_id in VIDEO_VIP_WORKFLOW_IDS:
                decision = _check_v54_subscription_gate(
                    self,
                    data,
                    required_model_id=f"runninghub/{workflow_id}",
                )
                if not bool(decision.get("allowed")):
                    denial = SUBSCRIPTION_CLIENT.subscription_required_payload(
                        decision.get("reasonMessage") or "未激活"
                    )
                    denial["reasonCode"] = decision.get("reasonCode") or ""
                    denial["subscriptionStatus"] = (
                        decision.get("status") or SUB_STATUS_NONE
                    )
                    denial["installId"] = decision.get("installId") or ""
                    denial["requiredModelId"] = decision.get("requiredModelId") or ""
                    _json_ok(
                        self,
                        denial,
                    )
                    return

            api_url = "https://www.runninghub.cn/task/openapi/create"
            instance_type = data.get("instanceType") or data.get("rhInstanceType") or ""
            instance_type = str(instance_type).strip().lower()
            if instance_type in ("24g", "default", "basic"):
                instance_type = "default"
            elif instance_type in ("48g", "plus", "pro"):
                instance_type = "plus"
            else:
                instance_type = "default"
            payload = dict(data)
            payload["instanceType"] = instance_type
            try:
                import requests as _req
                resp = _req.post(api_url, json=payload, timeout=900)
                self.send_response(resp.status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(resp.content)
            except ImportError:
                import urllib.request, urllib.error
                req_body = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(api_url, data=req_body, method="POST")
                req.add_header("Content-Type", "application/json")
                req.add_header("User-Agent", "Mozilla/5.0")
                try:
                    with urllib.request.urlopen(req, timeout=900) as resp:
                        resp_data = resp.read()
                    self.send_response(resp.status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(resp_data)
                except urllib.error.HTTPError as e:
                    self.send_response(e.code)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(e.read())
            except Exception as e:
                _json_err(self, 500, f"RunningHub workflow proxy error: {repr(e)}")
            return

        if path == "/api/v2/runninghubwf/query":
            body = _read_body(self)
            try:
                data = json.loads(body)
                api_key = (data.get("apiKey") or "").strip()
                task_id = str(data.get("taskId") or "").strip()
            except json.JSONDecodeError:
                _json_err(self, 400, "Invalid JSON"); return
            if not api_key or not task_id:
                _json_err(self, 400, "Missing apiKey or taskId"); return

            api_url = "https://www.runninghub.cn/task/openapi/outputs"
            payload = { "apiKey": api_key, "taskId": task_id }
            try:
                import requests as _req
                resp = _req.post(api_url, json=payload, timeout=60)
                self.send_response(resp.status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(resp.content)
            except ImportError:
                import urllib.request, urllib.error
                req_body = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(api_url, data=req_body, method="POST")
                req.add_header("Content-Type", "application/json")
                req.add_header("User-Agent", "Mozilla/5.0")
                try:
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        resp_data = resp.read()
                    self.send_response(resp.status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(resp_data)
                except urllib.error.HTTPError as e:
                    self.send_response(e.code)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(e.read())
            except Exception as e:
                _json_err(self, 500, f"RunningHub query proxy error: {repr(e)}")
            return

        if path == "/api/v2/runninghubwf/cancel":
            body = _read_body(self)
            try:
                data = json.loads(body)
                api_key = (data.get("apiKey") or "").strip()
                task_id = str(data.get("taskId") or "").strip()
            except json.JSONDecodeError:
                _json_err(self, 400, "Invalid JSON"); return
            if not api_key or not task_id:
                _json_err(self, 400, "Missing apiKey or taskId"); return

            api_url = "https://www.runninghub.cn/task/openapi/cancel"
            payload = { "apiKey": api_key, "taskId": task_id }
            try:
                import requests as _req
                resp = _req.post(api_url, json=payload, timeout=60)
                self.send_response(resp.status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(resp.content)
            except ImportError:
                import urllib.request, urllib.error
                req_body = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(api_url, data=req_body, method="POST")
                req.add_header("Content-Type", "application/json")
                req.add_header("User-Agent", "Mozilla/5.0")
                try:
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        resp_data = resp.read()
                    self.send_response(resp.status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(resp_data)
                except urllib.error.HTTPError as e:
                    self.send_response(e.code)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(e.read())
            except Exception as e:
                _json_err(self, 500, f"RunningHub cancel proxy error: {repr(e)}")
            return

        # 鈹€鈹€ PPIO 鍥惧儚鐢熸垚浠ｇ悊 鈹€鈹€
        if path == "/api/v2/proxy/image":
            body = _read_body(self)
            try:
                data = json.loads(body)
                api_url = data.pop("apiUrl", "").strip().rstrip("/")
                api_key = data.pop("apiKey", "").strip()
            except json.JSONDecodeError:
                _json_err(self, 400, "Invalid JSON"); return
            if not api_url or not api_key:
                _json_err(self, 400, "Missing apiUrl or apiKey"); return
            workflow_match = re.search(
                r"/openapi/v2/run/ai-app/(\d+)$",
                api_url,
                flags=re.IGNORECASE,
            )
            workflow_id = workflow_match.group(1) if workflow_match else ""
            if workflow_id in VIDEO_VIP_WORKFLOW_IDS:
                decision = _check_v54_subscription_gate(
                    self,
                    data,
                    required_model_id=f"runninghub/{workflow_id}",
                )
                if not bool(decision.get("allowed")):
                    denial = SUBSCRIPTION_CLIENT.subscription_required_payload(
                        decision.get("reasonMessage") or "未激活"
                    )
                    denial["reasonCode"] = decision.get("reasonCode") or ""
                    denial["subscriptionStatus"] = (
                        decision.get("status") or SUB_STATUS_NONE
                    )
                    denial["installId"] = decision.get("installId") or ""
                    denial["requiredModelId"] = decision.get("requiredModelId") or ""
                    _json_ok(
                        self,
                        denial,
                    )
                    return
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            }
            try:
                import requests as _req
                resp = _req.post(api_url, json=data, headers=headers, timeout=900)
                self.send_response(resp.status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(resp.content)
            except ImportError:
                import urllib.request, urllib.error
                req_body = json.dumps(data).encode("utf-8")
                req = urllib.request.Request(api_url, data=req_body, headers=headers, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=900) as resp:
                        resp_data = resp.read()
                    self.send_response(resp.status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(resp_data)
                except urllib.error.HTTPError as e:
                    self.send_response(e.code)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(e.read())
            except Exception as e:
                _json_err(self, 500, f"Proxy error: {repr(e)}")
            return

        # 鈹€鈹€ 閫氱敤浠ｇ悊 forwarded 鈹€鈹€
        if path == "/api/v2/proxy/completions":
            body = _read_body(self)
            try:
                data = json.loads(body)
                api_url = data.pop("apiUrl", "").strip().rstrip("/")
                api_key = data.pop("apiKey", "").strip()
            except json.JSONDecodeError:
                _json_err(self, 400, "Invalid JSON"); return
            
            if not api_url or not api_key:
                global_cfg = _get_custom_ai_config()
                api_url = api_url or global_cfg["apiUrl"]
                api_key = api_key or global_cfg["apiKey"]

            if not api_url or not api_key:
                _json_err(self, 400, "Missing apiUrl or apiKey"); return
            
            # 鍏煎 Gemini 鏍煎紡绔偣鎴栧凡瀹屾暣鐨勭鐐?
            if ":generateContent" in api_url or "/v1beta/models" in api_url or api_url.endswith("/chat/completions"):
                endpoint = api_url
            else:
                endpoint = f"{api_url}/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "application/json"
            }
            
            try:
                import requests
                req_body = json.dumps(data)
                try:
                    # 瓒呮椂鏃堕棿鏀逛负 300 绉掞紙5鍒嗛挓锛夛紝涓庡墠绔?aiTextApi.js 淇濇寔涓€鑷?
                    resp = requests.post(endpoint, data=req_body, headers=headers, timeout=300)
                except requests.exceptions.ConnectionError as ce:
                    _json_err(self, 502, f"鏃犳硶杩炴帴鍒?AI 鏈嶅姟鍣? {str(ce)}")
                    return
                except requests.exceptions.Timeout as te:
                    _json_err(self, 504, f"AI 鏈嶅姟鍣ㄨ姹傝秴鏃? {str(te)}")
                    return
                except requests.exceptions.RequestException as req_err:
                    _json_err(self, 502, f"AI 鏈嶅姟鍣ㄨ姹傚け璐? {str(req_err)}")
                    return
                
                # 妫€鏌ュ搷搴旀槸鍚︽槸 SSE 鏍煎紡锛屽鏋滄槸鍒欐彁鍙栨湁鏁?JSON
                resp_text = resp.text
                resp_content_type = resp.headers.get('Content-Type', '')
                
                # 濡傛灉鍝嶅簲鍖呭惈 text/event-stream 鎴栧琛?data: 鏍煎紡锛屽皾璇曟彁鍙?JSON
                is_sse = 'text/event-stream' in resp_content_type or resp_text.strip().startswith('data:')
                if is_sse:
                    try:
                        # 灏濊瘯浠?SSE 鏍煎紡涓彁鍙栨湁鏁?JSON
                        lines = [l.strip() for l in resp_text.split('\n') if l.strip().startswith('data:')]
                        if lines:
                            last_line = lines[-1].replace('data:', '').strip()
                            if last_line == '[DONE]':
                                # 鎵惧€掓暟绗簩涓湁鏁堣
                                valid_lines = [l for l in lines if l.replace('data:', '').strip() != '[DONE]']
                                if valid_lines:
                                    json_str = valid_lines[-1].replace('data:', '').strip()
                                    json_data = json.loads(json_str)
                                    resp_text = json.dumps(json_data)
                            else:
                                json_data = json.loads(last_line)
                                resp_text = json.dumps(json_data)
                    except Exception:
                        # 濡傛灉瑙ｆ瀽澶辫触锛屼繚鎸佸師鏍疯繑鍥?
                        pass
                
                self.send_response(resp.status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(resp_text.encode('utf-8'))
            except ImportError:
                # Fallback to urllib if requests is not installed
                import urllib.request
                req_body = json.dumps(data).encode("utf-8")
                req = urllib.request.Request(endpoint, data=req_body, headers=headers, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        resp_data = resp.read()
                        resp_text = resp_data.decode('utf-8')
                    
                    # 妫€鏌ュ搷搴旀槸鍚︽槸 SSE 鏍煎紡锛屽鏋滄槸鍒欐彁鍙栨湁鏁?JSON
                    if resp_text.strip().startswith('data:'):
                        try:
                            lines = [l.strip() for l in resp_text.split('\n') if l.strip().startswith('data:')]
                            if lines:
                                last_line = lines[-1].replace('data:', '').strip()
                                if last_line == '[DONE]':
                                    valid_lines = [l for l in lines if l.replace('data:', '').strip() != '[DONE]']
                                    if valid_lines:
                                        json_str = valid_lines[-1].replace('data:', '').strip()
                                        json_data = json.loads(json_str)
                                        resp_text = json.dumps(json_data)
                                else:
                                    json_data = json.loads(last_line)
                                    resp_text = json.dumps(json_data)
                        except Exception:
                            pass

                    self.send_response(resp.status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(resp_text.encode('utf-8'))
                except urllib.error.HTTPError as e:
                    self.send_response(e.code)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(e.read())
            except Exception as e:
                _json_err(self, 500, repr(e))
            return

        # 鈹€鈹€ 鑷畾涔?AI 鏂囨湰鐢熸垚锛堜唬鐞嗚浆鍙?OpenAI 鏍煎紡璇锋眰锛夆攢鈹€
        if path == "/api/v2/chat":
            body = _read_body(self)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                _json_err(self, 400, "Invalid JSON"); return
            api_url  = data.get("apiUrl", "").strip().rstrip("/")
            api_key  = data.get("apiKey", "").strip()
            model    = data.get("model", "")
            prompt   = data.get("prompt", "")
            # apiUrl/apiKey 鐣欑┖鏃讹紝璇诲彇鐜鍙橀噺鎴?config.json 涓殑鑷畾涔?AI 閰嶇疆
            if not api_url or not api_key:
                global_cfg = _get_custom_ai_config()
                api_url = api_url or global_cfg["apiUrl"]
                api_key = api_key or global_cfg["apiKey"]
            if not api_url or not api_key or not model or not prompt:
                _json_err(self, 400, "Missing required fields: apiUrl, apiKey, model, prompt"); return
            
            # 鍒ゆ柇绔偣鎷兼帴锛屽鏋滄湰韬氨鏄洿鎺ュ啓瀹屽埌浜?completion 灏变笉鎷兼帴浜?
            endpoint = api_url if api_url.endswith("/chat/completions") else f"{api_url}/chat/completions"
            
            import urllib.request
            req_body = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            }).encode("utf-8")
            req = urllib.request.Request(
                endpoint,
                data=req_body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))

                content = resp_data["choices"][0]["message"]["content"]
                _json_ok(self, {"content": content})
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                try: err_msg = json.loads(err_body).get("error", {}).get("message", err_body)
                except: err_msg = err_body
                _json_err(self, e.code, err_msg)
            except urllib.error.URLError as e:
                _json_err(self, 502, f"AI service connection failed: {getattr(e, 'reason', e)}")
            except Exception as e:
                _json_err(self, 500, str(e))
            return

        # 鈹€鈹€ 鑷姩鏇存柊锛歡it pull 鍚庡惎鍔?鍙屽嚮杩愯.bat 骞堕€€鍑哄綋鍓嶈繘绋?鈹€鈹€
        if path == "/api/v2/update/apply":
            try:
                # ZIP 鍖呭唴鐨?.git 鐢?CI 鐢熸垚锛涜繙绔彲鑳借 --force 鎺ㄩ€佸鑷村巻鍙查噸鍐?
                # 杩欓噷涓嶄娇鐢?git pull锛坢erge锛夛紝鑰屾槸閲囩敤 fetch + reset 纭榻愯繙绔増鏈紝閬垮厤鍐茬獊/鏃犺拷韪垎鏀瓑闂
                remotes = []
                try:
                    remotes = subprocess.check_output(
                        ['git', 'remote'],
                        cwd=DIRECTORY, stderr=subprocess.DEVNULL
                    ).decode().split()
                except Exception:
                    remotes = []
                remote = None
                for name in ("origin", "github", "gitee"):
                    if name in remotes:
                        remote = name
                        break
                if not remote and remotes:
                    remote = remotes[0]
                if not remote:
                    _json_ok(self, {'success': False, 'error': '鏈娴嬪埌鍙敤鐨?git remote锛堝彲鑳戒笉鏄€氳繃 Git 鑾峰彇鐨勭洰褰曪級'})
                    return

                fetch = subprocess.run(
                    ['git', 'fetch', remote, 'master'],
                    cwd=DIRECTORY,
                    capture_output=True, text=True, timeout=60
                )
                if fetch.returncode != 0:
                    err = fetch.stderr.strip() or fetch.stdout.strip()
                    _json_ok(self, {'success': False, 'error': err})
                    return
                reset = subprocess.run(
                    ['git', 'reset', '--hard', 'FETCH_HEAD'],
                    cwd=DIRECTORY,
                    capture_output=True, text=True, timeout=60
                )
                if reset.returncode == 0:
                    _json_ok(self, {'success': True})
                    def _restart():
                        import time, os
                        time.sleep(0.8)
                        bat = os.path.join(DIRECTORY, '鍙屽嚮杩愯.bat')
                        os.startfile(bat)
                        time.sleep(0.3)
                        os._exit(0)
                    threading.Thread(target=_restart, daemon=True).start()
                else:
                    err = reset.stderr.strip() or reset.stdout.strip()
                    _json_ok(self, {'success': False, 'error': err})
            except subprocess.TimeoutExpired:
                _json_err(self, 504, "git pull 超时，请检查网络")
            except Exception as e:
                _json_err(self, 500, str(e))
            return
        _json_err(self, 404, "Not found")


# 鈹€鈹€ 鍚姩 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
if __name__ == "__main__":
    # 鍚姩鑷姩鏇存柊鍚庡彴妫€鏌ョ嚎绋?
    _t = threading.Thread(target=_update_check_loop, daemon=True, name='AutoUpdateChecker')
    _t.start()
    if _sam3_enabled():
        def _sam3_warmup():
            try:
                time.sleep(2.0)
            except Exception:
                pass
            try:
                _sam3_load_sessions()
                _sam3_get_tokenizer()
                _sam3_get_language_features(prompt="visual")
                _sam3_touch()
            except Exception:
                pass
            try:
                do_full = (os.environ.get("SAM3_WARMUP_FULL_SEGMENT", "0") or "0").strip() in ("1", "true", "True", "YES", "yes")
            except Exception:
                do_full = False
            if do_full:
                try:
                    import io
                    Image = _sam3_get_pil_image()
                    im = Image.new("RGB", (1008, 1008), (0, 0, 0))
                    buf = io.BytesIO()
                    im.save(buf, format="JPEG", quality=80)
                    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                    _sam3_run_segment(
                        b64_data=b64,
                        points=[{"x": 300, "y": 300, "label": 1}],
                        prompt="visual",
                    )
                except Exception:
                    pass
        threading.Thread(target=_sam3_warmup, daemon=True, name='SAM3Warmup').start()
        def _sam3_idle_unload_loop():
            try:
                try:
                    unload_sec = float(os.environ.get("SAM3_IDLE_UNLOAD_SEC", "300") or "300")
                except Exception:
                    unload_sec = 300.0
                if unload_sec <= 0:
                    return
                max_check_sec = min(30.0, max(2.0, unload_sec / 10.0))
                time.sleep(min(3.0, max_check_sec))
                while True:
                    idle = _sam3_get_idle_sec()
                    if idle is not None and idle >= unload_sec:
                        with _sam3_infer_lock:
                            idle2 = _sam3_get_idle_sec()
                            if idle2 is not None and idle2 >= unload_sec:
                                _sam3_unload()
                                idle = None
                    if idle is None:
                        sleep_sec = max_check_sec
                    else:
                        remaining_sec = max(0.0, unload_sec - idle)
                        sleep_sec = max(0.5, min(max_check_sec, remaining_sec / 2.0))
                    time.sleep(sleep_sec)
            except Exception:
                return
        threading.Thread(target=_sam3_idle_unload_loop, daemon=True, name='SAM3IdleUnload').start()
    else:
        try:
            _sam3_unload()
        except Exception:
            pass
    port = PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except Exception:
            port = PORT
    bind_host = BIND_HOST
    if len(sys.argv) > 2:
        bind_host = str(sys.argv[2]).strip() or BIND_HOST
    with socketserver.ThreadingTCPServer((bind_host, port), Handler) as httpd:
        httpd.allow_reuse_address = True
        print("=" * 56)
        print("AI Canvas 服务已启动")
        print(f"http://{bind_host}:{port}")
        print("按 Ctrl+C 停止服务")
        print("=" * 56)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务已停止。")
