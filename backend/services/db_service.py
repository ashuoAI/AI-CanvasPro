import os
import threading
import time
import logging

logger = logging.getLogger(__name__)


class DatabaseConfig:
    def __init__(
        self,
        host=None,
        port=None,
        user=None,
        password=None,
        database=None,
        charset="utf8mb4",
        pool_size=5,
        pool_recycle=3600,
        connect_timeout=10,
    ):
        self.host = str(host or os.environ.get("DESIGN_TEAM_DB_HOST", "127.0.0.1")).strip()
        self.port = int(port or os.environ.get("DESIGN_TEAM_DB_PORT", "3306"))
        self.user = str(user or os.environ.get("DESIGN_TEAM_DB_USER", "root")).strip()
        self.password = str(password or os.environ.get("DESIGN_TEAM_DB_PASSWORD", "zw246888")).strip()
        self.database = str(database or os.environ.get("DESIGN_TEAM_DB_NAME", "design_team_db")).strip()
        self.charset = str(charset or "utf8mb4")
        self.pool_size = max(1, int(pool_size or 5))
        self.pool_recycle = max(60, int(pool_recycle or 3600))
        self.connect_timeout = max(1, int(connect_timeout or 10))

    def as_dict(self):
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "charset": self.charset,
            "connect_timeout": self.connect_timeout,
        }


class DatabaseService:
    _instance = None
    _lock = threading.Lock()

    def __init__(self, config=None):
        self._config = config if isinstance(config, DatabaseConfig) else DatabaseConfig()
        self._pool = None
        self._pool_lock = threading.Lock()
        self._pymysql = None

    @classmethod
    def get_instance(cls, config=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(config)
        return cls._instance

    def _ensure_pymysql(self):
        if self._pymysql is not None:
            return self._pymysql
        try:
            import pymysql
            self._pymysql = pymysql
            return pymysql
        except ImportError:
            raise ImportError(
                "pymysql is required for database operations. "
                "Install it with: pip install pymysql"
            )

    def _create_connection(self):
        pymysql = self._ensure_pymysql()
        cfg = self._config.as_dict()
        return pymysql.connect(
            **cfg,
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
        )

    def get_connection(self):
        return self._create_connection()

    def execute_query(self, sql, params=None, fetch_one=False):
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql, params or ())
                if sql.strip().upper().startswith("SELECT"):
                    if fetch_one:
                        result = cursor.fetchone()
                    else:
                        result = cursor.fetchall()
                    return result
                else:
                    conn.commit()
                    return cursor.rowcount
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            logger.error("Database query error: %s", str(e))
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def execute_many(self, sql, params_list):
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.executemany(sql, params_list)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            logger.error("Database executemany error: %s", str(e))
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def test_connection(self):
        try:
            result = self.execute_query("SELECT 1 AS ok", fetch_one=True)
            return bool(result and result.get("ok") == 1)
        except Exception as e:
            logger.warning("Database connection test failed: %s", str(e))
            return False

    def init_database(self, sql_file_path=None):
        if sql_file_path is None:
            sql_file_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "sql",
                "init_database.sql",
            )
        if not os.path.exists(sql_file_path):
            logger.warning("SQL init file not found: %s", sql_file_path)
            return False
        try:
            with open(sql_file_path, "r", encoding="utf-8") as f:
                sql_content = f.read()
            statements = self._split_sql_statements(sql_content)
            conn = self.get_connection()
            try:
                with conn.cursor() as cursor:
                    for stmt in statements:
                        stmt = stmt.strip()
                        if not stmt:
                            continue
                        try:
                            cursor.execute(stmt)
                        except Exception as e:
                            logger.warning("SQL statement warning: %s", str(e))
                    conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                logger.error("Database init error: %s", str(e))
                return False
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as e:
            logger.error("Failed to read SQL init file: %s", str(e))
            return False

    @staticmethod
    def _split_sql_statements(sql_content):
        statements = []
        current = []
        for line in sql_content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("--") or stripped.startswith("#"):
                continue
            if not stripped:
                if current:
                    statements.append("\n".join(current))
                    current = []
                continue
            current.append(line)
            if stripped.endswith(";"):
                stmt = "\n".join(current)
                stmt = stmt.rstrip(";").strip()
                if stmt:
                    statements.append(stmt)
                current = []
        if current:
            stmt = "\n".join(current).rstrip(";").strip()
            if stmt:
                statements.append(stmt)
        return statements