# auth.py
import bcrypt
from db import get_conn
import sqlite3

def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    return hashed.decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def register_user(name, email, password, phone=None, user_type=None):
    conn = get_conn()
    cur = conn.cursor()
    pw_hash = hash_password(password)
    try:
        cur.execute("""
            INSERT INTO users (name, email, password_hash, phone, user_type)
            VALUES (?, ?, ?, ?, ?)
        """, (name, email, pw_hash, phone, user_type))
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_user_by_email(email):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()
    return row

def get_user_by_id(uid):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (uid,))
    row = cur.fetchone()
    conn.close()
    return row
