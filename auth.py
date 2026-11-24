"""Autenticación con contraseñas cifradas (PBKDF2-SHA256 con sal)."""
import hashlib
import hmac
import secrets
import sqlite3

import db

ITERATIONS = 200_000


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()


def create_user(username, full_name, password, role="Operario"):
    username = username.strip().lower()
    if not username or not full_name.strip():
        raise ValueError("Usuario y nombre completo son obligatorios.")
    if len(password) < 6:
        raise ValueError("La contraseña debe tener al menos 6 caracteres.")
    salt = secrets.token_hex(16)
    with db.get_conn() as conn:
        try:
            conn.execute("""INSERT INTO users(username,full_name,role,salt,password_hash,created_at)
                            VALUES(?,?,?,?,?,?)""",
                         (username, full_name.strip(), role, salt, _hash(password, salt), db.now_iso()))
        except sqlite3.IntegrityError:
            raise ValueError("Ese nombre de usuario ya existe.")


def authenticate(username, password):
    """Devuelve un dict con los datos del usuario o None si las credenciales son inválidas."""
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=? AND active=1",
                           (username.strip().lower(),)).fetchone()
    if row is None:
        return None
    if hmac.compare_digest(_hash(password, row["salt"]), row["password_hash"]):
        return {"id": row["id"], "username": row["username"],
                "full_name": row["full_name"], "role": row["role"]}
    return None


def change_password(user_id, new_password):
    if len(new_password) < 6:
        raise ValueError("La contraseña debe tener al menos 6 caracteres.")
    salt = secrets.token_hex(16)
    with db.get_conn() as conn:
        conn.execute("UPDATE users SET salt=?, password_hash=? WHERE id=?",
                     (salt, _hash(new_password, salt), user_id))


def set_active(user_id, active):
    with db.get_conn() as conn:
        conn.execute("UPDATE users SET active=? WHERE id=?", (int(active), user_id))


def list_users():
    return db.query_df("SELECT id, username, full_name, role, active, created_at FROM users ORDER BY username")


def ensure_default_admin():
    """Crea el administrador inicial si todavía no hay usuarios."""
    with db.get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if n == 0:
        create_user("admin", "Administrador del sistema", "admin123", "Administrador")
        return True
    return False
