import base64
import json
import os
import re


class LibraryFileRouteService:
    _DEFAULT_PRESET_TYPES = ("ai-image", "ai-text", "ai-video", "ai-audio")
    _PRESET_THUMB_USER_PREFIX = "user/prompt/_thumbs/presets/"

    def __init__(
        self,
        *,
        user_dir_getter,
        asset_thumbs_dir_getter,
        workflow_thumbs_dir_getter,
        subscription_gate_service_getter=None,
    ):
        self._get_user_dir = user_dir_getter
        self._get_asset_thumbs_dir = asset_thumbs_dir_getter
        self._get_workflow_thumbs_dir = workflow_thumbs_dir_getter
        self._get_subscription_gate_service = subscription_gate_service_getter

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
    def _normalize_preset_template(value):
        text = str(value or "")
        text = re.sub(
            r'<span\b[^>]*\bdata-preset-placeholder=["\']user-input["\'][^>]*>[\s\S]*?</span>',
            "{用户输入}",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"<br\b[^>]*\/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</(div|p)>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        return text.strip()

    @staticmethod
    def _normalize_preset_desc(value):
        text = str(value or "")
        text = re.sub(r"<[^>]+>", "", text)
        return text.strip()

    def _normalize_preset_type(self, value):
        preset_type = str(value or "").strip()
        if preset_type not in self._DEFAULT_PRESET_TYPES:
            return ""
        return preset_type

    def _preset_dir(self, preset_type):
        return os.path.join(self._get_user_dir(), "prompt", preset_type)

    def _preset_path(self, preset_type, title):
        safe_title = self._safe_name(str(title or "").strip()).strip()
        if not safe_title:
            return ""
        return os.path.join(self._preset_dir(preset_type), f"{safe_title}.txt")

    def _preset_meta_path(self, preset_type, title):
        safe_title = self._safe_name(str(title or "").strip()).strip()
        if not safe_title:
            return ""
        return os.path.join(self._preset_dir(preset_type), f"{safe_title}.json")

    @staticmethod
    def _normalize_preset_thumb_local_path(value):
        local_path = str(value or "").strip().replace("\\", "/").lstrip("/")
        if not local_path.startswith(LibraryFileRouteService._PRESET_THUMB_USER_PREFIX):
            return ""
        return local_path

    def _preset_thumb_user_root(self):
        return os.path.join(self._get_user_dir(), "prompt", "_thumbs")

    def _preset_thumb_abs_path(self, local_path):
        normalized = self._normalize_preset_thumb_local_path(local_path)
        if not normalized:
            return ""
        rel = normalized[len("user/prompt/_thumbs/") :].lstrip("/")
        root = os.path.abspath(self._preset_thumb_user_root())
        abs_path = os.path.abspath(os.path.join(root, rel))
        if abs_path != root and not abs_path.startswith(root + os.sep):
            return ""
        return abs_path

    def _remove_preset_thumb(self, local_path):
        abs_path = self._preset_thumb_abs_path(local_path)
        if abs_path and os.path.exists(abs_path):
            try:
                os.remove(abs_path)
            except FileNotFoundError:
                pass

    def _save_preset_thumb(self, preset_type, title, data_url):
        if not isinstance(data_url, str) or not data_url.startswith("data:image/"):
            return "", self._json_err(400, "Invalid thumbnailDataUrl")
        try:
            header, encoded = data_url.split(",", 1)
        except Exception:
            return "", self._json_err(400, "Invalid thumbnailDataUrl")
        try:
            raw = base64.b64decode(encoded)
        except Exception:
            return "", self._json_err(400, "Invalid thumbnail base64")

        extension = self._extension_from_data_url_header(header)
        safe_title = self._safe_name(str(title or "").strip()).strip()
        if not safe_title:
            return "", self._json_err(400, "Invalid preset title")
        target_dir = os.path.join(self._preset_thumb_user_root(), "presets", preset_type)
        os.makedirs(target_dir, exist_ok=True)
        filename = f"{safe_title}{extension}"
        with open(os.path.join(target_dir, filename), "wb") as file:
            file.write(raw)
        return f"user/prompt/_thumbs/presets/{preset_type}/{filename}", None

    def _is_subscription_active(self, handler, payload):
        if not callable(self._get_subscription_gate_service):
            return False
        try:
            gate_service = self._get_subscription_gate_service()
            decision = gate_service.check_vip_subscription_gate(
                handler,
                payload,
                required_model_id="",
            )
        except Exception:
            return False
        if not isinstance(decision, dict):
            return False
        return bool(decision.get("allowed")) and str(
            decision.get("status") or ""
        ).strip().lower() == "active"

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
                            item = {
                                "title": filename[:-4],
                                "template": content,
                            }
                            meta_path = self._preset_meta_path(node_type, filename[:-4])
                            if meta_path and os.path.exists(meta_path):
                                try:
                                    with open(meta_path, "r", encoding="utf-8") as meta_file:
                                        meta = json.load(meta_file)
                                    desc = self._normalize_preset_desc(
                                        meta.get("desc") if isinstance(meta, dict) else ""
                                    )
                                    if desc:
                                        item["desc"] = desc
                                    thumb_local_path = self._normalize_preset_thumb_local_path(
                                        meta.get("thumbLocalPath") if isinstance(meta, dict) else ""
                                    )
                                    if thumb_local_path:
                                        item["thumbLocalPath"] = thumb_local_path
                                        item["thumbUrl"] = f"/{thumb_local_path}"
                                except Exception as exc:
                                    print(f"Error reading preset metadata {meta_path}: {exc}")
                            result[node_type].append(item)
                    except Exception as exc:
                        print(f"Error reading preset {path}: {exc}")
        return result

    def _save_preset(self, handler, data):
        preset_type = self._normalize_preset_type(data.get("nodeType"))
        title = str(data.get("title") or "").strip()
        original_title = str(data.get("originalTitle") or "").strip()
        template = self._normalize_preset_template(data.get("template"))
        desc = self._normalize_preset_desc(
            data.get("desc") if "desc" in data else data.get("description")
        )
        thumb_local_path = self._normalize_preset_thumb_local_path(
            data.get("thumbLocalPath") or data.get("thumbnailLocalPath")
        )
        thumbnail_data_url = str(data.get("thumbnailDataUrl") or "").strip()
        if not preset_type:
            return self._json_err(400, "Invalid nodeType")
        if not title:
            return self._json_err(400, "Preset title required")
        if not template:
            return self._json_err(400, "Preset template required")

        target_dir = self._preset_dir(preset_type)
        os.makedirs(target_dir, exist_ok=True)
        target_path = self._preset_path(preset_type, title)
        if not target_path:
            return self._json_err(400, "Invalid preset title")

        original_path = (
            self._preset_path(preset_type, original_title)
            if original_title
            else target_path
        )
        original_exists = bool(original_path and os.path.exists(original_path))
        target_exists = os.path.exists(target_path)
        if original_path != target_path and target_exists:
            return self._json_err(409, "Preset title already exists")

        current_count = len(self._read_presets().get(preset_type, []))
        creating_new = not original_exists and not target_exists
        if (
            creating_new
            and current_count >= 3
            and not self._is_subscription_active(handler, data)
        ):
            return self._json_err(403, "未授权用户每类节点最多 3 个自定义预设")

        with open(target_path, "w", encoding="utf-8") as file:
            file.write(template)
        original_thumb_local_path = ""
        original_meta_path = self._preset_meta_path(preset_type, original_title)
        if original_meta_path and os.path.exists(original_meta_path):
            try:
                with open(original_meta_path, "r", encoding="utf-8") as meta_file:
                    original_meta = json.load(meta_file)
                if isinstance(original_meta, dict):
                    original_thumb_local_path = self._normalize_preset_thumb_local_path(
                        original_meta.get("thumbLocalPath")
                    )
            except Exception:
                original_thumb_local_path = ""

        if thumbnail_data_url:
            next_thumb_path, thumb_error = self._save_preset_thumb(
                preset_type,
                title,
                thumbnail_data_url,
            )
            if thumb_error is not None:
                return thumb_error
            thumb_local_path = next_thumb_path
        target_meta_path = self._preset_meta_path(preset_type, title)
        meta_payload = {}
        if desc:
            meta_payload["desc"] = desc
        if thumb_local_path:
            meta_payload["thumbLocalPath"] = thumb_local_path
        if meta_payload and target_meta_path:
            with open(target_meta_path, "w", encoding="utf-8") as file:
                json.dump(meta_payload, file, ensure_ascii=False)
        elif target_meta_path and os.path.exists(target_meta_path):
            os.remove(target_meta_path)
        if original_path != target_path and original_exists:
            try:
                os.remove(original_path)
            except FileNotFoundError:
                pass
            if original_meta_path and os.path.exists(original_meta_path):
                try:
                    os.remove(original_meta_path)
                except FileNotFoundError:
                    pass
        if original_thumb_local_path and original_thumb_local_path != thumb_local_path:
            self._remove_preset_thumb(original_thumb_local_path)
        return self._json_ok(
            {
                "success": True,
                "nodeType": preset_type,
                "title": title,
                "thumbLocalPath": thumb_local_path,
            }
        )

    def _delete_preset(self, data):
        preset_type = self._normalize_preset_type(data.get("nodeType"))
        title = str(data.get("title") or "").strip()
        if not preset_type:
            return self._json_err(400, "Invalid nodeType")
        if not title:
            return self._json_err(400, "Preset title required")
        path = self._preset_path(preset_type, title)
        thumb_local_path = ""
        meta_path = self._preset_meta_path(preset_type, title)
        if meta_path and os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as meta_file:
                    meta = json.load(meta_file)
                if isinstance(meta, dict):
                    thumb_local_path = self._normalize_preset_thumb_local_path(
                        meta.get("thumbLocalPath")
                    )
            except Exception:
                thumb_local_path = ""
        if path and os.path.exists(path):
            os.remove(path)
        if meta_path and os.path.exists(meta_path):
            os.remove(meta_path)
        if thumb_local_path:
            self._remove_preset_thumb(thumb_local_path)
        return self._json_ok(
            {
                "success": True,
                "nodeType": preset_type,
                "title": title,
            }
        )

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
        if path == "/api/v2/user/presets/save":
            data, error = self._parse_json_object(body)
            if error is not None:
                return error
            return self._save_preset(handler, data)

        if path == "/api/v2/user/presets/delete":
            data, error = self._parse_json_object(body)
            if error is not None:
                return error
            return self._delete_preset(data)

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
                relative_prefix="data/assets/workflows/thumbs",
            )

        return None
