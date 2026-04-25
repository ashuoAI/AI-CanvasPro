import re
import threading
import time
from collections import OrderedDict


class SubscriptionGateService:
    def __init__(
        self,
        *,
        client,
        status_active="active",
        status_none="none",
        error_model_not_entitled="SUBSCRIPTION_MODEL_NOT_ENTITLED",
        model_name_map=None,
        cache_max=2048,
        success_logger=None,
    ):
        self.client = client
        self.status_active = str(status_active or "active").strip().lower() or "active"
        self.status_none = str(status_none or "none").strip().lower() or "none"
        self.error_model_not_entitled = str(
            error_model_not_entitled or "SUBSCRIPTION_MODEL_NOT_ENTITLED"
        ).strip() or "SUBSCRIPTION_MODEL_NOT_ENTITLED"
        self.model_name_map = dict(model_name_map or {})
        self.cache_max = max(1, int(cache_max or 2048))
        self.success_logger = success_logger
        self._allow_cache = OrderedDict()
        self._success_logged_installs = OrderedDict()
        self._lock = threading.Lock()

    def extract_install_id_from_request(self, handler, payload=None):
        return self.client.extract_install_id_from_request(handler, payload)

    def normalize_vip_model_id(self, value):
        s = str(value or "").strip()
        if not s:
            return ""
        if s == "ai-app/2047787809091620866":
            return "runninghub/2047787809091620866"
        if s.startswith("runninghub/"):
            return s
        if s.startswith("dreamina/"):
            return s
        if re.match(r"^\d+$", s):
            return f"runninghub/{s}"
        return s

    def extract_entitled_model_ids(self, payload):
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
            text = self.normalize_vip_model_id(item)
            if text and text not in out:
                out.append(text)
        return out

    def extract_expires_at(self, payload):
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

    def clear_vip_allow_cache(self, install_id):
        install = str(install_id or "").strip()
        if not install:
            return
        with self._lock:
            self._allow_cache.pop(install, None)

    def _get_cached_vip_allow_decision(self, install_id, model_id):
        install = str(install_id or "").strip()
        model = str(model_id or "").strip()
        if not install or not model:
            return None
        with self._lock:
            cached = self._allow_cache.get(install)
        if not isinstance(cached, dict):
            return None

        status = str(cached.get("status") or "").strip().lower()
        if status != self.status_active:
            return None

        now_ts = int(time.time())
        expires_at = int(cached.get("expiresAt") or 0)
        if expires_at > 0 and expires_at <= now_ts:
            with self._lock:
                self._allow_cache.pop(install, None)
            return None

        entitled_ids = self.extract_entitled_model_ids(cached)
        if entitled_ids and model not in entitled_ids:
            return None

        return {
            "allowed": True,
            "installId": install,
            "status": self.status_active,
            "reasonCode": "ACTIVE_CACHE_HIT",
            "reasonMessage": "",
            "requiredModelId": model,
            "payload": {
                "status": self.status_active,
                "expiresAt": expires_at,
                "entitledModelIds": entitled_ids,
            },
        }

    def _cache_vip_allow_decision(self, install_id, *, payload, entitled_ids):
        install = str(install_id or "").strip()
        if not install:
            return
        entry = {
            "status": self.status_active,
            "expiresAt": self.extract_expires_at(payload),
            "entitledModelIds": list(entitled_ids or []),
            "cachedAt": int(time.time()),
        }
        with self._lock:
            self._allow_cache.pop(install, None)
            self._allow_cache[install] = entry
            while len(self._allow_cache) > self.cache_max:
                self._allow_cache.popitem(last=False)

    def _mark_first_vip_gate_success_log(self, install_id):
        install = str(install_id or "").strip()
        if not install:
            return False
        with self._lock:
            if install in self._success_logged_installs:
                return False
            self._success_logged_installs[install] = int(time.time())
            while len(self._success_logged_installs) > self.cache_max:
                self._success_logged_installs.popitem(last=False)
        return True

    def _log_first_vip_gate_success(self, decision):
        if not isinstance(decision, dict):
            return
        if not bool(decision.get("allowed")):
            return
        status = str(decision.get("status") or "").strip().lower()
        reason = str(decision.get("reasonCode") or "").strip().upper()
        if status != self.status_active or reason != "ACTIVE":
            return
        if not self._mark_first_vip_gate_success_log(decision.get("installId")):
            return
        try:
            if callable(self.success_logger):
                self.success_logger(decision)
        except Exception:
            return

    def check_vip_subscription_gate(self, handler, payload=None, required_model_id=""):
        install_id = self.extract_install_id_from_request(handler, payload)
        model_id = self.normalize_vip_model_id(required_model_id)
        cached_decision = self._get_cached_vip_allow_decision(install_id, model_id)
        if isinstance(cached_decision, dict):
            return cached_decision

        decision = self.client.evaluate_install_active(install_id)
        decision = dict(decision) if isinstance(decision, dict) else {}
        decision["requiredModelId"] = model_id
        if bool(decision.get("allowed")) and model_id:
            entitled_ids = self.extract_entitled_model_ids(decision.get("payload"))
            entitled = (
                model_id in entitled_ids
                if entitled_ids
                else self.client.is_install_entitled_for_model(install_id, model_id)
            )
            if not entitled:
                decision["allowed"] = False
                decision["reasonCode"] = self.error_model_not_entitled
                model_name = self.model_name_map.get(model_id) or model_id
                decision["reasonMessage"] = f"当前订阅未包含 {model_name}"
                self.clear_vip_allow_cache(install_id)
            else:
                if not entitled_ids:
                    entitled_ids = [model_id]
                self._cache_vip_allow_decision(
                    install_id,
                    payload=decision.get("payload"),
                    entitled_ids=entitled_ids,
                )
        elif install_id:
            self.clear_vip_allow_cache(install_id)
        self._log_first_vip_gate_success(decision)
        return decision

    def build_subscription_denial_payload(self, decision):
        decision = dict(decision) if isinstance(decision, dict) else {}
        denial = self.client.subscription_required_payload(
            decision.get("reasonMessage") or "未激活"
        )
        denial["reasonCode"] = decision.get("reasonCode") or ""
        denial["subscriptionStatus"] = decision.get("status") or self.status_none
        denial["installId"] = decision.get("installId") or ""
        denial["requiredModelId"] = decision.get("requiredModelId") or ""
        return denial
