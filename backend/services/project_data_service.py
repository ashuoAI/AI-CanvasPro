import json
import uuid
from datetime import datetime

from .db_service import DatabaseService


class ProjectDataService:
    VALID_STATUSES = ("draft", "active", "archived", "deleted")

    def __init__(self, db_service=None):
        self._db = db_service if db_service is not None else DatabaseService.get_instance()

    def create_project(self, user_id, project_name, project_description=None, canvas_name=None, project_data=None):
        project_id = str(uuid.uuid4())
        now = datetime.now()
        sql = """
            INSERT INTO personal_projects
                (project_id, user_id, project_name, project_description, canvas_name, project_data, project_status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'draft', %s, %s)
        """
        self._db.execute_query(
            sql,
            (
                project_id,
                int(user_id),
                str(project_name),
                str(project_description) if project_description else None,
                str(canvas_name) if canvas_name else None,
                json.dumps(project_data, ensure_ascii=False) if project_data else None,
                now,
                now,
            ),
        )
        return self.get_project_by_id(project_id)

    def get_project_by_id(self, project_id):
        sql = """
            SELECT id, project_id, user_id, project_name, project_description,
                   thumbnail, project_data, project_status, canvas_name,
                   created_at, updated_at
            FROM personal_projects
            WHERE project_id = %s AND project_status != 'deleted'
        """
        result = self._db.execute_query(sql, (str(project_id),), fetch_one=True)
        return self._format_project(result) if result else None

    def get_user_projects(self, user_id, status=None, limit=50, offset=0):
        conditions = ["user_id = %s", "project_status != 'deleted'"]
        params = [int(user_id)]
        if status and status in self.VALID_STATUSES:
            conditions.append("project_status = %s")
            params.append(status)
        where = " AND ".join(conditions)
        sql = f"""
            SELECT id, project_id, user_id, project_name, project_description,
                   thumbnail, project_data, project_status, canvas_name,
                   created_at, updated_at
            FROM personal_projects
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([int(limit), int(offset)])
        results = self._db.execute_query(sql, tuple(params))
        return [self._format_project(r) for r in (results or [])]

    def count_user_projects(self, user_id, status=None):
        conditions = ["user_id = %s", "project_status != 'deleted'"]
        params = [int(user_id)]
        if status and status in self.VALID_STATUSES:
            conditions.append("project_status = %s")
            params.append(status)
        where = " AND ".join(conditions)
        sql = f"SELECT COUNT(*) AS total FROM personal_projects WHERE {where}"
        result = self._db.execute_query(sql, tuple(params), fetch_one=True)
        return result["total"] if result else 0

    def update_project(self, project_id, **kwargs):
        allowed_fields = {
            "project_name", "project_description", "thumbnail",
            "project_data", "project_status", "canvas_name",
        }
        updates = {}
        params = []
        for key, value in kwargs.items():
            if key not in allowed_fields:
                continue
            if key == "project_data" and value is not None:
                value = json.dumps(value, ensure_ascii=False)
            if key == "project_status" and value not in self.VALID_STATUSES:
                continue
            updates[key] = value
            params.append(value)
        if not updates:
            return self.get_project_by_id(project_id)
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        params.append(str(project_id))
        sql = f"""
            UPDATE personal_projects
            SET {set_clause}, updated_at = NOW()
            WHERE project_id = %s AND project_status != 'deleted'
        """
        self._db.execute_query(sql, tuple(params))
        return self.get_project_by_id(project_id)

    def soft_delete_project(self, project_id):
        sql = """
            UPDATE personal_projects
            SET project_status = 'deleted', updated_at = NOW()
            WHERE project_id = %s
        """
        return self._db.execute_query(sql, (str(project_id),))

    def hard_delete_project(self, project_id):
        sql = "DELETE FROM personal_projects WHERE project_id = %s"
        return self._db.execute_query(sql, (str(project_id),))

    def duplicate_project(self, project_id, user_id, new_name=None):
        original = self.get_project_by_id(project_id)
        if not original:
            return None
        return self.create_project(
            user_id=user_id,
            project_name=new_name or f"{original['project_name']} (副本)",
            project_description=original.get("project_description"),
            canvas_name=original.get("canvas_name"),
            project_data=original.get("project_data"),
        )

    def search_user_projects(self, user_id, keyword, limit=50, offset=0):
        sql = """
            SELECT id, project_id, user_id, project_name, project_description,
                   thumbnail, project_data, project_status, canvas_name,
                   created_at, updated_at
            FROM personal_projects
            WHERE user_id = %s
              AND project_status != 'deleted'
              AND (project_name LIKE %s OR project_description LIKE %s)
            ORDER BY updated_at DESC
            LIMIT %s OFFSET %s
        """
        like_keyword = f"%{keyword}%"
        results = self._db.execute_query(
            sql,
            (int(user_id), like_keyword, like_keyword, int(limit), int(offset)),
        )
        return [self._format_project(r) for r in (results or [])]

    @staticmethod
    def _format_project(row):
        if not row:
            return None
        project_data = row.get("project_data")
        if isinstance(project_data, str):
            try:
                project_data = json.loads(project_data)
            except (json.JSONDecodeError, TypeError):
                project_data = None
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "user_id": row["user_id"],
            "project_name": row["project_name"],
            "project_description": row.get("project_description"),
            "thumbnail": row.get("thumbnail"),
            "project_data": project_data,
            "project_status": row["project_status"],
            "canvas_name": row.get("canvas_name"),
            "created_at": row["created_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("created_at") else None,
            "updated_at": row["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("updated_at") else None,
        }