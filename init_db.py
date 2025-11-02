# init_db.py
import sqlite3
from pathlib import Path

DB_PATH = Path("data/community.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Pragmas
c.execute("PRAGMA foreign_keys = ON;")
c.execute("PRAGMA journal_mode = WAL;")

# users
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    phone TEXT,
    user_type TEXT,
    ngo_verified INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
""")

# listings
c.execute("""
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id INTEGER NOT NULL,
    title TEXT,
    notes TEXT,
    food_type TEXT, -- cooked / packaged
    veg INTEGER DEFAULT 1, -- 1 veg, 0 non-veg
    cuisine TEXT,
    prepared_at TEXT,
    packaged_at TEXT,
    expiry_at TEXT,
    quantity TEXT,
    photo_path TEXT,
    visibility TEXT DEFAULT 'anyone',
    lat REAL,
    lng REAL,
    address_text TEXT,
    status TEXT DEFAULT 'AVAILABLE',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(donor_id) REFERENCES users(id) ON DELETE CASCADE
);
""")

# claims
c.execute("""
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    receiver_id INTEGER NOT NULL,
    status TEXT DEFAULT 'RESERVED',
    reserved_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT,
    completed_at TEXT,
    FOREIGN KEY(listing_id) REFERENCES listings(id) ON DELETE CASCADE,
    FOREIGN KEY(receiver_id) REFERENCES users(id) ON DELETE CASCADE
);
""")

# notifications
c.execute("""
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL, -- 'claim', 'message', 'system'
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    related_listing_id INTEGER,
    related_user_id INTEGER,
    is_read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(related_listing_id) REFERENCES listings(id) ON DELETE CASCADE,
    FOREIGN KEY(related_user_id) REFERENCES users(id) ON DELETE CASCADE
);
""")

conn.commit()
conn.close()
print("DB initialized at", DB_PATH)
