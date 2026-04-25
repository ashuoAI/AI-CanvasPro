import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request


class DreaminaCliService:
    _DOWNLOAD_BASE = (
        "https://lf3-static.bytednsdoc.com/obj/eden-cn/psj_hupthlyk/"
        "ljhwZthlaukjlkulzlp/dreamina_cli_beta"
    )
    _WINDOWS_BINARY_URL = f"{_DOWNLOAD_BASE}/dreamina_cli_windows_amd64.exe"
    _LOGIN_SUCCESS_MARKER = "[DREAMINA:LOGIN_SUCCESS]"
    _LOGIN_REUSED_MARKER = "[DREAMINA:LOGIN_REUSED]"
    _QR_READY_MARKER = "[DREAMINA:QR_READY]"
    _DEFAULT_LOGIN_TIMEOUT_SEC = 90
    _LOGIN_PAGE_URL = "https://jimeng.jianying.com/"
    _ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-9;?]*[ -/]*[@-~]")

    def __init__(self, config_file, output_root_dir=None):
        self._config_file = os.path.abspath(config_file)
        self._user_dir = os.path.dirname(self._config_file)
        self._workspace_dir = os.path.dirname(self._user_dir)
        self._output_root_dir = os.path.abspath(output_root_dir) if output_root_dir else os.path.join(self._workspace_dir, "output")
        self._dreamina_output_root = os.path.join(self._output_root_dir, "dreamina")
        self._dreamina_video_output_dir = os.path.join(self._output_root_dir, "dreamina_video")
        self._dreamina_download_tmp_root = os.path.join(self._user_dir, "dreamina_downloads")
        self._managed_dir = os.path.join(self._user_dir, "tools", "dreamina")
        self._managed_command_path = os.path.join(
            self._managed_dir,
            "dreamina.exe" if os.name == "nt" else "dreamina",
        )
        self._lock = threading.Lock()
        self._credit_cache = None
        self._login_runtime = self._build_login_runtime()
        self._active_login_proc = None
        self._task_registry = {}
        self._query_counts = {}
        self._login_timeout_sec = self._resolve_login_timeout_sec()

    def _resolve_login_timeout_sec(self):
        raw = str(
            os.environ.get("AIC_DREAMINA_LOGIN_TIMEOUT_SEC", self._DEFAULT_LOGIN_TIMEOUT_SEC)
        ).strip()
        try:
            timeout_sec = int(raw)
        except Exception:
            timeout_sec = self._DEFAULT_LOGIN_TIMEOUT_SEC
        return max(30, timeout_sec)

    def _build_login_runtime(self):
        return {
            "active": False,
            "phase": "idle",
            "message": "",
            "error": "",
            "startedAt": 0,
            "completedAt": 0,
            "exitCode": None,
            "qrPath": "",
            "qrVersion": 0,
            "qrUpdatedAt": 0,
            "verificationUrl": "",
            "userCode": "",
            "loginMode": "headless",
            "loginPageUrl": self._LOGIN_PAGE_URL,
            "authorizeUrl": "",
            "callbackUrl": "",
            "manualLoginAvailable": False,
            "outputTail": [],
        }

    def _load_config(self):
        if not os.path.exists(self._config_file):
            return {}
        try:
            with open(self._config_file, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _load_settings(self):
        cfg = self._load_config()
        raw = cfg.get("dreaminaCli")
        if not isinstance(raw, dict):
            raw = {}
        return {
            "commandPath": str(raw.get("commandPath") or raw.get("command") or "").strip(),
            "loginMode": str(raw.get("loginMode") or "headless").strip().lower() or "headless",
        }

    def _candidate_commands(self):
        settings = self._load_settings()
        candidates = []

        def push(value):
            s = str(value or "").strip()
            if s and s not in candidates:
                candidates.append(s)

        push(settings.get("commandPath"))
        push(shutil.which("dreamina"))
        push(shutil.which("dreamina.exe"))
        push(self._managed_command_path)
        home = os.path.expanduser("~")
        push(os.path.join(home, "bin", "dreamina.exe"))
        push(os.path.join(home, "bin", "dreamina"))
        return candidates

    def _resolve_command_path(self):
        for candidate in self._candidate_commands():
            if os.path.isabs(candidate) and os.path.isfile(candidate):
                return os.path.abspath(candidate)
            resolved = shutil.which(candidate)
            if resolved:
                return os.path.abspath(resolved)
        return ""

    def _create_subprocess_env(self):
        env = os.environ.copy()
        env.setdefault("PYTHONUTF8", "1")
        env["PYTHONIOENCODING"] = "utf-8"
        return env

    def _normalize_runtime_message(self, message, fallback="即梦登录失败，请重试"):
        text = str(message or "").strip()
        if not text:
            return fallback
        lower = text.lower()
        if "bind:" in lower or "only one usage of each socket address" in lower:
            return "检测到上次未完成的登录流程，已自动重置，请重新点击登录"
        if "读取二维码响应失败" in text or "empty response body" in lower:
            return "即梦二维码获取失败，请重新点击登录"
        if "等待登录超时" in text:
            return "扫码登录已超时，请重新点击登录"
        return text

    def _run_command(self, args, timeout=30, command_path=""):
        resolved_path = str(command_path or "").strip() or self._resolve_command_path()
        if not resolved_path:
            return {
                "ok": False,
                "installed": False,
                "commandPath": "",
                "returncode": None,
                "output": "即梦组件尚未准备完成",
            }

        creation_flags = 0
        if os.name == "nt":
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            proc = subprocess.run(
                [resolved_path, *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=self._create_subprocess_env(),
                creationflags=creation_flags,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            return {
                "ok": proc.returncode == 0,
                "installed": True,
                "commandPath": resolved_path,
                "returncode": proc.returncode,
                "output": output,
            }
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") + (exc.stderr or "")
            return {
                "ok": False,
                "installed": True,
                "commandPath": resolved_path,
                "returncode": None,
                "output": output or "即梦组件执行超时",
            }
        except Exception as exc:
            return {
                "ok": False,
                "installed": True,
                "commandPath": resolved_path,
                "returncode": None,
                "output": str(exc),
            }

    def _append_runtime_output(self, line):
        runtime = self._login_runtime
        tail = runtime["outputTail"]
        if line:
            tail.append(line)
        if len(tail) > 80:
            del tail[: len(tail) - 80]
        self._sync_manual_login_links_locked()

    def _normalize_manual_url_candidate(self, url):
        value = str(url or "").strip()
        if not value:
            return ""
        value = re.sub(r'^[<（(【\["\'“‘]+', "", value)
        value = re.sub(r'[>）)】\]"\'”’]+$', "", value)
        value = re.sub(r"[，。；;、]+$", "", value)
        return value if value.startswith(("http://", "https://")) else ""

    def _extract_manual_login_links_from_lines(self, lines):
        normalized_lines = lines if isinstance(lines, list) else []
        urls = []
        next_authorize_url = ""
        for line in normalized_lines:
            text = str(line or "")
            if (not next_authorize_url) and "请在浏览器中打开以下链接" in text:
                next_authorize_url = "__PENDING__"
            elif next_authorize_url == "__PENDING__":
                next_authorize_url = text.strip()
            for match in re.findall(r"https?://[^\s]+", text):
                value = self._normalize_manual_url_candidate(match)
                if value and value not in urls:
                    urls.append(value)

        normalized_next = (
            self._normalize_manual_url_candidate(next_authorize_url)
            if next_authorize_url and next_authorize_url != "__PENDING__"
            else ""
        )
        strict_authorize_url = (
            normalized_next
            or next((url for url in urls if "/passport/web_login" in url), "")
            or next((url for url in urls if "/passport/web/web_login" in url), "")
        )
        callback_url = next(
            (url for url in urls if "/dreamina/cli/v1/dreamina_cli_login" in url),
            "",
        )
        fallback_continue_url = (
            callback_url
            or next((url for url in urls if url != self._LOGIN_PAGE_URL), "")
        )
        return {
            "authorizeUrl": callback_url or strict_authorize_url or fallback_continue_url or "",
            "strictAuthorizeUrl": strict_authorize_url or "",
            "callbackUrl": callback_url or "",
        }

    def _sync_manual_login_links_locked(self):
        runtime = self._login_runtime
        links = self._extract_manual_login_links_from_lines(runtime.get("outputTail") or [])
        runtime["loginPageUrl"] = self._LOGIN_PAGE_URL
        runtime["authorizeUrl"] = (
            str(runtime.get("verificationUrl") or "").strip()
            or links.get("authorizeUrl")
            or ""
        )
        runtime["callbackUrl"] = links.get("callbackUrl") or ""
        runtime["manualLoginAvailable"] = bool(
            runtime.get("authorizeUrl")
            or runtime.get("callbackUrl")
            or runtime.get("loginPageUrl")
        )

    def _extract_error_from_tail(self, tail_lines):
        for line in reversed(tail_lines or []):
            s = str(line or "").strip()
            if not s:
                continue
            if self._QR_READY_MARKER in s:
                continue
            return s
        return ""

    def _runtime_snapshot(self):
        runtime = self._login_runtime
        return {
            "active": bool(runtime.get("active")),
            "phase": str(runtime.get("phase") or "idle"),
            "message": str(runtime.get("message") or ""),
            "error": str(runtime.get("error") or ""),
            "startedAt": int(runtime.get("startedAt") or 0),
            "completedAt": int(runtime.get("completedAt") or 0),
            "exitCode": runtime.get("exitCode"),
            "qrAvailable": bool(runtime.get("qrPath")) and os.path.isfile(str(runtime.get("qrPath") or "")),
            "qrVersion": int(runtime.get("qrVersion") or 0),
            "qrUpdatedAt": int(runtime.get("qrUpdatedAt") or 0),
            "verificationUrl": str(runtime.get("verificationUrl") or ""),
            "userCode": str(runtime.get("userCode") or ""),
            "loginMode": str(runtime.get("loginMode") or "headless"),
            "loginPageUrl": str(runtime.get("loginPageUrl") or self._LOGIN_PAGE_URL),
            "authorizeUrl": str(runtime.get("authorizeUrl") or ""),
            "callbackUrl": str(runtime.get("callbackUrl") or ""),
            "manualLoginAvailable": bool(runtime.get("manualLoginAvailable")),
            "outputTail": list(runtime.get("outputTail") or []),
        }

    def _reset_runtime_locked(self, phase="idle", message="", active=False):
        self._login_runtime = self._build_login_runtime()
        self._login_runtime["phase"] = phase
        self._login_runtime["message"] = message
        self._login_runtime["active"] = active
        now_ms = int(time.time() * 1000)
        if active:
            self._login_runtime["startedAt"] = now_ms
        elif phase != "idle":
            self._login_runtime["completedAt"] = now_ms
        self._sync_manual_login_links_locked()

    def _set_runtime_failure(self, message):
        with self._lock:
            self._login_runtime["active"] = False
            self._login_runtime["phase"] = "failed"
            normalized = self._normalize_runtime_message(message)
            self._login_runtime["message"] = normalized
            self._login_runtime["error"] = normalized
            self._login_runtime["completedAt"] = int(time.time() * 1000)

    def _mark_qr_ready(self, qr_path):
        runtime = self._login_runtime
        runtime["phase"] = "qr_ready"
        runtime["qrPath"] = qr_path
        runtime["qrVersion"] = int(runtime.get("qrVersion") or 0) + 1
        runtime["qrUpdatedAt"] = int(time.time() * 1000)
        runtime["message"] = "请使用抖音 App 扫码，并在手机上确认即梦授权"
        runtime["error"] = ""

    def _mark_login_success(self, reused=False):
        runtime = self._login_runtime
        runtime["phase"] = "reused" if reused else "success"
        runtime["message"] = (
            "当前即梦登录态仍然有效"
            if reused
            else "即梦已登录成功"
        )
        runtime["error"] = ""

    def _finalize_login_runtime(self, returncode):
        with self._lock:
            runtime = self._login_runtime
            runtime["active"] = False
            runtime["completedAt"] = int(time.time() * 1000)
            runtime["exitCode"] = returncode
            phase = runtime.get("phase") or "idle"
            if phase in ("success", "reused"):
                self._credit_cache = None
                return
            if returncode == 0:
                runtime["phase"] = "done"
                runtime["message"] = runtime.get("message") or "即梦登录流程已完成"
                runtime["error"] = runtime.get("error") or ""
                return
            runtime["phase"] = "failed"
            runtime["error"] = self._normalize_runtime_message(
                runtime.get("error")
                or self._extract_error_from_tail(runtime.get("outputTail") or [])
            )
            runtime["message"] = runtime["error"] or "即梦登录失败，请重试"

    def _monitor_login_process(self, proc):
        try:
            while True:
                line = proc.stdout.readline() if proc.stdout else ""
                if not line:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.05)
                    continue
                clean_line = str(line).rstrip("\r\n")
                with self._lock:
                    self._append_runtime_output(clean_line)
                    if self._QR_READY_MARKER in clean_line:
                        qr_path = clean_line.split(self._QR_READY_MARKER, 1)[1].strip()
                        if qr_path:
                            self._mark_qr_ready(qr_path)
                    elif self._LOGIN_SUCCESS_MARKER in clean_line:
                        self._mark_login_success(reused=False)
                    elif self._LOGIN_REUSED_MARKER in clean_line:
                        self._mark_login_success(reused=True)
                    elif "verification_uri:" in clean_line:
                        url = self._normalize_manual_url_candidate(
                            clean_line.split("verification_uri:", 1)[1].strip()
                        )
                        if url:
                            self._login_runtime["phase"] = "qr_ready"
                            self._login_runtime["verificationUrl"] = url
                            self._login_runtime["authorizeUrl"] = url
                            self._login_runtime["manualLoginAvailable"] = True
                            self._login_runtime["message"] = "请在浏览器中打开即梦登录链接完成授权"
                            self._login_runtime["error"] = ""
                    elif "user_code:" in clean_line:
                        code = clean_line.split("user_code:", 1)[1].strip()
                        self._login_runtime["userCode"] = code
                        self._login_runtime["phase"] = "qr_ready"
                        self._login_runtime["message"] = f"请在浏览器中完成即梦授权，验证码：{code}"
                        self._login_runtime["error"] = ""
                    elif self._login_runtime.get("phase") in ("preparing", "starting"):
                        self._login_runtime["message"] = (
                            "即梦网页登录已启动，正在等待授权链接"
                            if self._login_runtime.get("loginMode") == "web"
                            else "即梦登录已启动，正在等待二维码"
                        )
                        self._login_runtime["phase"] = "starting"
        finally:
            try:
                returncode = proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self._terminate_login_process(proc)
                try:
                    returncode = proc.wait(timeout=3)
                except Exception:
                    returncode = -1
            self._finalize_login_runtime(returncode)
            with self._lock:
                if self._active_login_proc is proc:
                    self._active_login_proc = None

    def _mark_login_timeout(self, timeout_sec):
        timeout_sec = max(30, int(timeout_sec or 0))
        timeout_message = f"等待登录超时（{timeout_sec} 秒）"
        with self._lock:
            if not self._login_runtime.get("active"):
                return
            phase = str(self._login_runtime.get("phase") or "")
            if phase in ("success", "reused"):
                return
            self._append_runtime_output(timeout_message)
            self._login_runtime["phase"] = "failed"
            self._login_runtime["error"] = timeout_message
            self._login_runtime["message"] = "扫码登录超时，正在结束本次登录流程..."

    def _terminate_login_process(self, proc):
        if proc is None:
            return
        pid = int(getattr(proc, "pid", 0) or 0)
        terminated = False
        if os.name == "nt" and pid > 0:
            terminated = self._terminate_process_tree(pid)
        if terminated:
            return
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=2)
            return
        except Exception:
            pass
        try:
            proc.kill()
        except Exception:
            pass

    def _download_file(self, url, target_path):
        with urllib.request.urlopen(url, timeout=90) as response:
            with open(target_path, "wb") as target:
                shutil.copyfileobj(response, target)

    def _list_windows_dreamina_processes(self):
        if os.name != "nt":
            return []
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        script = (
            "$items = @(Get-CimInstance Win32_Process -Filter \"Name = 'dreamina.exe'\" "
            "| Select-Object ProcessId, CommandLine);"
            "$items | ConvertTo-Json -Compress"
        )
        try:
            proc = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                env=self._create_subprocess_env(),
                creationflags=creation_flags,
            )
        except Exception:
            return []
        if proc.returncode != 0:
            return []
        raw = str(proc.stdout or "").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except Exception:
            return []
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    def _is_headless_login_command(self, command_line):
        normalized = f" {str(command_line or '').replace(chr(34), '').lower()} "
        if "--headless" not in normalized:
            return False
        return " login " in normalized or " relogin " in normalized

    def _terminate_process_tree(self, pid):
        if os.name != "nt":
            return False
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.run(
                ["taskkill", "/PID", str(int(pid)), "/T", "/F"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                env=self._create_subprocess_env(),
                creationflags=creation_flags,
            )
            return proc.returncode == 0
        except Exception:
            return False

    def _cleanup_stale_login_processes(self):
        cleaned = 0
        for item in self._list_windows_dreamina_processes():
            pid = int(item.get("ProcessId") or 0)
            if pid <= 0:
                continue
            if not self._is_headless_login_command(item.get("CommandLine")):
                continue
            if self._terminate_process_tree(pid):
                cleaned += 1
        if cleaned:
            time.sleep(0.4)
        return cleaned

    def _ensure_managed_cli(self):
        if os.name != "nt":
            raise RuntimeError("当前版本仅支持在 Windows 自动准备即梦组件")

        target_path = self._managed_command_path
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        if os.path.isfile(target_path):
            probe = self._run_command(["version"], timeout=15, command_path=target_path)
            if probe.get("ok"):
                return target_path

        fd, temp_path = tempfile.mkstemp(
            prefix="dreamina-",
            suffix=".exe",
            dir=os.path.dirname(target_path),
        )
        os.close(fd)
        try:
            self._download_file(self._WINDOWS_BINARY_URL, temp_path)
            os.replace(temp_path, target_path)
            try:
                os.chmod(target_path, 0o755)
            except Exception:
                pass

            probe = self._run_command(["version"], timeout=15, command_path=target_path)
            if not probe.get("ok"):
                raise RuntimeError("即梦组件校验失败")
            return target_path
        except Exception as exc:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass
            raise RuntimeError("即梦组件准备失败，请检查网络后重试") from exc

    def _ensure_command_path(self):
        command_path = self._resolve_command_path()
        if command_path:
            return command_path
        return self._ensure_managed_cli()

    def _extract_json_candidates(self, text):
        raw = str(text or "")
        raw = self._ANSI_ESCAPE_RE.sub("", raw)
        candidates = []
        decoder = json.JSONDecoder()
        lines = raw.splitlines()

        def push(candidate):
            s = str(candidate or "").strip()
            if s and s not in candidates:
                candidates.append(s)

        for line in raw.splitlines():
            s = line.strip()
            if s.startswith("{") and s.endswith("}"):
                push(s)
        whole = raw.strip()
        if whole.startswith("{") and whole.endswith("}"):
            push(whole)
        # 优先按“从某一行开始是 JSON 对象”去提取，兼容前面带日志噪音的输出
        for idx, line in enumerate(lines):
            if not line.lstrip().startswith("{"):
                continue
            block = "\n".join(lines[idx:]).strip()
            if not block.startswith("{"):
                continue
            try:
                obj, end = decoder.raw_decode(block)
                if isinstance(obj, dict):
                    push(block[:end])
            except Exception:
                continue
        if "{\n" in raw or "\n}" in raw:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                push(raw[start : end + 1])
        # 最后再做字符级扫描兜底（某些日志会在 JSON 前拼接额外内容）
        for m in re.finditer(r"\{", raw):
            block = raw[m.start() :].lstrip()
            if not block.startswith("{"):
                continue
            try:
                obj, end = decoder.raw_decode(block)
                if isinstance(obj, dict):
                    push(block[:end])
            except Exception:
                continue
        return candidates

    def _parse_json_from_output(self, output):
        for candidate in reversed(self._extract_json_candidates(output)):
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except Exception:
                continue
        return {}

    def _parse_json_value_from_output(self, output):
        raw = str(output or "")
        raw = self._ANSI_ESCAPE_RE.sub("", raw)
        candidates = []
        decoder = json.JSONDecoder()
        lines = raw.splitlines()

        def push(candidate):
            s = str(candidate or "").strip()
            if s and s not in candidates:
                candidates.append(s)

        for line in lines:
            s = line.strip()
            if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
                push(s)
        whole = raw.strip()
        if whole and whole[0] in "[{" and whole[-1] in "]}":
            push(whole)
        for idx, line in enumerate(lines):
            stripped = line.lstrip()
            if not stripped.startswith("{") and not stripped.startswith("["):
                continue
            block = "\n".join(lines[idx:]).strip()
            if not block or block[0] not in "[{":
                continue
            try:
                _, end = decoder.raw_decode(block)
                push(block[:end])
            except Exception:
                continue
        for m in re.finditer(r"[\{\[]", raw):
            block = raw[m.start() :].lstrip()
            if not block or block[0] not in "[{":
                continue
            try:
                _, end = decoder.raw_decode(block)
                push(block[:end])
            except Exception:
                continue
        for candidate in reversed(candidates):
            try:
                data = json.loads(candidate)
                if isinstance(data, (dict, list)):
                    return data
            except Exception:
                continue
        return {}

    def _normalize_gen_status(self, value):
        s = str(value or "").strip().lower()
        if s in ("querying", "running", "pending", "processing", "queued"):
            return "querying"
        if s in ("success", "succeeded", "completed", "done"):
            return "success"
        if s in ("fail", "failed", "error"):
            return "failed"
        return s or "unknown"

    def _to_status_phase(self, gen_status, outputs):
        s = self._normalize_gen_status(gen_status)
        if s in ("querying", "running", "pending", "processing", "queued"):
            return "pending"
        if s == "success" or outputs:
            return "success"
        if s in ("fail", "failed", "error"):
            return "failed"
        return "pending"

    def _is_transient_query_error(self, output):
        text = str(output or "").strip().lower()
        if not text:
            return False
        hints = (
            "timeout",
            "time out",
            "timed out",
            "超时",
            "网络",
            "network",
            "connect",
            "connection",
            "socket",
            "econn",
            "enotfound",
            "eai_again",
            "temporary",
            "temporarily",
            "暂时",
            "稍后",
            "busy",
            "service unavailable",
            "rate limit",
            "too many requests",
            "429",
            "500",
            "502",
            "503",
            "504",
        )
        return any(hint in text for hint in hints)

    def _is_video_task_type(self, task_type):
        normalized = str(task_type or "").strip().lower()
        return "video" in normalized

    def _is_http_url(self, value):
        try:
            parsed = urllib.parse.urlparse(str(value or "").strip())
            return parsed.scheme in ("http", "https")
        except Exception:
            return False

    def _resolve_local_media_path(self, value):
        raw = str(value or "").strip()
        if not raw:
            return ""
        if os.path.isabs(raw) and os.path.isfile(raw):
            return os.path.abspath(raw)
        candidate_list = []
        normalized = raw.replace("\\", "/")
        if normalized.startswith("/"):
            candidate_list.append(os.path.join(self._workspace_dir, normalized.lstrip("/")))
        candidate_list.append(os.path.join(self._workspace_dir, normalized.lstrip("/")))
        candidate_list.append(os.path.join(self._workspace_dir, raw))
        candidate_list.append(os.path.join(self._user_dir, raw))
        for path in candidate_list:
            full = os.path.abspath(path)
            if os.path.isfile(full):
                return full
        return ""

    def _download_remote_media(self, url, temp_dir):
        parsed = urllib.parse.urlparse(str(url or "").strip())
        ext = os.path.splitext(parsed.path or "")[1]
        if not ext:
            ext = ".bin"
        fd, temp_path = tempfile.mkstemp(prefix="dreamina-input-", suffix=ext, dir=temp_dir)
        os.close(fd)
        req = urllib.request.Request(
            str(url).strip(),
            headers={"User-Agent": "Mozilla/5.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            with open(temp_path, "wb") as out:
                shutil.copyfileobj(resp, out)
        return temp_path

    def _normalize_media_inputs(self, values, temp_dir, *, required=False, max_count=None):
        items = values
        if isinstance(items, str):
            items = [items]
        if not isinstance(items, list):
            items = []
        resolved = []
        for value in items:
            raw = str(value or "").strip()
            if not raw:
                continue
            if self._is_http_url(raw):
                try:
                    resolved.append(self._download_remote_media(raw, temp_dir))
                except Exception as exc:
                    raise ValueError(f"下载输入素材失败: {raw}") from exc
                continue
            local_path = self._resolve_local_media_path(raw)
            if local_path:
                resolved.append(local_path)
                continue
            raise ValueError(f"输入素材不存在: {raw}")
        if max_count is not None and len(resolved) > int(max_count):
            raise ValueError(f"输入素材数量不能超过 {int(max_count)} 张")
        if required and not resolved:
            raise ValueError("缺少必填输入素材")
        return resolved

    def _extract_submit_id(self, data):
        if not isinstance(data, dict):
            return ""
        for key in ("submit_id", "submitId"):
            value = str(data.get(key) or "").strip()
            if value:
                return value
        nested = data.get("data")
        if isinstance(nested, dict):
            for key in ("submit_id", "submitId"):
                value = str(nested.get(key) or "").strip()
                if value:
                    return value
        return ""

    def _extract_fail_reason(self, data):
        if not isinstance(data, dict):
            return ""
        for key in ("fail_reason", "failReason", "error", "message"):
            value = str(data.get(key) or "").strip()
            if value:
                return value
        nested = data.get("data")
        if isinstance(nested, dict):
            for key in ("fail_reason", "failReason", "error", "message"):
                value = str(nested.get(key) or "").strip()
                if value:
                    return value
        return ""

    def _is_terminal_query_fail_reason(self, text):
        reason = str(text or "").strip().lower()
        if not reason:
            return False
        if self._is_transient_query_error(reason):
            return False
        hints = (
            "违规",
            "敏感",
            "审核未通过",
            "内容安全",
            "安全审核",
            "风控",
            "拦截",
            "sensitive",
            "flagged",
            "violation",
            "content filter",
            "content safety",
            "review failed",
        )
        return any(hint in reason for hint in hints)

    def _relative_output_path(self, abs_path):
        full = os.path.abspath(abs_path)
        root = os.path.abspath(self._workspace_dir)
        if full.startswith(root + os.sep):
            return full[len(root) + 1 :].replace("\\", "/")
        return full.replace("\\", "/")

    def _build_download_dir(self, task_type, submit_id):
        safe_task_type = re.sub(r"[^a-z0-9_-]+", "", str(task_type or "").lower()) or "unknown"
        safe_submit_id = re.sub(r"[^a-zA-Z0-9_-]+", "", str(submit_id or "").strip()) or "unknown"
        target = os.path.join(
            self._dreamina_download_tmp_root,
            safe_task_type,
            safe_submit_id,
        )
        os.makedirs(target, exist_ok=True)
        return os.path.abspath(target)

    def _next_flat_output_path(self, output_dir, base_name, ext):
        target_dir = os.path.abspath(output_dir)
        os.makedirs(target_dir, exist_ok=True)
        safe_base = str(base_name or "").strip() or "即梦文件"
        safe_ext = str(ext or "").strip()
        if safe_ext and not safe_ext.startswith("."):
            safe_ext = f".{safe_ext}"
        index = 0
        while True:
            candidate = os.path.join(target_dir, f"{safe_base}_{index:04d}{safe_ext}")
            if not os.path.exists(candidate):
                return candidate
            index += 1

    def _flatten_local_output_path(self, local_path, task_type):
        rel = str(local_path or "").strip()
        if not rel:
            return rel
        abs_path = rel
        if not os.path.isabs(abs_path):
            abs_path = os.path.join(self._workspace_dir, rel)
        abs_path = os.path.abspath(abs_path)
        if not os.path.isfile(abs_path):
            return rel.replace("\\", "/")

        output_dir = os.path.abspath(self._dreamina_video_output_dir)
        os.makedirs(output_dir, exist_ok=True)
        current_dir = os.path.abspath(os.path.dirname(abs_path))
        if current_dir == output_dir:
            return self._relative_output_path(abs_path)

        ext = os.path.splitext(abs_path)[1] or ""
        normalized_task = str(task_type or "").lower()
        if "video" in normalized_task:
            base_name = "dreamina_video"
        elif "image" in normalized_task:
            base_name = "dreamina_image"
        else:
            base_name = "dreamina_file"
        target_path = self._next_flat_output_path(output_dir, base_name, ext)
        shutil.move(abs_path, target_path)
        return self._relative_output_path(target_path)

    def _cleanup_empty_parents(self, path, stop_dir):
        current = os.path.abspath(str(path or ""))
        boundary = os.path.abspath(str(stop_dir or ""))
        while current and current.startswith(boundary + os.sep):
            try:
                os.rmdir(current)
            except Exception:
                break
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent

    def _register_submit_task(self, submit_id, task_type):
        if not submit_id:
            return
        with self._lock:
            self._task_registry[str(submit_id)] = {
                "taskType": str(task_type or "").strip(),
                "createdAt": int(time.time() * 1000),
            }
            self._query_counts.setdefault(str(submit_id), 0)

    def _get_registered_task_type(self, submit_id):
        with self._lock:
            item = self._task_registry.get(str(submit_id))
            if isinstance(item, dict):
                return str(item.get("taskType") or "").strip()
        return ""

    def _mark_query_called(self, submit_id):
        with self._lock:
            key = str(submit_id or "")
            count = int(self._query_counts.get(key) or 0)
            self._query_counts[key] = count + 1
            return count == 0

    def _query_task_list_entry(self, submit_id, command_path=""):
        sid = str(submit_id or "").strip()
        if not sid:
            return {}
        result = self._run_command(
            ["list_task", "--submit_id", sid, "--limit", "5"],
            timeout=20,
            command_path=command_path,
        )
        output_text = str(result.get("output") or "").strip()
        data = {}
        if output_text.startswith("[") and output_text.endswith("]"):
            try:
                data = json.loads(output_text)
            except Exception:
                data = {}
        if not isinstance(data, list):
            data = self._parse_json_value_from_output(output_text)
        if not isinstance(data, list):
            return {}
        for item in data:
            if not isinstance(item, dict):
                continue
            item_submit_id = str(
                item.get("submit_id") or item.get("submitId") or ""
            ).strip()
            if item_submit_id == sid:
                return item
        return {}

    def _resolve_video_query_fallback(self, submit_id, task_type, command_path=""):
        normalized_task_type = str(task_type or "").strip().lower()
        if (
            normalized_task_type
            and normalized_task_type != "unknown"
            and not self._is_video_task_type(task_type)
        ):
            return None
        try:
            entry = self._query_task_list_entry(submit_id, command_path=command_path)
        except Exception:
            return None
        if not entry:
            return None
        list_status = self._normalize_gen_status(
            entry.get("gen_status") or entry.get("genStatus")
        )
        fail_reason = self._extract_fail_reason(entry)
        raw = {"listTask": entry}
        if (
            (list_status == "failed" and fail_reason)
            or self._is_terminal_query_fail_reason(fail_reason)
        ):
            return {
                "status": "failed",
                "failReason": fail_reason,
                "raw": raw,
            }
        if list_status in ("querying", "success", "unknown"):
            return {
                "status": "pending",
                "failReason": "",
                "raw": raw,
            }
        return {
            "status": "pending",
            "failReason": "",
            "raw": raw,
        }

    def _build_query_fallback_response(
        self,
        submit_id,
        download_dir_rel,
        fallback,
        *,
        raw_extra=None,
    ):
        raw = {}
        if raw_extra and isinstance(raw_extra, dict):
            raw.update(raw_extra)
        if fallback and isinstance(fallback.get("raw"), dict):
            raw.update(fallback.get("raw") or {})
        response = {
            "submitId": str(submit_id or "").strip(),
            "status": fallback.get("status") or "pending",
            "outputs": [],
            "downloadDir": download_dir_rel,
            "raw": raw,
        }
        fail_reason = str(fallback.get("failReason") or "").strip()
        if fail_reason:
            response["failReason"] = fail_reason
        return response

    def _extract_outputs(self, data, download_dir_abs=""):
        outputs = []
        if not isinstance(data, dict):
            return outputs
        seen = set()

        def push(url_value="", local_path_value="", mime_type_value=""):
            url = str(url_value or "").strip()
            local_path = str(local_path_value or "").strip()
            mime_type = str(mime_type_value or "").strip()
            if not url and not local_path:
                return
            if local_path and os.path.isabs(local_path):
                local_path = self._relative_output_path(local_path)
            key = f"{url}|{local_path}"
            if key in seen:
                return
            seen.add(key)
            item = {}
            if url:
                item["url"] = url
            if local_path:
                item["localPath"] = local_path.replace("\\", "/")
                if not mime_type:
                    mime_type = mimetypes.guess_type(local_path)[0] or ""
            if mime_type:
                item["mimeType"] = mime_type
            outputs.append(item)

        if download_dir_abs and os.path.isdir(download_dir_abs):
            for root, _, files in os.walk(download_dir_abs):
                for name in sorted(files):
                    full = os.path.join(root, name)
                    if os.path.isfile(full):
                        push(local_path_value=full)

        buckets = []
        for key in ("results", "result", "data", "output", "outputs"):
            value = data.get(key)
            if isinstance(value, list):
                buckets.extend(value)
            elif isinstance(value, dict):
                buckets.append(value)

        for item in buckets:
            if isinstance(item, str):
                if item.startswith("http://") or item.startswith("https://"):
                    push(url_value=item)
                continue
            if not isinstance(item, dict):
                continue
            push(
                url_value=(
                    item.get("url")
                    or item.get("image_url")
                    or item.get("imageUrl")
                    or item.get("video_url")
                    or item.get("videoUrl")
                ),
                local_path_value=(
                    item.get("local_path")
                    or item.get("localPath")
                    or item.get("path")
                ),
                mime_type_value=item.get("mimeType") or item.get("mime_type"),
            )
        return outputs

    def _submit_generation_task(self, task_type, subcommand, payload, args_builder):
        if not isinstance(payload, dict):
            raise ValueError("请求体必须是 JSON 对象")
        command_path = self._ensure_command_path()
        temp_dir = tempfile.mkdtemp(prefix="dreamina-submit-", dir=self._user_dir)
        try:
            args = [subcommand]
            args.extend(args_builder(dict(payload), temp_dir))
            args.extend(["--poll", "0"])
            result = self._run_command(args, timeout=45, command_path=command_path)
            data = self._parse_json_from_output(result.get("output") or "")
            submit_id = self._extract_submit_id(data)
            gen_status = self._normalize_gen_status(
                data.get("gen_status")
                or data.get("genStatus")
                or ("success" if result.get("ok") else "failed")
            )
            fail_reason = self._extract_fail_reason(data) or str(result.get("output") or "").strip()
            if (not result.get("ok")) or gen_status in ("failed", "fail", "error"):
                raise RuntimeError(fail_reason or "即梦提交失败")
            if not submit_id:
                raise RuntimeError(fail_reason or "即梦提交失败，未返回 submitId")
            self._register_submit_task(submit_id, task_type)
            response = {
                "submitId": submit_id,
                "genStatus": "success" if gen_status == "success" else "querying",
            }
            if fail_reason and gen_status in ("failed", "fail", "error"):
                response["message"] = fail_reason
            return response
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def submit_text2image(self, payload):
        def build_args(data, temp_dir):
            prompt = str(data.get("prompt") or "").strip()
            if not prompt:
                raise ValueError("prompt 为必填项")
            args = ["--prompt", prompt]
            ratio = str(data.get("ratio") or "").strip()
            if ratio:
                args.extend(["--ratio", ratio])
            resolution_type = str(data.get("resolutionType") or "").strip()
            if resolution_type:
                args.extend(["--resolution_type", resolution_type])
            model_version = str(data.get("modelVersion") or "").strip()
            if model_version:
                args.extend(["--model_version", model_version])
            return args

        return self._submit_generation_task("text2image", "text2image", payload, build_args)

    def submit_image2image(self, payload):
        def build_args(data, temp_dir):
            prompt = str(data.get("prompt") or "").strip()
            if not prompt:
                raise ValueError("prompt 为必填项")
            images = self._normalize_media_inputs(
                data.get("images"),
                temp_dir,
                required=True,
                max_count=10,
            )
            args = ["--prompt", prompt, "--images", ",".join(images)]
            ratio = str(data.get("ratio") or "").strip()
            if ratio:
                args.extend(["--ratio", ratio])
            resolution_type = str(data.get("resolutionType") or "").strip()
            if resolution_type:
                args.extend(["--resolution_type", resolution_type])
            model_version = str(data.get("modelVersion") or "").strip()
            if model_version:
                args.extend(["--model_version", model_version])
            return args

        return self._submit_generation_task("image2image", "image2image", payload, build_args)

    def _append_video_submit_common_args(self, args, data, *, allow_ratio=False, allow_model_version=True):
        duration = data.get("duration")
        if duration is not None and str(duration).strip():
            args.extend(["--duration", str(duration)])
        if allow_ratio:
            ratio = str(data.get("ratio") or "").strip()
            if ratio:
                args.extend(["--ratio", ratio])
        video_resolution = str(data.get("videoResolution") or "").strip()
        if video_resolution:
            args.extend(["--video_resolution", video_resolution])
        if allow_model_version:
            model_version = str(data.get("modelVersion") or "").strip()
            if model_version:
                args.extend(["--model_version", model_version])
        return args

    def submit_text2video(self, payload):
        def build_args(data, temp_dir):
            prompt = str(data.get("prompt") or "").strip()
            if not prompt:
                raise ValueError("prompt 为必填项")
            args = ["--prompt", prompt]
            return self._append_video_submit_common_args(
                args,
                data,
                allow_ratio=True,
                allow_model_version=True,
            )

        return self._submit_generation_task("text2video", "text2video", payload, build_args)

    def submit_image2video(self, payload):
        def build_args(data, temp_dir):
            prompt = str(data.get("prompt") or "").strip()
            if not prompt:
                raise ValueError("prompt 为必填项")
            image_path = self._normalize_media_inputs(
                [data.get("image")],
                temp_dir,
                required=True,
                max_count=1,
            )[0]
            args = [
                "--image",
                image_path,
                "--prompt",
                prompt,
            ]
            return self._append_video_submit_common_args(
                args,
                data,
                allow_ratio=False,
                allow_model_version=True,
            )

        return self._submit_generation_task("image2video", "image2video", payload, build_args)

    def submit_frames2video(self, payload):
        def build_args(data, temp_dir):
            prompt = str(data.get("prompt") or "").strip()
            if not prompt:
                raise ValueError("prompt 为必填项")
            first_path = self._normalize_media_inputs(
                [data.get("first")],
                temp_dir,
                required=True,
                max_count=1,
            )[0]
            last_path = self._normalize_media_inputs(
                [data.get("last")],
                temp_dir,
                required=True,
                max_count=1,
            )[0]
            args = [
                "--first",
                first_path,
                "--last",
                last_path,
                "--prompt",
                prompt,
            ]
            return self._append_video_submit_common_args(
                args,
                data,
                allow_ratio=False,
                allow_model_version=True,
            )

        return self._submit_generation_task("frames2video", "frames2video", payload, build_args)

    def submit_multiframe2video(self, payload):
        def build_args(data, temp_dir):
            images = self._normalize_media_inputs(
                data.get("images"),
                temp_dir,
                required=True,
                max_count=20,
            )
            if len(images) < 2:
                raise ValueError("多帧叙事至少需要 2 张图片")
            args = ["--images", ",".join(images)]
            if len(images) == 2:
                prompt = str(data.get("prompt") or "").strip()
                if not prompt:
                    raise ValueError("两张图的多帧叙事需要 prompt")
                args.extend(["--prompt", prompt])
                duration = data.get("duration")
                if duration is not None and str(duration).strip():
                    args.extend(["--duration", str(duration)])
                return args

            prompts = data.get("transitionPrompts")
            durations = data.get("transitionDurations")
            if not isinstance(prompts, list):
                prompts = []
            if not isinstance(durations, list):
                durations = []
            expected_count = len(images) - 1
            if len(prompts) < expected_count:
                raise ValueError("transitionPrompts 数量不足")
            for index in range(expected_count):
                prompt = str(prompts[index] or "").strip()
                if not prompt:
                    raise ValueError("transitionPrompts 不能为空")
                args.extend(["--transition-prompt", prompt])
            for index in range(min(len(durations), expected_count)):
                duration_value = str(durations[index] or "").strip()
                if duration_value:
                    args.extend(["--transition-duration", duration_value])
            return args

        return self._submit_generation_task("multiframe2video", "multiframe2video", payload, build_args)

    def submit_multimodal2video(self, payload):
        def build_args(data, temp_dir):
            images = self._normalize_media_inputs(
                data.get("images"),
                temp_dir,
                required=False,
                max_count=9,
            )
            videos = self._normalize_media_inputs(
                data.get("videos"),
                temp_dir,
                required=False,
                max_count=3,
            )
            audios = self._normalize_media_inputs(
                data.get("audios"),
                temp_dir,
                required=False,
                max_count=3,
            )
            if not images and not videos:
                raise ValueError("全能参考至少需要 1 个图片或视频参考")
            args = []
            for image_path in images:
                args.extend(["--image", image_path])
            for video_path in videos:
                args.extend(["--video", video_path])
            for audio_path in audios:
                args.extend(["--audio", audio_path])
            prompt = str(data.get("prompt") or "").strip()
            if prompt:
                args.extend(["--prompt", prompt])
            return self._append_video_submit_common_args(
                args,
                data,
                allow_ratio=True,
                allow_model_version=True,
            )

        return self._submit_generation_task("multimodal2video", "multimodal2video", payload, build_args)

    def query_result(self, submit_id, auto_download=True):
        sid = str(submit_id or "").strip()
        if not sid:
            raise ValueError("submitId 为必填项")

        command_path = self._ensure_command_path()
        task_type = self._get_registered_task_type(sid) or "unknown"
        download_dir_abs = self._build_download_dir(task_type, sid)
        download_dir_rel = self._relative_output_path(download_dir_abs)

        first_call = self._mark_query_called(sid)
        should_download = bool(auto_download) and (not first_call)

        args = ["query_result", "--submit_id", sid]
        if should_download:
            args.extend(["--download_dir", download_dir_abs])

        result = self._run_command(args, timeout=40, command_path=command_path)
        output_text = str(result.get("output") or "").strip()
        data = self._parse_json_from_output(output_text)
        if not data and not result.get("ok"):
            fallback = self._resolve_video_query_fallback(
                sid,
                task_type,
                command_path=command_path,
            )
            if fallback and fallback.get("status") == "pending":
                return {
                    "submitId": sid,
                    "status": "pending",
                    "outputs": [],
                    "downloadDir": download_dir_rel,
                    "raw": fallback.get("raw") or {},
                }
            if self._is_transient_query_error(output_text):
                return {
                    "submitId": sid,
                    "status": "pending",
                    "outputs": [],
                    "downloadDir": download_dir_rel,
                    "raw": {},
                }
            if fallback and fallback.get("status") == "failed":
                return {
                    "submitId": sid,
                    "status": "failed",
                    "outputs": [],
                    "failReason": fallback.get("failReason") or output_text or "查询失败",
                    "downloadDir": download_dir_rel,
                    "raw": fallback.get("raw") or {},
                }
            return {
                "submitId": sid,
                "status": "failed",
                "outputs": [],
                "failReason": output_text or "查询失败",
                "downloadDir": download_dir_rel,
                "raw": {},
            }

        submit_from_result = self._extract_submit_id(data) or sid
        gen_status = (
            data.get("gen_status")
            or data.get("genStatus")
            or ("success" if result.get("ok") else "failed")
        )
        outputs = self._extract_outputs(data, download_dir_abs if should_download else "")
        if should_download and outputs:
            for item in outputs:
                if not isinstance(item, dict):
                    continue
                local_path = item.get("localPath")
                if not local_path:
                    continue
                item["localPath"] = self._flatten_local_output_path(local_path, task_type)
            self._cleanup_empty_parents(download_dir_abs, self._dreamina_download_tmp_root)
        status = self._to_status_phase(gen_status, outputs)
        fail_reason = self._extract_fail_reason(data)
        if status != "failed" and self._is_terminal_query_fail_reason(fail_reason):
            status = "failed"
        fallback = None
        if not outputs and status in ("pending", "success"):
            fallback = self._resolve_video_query_fallback(
                sid,
                task_type,
                command_path=command_path,
            )
            if fallback and fallback.get("status") == "failed":
                return self._build_query_fallback_response(
                    submit_from_result,
                    download_dir_rel,
                    fallback,
                    raw_extra={
                        "queryResult": data if isinstance(data, dict) else {},
                    },
                )
        if status == "failed" and not fail_reason:
            fail_reason = output_text
        if status == "failed":
            if fallback is None:
                fallback = self._resolve_video_query_fallback(
                    sid,
                    task_type,
                    command_path=command_path,
                )
            explicit_terminal_failure = bool(fail_reason) and not self._is_transient_query_error(
                fail_reason
            )
            if (
                fallback
                and fallback.get("status") == "pending"
                and not explicit_terminal_failure
            ):
                return {
                    "submitId": submit_from_result,
                    "status": "pending",
                    "outputs": [],
                    "downloadDir": download_dir_rel,
                    "raw": {
                        "queryResult": data if isinstance(data, dict) else {},
                        **(fallback.get("raw") or {}),
                    },
                }
            if fallback and fallback.get("status") == "failed" and not fail_reason:
                fail_reason = fallback.get("failReason") or ""
        response = {
            "submitId": submit_from_result,
            "status": status,
            "outputs": outputs,
            "downloadDir": download_dir_rel,
            "raw": data if isinstance(data, dict) else {},
        }
        if fail_reason:
            response["failReason"] = fail_reason
        return response

    def _run_login_sequence(self, force=False, mode="headless"):
        try:
            login_mode = str(mode or "headless").strip().lower() or "headless"
            is_web_mode = login_mode == "web"
            cleaned = self._cleanup_stale_login_processes()
            if cleaned:
                with self._lock:
                    self._login_runtime["phase"] = "preparing"
                    self._login_runtime["message"] = "正在恢复上次未完成的登录流程..."

            command_path = self._resolve_command_path()
            if not command_path:
                with self._lock:
                    self._login_runtime["phase"] = "preparing"
                    self._login_runtime["message"] = "首次使用正在准备即梦组件..."
                command_path = self._ensure_managed_cli()

            with self._lock:
                self._login_runtime["phase"] = "starting"
                self._login_runtime["loginMode"] = login_mode
                self._login_runtime["message"] = (
                    "正在启动即梦网页登录，请在浏览器完成授权..."
                    if is_web_mode
                    else "正在启动即梦扫码登录..."
                )
                self._sync_manual_login_links_locked()

            creation_flags = 0
            if os.name == "nt":
                creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

            login_args = [command_path, "relogin" if force else "login"]
            if not is_web_mode:
                login_args.append("--headless")

            proc = subprocess.Popen(
                login_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=self._create_subprocess_env(),
                cwd=self._user_dir,
                creationflags=creation_flags,
            )
            with self._lock:
                self._active_login_proc = proc
            timeout_marker = threading.Event()
            timeout_sec = int(self._login_timeout_sec or self._DEFAULT_LOGIN_TIMEOUT_SEC)

            def on_timeout():
                if timeout_marker.is_set():
                    return
                self._mark_login_timeout(timeout_sec)
                self._terminate_login_process(proc)

            timeout_timer = threading.Timer(timeout_sec, on_timeout)
            timeout_timer.daemon = True
            timeout_timer.start()
            try:
                self._monitor_login_process(proc)
            finally:
                timeout_marker.set()
                timeout_timer.cancel()
        except Exception as exc:
            self._set_runtime_failure(str(exc) or "即梦登录失败")

    def start_login(self, force=False, mode="headless"):
        login_mode = str(mode or "headless").strip().lower() or "headless"
        if login_mode not in ("headless", "web"):
            raise RuntimeError("当前仅支持网页登录或扫码登录")

        with self._lock:
            if self._login_runtime.get("active"):
                return self._runtime_snapshot()
            self._credit_cache = None
            self._reset_runtime_locked(
                phase="preparing",
                message=(
                    "正在准备即梦网页登录..."
                    if login_mode == "web"
                    else "正在准备即梦扫码登录..."
                ),
                active=True,
            )
            self._login_runtime["loginMode"] = login_mode
            self._sync_manual_login_links_locked()

        worker = threading.Thread(
            target=self._run_login_sequence,
            args=(bool(force), login_mode),
            daemon=True,
            name="DreaminaWebLogin" if login_mode == "web" else "DreaminaHeadlessLogin",
        )
        worker.start()
        return self.get_login_runtime()

    def logout(self):
        with self._lock:
            if self._login_runtime.get("active"):
                raise RuntimeError("请先完成当前登录流程，再退出登录")

        command_path = self._resolve_command_path()
        if command_path:
            result = self._run_command(["logout"], timeout=20, command_path=command_path)
            if not result.get("ok"):
                output = str(result.get("output") or "").strip()
                if output and "未检测到有效登录态" not in output:
                    raise RuntimeError(
                        self._extract_error_from_tail(output.splitlines()) or "退出登录失败，请重试"
                    )

        with self._lock:
            self._credit_cache = {
                "checkedAt": time.time(),
                "loggedIn": False,
                "credit": None,
                "message": "已退出登录",
            }
            self._reset_runtime_locked(
                phase="done",
                message="已退出登录",
                active=False,
            )
        return self.get_status(force_refresh=False)

    def get_status(self, force_refresh=False):
        settings = self._load_settings()
        command_path = self._resolve_command_path()
        installed = bool(command_path)

        with self._lock:
            runtime_snapshot = self._runtime_snapshot()
            cache = dict(self._credit_cache) if isinstance(self._credit_cache, dict) else None

        status = {
            "installed": installed,
            "loginMode": settings.get("loginMode") or "headless",
            "loggedIn": False,
            "credit": None,
            "message": "首次登录时会自动准备即梦组件",
            "runtime": runtime_snapshot,
        }

        if runtime_snapshot.get("active"):
            status["loggedIn"] = bool(cache.get("loggedIn")) if cache else False
            status["credit"] = cache.get("credit") if cache else None
            status["message"] = runtime_snapshot.get("message") or status["message"]
            return status

        if not installed:
            if cache and cache.get("message"):
                status["message"] = cache.get("message") or status["message"]
            return status

        now = time.time()
        if cache and not force_refresh and now - float(cache.get("checkedAt") or 0) < 8:
            status["loggedIn"] = bool(cache.get("loggedIn"))
            status["credit"] = cache.get("credit")
            status["message"] = cache.get("message") or "未登录，点击登录即可使用"
            return status

        result = self._run_command(["user_credit"], timeout=30, command_path=command_path)
        message = "未登录，点击登录即可使用"
        logged_in = False
        credit = None
        if result.get("ok"):
            try:
                credit = json.loads(result.get("output") or "{}")
            except Exception:
                credit = None
            logged_in = isinstance(credit, dict)
            message = "即梦已登录" if logged_in else "即梦状态暂不可用"
        else:
            output = str(result.get("output") or "").strip()
            if (not output) or ("未检测到有效登录态" in output):
                message = "未登录，点击登录即可使用"
            else:
                message = self._extract_error_from_tail(output.splitlines()) or "读取即梦状态失败"

        with self._lock:
            self._credit_cache = {
                "checkedAt": now,
                "loggedIn": logged_in,
                "credit": credit,
                "message": message,
            }

        status["loggedIn"] = logged_in
        status["credit"] = credit
        status["message"] = runtime_snapshot.get("message") or message
        return status

    def get_login_runtime(self):
        with self._lock:
            return self._runtime_snapshot()

    def get_qr_png(self):
        with self._lock:
            qr_path = str(self._login_runtime.get("qrPath") or "").strip()
        if not qr_path or not os.path.isfile(qr_path):
            return None
        try:
            with open(qr_path, "rb") as f:
                return f.read()
        except Exception:
            return None

    def _normalize_login_response_payload(self, login_response):
        if isinstance(login_response, dict):
            if not login_response:
                raise ValueError("登录响应 JSON 不能为空")
            return login_response
        text = str(login_response or "").strip()
        if not text:
            raise ValueError("请先粘贴导入页返回的完整 JSON")
        parsed = {}
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = self._parse_json_from_output(text)
        if not isinstance(parsed, dict) or not parsed:
            raise ValueError("登录响应 JSON 格式无效，请检查后重试")
        return parsed

    def import_login_response(self, login_response):
        payload = self._normalize_login_response_payload(login_response)
        command_path = self._ensure_command_path()
        os.makedirs(self._user_dir, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(
            prefix="dreamina-login-response-",
            suffix=".json",
            dir=self._user_dir,
        )
        os.close(fd)
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            with self._lock:
                self._append_runtime_output("已收到手动登录态 JSON，正在导入...")
                if self._login_runtime.get("active"):
                    self._login_runtime["message"] = "正在导入手动登录态..."
                    self._login_runtime["phase"] = "starting"
                active_proc = self._active_login_proc

            result = self._run_command(
                ["import_login_response", "--file", temp_path],
                timeout=45,
                command_path=command_path,
            )
            output = str(result.get("output") or "").strip()
            output_lines = [self._ANSI_ESCAPE_RE.sub("", str(line or "").strip()) for line in output.splitlines()]
            output_lines = [line for line in output_lines if line]

            with self._lock:
                for line in output_lines[-20:]:
                    self._append_runtime_output(line)
                if result.get("ok"):
                    now_ms = int(time.time() * 1000)
                    self._append_runtime_output("手动登录态导入成功，正在同步登录状态...")
                    self._credit_cache = None
                    self._mark_login_success(reused=False)
                    self._login_runtime["active"] = False
                    self._login_runtime["completedAt"] = now_ms
                    self._login_runtime["exitCode"] = 0
                    self._login_runtime["message"] = "手动登录态已导入，登录状态同步中..."
                else:
                    fail_line = self._extract_error_from_tail(output_lines) or "手动登录态导入失败"
                    self._append_runtime_output(f"手动登录态导入失败：{fail_line}")

            if not result.get("ok"):
                raise RuntimeError(self._extract_error_from_tail(output_lines) or "手动登录态导入失败")

            if active_proc is not None:
                self._terminate_login_process(active_proc)

            return {
                "runtime": self.get_login_runtime(),
                "status": self.get_status(force_refresh=True),
            }
        finally:
            try:
                os.remove(temp_path)
            except Exception:
                pass
