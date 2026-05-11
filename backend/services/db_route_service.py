import json
import urllib.parse

from .user_auth_service import UserAuthService
from .project_data_service import ProjectDataService
from .settings_data_service import SettingsDataService


class DatabaseRouteService:
    def __init__(
        self,
        *,
        user_auth_service=None,
        project_data_service=None,
        settings_data_service=None,
    ):
        self._auth = user_auth_service or UserAuthService()
        self._projects = project_data_service or ProjectDataService()
        self._settings = settings_data_service or SettingsDataService()

    @staticmethod
    def _json_ok(data):
        return {"kind": "json_ok", "data": data}

    @staticmethod
    def _json_err(code, message):
        return {"kind": "json_err", "code": int(code), "message": str(message or "")}

    @staticmethod
    def _parse_body(body):
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return None, "Invalid JSON"
        if not isinstance(data, dict):
            return None, "Request body must be a JSON object"
        return data, None

    def _authenticate(self, handler):
        token = self._auth.extract_token_from_request(handler)
        if not token:
            return None, self._json_err(401, "Missing authentication token")

        user = self._auth.validate_jwt(token)
        if user:
            return user, None

        user = self._auth.validate_token(token)
        if user:
            return user, None

        return None, self._json_err(401, "Invalid or expired token")

    def _get_query_param(self, handler, key, default=None):
        parsed = urllib.parse.urlparse(str(handler.path or ""))
        qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True, max_num_fields=50)
        values = qs.get(str(key), [])
        return values[0] if values else default

    def _get_int_query_param(self, handler, key, default=0):
        raw = self._get_query_param(handler, key)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    def handle_get(self, handler, path):
        clean_path = str(path or "").split("?", 1)[0].rstrip("/") or "/"

        if clean_path == "/api/v2/db/health":
            return self._handle_health()

        if clean_path == "/api/v2/db/auth/validate":
            return self._handle_validate_token(handler)

        if clean_path == "/api/v2/db/auth/user-info":
            return self._handle_get_user_info(handler)

        if clean_path == "/api/v2/db/projects":
            return self._handle_list_projects(handler)

        if clean_path.startswith("/api/v2/db/projects/"):
            project_id = clean_path[len("/api/v2/db/projects/"):]
            if project_id:
                return self._handle_get_project(handler, project_id)

        if clean_path == "/api/v2/db/settings":
            return self._handle_get_settings(handler)

        return None

    def handle_post(self, handler, path, body):
        clean_path = str(path or "").split("?", 1)[0].rstrip("/") or "/"

        if clean_path == "/api/v2/db/auth/login":
            return self._handle_login(handler, body)

        if clean_path == "/api/v2/db/auth/logout":
            return self._handle_logout(handler, body)

        if clean_path == "/api/v2/db/auth/generate-token":
            return self._handle_generate_token(handler, body)

        if clean_path == "/api/v2/db/projects":
            return self._handle_create_project(handler, body)

        if clean_path.startswith("/api/v2/db/projects/"):
            project_id = clean_path[len("/api/v2/db/projects/"):]
            if project_id.endswith("/duplicate"):
                pid = project_id[:-len("/duplicate")]
                return self._handle_duplicate_project(handler, pid, body)
            if project_id.endswith("/delete"):
                pid = project_id[:-len("/delete")]
                return self._handle_delete_project(handler, pid)
            if project_id:
                return self._handle_update_project(handler, project_id, body)

        if clean_path == "/api/v2/db/settings":
            return self._handle_update_settings(handler, body)

        if clean_path == "/api/v2/db/settings/reset":
            return self._handle_reset_settings(handler, body)

        return None

    def handle_delete(self, handler, path):
        clean_path = str(path or "").split("?", 1)[0].rstrip("/") or "/"

        if clean_path.startswith("/api/v2/db/projects/"):
            project_id = clean_path[len("/api/v2/db/projects/"):]
            if project_id:
                return self._handle_delete_project(handler, project_id)

        return None

    def _handle_health(self):
        from .db_service import DatabaseService
        db = DatabaseService.get_instance()
        db_ok = db.test_connection()
        return self._json_ok({
            "status": "ok" if db_ok else "degraded",
            "database": "connected" if db_ok else "disconnected",
            "service": "ai-canvaspro-db",
        })

    def _handle_login(self, handler, body=None):
        data, err = self._parse_body(body)
        if err:
            return self._json_err(400, err)
        username = str(data.get("username") or "").strip()
        password = str(data.get("password") or "").strip()

        if not username or not password:
            return self._json_err(400, "Username and password are required")

        user = self._auth.verify_user_credentials(username, password)
        if not user:
            return self._json_err(401, "Invalid username or password")

        expire_seconds = None
        try:
            expire_seconds = int(data.get("expire_seconds", 0)) or None
        except (TypeError, ValueError):
            pass

        jwt_info = self._auth.generate_jwt(user, expire_seconds)
        return self._json_ok({
            "success": True,
            "user": user,
            "token": jwt_info["token"],
            "expires_at": jwt_info["expires_at"],
        })

    def _handle_logout(self, handler, body):
        user, err = self._authenticate(handler)
        if err:
            return err
        token = self._auth.extract_token_from_request(handler)
        self._auth.revoke_token(token)
        return self._json_ok({"success": True, "message": "Logged out successfully"})

    def _handle_generate_token(self, handler, body):
        data, err = self._parse_body(body)
        if err:
            return self._json_err(400, err)
        user_id = data.get("user_id")
        if not user_id:
            return self._json_err(400, "user_id is required")
        expire_seconds = None
        try:
            expire_seconds = int(data.get("expire_seconds", 0)) or None
        except (TypeError, ValueError):
            pass
        token_info = self._auth.generate_auth_token(int(user_id), expire_seconds)
        return self._json_ok({
            "success": True,
            "token": token_info["token"],
            "expires_at": token_info["expires_at"],
        })

    def _handle_validate_token(self, handler):
        user, err = self._authenticate(handler)
        if err:
            return err
        user_info = self._auth.get_user_info(user["user_id"])
        return self._json_ok({
            "success": True,
            "valid": True,
            "user": user_info or {"user_id": user["user_id"]},
        })

    def _handle_get_user_info(self, handler):
        user, err = self._authenticate(handler)
        if err:
            return err
        user_info = self._auth.get_user_info(user["user_id"])
        if not user_info:
            return self._json_err(404, "User not found")
        return self._json_ok({"success": True, "user": user_info})

    def _handle_list_projects(self, handler):
        user, err = self._authenticate(handler)
        if err:
            return err
        status = self._get_query_param(handler, "status")
        keyword = self._get_query_param(handler, "keyword")
        limit = self._get_int_query_param(handler, "limit", 50)
        offset = self._get_int_query_param(handler, "offset", 0)

        if keyword:
            projects = self._projects.search_user_projects(
                user["user_id"], keyword, limit=limit, offset=offset
            )
        else:
            projects = self._projects.get_user_projects(
                user["user_id"], status=status, limit=limit, offset=offset
            )
        total = self._projects.count_user_projects(user["user_id"], status=status)

        return self._json_ok({
            "success": True,
            "projects": projects,
            "total": total,
            "limit": limit,
            "offset": offset,
        })

    def _handle_get_project(self, handler, project_id):
        user, err = self._authenticate(handler)
        if err:
            return err
        project = self._projects.get_project_by_id(project_id)
        if not project:
            return self._json_err(404, "Project not found")
        if project["user_id"] != user["user_id"]:
            return self._json_err(403, "Access denied")
        return self._json_ok({"success": True, "project": project})

    def _handle_create_project(self, handler, body):
        user, err = self._authenticate(handler)
        if err:
            return err
        data, parse_err = self._parse_body(body)
        if parse_err:
            return self._json_err(400, parse_err)

        project_name = str(data.get("project_name") or data.get("projectName") or "").strip()
        if not project_name:
            return self._json_err(400, "project_name is required")

        project = self._projects.create_project(
            user_id=user["user_id"],
            project_name=project_name,
            project_description=data.get("project_description") or data.get("projectDescription"),
            canvas_name=data.get("canvas_name") or data.get("canvasName"),
            project_data=data.get("project_data") or data.get("projectData"),
        )
        return self._json_ok({"success": True, "project": project})

    def _handle_update_project(self, handler, project_id, body):
        user, err = self._authenticate(handler)
        if err:
            return err
        existing = self._projects.get_project_by_id(project_id)
        if not existing:
            return self._json_err(404, "Project not found")
        if existing["user_id"] != user["user_id"]:
            return self._json_err(403, "Access denied")

        data, parse_err = self._parse_body(body)
        if parse_err:
            return self._json_err(400, parse_err)

        update_kwargs = {}
        field_mapping = {
            "project_name": "project_name",
            "projectName": "project_name",
            "project_description": "project_description",
            "projectDescription": "project_description",
            "thumbnail": "thumbnail",
            "project_data": "project_data",
            "projectData": "project_data",
            "project_status": "project_status",
            "projectStatus": "project_status",
            "canvas_name": "canvas_name",
            "canvasName": "canvas_name",
        }
        for src_key, dst_key in field_mapping.items():
            if src_key in data:
                update_kwargs[dst_key] = data[src_key]

        if not update_kwargs:
            return self._json_err(400, "No valid fields to update")

        project = self._projects.update_project(project_id, **update_kwargs)
        return self._json_ok({"success": True, "project": project})

    def _handle_delete_project(self, handler, project_id):
        user, err = self._authenticate(handler)
        if err:
            return err
        existing = self._projects.get_project_by_id(project_id)
        if not existing:
            return self._json_err(404, "Project not found")
        if existing["user_id"] != user["user_id"]:
            return self._json_err(403, "Access denied")

        hard = self._get_query_param(handler, "hard") in ("1", "true", "yes")
        if hard:
            self._projects.hard_delete_project(project_id)
        else:
            self._projects.soft_delete_project(project_id)
        return self._json_ok({"success": True, "message": "Project deleted"})

    def _handle_duplicate_project(self, handler, project_id, body):
        user, err = self._authenticate(handler)
        if err:
            return err
        existing = self._projects.get_project_by_id(project_id)
        if not existing:
            return self._json_err(404, "Project not found")
        if existing["user_id"] != user["user_id"]:
            return self._json_err(403, "Access denied")

        data, _ = self._parse_body(body)
        new_name = None
        if data:
            new_name = data.get("project_name") or data.get("projectName")

        project = self._projects.duplicate_project(project_id, user["user_id"], new_name)
        if not project:
            return self._json_err(500, "Failed to duplicate project")
        return self._json_ok({"success": True, "project": project})

    def _handle_get_settings(self, handler):
        user, err = self._authenticate(handler)
        if err:
            return err
        settings = self._settings.get_settings(user["user_id"])
        return self._json_ok({"success": True, "settings": settings})

    def _handle_update_settings(self, handler, body):
        user, err = self._authenticate(handler)
        if err:
            return err
        data, parse_err = self._parse_body(body)
        if parse_err:
            return self._json_err(400, parse_err)

        field_mapping = {
            "theme": "theme",
            "language": "language",
            "canvas_preferences": "canvas_preferences",
            "canvasPreferences": "canvas_preferences",
            "node_behavior": "node_behavior",
            "nodeBehavior": "node_behavior",
            "appearance": "appearance",
            "notification": "notification",
            "shortcuts": "shortcuts",
            "other_settings": "other_settings",
            "otherSettings": "other_settings",
        }
        update_kwargs = {}
        for src_key, dst_key in field_mapping.items():
            if src_key in data:
                update_kwargs[dst_key] = data[src_key]

        if not update_kwargs:
            return self._json_err(400, "No valid settings fields to update")

        settings = self._settings.update_settings(user["user_id"], **update_kwargs)
        return self._json_ok({"success": True, "settings": settings})

    def _handle_reset_settings(self, handler, body):
        user, err = self._authenticate(handler)
        if err:
            return err
        settings = self._settings.reset_settings(user["user_id"])
        return self._json_ok({"success": True, "settings": settings})