import json
import urllib.error
import urllib.parse
import urllib.request


class RemoteProxyRouteService:
    def __init__(
        self,
        *,
        read_body,
        subscription_gate_service_getter,
        video_vip_workflow_ids,
    ):
        self._read_body = read_body
        self._get_subscription_gate_service = subscription_gate_service_getter
        self._video_vip_workflow_ids = {
            str(workflow_id or "").strip()
            for workflow_id in (video_vip_workflow_ids or set())
            if str(workflow_id or "").strip()
        }

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
    def _proxy_response(status, body, *, content_type="application/json; charset=utf-8"):
        payload = body if isinstance(body, (bytes, bytearray)) else bytes(body or b"")
        return {
            "kind": "binary",
            "status": int(status),
            "body": bytes(payload),
            "contentType": str(content_type or "application/json; charset=utf-8"),
        }

    @staticmethod
    def _parse_json_object(body):
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return None, RemoteProxyRouteService._json_err(400, "Invalid JSON")
        if not isinstance(data, dict):
            return None, RemoteProxyRouteService._json_err(400, "Invalid JSON")
        return data, None

    @staticmethod
    def _parse_query(raw_path, *, max_num_fields=20):
        parsed = urllib.parse.urlparse(str(raw_path or ""))
        return urllib.parse.parse_qs(
            parsed.query,
            keep_blank_values=True,
            max_num_fields=max_num_fields,
        )

    @staticmethod
    def _extract_bearer_token(header_value):
        auth_value = str(header_value or "").strip()
        if auth_value.lower().startswith("bearer "):
            return auth_value[7:].strip()
        return ""

    def _extract_proxy_api_key(self, handler, query):
        api_key = query.get("apiKey", [""])[0].strip() if "apiKey" in query else ""
        if api_key:
            return api_key.rstrip(",")
        return self._extract_bearer_token(handler.headers.get("Authorization", ""))

    @staticmethod
    def _normalize_runninghub_instance_type(value):
        instance_type = str(value or "").strip().lower()
        if instance_type in ("24g", "default", "basic"):
            return "default"
        if instance_type in ("48g", "plus", "pro"):
            return "plus"
        return "default"

    @staticmethod
    def _requests_module():
        import requests

        return requests

    def _read_json_request(self, handler):
        return self._parse_json_object(self._read_body(handler))

    def _vip_gate_denial_response(self, handler, payload, *, required_model_id):
        gate_service = self._get_subscription_gate_service()
        decision = gate_service.check_vip_subscription_gate(
            handler,
            payload,
            required_model_id=required_model_id,
        )
        if bool(decision.get("allowed")):
            return None
        return self._json_ok(gate_service.build_subscription_denial_payload(decision))

    def _post_json_to_remote(self, api_url, payload, *, timeout, error_prefix):
        try:
            requests = self._requests_module()
            resp = requests.post(api_url, json=payload, timeout=timeout)
            return self._proxy_response(resp.status_code, resp.content)
        except ImportError:
            req_body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(api_url, data=req_body, method="POST")
            req.add_header("Content-Type", "application/json")
            req.add_header("User-Agent", "Mozilla/5.0")
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    resp_data = resp.read()
                return self._proxy_response(resp.status, resp_data)
            except urllib.error.HTTPError as exc:
                return self._proxy_response(exc.code, exc.read())
        except Exception as exc:
            return self._json_err(500, f"{error_prefix}: {repr(exc)}")

    def _handle_task_proxy(self, handler):
        query = self._parse_query(handler.path, max_num_fields=10)
        api_url = query.get("apiUrl", [""])[0].strip() if "apiUrl" in query else ""
        api_key = self._extract_proxy_api_key(handler, query)
        api_url = api_url.rstrip(",")
        if not api_url or not api_key:
            return self._json_err(400, "Missing apiUrl or apiKey")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        }
        try:
            try:
                requests = self._requests_module()
                resp = requests.get(api_url, headers=headers, timeout=30)
                return self._proxy_response(resp.status_code, resp.content)
            except ImportError:
                pass
            except Exception:
                pass

            req = urllib.request.Request(api_url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_data = resp.read()
                return self._proxy_response(200, resp_data)
            except urllib.error.HTTPError as exc:
                return self._proxy_response(exc.code, exc.read())
            except Exception as exc:
                return self._json_err(500, f"Urllib polling error: {str(exc)}")
        except Exception as exc:
            return self._json_err(500, f"Task proxy global error: {repr(exc)}")

    def _handle_upload_proxy(self, handler):
        query = self._parse_query(handler.path)
        api_url = query.get("apiUrl", [""])[0].strip()
        api_key = self._extract_proxy_api_key(handler, query)
        if not api_url or not api_key:
            return self._json_err(400, "Missing apiUrl or apiKey")

        try:
            content_length = int(handler.headers.get("Content-Length", 0))
            body = handler.rfile.read(content_length)
            content_type = handler.headers.get("Content-Type", "")

            req = urllib.request.Request(api_url, data=body, method="POST")
            req.add_header("Authorization", f"Bearer {api_key}")
            req.add_header("Content-Type", content_type)
            req.add_header("Content-Length", str(len(body)))

            with urllib.request.urlopen(req, timeout=60) as resp:
                return self._proxy_response(resp.status, resp.read())
        except urllib.error.HTTPError as exc:
            return self._proxy_response(exc.code, exc.read())
        except Exception as exc:
            return self._json_err(500, f"Upload proxy error: {str(exc)}")

    def _handle_runninghub_workflow_run(self, handler):
        data, error = self._read_json_request(handler)
        if error is not None:
            return error

        api_key = (data.get("apiKey") or "").strip()
        workflow_id = str(data.get("workflowId") or "").strip()
        node_info_list = data.get("nodeInfoList")
        if not api_key or not workflow_id or not isinstance(node_info_list, list):
            return self._json_err(400, "Missing apiKey or workflowId or nodeInfoList")

        if workflow_id in self._video_vip_workflow_ids:
            denial = self._vip_gate_denial_response(
                handler,
                data,
                required_model_id=f"runninghub/{workflow_id}",
            )
            if denial is not None:
                return denial

        payload = dict(data)
        payload["instanceType"] = self._normalize_runninghub_instance_type(
            data.get("instanceType") or data.get("rhInstanceType") or ""
        )
        return self._post_json_to_remote(
            "https://www.runninghub.cn/task/openapi/create",
            payload,
            timeout=900,
            error_prefix="RunningHub workflow proxy error",
        )

    def _handle_runninghub_task_action(self, handler, *, api_url, error_prefix):
        data, error = self._read_json_request(handler)
        if error is not None:
            return error

        api_key = (data.get("apiKey") or "").strip()
        task_id = str(data.get("taskId") or "").strip()
        if not api_key or not task_id:
            return self._json_err(400, "Missing apiKey or taskId")

        return self._post_json_to_remote(
            api_url,
            {"apiKey": api_key, "taskId": task_id},
            timeout=60,
            error_prefix=error_prefix,
        )

    def handle_get(self, handler, path):
        if path == "/api/v2/proxy/task":
            return self._handle_task_proxy(handler)
        return None

    def handle_post(self, handler, path):
        if path == "/api/v2/proxy/upload":
            return self._handle_upload_proxy(handler)

        if path == "/api/v2/runninghubwf/run":
            return self._handle_runninghub_workflow_run(handler)

        if path == "/api/v2/runninghubwf/query":
            return self._handle_runninghub_task_action(
                handler,
                api_url="https://www.runninghub.cn/task/openapi/outputs",
                error_prefix="RunningHub query proxy error",
            )

        if path == "/api/v2/runninghubwf/cancel":
            return self._handle_runninghub_task_action(
                handler,
                api_url="https://www.runninghub.cn/task/openapi/cancel",
                error_prefix="RunningHub cancel proxy error",
            )

        return None
