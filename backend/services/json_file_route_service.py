import json
import os
import re
from urllib.parse import parse_qs, unquote, urlparse


class JsonFileRouteService:
    def __init__(
        self,
        *,
        canvas_dir_getter,
        assets_dir_getter,
        workflows_dir_getter,
        user_dir_getter,
        read_user_settings,
        write_user_settings,
        atomic_write_json,
        output_dir_getter=None,
    ):
        self._get_canvas_dir = canvas_dir_getter
        self._get_assets_dir = assets_dir_getter
        self._get_workflows_dir = workflows_dir_getter
        self._get_user_dir = user_dir_getter
        self._read_user_settings = read_user_settings
        self._write_user_settings = write_user_settings
        self._atomic_write_json = atomic_write_json
        self._get_output_dir = output_dir_getter

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
            return None, JsonFileRouteService._json_err(400, "Invalid JSON")
        if not isinstance(data, dict):
            return None, JsonFileRouteService._json_err(400, "Invalid JSON")
        return data, None

    @staticmethod
    def _parse_json_value(body):
        try:
            return json.loads(body), None
        except json.JSONDecodeError:
            return None, JsonFileRouteService._json_err(400, "Invalid JSON")

    @staticmethod
    def _safe_json_filename(filename):
        name = str(filename or "")
        return bool(name and name.endswith(".json") and "/" not in name and ".." not in name)

    @staticmethod
    def _valid_json_path_fragment(filename):
        name = str(filename or "")
        return bool(name and name.endswith(".json") and ".." not in name)

    @staticmethod
    def _safe_name(value):
        return re.sub(r'[\\/:*?"<>|]', "_", str(value or ""))

    @staticmethod
    def _load_json_file(path, default=None):
        try:
            with open(path, "r", encoding="utf-8-sig") as file:
                return json.load(file)
        except Exception:
            return default

    @staticmethod
    def _write_json_file(path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def _list_projects(self):
        canvas_dir = self._get_canvas_dir()
        files = []
        for filename in os.listdir(canvas_dir):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(canvas_dir, filename)
            files.append(
                {
                    "filename": filename,
                    "name": filename[:-5],
                    "mtime": os.path.getmtime(path),
                }
            )
        files.sort(key=lambda item: item["mtime"], reverse=True)
        return files

    def _load_project(self, path):
        filename = unquote(path[len("/api/v2/projects/") :])
        if not filename or ".." in filename:
            return None
        project_path = os.path.join(self._get_canvas_dir(), filename)
        if not os.path.exists(project_path):
            return self._json_err(404, "Project not found")
        with open(project_path, "r", encoding="utf-8-sig") as file:
            return self._json_ok(json.load(file))

    def _list_json_objects(self, directory, *, id_from_filename=False):
        items = []
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                if not filename.endswith(".json"):
                    continue
                path = os.path.join(directory, filename)
                data = self._load_json_file(path)
                if isinstance(data, dict):
                    if id_from_filename and not data.get("id"):
                        data["id"] = filename[:-5]
                    items.append(data)
        return items

    @staticmethod
    def _first_query_value(query, key, default=""):
        values = query.get(str(key)) or []
        if not values:
            return default
        return str(values[0] or "").strip()

    @staticmethod
    def _parse_int(value, default, *, min_value=None, max_value=None):
        try:
            next_value = int(str(value).strip())
        except Exception:
            next_value = int(default)
        if min_value is not None:
            next_value = max(int(min_value), next_value)
        if max_value is not None:
            next_value = min(int(max_value), next_value)
        return next_value

    @staticmethod
    def _normalize_virtual_path(value):
        text = str(value or "").strip().replace("\\", "/")
        if not text:
            return ""
        parsed = urlparse(text)
        if parsed.scheme in ("http", "https", "blob", "data", "file", "javascript"):
            return ""
        if parsed.scheme and not text.startswith("/"):
            return ""
        return unquote(text).strip().lstrip("/")

    @classmethod
    def _asset_primary_media_paths(cls, asset):
        paths = []

        def push(value):
            text = str(value or "").strip()
            if text:
                paths.append(text)

        node = None
        nodes = asset.get("nodes") if isinstance(asset, dict) else None
        if isinstance(nodes, list) and nodes:
            node = nodes[0] if isinstance(nodes[0], dict) else None
        if isinstance(node, dict):
            for key in ("localPath", "videoUrl", "audioUrl", "imageUrl"):
                push(node.get(key))

        push(asset.get("coverUrl") if isinstance(asset, dict) else "")
        items = asset.get("items") if isinstance(asset, dict) else None
        if isinstance(items, list) and items:
            first_item = items[0] if isinstance(items[0], dict) else None
            if isinstance(first_item, dict):
                push(first_item.get("thumbSrc"))
        return paths

    def _output_virtual_path_exists(self, virtual_path):
        local_path = self._normalize_virtual_path(virtual_path)
        if not local_path.startswith("output/"):
            return True
        if not self._get_output_dir:
            return True
        output_dir = os.path.abspath(self._get_output_dir())
        rel_path = local_path[len("output/") :].lstrip("/")
        abs_path = os.path.abspath(os.path.join(output_dir, *rel_path.split("/")))
        try:
            if os.path.commonpath([abs_path, output_dir]) != output_dir:
                return False
        except Exception:
            return False
        return os.path.exists(abs_path)

    def _generation_history_media_exists(self, asset):
        if not isinstance(asset, dict):
            return False
        if str(asset.get("kind") or "").strip() != "generation-history":
            return True
        for path in self._asset_primary_media_paths(asset):
            local_path = self._normalize_virtual_path(path)
            if local_path.startswith("output/"):
                return self._output_virtual_path_exists(local_path)
        return True

    def _list_assets(self, handler, path):
        assets = self._list_json_objects(self._get_assets_dir(), id_from_filename=True)
        raw_query = getattr(handler, "path", path) if handler is not None else path
        query = parse_qs(urlparse(str(raw_query or "")).query, keep_blank_values=True)
        if not query:
            return assets

        kind = self._first_query_value(query, "kind")
        project_id = self._first_query_value(query, "projectId")
        media_kind = self._first_query_value(query, "mediaKind")
        order = str(self._first_query_value(query, "order", "desc") or "desc").lower()
        if order not in ("asc", "desc"):
            order = "desc"
        offset = self._parse_int(self._first_query_value(query, "offset", "0"), 0, min_value=0)
        limit = self._parse_int(
            self._first_query_value(query, "limit", "80"),
            80,
            min_value=1,
            max_value=200,
        )

        filtered = []
        for asset in assets:
            if kind and str(asset.get("kind") or "").strip() != kind:
                continue
            if project_id and str(asset.get("projectId") or "").strip() != project_id:
                continue
            if media_kind and str(asset.get("mediaKind") or "").strip().lower() != media_kind.lower():
                continue
            if not self._generation_history_media_exists(asset):
                continue
            filtered.append(asset)

        filtered.sort(
            key=lambda item: float(item.get("updatedAt") or item.get("createdAt") or 0),
            reverse=order == "desc",
        )
        total = len(filtered)
        items = filtered[offset : offset + limit]
        next_offset = offset + len(items)
        has_more = next_offset < total
        return {
            "items": items,
            "total": total,
            "nextOffset": next_offset if has_more else None,
            "hasMore": has_more,
        }

    def _load_user_json(self, path):
        filename = path[len("/api/v2/user/") :]
        if not self._safe_json_filename(filename):
            return None
        if filename == "settings.json":
            return self._json_ok(self._read_user_settings())
        file_path = os.path.join(self._get_user_dir(), filename)
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8-sig") as file:
                return self._json_ok(json.load(file))
        return self._json_ok({})

    def _save_project(self, body):
        data, error = self._parse_json_object(body)
        if error is not None:
            return error
        name = str(data.get("projectName", "未命名画布")).strip() or "未命名画布"
        filename = self._safe_name(name) + ".json"
        path = os.path.join(self._get_canvas_dir(), filename)
        if "canvases" in data:
            payload = {
                "canvases": data["canvases"],
                "activeCanvasId": data.get("activeCanvasId", "canvas_1"),
            }
        else:
            payload = {
                "nodes": data.get("nodes", {}),
                "edges": data.get("edges", {}),
                "viewport": data.get("viewport", {}),
            }
        self._atomic_write_json(path, payload)
        return self._json_ok({"success": True, "filename": filename})

    def _save_asset(self, body):
        data, error = self._parse_json_object(body)
        if error is not None:
            return error
        asset_id = data.get("id")
        if not asset_id:
            return self._json_err(400, "Asset ID required")
        filename = self._safe_name(asset_id) + ".json"
        self._write_json_file(os.path.join(self._get_assets_dir(), filename), data)
        return self._json_ok({"success": True, "id": asset_id})

    def _save_workflow(self, body):
        data, error = self._parse_json_object(body)
        if error is not None:
            return error
        workflow_id = data.get("id")
        if not workflow_id:
            return self._json_err(400, "Workflow ID required")
        filename = self._safe_name(workflow_id) + ".json"
        if not data.get("scope"):
            data["scope"] = "private"
        self._write_json_file(os.path.join(self._get_workflows_dir(), filename), data)
        return self._json_ok({"success": True, "id": workflow_id})

    def _save_user_json(self, path, body):
        filename = path[len("/api/v2/user/") :]
        if not self._safe_json_filename(filename):
            return self._json_err(400, "Invalid filename")
        data, error = self._parse_json_value(body)
        if error is not None:
            return error
        if filename == "settings.json":
            try:
                self._write_user_settings(data)
            except ValueError as exc:
                return self._json_err(400, str(exc))
            return self._json_ok(
                {
                    "success": True,
                    "settings": self._read_user_settings(),
                }
            )
        self._write_json_file(os.path.join(self._get_user_dir(), filename), data)
        return self._json_ok({"success": True})

    def _delete_json_file(self, path, *, prefix, directory, not_found_message):
        filename = unquote(path[len(prefix) :])
        if not self._valid_json_path_fragment(filename):
            return self._json_err(400, "Invalid request")
        file_path = os.path.join(directory, filename)
        if not os.path.exists(file_path):
            return self._json_err(404, not_found_message)
        os.remove(file_path)
        return self._json_ok({"success": True})

    def _rename_project(self, path, body):
        filename = unquote(path[len("/api/v2/projects/") :])
        if not self._valid_json_path_fragment(filename):
            return self._json_err(400, "Invalid request")
        file_path = os.path.join(self._get_canvas_dir(), filename)
        if not os.path.exists(file_path):
            return self._json_err(404, "Project not found")
        data, error = self._parse_json_object(body)
        if error is not None:
            return error
        new_name = str(data.get("name") or "").strip()
        if not new_name:
            return self._json_err(400, "Name required")
        new_filename = self._safe_name(new_name) + ".json"
        os.rename(file_path, os.path.join(self._get_canvas_dir(), new_filename))
        return self._json_ok({"success": True, "filename": new_filename})

    def handle_get(self, handler, path):
        if path == "/api/v2/projects":
            return self._json_ok(self._list_projects())

        if path.startswith("/api/v2/projects/") and not path.endswith("/save"):
            return self._load_project(path)

        if path == "/api/v2/assets":
            return self._json_ok(self._list_assets(handler, path))

        if path == "/api/v2/workflows":
            return self._json_ok(
                self._list_json_objects(self._get_workflows_dir(), id_from_filename=True)
            )

        if path.startswith("/api/v2/user/") and not path.startswith("/api/v2/user/presets"):
            return self._load_user_json(path)

        return None

    def handle_post(self, handler, path, body):
        if path == "/api/v2/projects/save":
            return self._save_project(body)

        if path == "/api/v2/assets/save":
            return self._save_asset(body)

        if path == "/api/v2/workflows/save":
            return self._save_workflow(body)

        if path.startswith("/api/v2/user/"):
            return self._save_user_json(path, body)

        return None

    def handle_delete(self, handler, path):
        if path.startswith("/api/v2/projects/"):
            return self._delete_json_file(
                path,
                prefix="/api/v2/projects/",
                directory=self._get_canvas_dir(),
                not_found_message="Project not found",
            )

        if path.startswith("/api/v2/assets/"):
            return self._delete_json_file(
                path,
                prefix="/api/v2/assets/",
                directory=self._get_assets_dir(),
                not_found_message="Asset not found",
            )

        if path.startswith("/api/v2/workflows/"):
            return self._delete_json_file(
                path,
                prefix="/api/v2/workflows/",
                directory=self._get_workflows_dir(),
                not_found_message="Workflow not found",
            )

        return None

    def handle_patch(self, handler, path, body):
        if path.startswith("/api/v2/projects/"):
            return self._rename_project(path, body)

        return None
