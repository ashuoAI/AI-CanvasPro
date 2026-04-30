import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request


SUBSCRIPTION_NETWORK_HELP_MESSAGE = (
    "授权服务不可用，请检查网络；如果当前网络无法连接授权服务器，"
    "请打开科学上网/代理后重试，或查看飞书文档《关于网络》。"
)


class SubscriptionRemoteClient:
    def __init__(
        self,
        *,
        api_base_url,
        timeout_seconds,
        status_active,
        err_required,
        required_message,
        contact_text,
        contact_url,
    ):
        self.api_base_url = str(api_base_url or "").strip().rstrip("/")
        self.timeout_seconds = max(1, int(timeout_seconds or 5))
        self.status_active = str(status_active or "active")
        self.err_required = str(err_required or "SUBSCRIPTION_REQUIRED")
        self.required_message = str(required_message or "该模型为 VIP，请先激活 CDKEY/订阅")
        self.contact_text = str(contact_text or "").strip()
        self.contact_url = str(contact_url or "").strip()
        self.status_none = "none"
        self.status_expired = "expired"

    def normalize_install_id(self, value):
        s = str(value or "").strip()
        if not s or len(s) > 128:
            return ""
        if not re.match(r"^[A-Za-z0-9._:-]+$", s):
            return ""
        return s

    def extract_install_id_from_request(self, handler, payload=None):
        header_value = handler.headers.get("X-AIC-Install-Id", "")
        install = self.normalize_install_id(header_value)
        if install:
            return install
        if isinstance(payload, dict):
            install = self.normalize_install_id(payload.get("installId"))
            if install:
                return install
        parsed = urllib.parse.urlparse(handler.path)
        qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True, max_num_fields=20)
        install_qs = (qs.get("installId") or [""])[0]
        return self.normalize_install_id(install_qs)

    def subscription_required_payload(self, reason=None):
        message = self.required_message
        if reason:
            message = f"{message}（{reason}）"
        return {
            "success": False,
            "code": self.err_required,
            "message": message,
            "contactText": self.contact_text,
            "contactUrl": self.contact_url,
        }

    def _request_json(self, method, path, *, payload=None, query=None):
        if not self.api_base_url:
            return None
        base_path = str(path or "").strip()
        if not base_path.startswith("/"):
            base_path = "/" + base_path
        url = f"{self.api_base_url}{base_path}"
        if isinstance(query, dict) and query:
            encoded = urllib.parse.urlencode(query)
            if encoded:
                url = f"{url}?{encoded}"
        req_body = None
        if payload is not None:
            req_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=req_body, method=method)
        req.add_header("Accept", "application/json")
        if req_body is not None:
            req.add_header("Content-Type", "application/json")
        raw = b""
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            try:
                raw = e.read()
            except Exception:
                raw = b""
        except (urllib.error.URLError, TimeoutError):
            return None
        except Exception:
            return None
        try:
            data = json.loads(raw.decode("utf-8", errors="ignore"))
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def _extract_payload_dict(self, data):
        if not isinstance(data, dict):
            return {}
        nested = data.get("data")
        if isinstance(nested, dict):
            return nested
        return data

    def _normalize_status(self, status_value):
        status = str(status_value or "").strip().lower()
        if status == str(self.status_active).strip().lower():
            return self.status_active
        if status == self.status_expired:
            return self.status_expired
        if status == self.status_none:
            return self.status_none
        return self.status_none

    def fetch_subscription_status(self, install_id):
        install = self.normalize_install_id(install_id)
        if not install:
            return None
        return self._request_json(
            "GET",
            "/api/subscription/status",
            query={"installId": install},
        )

    def activate_cdkey(self, install_id, cdkey):
        install = self.normalize_install_id(install_id)
        token = str(cdkey or "").strip()
        if not install or not token:
            return None
        return self._request_json(
            "POST",
            "/api/subscription/activate",
            payload={"installId": install, "cdkey": token},
        )

    def evaluate_install_active(self, install_id):
        install = self.normalize_install_id(install_id)
        if not install:
            return {
                "allowed": False,
                "installId": "",
                "status": self.status_none,
                "reasonCode": "MISSING_INSTALL_ID",
                "reasonMessage": "缺少 installId",
                "payload": None,
            }
        data = self.fetch_subscription_status(install)
        if not isinstance(data, dict):
            return {
                "allowed": False,
                "installId": install,
                "status": self.status_none,
                "reasonCode": "SERVICE_UNAVAILABLE",
                "reasonMessage": SUBSCRIPTION_NETWORK_HELP_MESSAGE,
                "payload": None,
            }
        payload = self._extract_payload_dict(data)
        status_value = (
            payload.get("status")
            or payload.get("subscriptionStatus")
            or payload.get("state")
            or ""
        )
        status = self._normalize_status(status_value)
        if status == self.status_active:
            return {
                "allowed": True,
                "installId": install,
                "status": status,
                "reasonCode": "ACTIVE",
                "reasonMessage": "",
                "payload": data,
            }
        if status == self.status_expired:
            reason_code = "SUBSCRIPTION_EXPIRED"
            reason_message = "订阅已过期"
        else:
            reason_code = "NOT_ACTIVE"
            reason_message = "未激活"
        return {
            "allowed": False,
            "installId": install,
            "status": status,
            "reasonCode": reason_code,
            "reasonMessage": reason_message,
            "payload": data,
        }

    def _fetch_status_payload(self, install_id):
        return self.fetch_subscription_status(install_id)

    def is_install_entitled_for_model(self, install_id, model_id):
        install = self.normalize_install_id(install_id)
        if not install:
            return False
        data = self._fetch_status_payload(install)
        if not isinstance(data, dict):
            return False
        payload = self._extract_payload_dict(data)
        status_value = (
            payload.get("status")
            or payload.get("subscriptionStatus")
            or payload.get("state")
            or ""
        )
        if self._normalize_status(status_value) != self.status_active:
            return False
        entitled = payload.get("entitledModelIds")
        if not isinstance(entitled, list):
            entitled = payload.get("entitled_model_ids")
        if not isinstance(entitled, list):
            return False
        model = str(model_id or "").strip()
        return model in [str(m or "").strip() for m in entitled]
