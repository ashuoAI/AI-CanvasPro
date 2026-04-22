r"""
./server.py - AI Canvas V2 ????

????:
  cd v2
  venv\Scripts\python server.py

?????: http://localhost:8777

??????? v2/ ??:
  user/Canvas Project/  - ??????
  user/shortcuts.json   - ?????
  user/settings.json    - ?????
  user/config.json      - API Key ??
  data/uploads/         - ??????

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
import shutil

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from services.hot_update_service import HotUpdateService
from services.http_route_dispatcher import HttpRouteDispatcher
from services.config_route_service import ConfigRouteService
from services.json_file_route_service import JsonFileRouteService
from services.library_file_route_service import LibraryFileRouteService
from services.subscription_gate_service import SubscriptionGateService
from services.subscription_client import SubscriptionRemoteClient
from services.dreamina_cli_service import DreaminaCliService
from services.dreamina_route_service import DreaminaRouteService
from services.sam3_service import Sam3Service
from services.sam3_route_service import Sam3RouteService

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
DIRECTORY = os.path.abspath(os.path.dirname(__file__))   # v2/ 绝对路径
# --- ???? ---
# ? index.html ????
import re

def get_version_from_index_html():
    """? index.html ??????"""
    index_path = os.path.join(DIRECTORY, "index.html")
    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # 匹配 <meta name="app-version" content="V0.0.7">
        match = re.search(r'<meta name="app-version" content="([^"]+)"', content)
        if match:
            return match.group(1)
    except Exception:
        pass
    return "V0.0.7"  # ????

LOCAL_VERSION   = get_version_from_index_html()  # ? index.html ????
_gen_seq_lock   = threading.Lock()
_smart_clip_jobs = {}
_smart_clip_lock = threading.Lock()

# --- ???????? v2/ ?? ---
DEFAULT_USER_DIR = os.path.join(DIRECTORY, "user")
DEFAULT_OUTPUT_DIR = os.path.join(DIRECTORY, "output")
DEFAULT_UPLOADS_DIR = os.path.join(DIRECTORY, "data", "uploads")

USER_DIR       = DEFAULT_USER_DIR
CANVAS_DIR     = os.path.join(USER_DIR,  "Canvas Project")
ASSETS_DIR     = os.path.join(DIRECTORY, "data", "assets")
ASSET_THUMBS_DIR = os.path.join(ASSETS_DIR, "thumbs")
WORKFLOWS_DIR  = os.path.join(DIRECTORY, "data", "workflows")
WORKFLOW_THUMBS_DIR = os.path.join(WORKFLOWS_DIR, "thumbs")
UPLOADS_DIR    = DEFAULT_UPLOADS_DIR
OUTPUT_DIR     = DEFAULT_OUTPUT_DIR
CONFIG_FILE    = os.path.join(USER_DIR, "config.json")
SETTINGS_FILE  = os.path.join(USER_DIR, "settings.json")
GEN_SEQ_STATE_FILE = os.path.join(OUTPUT_DIR, ".gen_seq_state.json")
MAX_UPLOAD_BYTES = _get_int_env("AIC_UPLOAD_MAX_BYTES", 100 * 1024 * 1024, 1)
IMAGE_DERIVATIVE_DISPLAY_MAX_EDGE = 1280
IMAGE_DERIVATIVE_THUMB_MAX_EDGE = 320
IMAGE_DERIVATIVE_DISPLAY_QUALITY = 78
IMAGE_DERIVATIVE_THUMB_QUALITY = 70
IMAGE_DERIVATIVE_ROOT_DIRNAME = "_derived"

V54_VIP_MODEL_ID = "runninghub/2041741496667348994"
V54_VIP_WORKFLOW_ID = "2041741496667348994"
DREAMINA_VIDEO_VIP_MODEL_ID = "dreamina/video_vip"
VIDEO_VIP_MODEL_IDS = (
    "runninghub/2041741496667348994",
    "dreamina/video_vip",
)
VIDEO_VIP_WORKFLOW_IDS = set(
    mid.split("/", 1)[1]
    for mid in VIDEO_VIP_MODEL_IDS
    if mid.startswith("runninghub/") and "/" in mid
)
VIDEO_VIP_MODEL_NAME_MAP = {
    "runninghub/2041741496667348994": "视频编辑V5.4",
    "dreamina/video_vip": "即梦视频",
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
OFFICIAL_SUBSCRIPTION_API_BASE = "https://api.ashuoai.com"


def _get_system_state_dir():
    app_folder = "AI-CanvasPro"
    if sys.platform.startswith("win"):
        base_dir = (
            os.environ.get("LOCALAPPDATA")
            or os.environ.get("APPDATA")
            or os.path.expanduser("~")
        )
        return os.path.join(base_dir, app_folder)
    if sys.platform == "darwin":
        return os.path.join(
            os.path.expanduser("~/Library/Application Support"),
            app_folder,
        )
    base_dir = (
        os.environ.get("XDG_STATE_HOME")
        or os.path.expanduser("~/.local/state")
    )
    return os.path.join(base_dir, app_folder)


SYSTEM_STATE_DIR = _get_system_state_dir()
SYSTEM_SETTINGS_FILE = os.path.join(SYSTEM_STATE_DIR, "settings.json")


def _read_json_file(path, default=None):
    fallback = {} if default is None else default
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else fallback
    except Exception:
        return fallback


def _write_json_file(path, data):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _normalize_storage_dir(raw, fallback):
    value = str(raw or "").strip()
    if not value:
        return os.path.abspath(fallback)
    value = os.path.expandvars(os.path.expanduser(value))
    return os.path.abspath(value)


def _file_save_paths_from_settings(settings):
    src = settings.get("fileSavePaths") if isinstance(settings, dict) else {}
    if not isinstance(src, dict):
        src = {}
    return {
        "userDir": _normalize_storage_dir(src.get("userDir"), DEFAULT_USER_DIR),
        "outputDir": _normalize_storage_dir(src.get("outputDir"), DEFAULT_OUTPUT_DIR),
        "tempDir": _normalize_storage_dir(src.get("tempDir"), DEFAULT_UPLOADS_DIR),
    }


def _current_file_save_paths():
    return {
        "userDir": os.path.abspath(USER_DIR),
        "outputDir": os.path.abspath(OUTPUT_DIR),
        "tempDir": os.path.abspath(UPLOADS_DIR),
    }


def _is_path_inside(candidate, root):
    try:
        candidate_abs = os.path.normcase(os.path.abspath(candidate))
        root_abs = os.path.normcase(os.path.abspath(root))
        return os.path.commonpath([candidate_abs, root_abs]) == root_abs
    except Exception:
        return False


def _is_same_or_nested_path(a, b):
    aa = os.path.normcase(os.path.abspath(a))
    bb = os.path.normcase(os.path.abspath(b))
    return aa == bb or _is_path_inside(aa, bb) or _is_path_inside(bb, aa)


def _validate_file_save_paths(paths):
    normalized = {
        "userDir": _normalize_storage_dir(paths.get("userDir"), DEFAULT_USER_DIR),
        "outputDir": _normalize_storage_dir(paths.get("outputDir"), DEFAULT_OUTPUT_DIR),
        "tempDir": _normalize_storage_dir(paths.get("tempDir"), DEFAULT_UPLOADS_DIR),
    }
    for label, p in (
        ("用户设置保存路径", normalized["userDir"]),
        ("输出文件保存路径", normalized["outputDir"]),
        ("临时文件保存路径", normalized["tempDir"]),
    ):
        if not os.path.isabs(p):
            raise ValueError(f"{label}必须是绝对路径")
        if os.path.exists(p) and not os.path.isdir(p):
            raise ValueError(f"{label}不能指向文件")

    pairs = (
        ("用户设置保存路径", normalized["userDir"], "输出文件保存路径", normalized["outputDir"]),
        ("用户设置保存路径", normalized["userDir"], "临时文件保存路径", normalized["tempDir"]),
        ("输出文件保存路径", normalized["outputDir"], "临时文件保存路径", normalized["tempDir"]),
    )
    for left_label, left, right_label, right in pairs:
        if _is_same_or_nested_path(left, right):
            raise ValueError(f"{left_label}和{right_label}不能相同或互相包含")
    return normalized


def _copy_missing_tree(src, dst):
    src = os.path.abspath(src)
    dst = os.path.abspath(dst)
    if not os.path.isdir(src):
        return
    os.makedirs(dst, exist_ok=True)
    for root, dirs, files in os.walk(src):
        rel_root = os.path.relpath(root, src)
        target_root = dst if rel_root == "." else os.path.join(dst, rel_root)
        os.makedirs(target_root, exist_ok=True)
        for dirname in dirs:
            os.makedirs(os.path.join(target_root, dirname), exist_ok=True)
        for filename in files:
            src_file = os.path.join(root, filename)
            dst_file = os.path.join(target_root, filename)
            if os.path.exists(dst_file):
                continue
            try:
                shutil.copy2(src_file, dst_file)
            except Exception:
                pass


def _refresh_storage_globals(paths):
    global USER_DIR, CANVAS_DIR, UPLOADS_DIR, OUTPUT_DIR, CONFIG_FILE, SETTINGS_FILE
    global GEN_SEQ_STATE_FILE, DREAMINA_CLI_SERVICE, DREAMINA_ROUTE_SERVICE
    USER_DIR = os.path.abspath(paths["userDir"])
    CANVAS_DIR = os.path.join(USER_DIR, "Canvas Project")
    UPLOADS_DIR = os.path.abspath(paths["tempDir"])
    OUTPUT_DIR = os.path.abspath(paths["outputDir"])
    CONFIG_FILE = os.path.join(USER_DIR, "config.json")
    SETTINGS_FILE = os.path.join(USER_DIR, "settings.json")
    GEN_SEQ_STATE_FILE = os.path.join(OUTPUT_DIR, ".gen_seq_state.json")
    try:
        DREAMINA_CLI_SERVICE = DreaminaCliService(CONFIG_FILE, output_root_dir=OUTPUT_DIR)
        DREAMINA_ROUTE_SERVICE = DreaminaRouteService(
            cli_service=DREAMINA_CLI_SERVICE,
            subscription_gate_service=SUBSCRIPTION_GATE_SERVICE,
            video_required_model_id=DREAMINA_VIDEO_VIP_MODEL_ID,
        )
    except NameError:
        pass


def _ensure_storage_dirs():
    os.makedirs(USER_DIR, exist_ok=True)
    os.makedirs(CANVAS_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _apply_file_save_paths(paths, migrate=False):
    normalized = _validate_file_save_paths(paths)
    previous = _current_file_save_paths()
    for p in normalized.values():
        os.makedirs(p, exist_ok=True)
    if migrate:
        _copy_missing_tree(previous["userDir"], normalized["userDir"])
        _copy_missing_tree(previous["outputDir"], normalized["outputDir"])
        _copy_missing_tree(previous["tempDir"], normalized["tempDir"])
    _refresh_storage_globals(normalized)
    _ensure_storage_dirs()
    return _current_file_save_paths()


def _persist_system_file_save_paths(paths):
    system_settings = _read_json_file(SYSTEM_SETTINGS_FILE, {})
    next_system_settings = dict(system_settings)
    next_system_settings["fileSavePaths"] = dict(paths)
    if system_settings.get("installId"):
        next_system_settings["installId"] = system_settings.get("installId")
    _write_json_file(SYSTEM_SETTINGS_FILE, next_system_settings)

def _is_enabled_env(name):
    try:
        value = str(os.environ.get(name, "") or "").strip().lower()
    except Exception:
        return False
    return value in ("1", "true", "yes", "on")

def _resolve_subscription_api_base():
    allow_override = (
        _is_enabled_env("AIC_ALLOW_SUBSCRIPTION_API_OVERRIDE")
        or _is_enabled_env("AIC_DEV_MODE")
    )
    raw_override = (os.environ.get("AIC_SUBSCRIPTION_API_BASE", "") or "").strip()
    if allow_override and raw_override:
        return raw_override.rstrip("/"), True
    return OFFICIAL_SUBSCRIPTION_API_BASE, False

SUBSCRIPTION_API_BASE, SUBSCRIPTION_API_BASE_OVERRIDDEN = _resolve_subscription_api_base()
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
SUBSCRIPTION_GATE_SERVICE = SubscriptionGateService(
    client=SUBSCRIPTION_CLIENT,
    status_active=SUB_STATUS_ACTIVE,
    status_none=SUB_STATUS_NONE,
    error_model_not_entitled=SUB_ERROR_MODEL_NOT_ENTITLED,
    model_name_map=VIDEO_VIP_MODEL_NAME_MAP,
    success_logger=lambda decision: print("[subscription][vip_gate] first VIP verification passed"),
)
os.makedirs(SYSTEM_STATE_DIR, exist_ok=True)
_startup_system_settings = _read_json_file(SYSTEM_SETTINGS_FILE, {})
_startup_local_settings = _read_json_file(os.path.join(DEFAULT_USER_DIR, "settings.json"), {})
_startup_settings = dict(_startup_local_settings)
if isinstance(_startup_system_settings.get("fileSavePaths"), dict):
    _startup_settings["fileSavePaths"] = _startup_system_settings.get("fileSavePaths")
try:
    _apply_file_save_paths(_file_save_paths_from_settings(_startup_settings), migrate=False)
except Exception:
    _apply_file_save_paths(
        {
            "userDir": DEFAULT_USER_DIR,
            "outputDir": DEFAULT_OUTPUT_DIR,
            "tempDir": DEFAULT_UPLOADS_DIR,
        },
        migrate=False,
    )
DREAMINA_CLI_SERVICE = DreaminaCliService(CONFIG_FILE, output_root_dir=OUTPUT_DIR)
DREAMINA_ROUTE_SERVICE = DreaminaRouteService(
    cli_service=DREAMINA_CLI_SERVICE,
    subscription_gate_service=SUBSCRIPTION_GATE_SERVICE,
    video_required_model_id=DREAMINA_VIDEO_VIP_MODEL_ID,
)
# 确保目录存在
os.makedirs(ASSETS_DIR,  exist_ok=True)
os.makedirs(ASSET_THUMBS_DIR, exist_ok=True)
os.makedirs(WORKFLOWS_DIR, exist_ok=True)
os.makedirs(WORKFLOW_THUMBS_DIR, exist_ok=True)


def _read_user_settings():
    local_settings = _read_json_file(SETTINGS_FILE, {})
    system_settings = _read_json_file(SYSTEM_SETTINGS_FILE, {})

    system_install_id = str(system_settings.get("installId") or "").strip()
    local_install_id = str(local_settings.get("installId") or "").strip()
    system_file_save_paths = (
        system_settings.get("fileSavePaths")
        if isinstance(system_settings.get("fileSavePaths"), dict)
        else None
    )

    # 兼容旧版本：首次读到仓库内 settings.json 的 installId 时自动迁移到系统目录。
    if not system_install_id and local_install_id:
        system_settings = dict(system_settings)
        system_settings["installId"] = local_install_id
        try:
            _write_json_file(SYSTEM_SETTINGS_FILE, system_settings)
        except Exception:
            pass
        system_install_id = local_install_id

    merged = dict(local_settings)
    if system_install_id:
        merged["installId"] = system_install_id
    if system_file_save_paths:
        merged["fileSavePaths"] = _file_save_paths_from_settings(
            {"fileSavePaths": system_file_save_paths}
        )
    else:
        merged["fileSavePaths"] = _current_file_save_paths()
    return merged


def _write_user_settings(data):
    payload = dict(data) if isinstance(data, dict) else {}
    if isinstance(payload.get("fileSavePaths"), dict):
        applied_paths = _apply_file_save_paths(payload["fileSavePaths"], migrate=True)
        payload["fileSavePaths"] = applied_paths
        _persist_system_file_save_paths(applied_paths)
    elif "fileSavePaths" not in payload:
        payload["fileSavePaths"] = _current_file_save_paths()
    _write_json_file(SETTINGS_FILE, payload)

    install_id = str(payload.get("installId") or "").strip()
    system_settings = _read_json_file(SYSTEM_SETTINGS_FILE, {})
    next_system_settings = dict(system_settings)
    if install_id:
        next_system_settings["installId"] = install_id
    next_system_settings["fileSavePaths"] = dict(payload.get("fileSavePaths") or _current_file_save_paths())
    _write_json_file(SYSTEM_SETTINGS_FILE, next_system_settings)

def _is_dev_build():
    return os.path.exists(os.path.join(DIRECTORY, ".dev"))

def _is_advanced_mode():
    return os.path.exists(os.path.join(DIRECTORY, ".Advanced"))

UPDATE_SERVICE = HotUpdateService(
    directory=DIRECTORY,
    local_version=LOCAL_VERSION,
    is_dev_build=_is_dev_build,
)

SAM3_SERVICE = Sam3Service(
    directory=DIRECTORY,
    assets_dir=ASSETS_DIR,
    uploads_dir_provider=lambda: UPLOADS_DIR,
    output_dir_provider=lambda: OUTPUT_DIR,
    path_inside_checker=_is_path_inside,
)
SAM3_ROUTE_SERVICE = Sam3RouteService(sam3_service=SAM3_SERVICE)
CONFIG_ROUTE_SERVICE = ConfigRouteService(config_file_getter=lambda: CONFIG_FILE)
JSON_FILE_ROUTE_SERVICE = JsonFileRouteService(
    canvas_dir_getter=lambda: CANVAS_DIR,
    assets_dir_getter=lambda: ASSETS_DIR,
    workflows_dir_getter=lambda: WORKFLOWS_DIR,
    user_dir_getter=lambda: USER_DIR,
    read_user_settings=_read_user_settings,
    write_user_settings=_write_user_settings,
    atomic_write_json=lambda path, data: _atomic_write_json(path, data),
)
LIBRARY_FILE_ROUTE_SERVICE = LibraryFileRouteService(
    user_dir_getter=lambda: USER_DIR,
    asset_thumbs_dir_getter=lambda: ASSET_THUMBS_DIR,
    workflow_thumbs_dir_getter=lambda: WORKFLOW_THUMBS_DIR,
)

def _get_custom_ai_config():
    return CONFIG_ROUTE_SERVICE.get_custom_ai_config()


def _extract_install_id_from_request(handler, payload=None):
    return SUBSCRIPTION_GATE_SERVICE.extract_install_id_from_request(handler, payload)


def _enforce_vip_subscription_gate(handler, payload=None, required_model_id=""):
    decision = SUBSCRIPTION_GATE_SERVICE.check_vip_subscription_gate(
        handler,
        payload,
        required_model_id=required_model_id,
    )
    if bool(decision.get("allowed")):
        return True
    _json_ok(handler, SUBSCRIPTION_GATE_SERVICE.build_subscription_denial_payload(decision))
    return False


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


def _send_route_response(handler, response):
    if not isinstance(response, dict):
        raise ValueError("Route response must be a dict")
    kind = str(response.get("kind") or "").strip()
    if kind == "json_ok":
        _json_ok(handler, response.get("data"))
        return
    if kind == "json_err":
        _json_err(
            handler,
            int(response.get("code") or 500),
            response.get("message") or "Unknown error",
        )
        return
    if kind == "binary":
        body = response.get("body") or b""
        if isinstance(body, str):
            body = body.encode("utf-8")
        else:
            body = bytes(body)
        handler.send_response(int(response.get("status") or 200))
        handler.send_header(
            "Content-Type",
            str(response.get("contentType") or "application/octet-stream"),
        )
        headers = response.get("headers") if isinstance(response.get("headers"), dict) else {}
        for name, value in headers.items():
            handler.send_header(str(name), str(value))
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        try:
            handler.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass
        return
    raise ValueError(f"Unknown route response kind: {kind}")

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


HTTP_ROUTE_DISPATCHER = HttpRouteDispatcher(
    local_version=LOCAL_VERSION,
    is_dev_build=_is_dev_build,
    is_advanced_mode=_is_advanced_mode,
    subscription_client_getter=lambda: SUBSCRIPTION_CLIENT,
    subscription_gate_service_getter=lambda: SUBSCRIPTION_GATE_SERVICE,
    config_route_service_getter=lambda: CONFIG_ROUTE_SERVICE,
    json_file_route_service_getter=lambda: JSON_FILE_ROUTE_SERVICE,
    library_file_route_service_getter=lambda: LIBRARY_FILE_ROUTE_SERVICE,
    dreamina_route_service_getter=lambda: DREAMINA_ROUTE_SERVICE,
    sam3_route_service_getter=lambda: SAM3_ROUTE_SERVICE,
    update_service_getter=lambda: UPDATE_SERVICE,
    smart_clip_cleanup=_smart_clip_cleanup,
    smart_clip_jobs=_smart_clip_jobs,
    smart_clip_lock=_smart_clip_lock,
    sub_status_none=SUB_STATUS_NONE,
    sub_error_invalid_arguments=SUB_ERROR_INVALID_ARGUMENTS,
    default_sub_contact_text=DEFAULT_SUB_CONTACT_TEXT,
    default_sub_contact_url=DEFAULT_SUB_CONTACT_URL,
    json_ok=_json_ok,
    json_err=_json_err,
    send_route_response=_send_route_response,
    read_body=_read_body,
)


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
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        raise

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


def _normalize_posix_rel_path(path_value):
    return str(path_value or "").replace("\\", "/").strip("/")


def _join_virtual_local_path(root_prefix, rel_path):
    root = _normalize_posix_rel_path(root_prefix)
    rel = _normalize_posix_rel_path(rel_path)
    if root and rel:
        return f"{root}/{rel}"
    return root or rel


def _resolve_virtual_media_root(local_path=None, abs_path=None):
    norm_local = _normalize_posix_rel_path(local_path)
    if norm_local.startswith("output/"):
        rel = norm_local[len("output/"):].lstrip("/")
        return OUTPUT_DIR, "output", rel
    if norm_local.startswith("data/uploads/"):
        rel = norm_local[len("data/uploads/"):].lstrip("/")
        return UPLOADS_DIR, "data/uploads", rel

    abs_candidate = os.path.abspath(abs_path) if abs_path else None
    if abs_candidate and _is_path_inside(abs_candidate, OUTPUT_DIR):
        rel = os.path.relpath(abs_candidate, OUTPUT_DIR).replace("\\", "/")
        return OUTPUT_DIR, "output", rel
    if abs_candidate and _is_path_inside(abs_candidate, UPLOADS_DIR):
        rel = os.path.relpath(abs_candidate, UPLOADS_DIR).replace("\\", "/")
        return UPLOADS_DIR, "data/uploads", rel
    return None, None, None


def _image_variant_needs_alpha(img):
    try:
        if "A" in (img.getbands() or ()):
            return True
    except Exception:
        pass
    try:
        if img.mode == "P" and "transparency" in getattr(img, "info", {}):
            return True
    except Exception:
        pass
    return False


def _build_image_derivative_target(root_abs, root_prefix, rel_original_path, variant, ext):
    normalized_rel = _normalize_posix_rel_path(rel_original_path)
    rel_dir = _normalize_posix_rel_path(os.path.dirname(normalized_rel))
    base_name = os.path.splitext(os.path.basename(normalized_rel))[0]
    rel_parts = [IMAGE_DERIVATIVE_ROOT_DIRNAME, variant]
    if rel_dir:
        rel_parts.extend([p for p in rel_dir.split("/") if p])
    rel_parts.append(f"{base_name}.{variant}.{ext}")
    rel_variant = "/".join(rel_parts)
    abs_variant = os.path.abspath(os.path.join(root_abs, *rel_variant.split("/")))
    local_variant = _join_virtual_local_path(root_prefix, rel_variant)
    return abs_variant, local_variant


def _save_image_derivative_variant(source_img, out_path, max_edge, ext, quality, keep_alpha):
    from PIL import Image

    resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS", getattr(Image, "LANCZOS", Image.BICUBIC))
    img = source_img.copy()
    img.thumbnail((max_edge, max_edge), resampling)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if keep_alpha:
        if img.mode not in ("RGBA", "LA"):
            img = img.convert("RGBA")
        if ext == "webp":
            img.save(out_path, format="WEBP", quality=quality, method=6)
            return
        img.save(out_path, format="PNG", optimize=True)
        return

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    if img.mode == "L":
        img = img.convert("RGB")
    if ext == "jpg":
        img.save(
            out_path,
            format="JPEG",
            quality=quality,
            optimize=True,
            progressive=True,
        )
        return
    img.save(out_path, format=ext.upper())


def _collect_image_derivative_payload(abs_path, root_abs, root_prefix, rel_original_path):
    try:
        from PIL import Image, ImageOps
    except Exception:
        return {}

    if not abs_path or not os.path.isfile(abs_path):
        return {}
    if not root_abs or not root_prefix or not rel_original_path:
        return {}
    if not _is_path_inside(abs_path, root_abs):
        return {}

    try:
        with Image.open(abs_path) as opened:
            base_img = ImageOps.exif_transpose(opened)
            original_width, original_height = base_img.size
            if not (original_width > 0 and original_height > 0):
                return {}
            keep_alpha = _image_variant_needs_alpha(opened) or _image_variant_needs_alpha(base_img)
            variant_ext = "png" if keep_alpha else "jpg"
            display_abs, display_local = _build_image_derivative_target(
                root_abs,
                root_prefix,
                rel_original_path,
                "display",
                variant_ext,
            )
            thumb_abs, thumb_local = _build_image_derivative_target(
                root_abs,
                root_prefix,
                rel_original_path,
                "thumb",
                variant_ext,
            )
            _save_image_derivative_variant(
                base_img,
                display_abs,
                IMAGE_DERIVATIVE_DISPLAY_MAX_EDGE,
                variant_ext,
                IMAGE_DERIVATIVE_DISPLAY_QUALITY,
                keep_alpha,
            )
            _save_image_derivative_variant(
                base_img,
                thumb_abs,
                IMAGE_DERIVATIVE_THUMB_MAX_EDGE,
                variant_ext,
                IMAGE_DERIVATIVE_THUMB_QUALITY,
                keep_alpha,
            )
    except Exception:
        return {}

    original_local = _join_virtual_local_path(root_prefix, rel_original_path)
    return {
        "localPath": original_local,
        "originalLocalPath": original_local,
        "displayLocalPath": display_local,
        "thumbLocalPath": thumb_local,
        "originalWidth": int(original_width),
        "originalHeight": int(original_height),
    }


def _augment_saved_media_response(payload, abs_path, local_path):
    root_abs, root_prefix, rel_original_path = _resolve_virtual_media_root(local_path, abs_path)
    if not root_abs or not root_prefix or not rel_original_path:
        return payload

    derivative_payload = _collect_image_derivative_payload(
        abs_path,
        root_abs,
        root_prefix,
        rel_original_path,
    )
    if not derivative_payload:
        return payload

    next_payload = dict(payload or {})
    next_payload.update(derivative_payload)
    original_local = str(next_payload.get("originalLocalPath") or "").strip()
    display_local = str(next_payload.get("displayLocalPath") or "").strip()
    thumb_local = str(next_payload.get("thumbLocalPath") or "").strip()
    if original_local:
        next_payload["originalUrl"] = "/" + original_local.lstrip("/")
    if display_local:
        next_payload["displayUrl"] = "/" + display_local.lstrip("/")
    if thumb_local:
        next_payload["thumbUrl"] = "/" + thumb_local.lstrip("/")
    return next_payload


def _resolve_local_virtual_path(src_path):
    safe_src = str(src_path or "").strip().lstrip("/")
    norm_src = os.path.normpath(safe_src)
    if not safe_src or norm_src.startswith("..") or norm_src.startswith("../") or norm_src.startswith("..\\"):
        return None
    norm_slash = norm_src.replace("\\", "/")
    if norm_slash.startswith("output/"):
        rel = norm_slash[len("output/"):].lstrip("/")
        return os.path.abspath(os.path.join(OUTPUT_DIR, rel))
    if norm_slash.startswith("data/uploads/"):
        rel = norm_slash[len("data/uploads/"):].lstrip("/")
        return os.path.abspath(os.path.join(UPLOADS_DIR, rel))
    return os.path.abspath(os.path.join(DIRECTORY, norm_src))


class Handler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def translate_path(self, path):
        raw_path = urllib.parse.urlsplit(path).path
        decoded_path = urllib.parse.unquote(raw_path).replace("\\", "/")
        virtual_roots = (
            ("/output/", OUTPUT_DIR),
            ("/data/uploads/", UPLOADS_DIR),
        )
        for prefix, root_dir in virtual_roots:
            if decoded_path == prefix[:-1] or decoded_path.startswith(prefix):
                rel = decoded_path[len(prefix):].lstrip("/")
                rel = os.path.normpath(rel)
                if rel in ("", "."):
                    return os.path.abspath(root_dir)
                if rel.startswith(".."):
                    return os.path.abspath(root_dir)
                return os.path.abspath(os.path.join(root_dir, rel))
        return super().translate_path(path)

    # 屏蔽日志噪音（按霢注释掉）
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

    # ┢┢ OPTIONS 预检（CORS）─┢┢┢┢┢┢┢┢┢┢┢┢┢┢┢┢┢┢┢┢┢┢┢┢┢┢┢┢┢
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, PATCH, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, X-AIC-Install-Id",
        )
        self.end_headers()

    # ════════════════════════════════════════════════════
    #  DELETE  /api/v2/projects/{filename}
    # ════════════════════════════════════════════════════
    def do_DELETE(self):
        path = self.path.split("?")[0]
        if HTTP_ROUTE_DISPATCHER.handle_delete(self, path):
            return

        _json_err(self, 400, "Invalid request")

    # ════════════════════════════════════════════════════
    #  PATCH  /api/v2/projects/{filename}  ?rename
    # ════════════════════════════════════════════════════
    def do_PATCH(self):
        path = self.path.split("?")[0]
        if HTTP_ROUTE_DISPATCHER.handle_patch(self, path):
            return

        _json_err(self, 400, "Invalid request")

    # ════════════════════════════════════════════════════
    #  GET
    # ════════════════════════════════════════════════════
    def do_GET(self):
        path = self.path.split("?")[0]

        if HTTP_ROUTE_DISPATCHER.handle_get(self, path):
            return

        # --- ?????? (GET) ---
        if path == "/api/v2/proxy/task":
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            # ?? keep_blank_values=True ? max_num_fields=10 ??????
            qs = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=10)
            api_url = qs.get("apiUrl", [""])[0].strip() if "apiUrl" in qs else ""
            api_key = qs.get("apiKey", [""])[0].strip() if "apiKey" in qs else ""
            # ???????
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
                # ???? requests??????
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

                # ???? urllib??????????????????????
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

        # --- ???????? SimpleHTTPRequestHandler ??? ---
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

    # ════════════════════════════════════════════════════
    #  POST
    # ════════════════════════════════════════════════════
    def do_POST(self):
        path = self.path.split("?")[0]

        if HTTP_ROUTE_DISPATCHER.handle_post(self, path):
            return

        # ┢┢ 文件上传 ┢┢
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
                response_payload = _augment_saved_media_response(
                    {
                        "url": rel_url,
                        "localPath": f"data/uploads/{safe_fn}",
                        "filename": safe_fn,
                    },
                    fpath,
                    f"data/uploads/{safe_fn}",
                )
                _json_ok(self, response_payload)
            except Exception as e:
                try:
                    _json_err(self, 500, f"Upload failed: {str(e)}")
                except Exception:
                    pass
            return

        if path == "/api/v2/images/derivatives/ensure":
            body = _read_body(self)
            try:
                data = json.loads(body or b"{}")
            except Exception:
                _json_err(self, 400, "Invalid JSON")
                return

            local_path = str(data.get("localPath") or data.get("path") or "").strip()
            if not local_path:
                _json_err(self, 400, "Missing localPath")
                return

            abs_path = _resolve_local_virtual_path(local_path)
            if not abs_path or not os.path.isfile(abs_path):
                _json_err(self, 404, "Image not found")
                return

            root_abs, root_prefix, rel_original_path = _resolve_virtual_media_root(local_path, abs_path)
            derivative_payload = _collect_image_derivative_payload(
                abs_path,
                root_abs,
                root_prefix,
                rel_original_path,
            )
            if not derivative_payload:
                _json_err(self, 400, "Derivative generation failed")
                return

            response_payload = {
                "success": True,
                **derivative_payload,
            }
            response_payload["url"] = "/" + str(response_payload["localPath"]).lstrip("/")
            response_payload["originalUrl"] = "/" + str(response_payload["originalLocalPath"]).lstrip("/")
            response_payload["displayUrl"] = "/" + str(response_payload["displayLocalPath"]).lstrip("/")
            response_payload["thumbUrl"] = "/" + str(response_payload["thumbLocalPath"]).lstrip("/")
            _json_ok(self, response_payload)
            return

        # --- ?????????????????? output? ---
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
                if sub_dir and re.match(r"^[a-zA-Z0-9 _-]+$", sub_dir):
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
                    response_payload = _augment_saved_media_response(
                        {
                            "success": True,
                            "filename": filename,
                            "path": rel_path,
                            "localPath": rel_path,
                            "url": f"/{rel_path}",
                        },
                        fpath,
                        rel_path,
                    )
                    _json_ok(
                        self,
                        response_payload,
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
            
            # ??????????????????????????? DIRECTORY?
            safe_src = src_path.lstrip("/")
            norm_src = os.path.normpath(safe_src)
            if norm_src.startswith("..") or norm_src.startswith("../") or norm_src.startswith("..\\"):
                _json_err(self, 400, "Invalid src path")
                return
            local_src = _resolve_local_virtual_path(src_path)
            
            if not local_src or not os.path.exists(local_src):
                _json_err(self, 404, "Source video not found")
                return
                
            # 准备输出目录
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

                # 使用 FFmpeg 进行精准裁剪 (-ss 放在输入前可以加速，放在输入后可以更精准，这里用精确模式)
                # ??????????????????? copy ??????????
                # ???????????????
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
                
                # ????????Windows?
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

        # ┢┢ 音频裁剪 (依赖 FFmpeg) ┢┢
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
            local_src = _resolve_local_virtual_path(src_path)

            if not local_src or not os.path.exists(local_src):
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
                local_src = _resolve_local_virtual_path(sp)
                if not local_src or not os.path.exists(local_src):
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
            local_src = _resolve_local_virtual_path(src_path)

            if not local_src or not os.path.exists(local_src):
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

        # --- ???????? FFprobe/FFmpeg? ---
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
            local_src = _resolve_local_virtual_path(src_path)

            if not local_src or not os.path.exists(local_src):
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

        # ┢┢ 视频首帧缩略图（依赖 FFmpeg，产物落盘到 output/VideoThumbs?┢┢
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

            # ??????????????????????????? DIRECTORY?
            safe_src = src_path.lstrip("/")
            norm_src = os.path.normpath(safe_src)
            if norm_src.startswith("..") or norm_src.startswith("../") or norm_src.startswith("..\\"):
                _json_err(self, 400, "Invalid src path")
                return
            local_src = _resolve_local_virtual_path(src_path)

            if not local_src or not os.path.exists(local_src):
                _json_err(self, 404, "Source video not found")
                return

            try:
                st = os.stat(local_src)
            except Exception:
                _json_err(self, 500, "Cannot stat source video")
                return

            # ????? + mtime + size????????????????? output ??
            sig = f"{norm_src}|{getattr(st, 'st_mtime_ns', int(st.st_mtime * 1e9))}|{st.st_size}"
            h = hashlib.sha1(sig.encode("utf-8", errors="ignore")).hexdigest()[:12]

            thumb_dir = os.path.join(OUTPUT_DIR, "VideoThumbs")
            os.makedirs(thumb_dir, exist_ok=True)
            filename = f"vthumb_{h}.jpg"
            out_path = os.path.join(thumb_dir, filename)

            if not os.path.exists(out_path):
                try:
                    # 快速抽首帧：优先返回速度（首屏体验）而非清晰度
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
                        "scale=240:-2",
                        "-q:v",
                        "8",
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

        # --- ??? URL ?????? output?????????????? ---
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
            response_payload = _augment_saved_media_response(
                {
                    "success": True,
                    "filename": filename,
                    "path": rel_path,
                    "localPath": rel_path,
                    "url": f"/{rel_path}",
                },
                fpath,
                rel_path,
            )
            _json_ok(
                self,
                response_payload,
            )
            return

        # ┢┢ 文件上传代理（RunningHUB 等）┢┢
        if path == "/api/v2/proxy/upload":
            try:
                import urllib.request
                import urllib.error
                
                # ??????? apiUrl ? apiKey
                from urllib.parse import parse_qs, urlparse
                qs = parse_qs(urlparse(self.path).query)
                api_url = qs.get("apiUrl", [""])[0].strip()
                api_key = qs.get("apiKey", [""])[0].strip()
                
                if not api_url or not api_key:
                    _json_err(self, 400, "Missing apiUrl or apiKey"); return
                
                # ????????multipart/form-data?
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)
                content_type = self.headers.get('Content-Type', '')
                
                # ????? RunningHUB
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
                    rel = s2[len("output/"):].lstrip("/\\")
                    fp = os.path.abspath(os.path.join(OUTPUT_DIR, rel))
                    if _is_path_inside(fp, OUTPUT_DIR) and os.path.isfile(fp):
                        return fp
                if s2.startswith("data/uploads/"):
                    rel = s2[len("data/uploads/"):].lstrip("/\\")
                    fp = os.path.abspath(os.path.join(UPLOADS_DIR, rel))
                    if _is_path_inside(fp, UPLOADS_DIR) and os.path.isfile(fp):
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
                if not _enforce_vip_subscription_gate(
                    self,
                    data,
                    required_model_id=f"runninghub/{workflow_id}",
                ):
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

        # ┢┢ PPIO 图像生成代理 ┢┢
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
            def _extract_task_id_from_text(raw_text):
                text = str(raw_text or "")
                if not text:
                    return ""
                patterns = [
                    r'"task_id"\s*:\s*"([^"]+)"',
                    r'"taskId"\s*:\s*"([^"]+)"',
                    r'"id"\s*:\s*"([^"]+)"',
                    r'"data"\s*:\s*"([^"]{8,})"',
                    r'\btask[_-]?id\b\s*[:=]\s*["\']?([a-zA-Z0-9._:-]+)["\']?',
                    r'\bid\b\s*[:=]\s*["\']?([a-zA-Z0-9._:-]{8,})["\']?',
                ]
                for pattern in patterns:
                    match = re.search(pattern, text, flags=re.IGNORECASE)
                    if match:
                        value = str(match.group(1) or "").strip()
                        if value:
                            return value
                return ""
            workflow_match = re.search(
                r"/openapi/v2/run/ai-app/(\d+)$",
                api_url,
                flags=re.IGNORECASE,
            )
            workflow_id = workflow_match.group(1) if workflow_match else ""
            is_runninghub_query_endpoint = bool(
                re.search(r"/openapi/v2/query(?:$|[/?])", api_url, flags=re.IGNORECASE)
            )
            # 仅在“提交任务”类端点启用 task_id 快速探测；
            # 查询类端点必须透传完整响应，否则前端无法拿到最终出图 URL。
            is_grsai_query_endpoint = bool(
                re.search(r"/v1/draw/(?:result|query)(?:$|[/?])", api_url, flags=re.IGNORECASE)
            )
            allow_task_probe_short_circuit = not (
                is_runninghub_query_endpoint or is_grsai_query_endpoint
            )
            if workflow_id in VIDEO_VIP_WORKFLOW_IDS:
                if not _enforce_vip_subscription_gate(
                    self,
                    data,
                    required_model_id=f"runninghub/{workflow_id}",
                ):
                    return
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
                # 减少代理复用连接被远端提前关闭导致的偶发断链
                "Connection": "close",
            }
            try:
                import requests as _req
                retry_delays = (0.0, 0.3, 0.9)
                proxy_error_markers = (
                    "ProxyError",
                    "Unable to connect to proxy",
                    "RemoteDisconnected",
                    "MaxRetryError",
                )
                for attempt_idx, delay_sec in enumerate(retry_delays):
                    if delay_sec > 0:
                        time.sleep(delay_sec)
                    try:
                        resp = _req.post(
                            api_url,
                            json=data,
                            headers=headers,
                            timeout=900,
                            stream=True,
                        )
                        header_task_id = ""
                        for key in (
                            "x-task-id",
                            "x-taskid",
                            "task-id",
                            "taskid",
                            "x-request-id",
                            "request-id",
                            "x-job-id",
                            "job-id",
                        ):
                            value = str(resp.headers.get(key, "") or "").strip()
                            if value:
                                header_task_id = value
                                break
                        if header_task_id and allow_task_probe_short_circuit:
                            _json_ok(
                                self,
                                {
                                    "task_id": header_task_id,
                                    "status": "submitted",
                                    "source": "header",
                                },
                            )
                            try:
                                resp.close()
                            except Exception:
                                pass
                            return

                        chunks = []
                        bytes_read = 0
                        max_probe_bytes = 256 * 1024
                        found_task_id = ""
                        for chunk in resp.iter_content(chunk_size=4096):
                            if not chunk:
                                continue
                            chunks.append(chunk)
                            bytes_read += len(chunk)
                            if found_task_id:
                                continue
                            if bytes_read <= max_probe_bytes:
                                probe_text = b"".join(chunks).decode("utf-8", "ignore")
                                found_task_id = _extract_task_id_from_text(probe_text)
                                if found_task_id and allow_task_probe_short_circuit:
                                    _json_ok(
                                        self,
                                        {
                                            "task_id": found_task_id,
                                            "status": "submitted",
                                            "source": "body-probe",
                                        },
                                    )
                                    try:
                                        resp.close()
                                    except Exception:
                                        pass
                                    return

                        full_content = b"".join(chunks)
                        self.send_response(resp.status_code)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        self.wfile.write(full_content)
                        return
                    except _req.exceptions.ProxyError:
                        if attempt_idx == len(retry_delays) - 1:
                            raise
                    except _req.exceptions.ConnectionError as e:
                        msg = repr(e)
                        is_proxy_chain_error = any(
                            marker in msg for marker in proxy_error_markers
                        )
                        if is_proxy_chain_error:
                            if attempt_idx == len(retry_delays) - 1:
                                raise
                            continue
                        raise
            except ImportError:
                import urllib.request, urllib.error
                req_body = json.dumps(data).encode("utf-8")
                req = urllib.request.Request(api_url, data=req_body, headers=headers, method="POST")
                retry_delays = (0.0, 0.3, 0.9)
                proxy_error_markers = (
                    "ProxyError",
                    "Unable to connect to proxy",
                    "RemoteDisconnected",
                    "MaxRetryError",
                )
                for attempt_idx, delay_sec in enumerate(retry_delays):
                    if delay_sec > 0:
                        time.sleep(delay_sec)
                    try:
                        with urllib.request.urlopen(req, timeout=900) as resp:
                            resp_data = resp.read()
                        self.send_response(resp.status)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        self.wfile.write(resp_data)
                        return
                    except urllib.error.HTTPError as e:
                        self.send_response(e.code)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        self.wfile.write(e.read())
                        return
                    except urllib.error.URLError as e:
                        msg = repr(e)
                        is_proxy_chain_error = any(
                            marker in msg for marker in proxy_error_markers
                        )
                        if is_proxy_chain_error:
                            if attempt_idx == len(retry_delays) - 1:
                                raise
                            continue
                        raise
            except Exception as e:
                _json_err(self, 500, f"Proxy error: {repr(e)}")
            return

        # ┢┢ 通用代理 forwarded ┢┢
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
            
            # ?? Gemini ???????????
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
                    # ??????? 300 ???? aiTextApi.js ??????
                    resp = requests.post(endpoint, data=req_body, headers=headers, timeout=300)
                except requests.exceptions.ConnectionError as ce:
                    _json_err(self, 502, f"????? AI ???: {str(ce)}")
                    return
                except requests.exceptions.Timeout as te:
                    _json_err(self, 504, f"AI ???????: {str(te)}")
                    return
                except requests.exceptions.RequestException as req_err:
                    _json_err(self, 502, f"AI ???????: {str(req_err)}")
                    return
                
                # ??????? SSE ??????????? JSON
                resp_text = resp.text
                resp_content_type = resp.headers.get('Content-Type', '')
                
                # ?????? text/event-stream ??? data: ??????? JSON
                is_sse = 'text/event-stream' in resp_content_type or resp_text.strip().startswith('data:')
                if is_sse:
                    try:
                        # ??? SSE ??????? JSON
                        lines = [l.strip() for l in resp_text.split('\n') if l.strip().startswith('data:')]
                        if lines:
                            last_line = lines[-1].replace('data:', '').strip()
                            if last_line == '[DONE]':
                                # 找数第二个有效行
                                valid_lines = [l for l in lines if l.replace('data:', '').strip() != '[DONE]']
                                if valid_lines:
                                    json_str = valid_lines[-1].replace('data:', '').strip()
                                    json_data = json.loads(json_str)
                                    resp_text = json.dumps(json_data)
                            else:
                                json_data = json.loads(last_line)
                                resp_text = json.dumps(json_data)
                    except Exception:
                        # ?????????????
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
                    
                    # ??????? SSE ??????????? JSON
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

        # --- ??? AI ????????? OpenAI ????? ---
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
            # apiUrl/apiKey ??????????? config.json ????? AI ??
            if not api_url or not api_key:
                global_cfg = _get_custom_ai_config()
                api_url = api_url or global_cfg["apiUrl"]
                api_key = api_key or global_cfg["apiKey"]
            if not api_url or not api_key or not model or not prompt:
                _json_err(self, 400, "Missing required fields: apiUrl, apiKey, model, prompt"); return
            
            # ????????????? /chat/completions ????
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

        _json_err(self, 404, "Not found")


# --- ?? ---
if __name__ == "__main__":
    # ????????????
    _t = threading.Thread(target=UPDATE_SERVICE.update_check_loop, daemon=True, name='AutoUpdateChecker')
    _t.start()
    SAM3_SERVICE.start_background_workers()
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
        display_host = "127.0.0.1" if bind_host == "0.0.0.0" else bind_host
        print("=" * 56)
        if SUBSCRIPTION_API_BASE_OVERRIDDEN:
            print(f"[subscription] api base override enabled: {SUBSCRIPTION_API_BASE}")
        else:
            print("[subscription] api base = official")
        print("AI Canvas 服务已启动")
        print(f"http://{display_host}:{port}")
        print("按 Ctrl+C 停止服务")
        print("=" * 56)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务已停止。")
