import json
from datetime import datetime

from .db_service import DatabaseService


class SettingsDataService:
    ALLOWED_SETTING_FIELDS = {
        "theme", "language", "canvas_preferences",
        "node_behavior", "appearance", "notification",
        "shortcuts", "other_settings",
    }

    DEFAULT_SETTINGS = {
        "theme": "auto",
        "language": "zh-CN",
        "canvas_preferences": {
            "showGrid": True,
            "snapToGrid": True,
            "gridSize": 20,
            "zoomSensitivity": 1.0,
        },
        "node_behavior": {
            "defaultImageWidth": 512,
            "defaultImageHeight": 512,
            "autoSaveInterval": 300,
        },
        "appearance": {
            "fontSize": 14,
            "compactMode": False,
            "showMinimap": True,
        },
        "notification": {
            "taskComplete": True,
            "taskFailed": True,
            "soundEnabled": True,
        },
        "shortcuts": {},
        "other_settings": {},
    }

    def __init__(self, db_service=None):
        self._db = db_service if db_service is not None else DatabaseService.get_instance()

    def get_settings(self, user_id):
        sql = """
            SELECT id, user_id, theme, language,
                   canvas_preferences, node_behavior, appearance,
                   notification, shortcuts, other_settings,
                   created_at, updated_at
            FROM personal_settings
            WHERE user_id = %s
        """
        result = self._db.execute_query(sql, (int(user_id),), fetch_one=True)
        if result:
            return self._format_settings(result)
        return self._create_default_settings(user_id)

    def _create_default_settings(self, user_id):
        now = datetime.now()
        sql = """
            INSERT INTO personal_settings
                (user_id, theme, language, canvas_preferences, node_behavior,
                 appearance, notification, shortcuts, other_settings, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        defaults = self.DEFAULT_SETTINGS
        self._db.execute_query(
            sql,
            (
                int(user_id),
                defaults["theme"],
                defaults["language"],
                json.dumps(defaults["canvas_preferences"], ensure_ascii=False),
                json.dumps(defaults["node_behavior"], ensure_ascii=False),
                json.dumps(defaults["appearance"], ensure_ascii=False),
                json.dumps(defaults["notification"], ensure_ascii=False),
                json.dumps(defaults["shortcuts"], ensure_ascii=False),
                json.dumps(defaults["other_settings"], ensure_ascii=False),
                now,
                now,
            ),
        )
        return {
            "user_id": int(user_id),
            "theme": defaults["theme"],
            "language": defaults["language"],
            "canvas_preferences": defaults["canvas_preferences"],
            "node_behavior": defaults["node_behavior"],
            "appearance": defaults["appearance"],
            "notification": defaults["notification"],
            "shortcuts": defaults["shortcuts"],
            "other_settings": defaults["other_settings"],
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def update_settings(self, user_id, **kwargs):
        existing = self.get_settings(user_id)
        if not existing:
            existing = self._create_default_settings(user_id)

        updates = {}
        params = []
        for field in self.ALLOWED_SETTING_FIELDS:
            if field in kwargs:
                value = kwargs[field]
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                updates[field] = value
                params.append(value)

        if not updates:
            return existing

        set_clause = ", ".join(f"{k} = %s" for k in updates)
        params.append(int(user_id))
        sql = f"""
            UPDATE personal_settings
            SET {set_clause}, updated_at = NOW()
            WHERE user_id = %s
        """
        self._db.execute_query(sql, tuple(params))
        return self.get_settings(user_id)

    def update_single_setting(self, user_id, field, value):
        if field not in self.ALLOWED_SETTING_FIELDS:
            raise ValueError(f"Setting field '{field}' is not allowed")
        return self.update_settings(user_id, **{field: value})

    def reset_settings(self, user_id):
        sql = "DELETE FROM personal_settings WHERE user_id = %s"
        self._db.execute_query(sql, (int(user_id),))
        return self._create_default_settings(user_id)

    def delete_settings(self, user_id):
        sql = "DELETE FROM personal_settings WHERE user_id = %s"
        return self._db.execute_query(sql, (int(user_id),))

    @staticmethod
    def _parse_json_field(value):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value

    @classmethod
    def _format_settings(cls, row):
        if not row:
            return None
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "theme": row.get("theme", "auto"),
            "language": row.get("language", "zh-CN"),
            "canvas_preferences": cls._parse_json_field(row.get("canvas_preferences")),
            "node_behavior": cls._parse_json_field(row.get("node_behavior")),
            "appearance": cls._parse_json_field(row.get("appearance")),
            "notification": cls._parse_json_field(row.get("notification")),
            "shortcuts": cls._parse_json_field(row.get("shortcuts")),
            "other_settings": cls._parse_json_field(row.get("other_settings")),
            "created_at": row["created_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("created_at") else None,
            "updated_at": row["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("updated_at") else None,
        }