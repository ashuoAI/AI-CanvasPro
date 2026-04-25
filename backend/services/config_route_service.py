import json
import os


class ConfigRouteService:
    def __init__(self, *, config_file_getter):
        self._get_config_file = config_file_getter

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
    def _parse_json_object(body):
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return None, ConfigRouteService._json_err(400, "Invalid JSON")
        if not isinstance(data, dict):
            return None, ConfigRouteService._json_err(400, "Invalid JSON")
        return data, None

    def _config_file(self):
        return os.path.abspath(self._get_config_file())

    def _read_config(self):
        path = self._config_file()
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8-sig") as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                return {}
        return data if isinstance(data, dict) else {}

    def _write_config(self, data):
        path = self._config_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def get_custom_ai_config(self):
        env_url = os.environ.get("CUSTOM_AI_URL", "").strip()
        env_key = os.environ.get("CUSTOM_AI_KEY", "").strip()

        cfg_url = ""
        cfg_key = ""
        try:
            cfg = self._read_config()
            custom_ai = cfg.get("custom_ai", {}) if isinstance(cfg, dict) else {}
            cfg_url = custom_ai.get("apiUrl") or cfg.get("apiUrl", "")
            cfg_key = custom_ai.get("apiKey") or cfg.get("apiKey", "")
        except Exception:
            pass

        return {
            "apiUrl": env_url if env_url else cfg_url,
            "apiKey": env_key if env_key else cfg_key,
            "source": "env" if (env_url or env_key) else "config",
        }

    @staticmethod
    def _masked_key(api_key):
        key = str(api_key or "")
        if len(key) > 4:
            return key[:4] + "*" * (len(key) - 4)
        return "*" * len(key) if key else ""

    def _read_public_config(self):
        cfg = self._read_config()

        env_grsai_key = os.environ.get("GRSAI_API_KEY", "").strip()
        if env_grsai_key:
            old_key = cfg.get("apiKey") or cfg.get("apiKeyInput")
            providers = cfg.get("providers", {})
            if not isinstance(providers, dict):
                providers = {}
                cfg["providers"] = providers
            grsai = providers.get("grsai", {})
            if not isinstance(grsai, dict):
                grsai = {}
            providers["grsai"] = grsai
            if not old_key and not grsai.get("apiKey"):
                grsai["apiKey"] = env_grsai_key

        env_ppio_key = os.environ.get("PPIO_API_KEY", "").strip()
        if env_ppio_key:
            providers = cfg.get("providers", {})
            if not isinstance(providers, dict):
                providers = {}
                cfg["providers"] = providers
            ppio = providers.get("ppio", {})
            if not isinstance(ppio, dict):
                ppio = {}
            providers["ppio"] = ppio
            if not ppio.get("apiKey"):
                ppio["apiKey"] = env_ppio_key

        return cfg

    def _read_custom_ai_public_config(self):
        cfg = self.get_custom_ai_config()
        api_key = cfg["apiKey"]
        return {
            "apiUrl": cfg["apiUrl"],
            "apiKeyMasked": self._masked_key(api_key),
            "hasKey": bool(api_key),
            "source": cfg["source"],
        }

    def handle_get(self, handler, path):
        if path == "/api/config":
            return self._json_ok(self._read_public_config())

        if path == "/api/v2/config/custom-ai":
            return self._json_ok(self._read_custom_ai_public_config())

        return None

    def handle_post(self, handler, path, body):
        if path == "/api/config":
            data, error = self._parse_json_object(body)
            if error is not None:
                return error
            self._write_config(data)
            return self._json_ok({"success": True})

        if path == "/api/v2/config/custom-ai":
            data, error = self._parse_json_object(body)
            if error is not None:
                return error
            if self.get_custom_ai_config().get("source") == "env":
                return self._json_err(
                    403,
                    "Config is locked by environment variables (CUSTOM_AI_URL / CUSTOM_AI_KEY)",
                )
            try:
                existing = self._read_config()
                existing["custom_ai"] = {
                    "apiUrl": str(data.get("apiUrl") or "").strip(),
                    "apiKey": str(data.get("apiKey") or "").strip(),
                }
                self._write_config(existing)
                return self._json_ok({"success": True})
            except Exception as exc:
                return self._json_err(500, str(exc))

        return None
