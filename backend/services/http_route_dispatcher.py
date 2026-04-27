import json
import subprocess
import time
import urllib.parse


class HttpRouteDispatcher:
    _TRUE_VALUES = ("1", "true", "yes", "on")

    def __init__(
        self,
        *,
        local_version,
        is_dev_build,
        is_advanced_mode,
        subscription_client_getter,
        subscription_gate_service_getter,
        config_route_service_getter,
        json_file_route_service_getter,
        library_file_route_service_getter,
        media_file_route_service_getter,
        local_media_processing_route_service_getter,
        remote_proxy_route_service_getter,
        dreamina_route_service_getter,
        update_service_getter,
        smart_clip_cleanup,
        smart_clip_jobs,
        smart_clip_lock,
        sub_status_none,
        sub_error_invalid_arguments,
        default_sub_contact_text,
        default_sub_contact_url,
        json_ok,
        json_err,
        send_route_response,
        read_body,
    ):
        self.local_version = str(local_version or "")
        self._is_dev_build = is_dev_build
        self._is_advanced_mode = is_advanced_mode
        self._get_subscription_client = subscription_client_getter
        self._get_subscription_gate_service = subscription_gate_service_getter
        self._get_config_route_service = config_route_service_getter
        self._get_json_file_route_service = json_file_route_service_getter
        self._get_library_file_route_service = library_file_route_service_getter
        self._get_media_file_route_service = media_file_route_service_getter
        self._get_local_media_processing_route_service = local_media_processing_route_service_getter
        self._get_remote_proxy_route_service = remote_proxy_route_service_getter
        self._get_dreamina_route_service = dreamina_route_service_getter
        self._get_update_service = update_service_getter
        self._smart_clip_cleanup = smart_clip_cleanup
        self._smart_clip_jobs = smart_clip_jobs
        self._smart_clip_lock = smart_clip_lock
        self._sub_status_none = str(sub_status_none or "")
        self._sub_error_invalid_arguments = str(sub_error_invalid_arguments or "")
        self._default_sub_contact_text = str(default_sub_contact_text or "")
        self._default_sub_contact_url = str(default_sub_contact_url or "")
        self._json_ok = json_ok
        self._json_err = json_err
        self._send_route_response = send_route_response
        self._read_body = read_body

    @classmethod
    def _parse_query(cls, raw_path, *, max_num_fields):
        parsed = urllib.parse.urlparse(str(raw_path or ""))
        return urllib.parse.parse_qs(
            parsed.query,
            keep_blank_values=True,
            max_num_fields=int(max_num_fields),
        )

    @classmethod
    def _parse_query_flag(cls, query, key, *, default=False):
        raw = (query.get(str(key)) or [None])[0]
        if raw is None:
            return bool(default)
        return str(raw).strip().lower() in cls._TRUE_VALUES

    def _subscription_missing_payload(self, *, message):
        return {
            "success": False,
            "status": self._sub_status_none,
            "errorCode": self._sub_error_invalid_arguments,
            "message": str(message or ""),
            "contactText": self._default_sub_contact_text,
            "contactUrl": self._default_sub_contact_url,
        }

    def _subscription_unavailable_payload(self):
        return {
            "success": False,
            "status": self._sub_status_none,
            "errorCode": "SUBSCRIPTION_SERVICE_UNAVAILABLE",
            "message": "授权服务不可用",
            "contactText": self._default_sub_contact_text,
            "contactUrl": self._default_sub_contact_url,
        }

    def _activation_missing_payload(self):
        return {
            "success": False,
            "errorCode": self._sub_error_invalid_arguments,
            "message": "Missing installId or cdkey",
            "contactText": self._default_sub_contact_text,
            "contactUrl": self._default_sub_contact_url,
        }

    def _runtime_info_payload(self):
        return {
            "success": True,
            "isDevBuild": bool(self._is_dev_build()),
            "isAdvancedMode": bool(self._is_advanced_mode()),
            "localVersion": self.local_version,
        }

    def _handle_subscription_status(self, handler):
        client = self._get_subscription_client()
        gate_service = self._get_subscription_gate_service()
        query = self._parse_query(handler.path, max_num_fields=20)
        install_id_qs = (query.get("installId") or [""])[0]
        install_id = client.normalize_install_id(install_id_qs)
        if not install_id:
            install_id = gate_service.extract_install_id_from_request(handler)
        if not install_id:
            self._json_ok(
                handler,
                self._subscription_missing_payload(message="Missing installId"),
            )
            return True
        payload = client.fetch_subscription_status(install_id)
        if isinstance(payload, dict):
            self._json_ok(handler, payload)
        else:
            self._json_ok(handler, self._subscription_unavailable_payload())
        return True

    def _handle_heartbeat_stream(self, handler):
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.end_headers()
        try:
            while True:
                handler.wfile.write(b"data: ping\n\n")
                handler.wfile.flush()
                time.sleep(5)
        except Exception:
            pass
        return True

    def _handle_update_check(self, handler):
        query = self._parse_query(handler.path, max_num_fields=10)
        info = self._get_update_service().check_for_updates(
            force=self._parse_query_flag(query, "force", default=False),
            include_current=self._parse_query_flag(
                query,
                "includeCurrent",
                default=False,
            ),
        )
        if info:
            self._json_ok(handler, info)
        else:
            self._json_ok(
                handler,
                {
                    "hasUpdate": False,
                    "localVersion": self.local_version,
                },
            )
        return True

    def _handle_update_local_preview(self, handler):
        self._json_ok(handler, self._get_update_service().build_local_update_preview())
        return True

    def _handle_smart_clip_status(self, handler):
        query = self._parse_query(handler.path, max_num_fields=10)
        job_id = (query.get("jobId") or [""])[0].strip()
        if not job_id:
            self._json_err(handler, 400, "Missing jobId")
            return True
        self._smart_clip_cleanup()
        with self._smart_clip_lock:
            job = self._smart_clip_jobs.get(job_id)
        if not job:
            self._json_err(handler, 404, "Job not found")
            return True
        self._json_ok(handler, job)
        return True

    def _handle_subscription_activate(self, handler):
        body = self._read_body(handler)
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._json_err(handler, 400, "Invalid JSON")
            return True
        if not isinstance(data, dict):
            self._json_err(handler, 400, "Invalid JSON")
            return True
        client = self._get_subscription_client()
        gate_service = self._get_subscription_gate_service()
        install_id = gate_service.extract_install_id_from_request(handler, data)
        cdkey = str(data.get("cdkey") or "").strip()
        if not install_id or not cdkey:
            self._json_ok(handler, self._activation_missing_payload())
            return True
        payload = client.activate_cdkey(install_id, cdkey)
        gate_service.clear_vip_allow_cache(install_id)
        if isinstance(payload, dict):
            self._json_ok(handler, payload)
        else:
            self._json_ok(handler, self._subscription_unavailable_payload())
        return True

    def _handle_update_apply(self, handler):
        try:
            self._json_ok(handler, self._get_update_service().apply_hot_update())
        except subprocess.TimeoutExpired:
            self._json_err(handler, 504, "git pull 超时，请检查网络")
        except Exception as exc:
            self._json_err(handler, 500, str(exc))
        return True

    def handle_get(self, handler, path):
        if path == "/api/v2/runtime/info":
            self._json_ok(handler, self._runtime_info_payload())
            return True

        if path == "/api/v2/subscription/status":
            return self._handle_subscription_status(handler)

        config_get_response = self._get_config_route_service().handle_get(
            handler,
            path,
        )
        if config_get_response is not None:
            self._send_route_response(handler, config_get_response)
            return True

        json_file_get_response = self._get_json_file_route_service().handle_get(
            handler,
            path,
        )
        if json_file_get_response is not None:
            self._send_route_response(handler, json_file_get_response)
            return True

        library_file_get_response = self._get_library_file_route_service().handle_get(
            handler,
            path,
        )
        if library_file_get_response is not None:
            self._send_route_response(handler, library_file_get_response)
            return True

        dreamina_get_response = self._get_dreamina_route_service().handle_get(
            handler,
            path,
        )
        if dreamina_get_response is not None:
            self._send_route_response(handler, dreamina_get_response)
            return True

        media_file_get_response = self._get_media_file_route_service().handle_get(
            handler,
            path,
        )
        if media_file_get_response is not None:
            self._send_route_response(handler, media_file_get_response)
            return True

        if path == "/api/v2/heartbeat_stream":
            return self._handle_heartbeat_stream(handler)

        if path == "/api/v2/update/check":
            return self._handle_update_check(handler)

        if path == "/api/v2/update/local-preview":
            return self._handle_update_local_preview(handler)

        if path == "/api/v2/video/smart_clip/status":
            return self._handle_smart_clip_status(handler)

        remote_proxy_get_response = self._get_remote_proxy_route_service().handle_get(
            handler,
            path,
        )
        if remote_proxy_get_response is not None:
            self._send_route_response(handler, remote_proxy_get_response)
            return True

        return False

    def handle_post(self, handler, path):
        if path == "/api/v2/subscription/activate":
            return self._handle_subscription_activate(handler)

        config_post_response = self._get_config_route_service().handle_post(
            handler,
            path,
            self._read_body(handler)
            if path in ("/api/config", "/api/v2/config/custom-ai")
            else b"",
        )
        if config_post_response is not None:
            self._send_route_response(handler, config_post_response)
            return True

        json_file_post_response = self._get_json_file_route_service().handle_post(
            handler,
            path,
            self._read_body(handler)
            if (
                path in (
                    "/api/v2/projects/save",
                    "/api/v2/assets/save",
                    "/api/v2/workflows/save",
                )
                or path.startswith("/api/v2/user/")
            )
            else b"",
        )
        if json_file_post_response is not None:
            self._send_route_response(handler, json_file_post_response)
            return True

        library_file_post_response = self._get_library_file_route_service().handle_post(
            handler,
            path,
            self._read_body(handler)
            if path
            in (
                "/api/v2/assets/thumb/save",
                "/api/v2/workflows/thumb/save",
            )
            else b"",
        )
        if library_file_post_response is not None:
            self._send_route_response(handler, library_file_post_response)
            return True

        dreamina_post_response = self._get_dreamina_route_service().handle_post(
            handler,
            path,
            self._read_body(handler) if path.startswith("/api/v2/dreamina/") else b"",
        )
        if dreamina_post_response is not None:
            self._send_route_response(handler, dreamina_post_response)
            return True

        media_file_post_response = self._get_media_file_route_service().handle_post(
            handler,
            path,
        )
        if media_file_post_response is not None:
            self._send_route_response(handler, media_file_post_response)
            return True

        local_media_post_response = self._get_local_media_processing_route_service().handle_post(
            handler,
            path,
        )
        if local_media_post_response is not None:
            self._send_route_response(handler, local_media_post_response)
            return True

        remote_proxy_post_response = self._get_remote_proxy_route_service().handle_post(
            handler,
            path,
        )
        if remote_proxy_post_response is not None:
            self._send_route_response(handler, remote_proxy_post_response)
            return True

        if path == "/api/v2/update/apply":
            return self._handle_update_apply(handler)

        return False

    def handle_delete(self, handler, path):
        json_file_delete_response = self._get_json_file_route_service().handle_delete(
            handler,
            path,
        )
        if json_file_delete_response is not None:
            self._send_route_response(handler, json_file_delete_response)
            return True
        return False

    def handle_patch(self, handler, path):
        json_file_patch_response = self._get_json_file_route_service().handle_patch(
            handler,
            path,
            self._read_body(handler) if path.startswith("/api/v2/projects/") else b"",
        )
        if json_file_patch_response is not None:
            self._send_route_response(handler, json_file_patch_response)
            return True
        return False
