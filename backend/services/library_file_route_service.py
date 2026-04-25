import base64
import json
import os
import re


class LibraryFileRouteService:
    _DEFAULT_PRESET_TYPES = ("ai-image", "ai-text", "ai-video", "ai-audio")

    def __init__(
        self,
        *,
        user_dir_getter,
        asset_thumbs_dir_getter,
        workflow_thumbs_dir_getter,
    ):
        self._get_user_dir = user_dir_getter
        self._get_asset_thumbs_dir = asset_thumbs_dir_getter
        self._get_workflow_thumbs_dir = workflow_thumbs_dir_getter

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
            return None, LibraryFileRouteService._json_err(400, "Invalid JSON")
        if not isinstance(data, dict):
            return None, LibraryFileRouteService._json_err(400, "Invalid JSON")
        return data, None

    @staticmethod
    def _safe_name(value):
        return re.sub(r'[\\/:*?"<>|]', "_", str(value))

    @staticmethod
    def _extension_from_data_url_header(header):
        mime = "image/jpeg"
        try:
            mime = str(header or "")[5:].split(";", 1)[0]
        except Exception:
            pass
        if mime.endswith("png"):
            return ".png"
        if mime.endswith("webp"):
            return ".webp"
        return ".jpg"

    def _read_presets(self):
        prompt_dir = os.path.join(self._get_user_dir(), "prompt")
        for preset_type in self._DEFAULT_PRESET_TYPES:
            os.makedirs(os.path.join(prompt_dir, preset_type), exist_ok=True)

        result = {}
        if os.path.exists(prompt_dir):
            for node_type in os.listdir(prompt_dir):
                type_dir = os.path.join(prompt_dir, node_type)
                if not os.path.isdir(type_dir):
                    continue
                result[node_type] = []
                for filename in os.listdir(type_dir):
                    if not filename.endswith(".txt"):
                        continue
                    path = os.path.join(type_dir, filename)
                    try:
                        with open(path, "r", encoding="utf-8") as file:
                            content = file.read().strip()
                        if content:
                            result[node_type].append(
                                {
                                    "title": filename[:-4],
                                    "template": content,
                                }
                            )
                    except Exception as exc:
                        print(f"Error reading preset {path}: {exc}")
        return result

    def _save_thumb(
        self,
        *,
        data,
        id_fields,
        default_key,
        id_required_message,
        target_dir,
        relative_prefix,
    ):
        item_id = ""
        for field in id_fields:
            item_id = data.get(field) or item_id
            if item_id:
                break
        key = data.get("key") or data.get("idx") or default_key
        data_url = data.get("dataUrl") or ""

        if not item_id:
            return self._json_err(400, id_required_message)
        if not isinstance(data_url, str) or not data_url.startswith("data:image/"):
            return self._json_err(400, "Invalid dataUrl")

        try:
            header, encoded = data_url.split(",", 1)
        except Exception:
            return self._json_err(400, "Invalid dataUrl")

        try:
            raw = base64.b64decode(encoded)
        except Exception:
            return self._json_err(400, "Invalid base64")

        extension = self._extension_from_data_url_header(header)
        filename = f"{self._safe_name(item_id)}_{self._safe_name(key)}{extension}"
        os.makedirs(target_dir, exist_ok=True)
        with open(os.path.join(target_dir, filename), "wb") as file:
            file.write(raw)

        local_path = f"{relative_prefix}/{filename}"
        return self._json_ok(
            {
                "success": True,
                "url": f"/{local_path}",
                "localPath": local_path,
                "filename": filename,
            }
        )

    def handle_get(self, handler, path):
        if path == "/api/v2/user/presets":
            return self._json_ok(self._read_presets())
        return None

    def handle_post(self, handler, path, body):
        if path == "/api/v2/assets/thumb/save":
            data, error = self._parse_json_object(body)
            if error is not None:
                return error
            return self._save_thumb(
                data=data,
                id_fields=("assetId", "id"),
                default_key="0",
                id_required_message="Asset ID required",
                target_dir=self._get_asset_thumbs_dir(),
                relative_prefix="data/assets/thumbs",
            )

        if path == "/api/v2/workflows/thumb/save":
            data, error = self._parse_json_object(body)
            if error is not None:
                return error
            return self._save_thumb(
                data=data,
                id_fields=("workflowId", "id"),
                default_key="cover",
                id_required_message="Workflow ID required",
                target_dir=self._get_workflow_thumbs_dir(),
                relative_prefix="data/workflows/thumbs",
            )

        return None
