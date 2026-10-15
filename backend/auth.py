"""Password hashing (PBKDF2-SHA256, standard library) and bearer-token sessions."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from . import config
from .database import get_conn, one

ITERATIONS = 120_000


def hash_password(password, salt_hex=None):
    salt_hex = salt_hex or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), ITERATIONS).hex()
    return digest, salt_hex


def create_user(conn, username, full_name, role, password):
    digest, salt = hash_password(password)
    conn.execute("INSERT INTO users (username, full_name, role, password_hash, salt) VALUES (?,?,?,?,?)",
                 (username, full_name, role, digest, salt))


def login(username, password):
    u = one("SELECT * FROM users WHERE username = ? AND role <> 'SYSTEM'", (username,))
    if not u:
        hash_password(password)  # same work either way, so timing does not reveal valid usernames
        return None
    digest, _ = hash_password(password, u["salt"])
    if not hmac.compare_digest(digest, u["password_hash"]):
        return None
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=config.SESSION_HOURS)).isoformat()
    get_conn().execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?,?,?)",
                       (token, u["user_id"], expires))
    return {"token": token, "username": u["username"], "full_name": u["full_name"], "role": u["role"]}


def user_for_token(token):
    if not token:
        return None
    u = one("SELECT u.user_id, u.username, u.full_name, u.role, s.expires_at FROM sessions s "
            "JOIN users u ON u.user_id = s.user_id WHERE s.token = ?", (token,))
    if not u or u["expires_at"] < datetime.now(timezone.utc).isoformat():
        return None
    return u


def logout(token):
    get_conn().execute("DELETE FROM sessions WHERE token = ?", (token,))
