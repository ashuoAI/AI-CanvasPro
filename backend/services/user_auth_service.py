import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta

from .db_service import DatabaseService


class UserAuthService:
    TOKEN_BYTE_LENGTH = 64
    DEFAULT_TOKEN_EXPIRE_SECONDS = 3600
    DEFAULT_JWT_EXPIRE_SECONDS = 86400

    def __init__(self, db_service=None, token_secret=None, jwt_secret=None):
        self._db = db_service if db_service is not None else DatabaseService.get_instance()
        self._token_secret = str(
            token_secret
            or os.environ.get("AIC_AUTH_TOKEN_SECRET", "")
            or "aicanvaspro-default-secret-change-in-production"
        ).strip()
        self._jwt_secret = str(
            jwt_secret
            or os.environ.get("AIC_JWT_SECRET", "")
            or os.environ.get("JWT_SECRET", "")
            or "design-team-jwt-secret-change-in-production"
        ).strip()

    # ──────────────────────────────────────────────
    #  JWT 令牌（兼容设计管理系统 + 本程序独立登录）
    # ──────────────────────────────────────────────

    def generate_jwt(self, user_info, expire_seconds=None):
        expire_seconds = max(60, int(expire_seconds or self.DEFAULT_JWT_EXPIRE_SECONDS))
        header = {"alg": "HS256", "typ": "JWT"}
        now = int(time.time())
        payload = {
            "sub": str(user_info.get("user_id") or user_info.get("id", "")),
            "username": str(user_info.get("username", "")),
            "role": str(user_info.get("role", "designer")),
            "iat": now,
            "exp": now + expire_seconds,
        }
        header_b64 = self._b64url_encode(json.dumps(header, separators=(",", ":")))
        payload_b64 = self._b64url_encode(json.dumps(payload, separators=(",", ":")))
        signature = hmac.new(
            self._jwt_secret.encode("utf-8"),
            f"{header_b64}.{payload_b64}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        token = f"{header_b64}.{payload_b64}.{signature}"
        return {
            "token": token,
            "expires_at": datetime.fromtimestamp(now + expire_seconds).strftime("%Y-%m-%d %H:%M:%S"),
            "expire_seconds": expire_seconds,
        }

    def validate_jwt(self, token):
        if not token:
            return None
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            header_b64, payload_b64, signature = parts
            expected_sig = hmac.new(
                self._jwt_secret.encode("utf-8"),
                f"{header_b64}.{payload_b64}".encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(signature, expected_sig):
                return None
            payload = json.loads(self._b64url_decode(payload_b64))
            if payload.get("exp", 0) < int(time.time()):
                return None
            return {
                "user_id": int(payload.get("sub", 0)),
                "username": payload.get("username", ""),
                "role": payload.get("role", "designer"),
            }
        except (ValueError, json.JSONDecodeError, AttributeError):
            return None

    # ──────────────────────────────────────────────
    #  API 令牌（HMAC签名，用于跨系统跳转）
    # ──────────────────────────────────────────────

    def generate_auth_token(self, user_id, expire_seconds=None):
        expire_seconds = max(60, int(expire_seconds or self.DEFAULT_TOKEN_EXPIRE_SECONDS))
        raw_token = secrets.token_hex(self.TOKEN_BYTE_LENGTH)
        token = self._sign_token(raw_token)
        expires_at = datetime.now() + timedelta(seconds=expire_seconds)

        sql = """
            INSERT INTO user_auth_tokens (user_id, token, token_type, expires_at)
            VALUES (%s, %s, 'api', %s)
        """
        self._db.execute_query(sql, (int(user_id), token, expires_at))
        return {
            "token": token,
            "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            "expire_seconds": expire_seconds,
        }

    def validate_token(self, token):
        if not token or not self._verify_token_signature(token):
            return None
        sql = """
            SELECT user_id, expires_at
            FROM user_auth_tokens
            WHERE token = %s AND expires_at > NOW()
        """
        result = self._db.execute_query(sql, (str(token),), fetch_one=True)
        if not result:
            return None
        return {
            "user_id": result["user_id"],
            "expires_at": result["expires_at"].strftime("%Y-%m-%d %H:%M:%S") if result.get("expires_at") else None,
        }

    def revoke_token(self, token):
        sql = "DELETE FROM user_auth_tokens WHERE token = %s"
        return self._db.execute_query(sql, (str(token),))

    def revoke_user_tokens(self, user_id):
        sql = "DELETE FROM user_auth_tokens WHERE user_id = %s"
        return self._db.execute_query(sql, (int(user_id),))

    def cleanup_expired_tokens(self):
        sql = "DELETE FROM user_auth_tokens WHERE expires_at <= NOW()"
        return self._db.execute_query(sql)

    # ──────────────────────────────────────────────
    #  用户信息查询（对齐设计管理系统 users 表）
    # ──────────────────────────────────────────────

    def get_user_info(self, user_id):
        sql = """
            SELECT id, username, email, real_name, position, role,
                   daily_cost, phone, design_level_coefficient, avatar,
                   status, created_at
            FROM users
            WHERE id = %s AND status = 'active'
        """
        result = self._db.execute_query(sql, (int(user_id),), fetch_one=True)
        if not result:
            return None
        return {
            "user_id": result["id"],
            "username": result.get("username", ""),
            "email": result.get("email", ""),
            "real_name": result.get("real_name", ""),
            "position": result.get("position", ""),
            "role": result.get("role", "designer"),
            "daily_cost": float(result.get("daily_cost", 0) or 0),
            "phone": result.get("phone", ""),
            "design_level_coefficient": float(result.get("design_level_coefficient", 1) or 1),
            "avatar": result.get("avatar", ""),
            "status": result.get("status", "active"),
            "created_at": result["created_at"].strftime("%Y-%m-%d %H:%M:%S") if result.get("created_at") else None,
        }

    # ──────────────────────────────────────────────
    #  用户凭证验证（独立登录 + 设计管理系统兼容）
    # ──────────────────────────────────────────────

    def verify_user_credentials(self, username, password):
        sql = """
            SELECT id, username, password, email, real_name, position,
                   role, daily_cost, phone, design_level_coefficient, avatar, status
            FROM users
            WHERE username = %s AND status = 'active'
        """
        result = self._db.execute_query(sql, (str(username),), fetch_one=True)
        if not result:
            return None
        stored_password = result.get("password", "")
        if not self._verify_password(password, stored_password):
            return None
        return {
            "user_id": result["id"],
            "username": result.get("username", ""),
            "email": result.get("email", ""),
            "real_name": result.get("real_name", ""),
            "position": result.get("position", ""),
            "role": result.get("role", "designer"),
            "daily_cost": float(result.get("daily_cost", 0) or 0),
            "phone": result.get("phone", ""),
            "design_level_coefficient": float(result.get("design_level_coefficient", 1) or 1),
            "avatar": result.get("avatar", ""),
        }

    # ──────────────────────────────────────────────
    #  签名与验证工具方法
    # ──────────────────────────────────────────────

    def _sign_token(self, raw_token):
        signature = hmac.new(
            self._token_secret.encode("utf-8"),
            raw_token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{raw_token}.{signature}"

    def _verify_token_signature(self, token):
        try:
            raw_token, signature = token.rsplit(".", 1)
            expected = hmac.new(
                self._token_secret.encode("utf-8"),
                raw_token.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(signature, expected)
        except (ValueError, AttributeError):
            return False

    @staticmethod
    def _verify_password(plain_password, stored_hash):
        if not stored_hash or not plain_password:
            return False
        if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$") or stored_hash.startswith("$2y$"):
            try:
                import bcrypt
                return bcrypt.checkpw(plain_password.encode("utf-8"), stored_hash.encode("utf-8"))
            except ImportError:
                pass
        hashed = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(hashed, stored_hash)

    @staticmethod
    def _b64url_encode(data):
        import base64
        return base64.urlsafe_b64encode(data.encode("utf-8")).rstrip(b"=").decode("ascii")

    @staticmethod
    def _b64url_decode(data):
        import base64
        padding = 4 - len(data) % 4
        if padding != 4:
            data += "=" * padding
        return base64.urlsafe_b64decode(data).decode("utf-8")

    # ──────────────────────────────────────────────
    #  从 HTTP 请求中提取 token
    # ──────────────────────────────────────────────

    def extract_token_from_request(self, handler):
        auth_header = str(handler.headers.get("Authorization", "") or "").strip()
        if auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip()
        token = str(handler.headers.get("X-AIC-Auth-Token", "") or "").strip()
        if token:
            return token
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(handler.path)
        qs = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=20)
        for key in ("token", "jwt", "auth_token"):
            val = (qs.get(key) or [""])[0]
            if val.strip():
                return val.strip()
        return None