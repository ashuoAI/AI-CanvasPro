import json
import urllib.parse


class DreaminaRouteService:
    _TRUE_VALUES = ("1", "true", "yes", "on")

    def __init__(
        self,
        *,
        cli_service,
        subscription_gate_service,
        video_required_model_id,
    ):
        self.cli_service = cli_service
        self.subscription_gate_service = subscription_gate_service
        self.video_required_model_id = str(video_required_model_id or "").strip()

    @staticmethod
    def _json_ok(data):
        return {"kind": "json_ok", "data": data}

    @staticmethod
    def _json_err(code, message):
        return {
            "kind": "json_err",
            "code": int(code),
            "message": str(message or ""),
        }

    @staticmethod
    def _binary(status, body, *, content_type, headers=None):
        payload = body if isinstance(body, (bytes, bytearray)) else bytes(body or b"")
        return {
            "kind": "binary",
            "status": int(status),
            "body": bytes(payload),
            "contentType": str(content_type or "application/octet-stream"),
            "headers": dict(headers or {}),
        }

    @classmethod
    def _parse_query(cls, raw_path, *, max_num_fields=20):
        parsed = urllib.parse.urlparse(str(raw_path or ""))
        return urllib.parse.parse_qs(
            parsed.query,
            keep_blank_values=True,
            max_num_fields=max_num_fields,
        )

    @classmethod
    def _parse_query_flag(cls, query, key, *, default=False):
        raw = (query.get(str(key)) or [None])[0]
        if raw is None:
            return bool(default)
        return str(raw).strip().lower() in cls._TRUE_VALUES

    @classmethod
    def _parse_payload_flag(cls, value):
        if isinstance(value, str):
            return value.strip().lower() in cls._TRUE_VALUES
        return bool(value)

    @staticmethod
    def _parse_json_object(body):
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return None, DreaminaRouteService._json_err(400, "Invalid JSON")
        if not isinstance(data, dict):
            return None, DreaminaRouteService._json_err(400, "Invalid JSON")
        return data, None

    def _start_login_response(self, *, force, mode):
        try:
            runtime = self.cli_service.start_login(
                force=bool(force),
                mode=str(mode or "headless"),
            )
            return self._json_ok(
                {
                    "success": True,
                    "runtime": runtime,
                    "status": self.cli_service.get_status(force_refresh=True),
                }
            )
        except Exception as exc:
            return self._json_ok(
                {
                    "success": False,
                    "message": str(exc),
                    "runtime": self.cli_service.get_login_runtime(),
                }
            )

    def _import_login_response(self, data):
        login_response = data.get("loginResponse")
        if login_response is None:
            login_response = data.get("jsonText")
        try:
            imported = self.cli_service.import_login_response(login_response)
            return self._json_ok(
                {
                    "success": True,
                    **(imported if isinstance(imported, dict) else {}),
                }
            )
        except ValueError as exc:
            return self._json_ok(
                {
                    "success": False,
                    "message": str(exc),
                    "runtime": self.cli_service.get_login_runtime(),
                }
            )
        except Exception as exc:
            return self._json_ok(
                {
                    "success": False,
                    "message": str(exc),
                    "runtime": self.cli_service.get_login_runtime(),
                    "status": self.cli_service.get_status(force_refresh=False),
                }
            )

    def _logout_response(self):
        try:
            return self._json_ok(
                {
                    "success": True,
                    "status": self.cli_service.logout(),
                }
            )
        except Exception as exc:
            return self._json_ok(
                {
                    "success": False,
                    "message": str(exc),
                    "status": self.cli_service.get_status(force_refresh=False),
                }
            )

    def _submit_response(self, data, submitter):
        try:
            return self._json_ok(
                {
                    "success": True,
                    **submitter(data),
                }
            )
        except ValueError as exc:
            return self._json_err(400, str(exc))
        except Exception as exc:
            return self._json_ok({"success": False, "message": str(exc)})

    def _video_gate_denial_response(self, handler, data):
        decision = self.subscription_gate_service.check_vip_subscription_gate(
            handler,
            data,
            required_model_id=self.video_required_model_id,
        )
        if bool(decision.get("allowed")):
            return None
        return self._json_ok(
            self.subscription_gate_service.build_subscription_denial_payload(decision)
        )

    def handle_get(self, handler, path):
        if path == "/api/v2/dreamina/status":
            qs = self._parse_query(handler.path)
            force_refresh = self._parse_query_flag(qs, "refresh", default=False)
            return self._json_ok(
                self.cli_service.get_status(force_refresh=force_refresh)
            )

        if path == "/api/v2/dreamina/login/runtime":
            return self._json_ok(self.cli_service.get_login_runtime())

        if path == "/api/v2/dreamina/login/qr":
            png_bytes = self.cli_service.get_qr_png()
            if not png_bytes:
                return self._json_err(404, "Dreamina QR code not ready")
            return self._binary(
                200,
                png_bytes,
                content_type="image/png",
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                },
            )

        if path == "/api/v2/dreamina/query_result":
            qs = self._parse_query(handler.path)
            submit_id = str((qs.get("submitId") or [""])[0] or "").strip()
            if not submit_id:
                return self._json_err(400, "Missing submitId")
            auto_download = self._parse_query_flag(qs, "autoDownload", default=True)
            try:
                return self._json_ok(
                    {
                        "success": True,
                        **self.cli_service.query_result(
                            submit_id=submit_id,
                            auto_download=auto_download,
                        ),
                    }
                )
            except ValueError as exc:
                return self._json_err(400, str(exc))
            except Exception as exc:
                return self._json_ok(
                    {
                        "success": False,
                        "message": str(exc),
                        "submitId": submit_id,
                        "status": "failed",
                        "outputs": [],
                    }
                )

        return None

    def handle_post(self, handler, path, body):
        if path == "/api/v2/dreamina/login":
            data, error = self._parse_json_object(body)
            if error:
                return error
            return self._start_login_response(
                force=False,
                mode=str(data.get("mode") or "headless"),
            )

        if path == "/api/v2/dreamina/relogin":
            data, error = self._parse_json_object(body)
            if error:
                return error
            return self._start_login_response(
                force=True,
                mode=str(data.get("mode") or "headless"),
            )

        if path == "/api/v2/dreamina/login/web":
            data, error = self._parse_json_object(body)
            if error:
                return error
            return self._start_login_response(
                force=self._parse_payload_flag(data.get("force")),
                mode="web",
            )

        if path == "/api/v2/dreamina/login/import":
            data, error = self._parse_json_object(body)
            if error:
                return error
            return self._import_login_response(data)

        if path == "/api/v2/dreamina/logout":
            return self._logout_response()

        submit_routes = {
            "/api/v2/dreamina/text2image": (
                self.cli_service.submit_text2image,
                False,
            ),
            "/api/v2/dreamina/image2image": (
                self.cli_service.submit_image2image,
                False,
            ),
            "/api/v2/dreamina/text2video": (
                self.cli_service.submit_text2video,
                True,
            ),
            "/api/v2/dreamina/image2video": (
                self.cli_service.submit_image2video,
                True,
            ),
            "/api/v2/dreamina/frames2video": (
                self.cli_service.submit_frames2video,
                True,
            ),
            "/api/v2/dreamina/multiframe2video": (
                self.cli_service.submit_multiframe2video,
                True,
            ),
            "/api/v2/dreamina/multimodal2video": (
                self.cli_service.submit_multimodal2video,
                True,
            ),
        }
        route = submit_routes.get(path)
        if route is None:
            return None

        data, error = self._parse_json_object(body)
        if error:
            return error
        submitter, requires_video_gate = route
        if requires_video_gate:
            denial = self._video_gate_denial_response(handler, data)
            if denial is not None:
                return denial
        return self._submit_response(data, submitter)
