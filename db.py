# db.py
import sqlite3
from sqlite3 import Connection, Row
from pathlib import Path
import streamlit as st

def get_db_path():
    # prefer secrets
    try:
        p = st.secrets["db_path"]
    except Exception:
        p = "data/community.db"
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    return p

def get_conn() -> Connection:
    p = get_db_path()
    conn = sqlite3.connect(p, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def create_listing(data: dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO listings (
            donor_id, title, notes, food_type, veg, cuisine, prepared_at,
            packaged_at, expiry_at, quantity, photo_path, visibility, lat, lng, address_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("donor_id"),
        data.get("title"),
        data.get("notes"),
        data.get("food_type"),
        1 if data.get("veg", True) else 0,
        data.get("cuisine"),
        data.get("prepared_at"),
        data.get("packaged_at"),
        data.get("expiry_at"),
        data.get("quantity"),
        data.get("photo_path"),
        data.get("visibility", "anyone"),
        data.get("lat"),
        data.get("lng"),
        data.get("address_text"),
    ))
    conn.commit()
    lid = cur.lastrowid
    conn.close()
    return lid

def get_available_listings():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM listings WHERE status = 'AVAILABLE' ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    return rows

def expire_old_listings(now_iso, expiry_threshold_days=2):
    # basic example: if expiry_at passed or created more than threshold
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE listings SET status='EXPIRED' WHERE status='AVAILABLE' AND expiry_at IS NOT NULL AND expiry_at < ?", (now_iso,))
    # optional: auto-expire old ones based on created_at age
    conn.commit()
    conn.close()

def atomic_claim_listing(listing_id: int, receiver_id: int, ttl_minutes=60):
    """
    Attempt to reserve a listing atomically. Returns claim_id on success, None on failure.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("BEGIN;")
        cur.execute("UPDATE listings SET status='RESERVED' WHERE id=? AND status='AVAILABLE';", (listing_id,))
        if cur.rowcount == 0:
            conn.rollback()
            return None
        import datetime
        now = datetime.datetime.utcnow()
        expires_at = (now + datetime.timedelta(minutes=ttl_minutes)).isoformat()
        cur.execute("INSERT INTO claims (listing_id, receiver_id, expires_at) VALUES (?, ?, ?);", (listing_id, receiver_id, expires_at))
        claim_id = cur.lastrowid
        conn.commit()
        return claim_id
    except Exception as e:
        conn.rollback()
        print("claim error:", e)
        return None
    finally:
        conn.close()

def get_listing_by_id(lid):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM listings WHERE id = ?", (lid,))
    row = cur.fetchone()
    conn.close()
    return row

# Notification functions
# db.py - Replace the entire notification section with this:

# Notification functions - COMPLETELY REWRITTEN
def create_notification(user_id, type, title, message, related_listing_id=None, related_user_id=None):
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        print(f"🔔 Creating notification for user {user_id}: {title}")
        
        # First, ensure the notifications table has the correct structure
        try:
            # Check if is_read column exists, if not add it
            cur.execute("PRAGMA table_info(notifications)")
            columns = [col[1] for col in cur.fetchall()]
            if 'is_read' not in columns:
                cur.execute("ALTER TABLE notifications ADD COLUMN is_read INTEGER DEFAULT 0")
                print("✅ Added missing is_read column to notifications table")
        except Exception as alter_error:
            print(f"⚠️ Could not alter table: {alter_error}")
        
        # Insert the notification
        cur.execute("""
            INSERT INTO notifications (user_id, type, title, message, related_listing_id, related_user_id, is_read)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, type, title, message, related_listing_id, related_user_id, 0))
        
        conn.commit()
        notification_id = cur.lastrowid
        conn.close()
        
        print(f"✅ Notification created successfully: ID {notification_id}")
        return notification_id
        
    except Exception as e:
        print(f"❌ Error creating notification: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return None

def get_user_notifications(user_id, limit=20):
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # First ensure the table has the correct structure
        try:
            cur.execute("PRAGMA table_info(notifications)")
            columns = [col[1] for col in cur.fetchall()]
            if 'is_read' not in columns:
                cur.execute("ALTER TABLE notifications ADD COLUMN is_read INTEGER DEFAULT 0")
                conn.commit()
                print("✅ Added missing is_read column in get_user_notifications")
        except:
            pass
        
        # Now query the notifications
        cur.execute("""
            SELECT n.*, 
                   u.name as related_user_name, 
                   l.title as listing_title,
                   COALESCE(n.is_read, 0) as is_read
            FROM notifications n
            LEFT JOIN users u ON n.related_user_id = u.id
            LEFT JOIN listings l ON n.related_listing_id = l.id
            WHERE n.user_id = ?
            ORDER BY n.created_at DESC
            LIMIT ?
        """, (user_id, limit))
        
        rows = cur.fetchall()
        conn.close()
        
        print(f"📨 Retrieved {len(rows)} notifications for user {user_id}")
        return rows
        
    except Exception as e:
        print(f"❌ Error getting notifications: {e}")
        return []

def mark_notification_as_read(notification_id):
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Ensure is_read column exists
        try:
            cur.execute("PRAGMA table_info(notifications)")
            columns = [col[1] for col in cur.fetchall()]
            if 'is_read' not in columns:
                cur.execute("ALTER TABLE notifications ADD COLUMN is_read INTEGER DEFAULT 0")
                conn.commit()
        except:
            pass
        
        cur.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
        conn.commit()
        conn.close()
        
        print(f"✅ Marked notification {notification_id} as read")
        return True
        
    except Exception as e:
        print(f"❌ Error marking notification as read: {e}")
        return False

def get_unread_notification_count(user_id):
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Ensure is_read column exists
        try:
            cur.execute("PRAGMA table_info(notifications)")
            columns = [col[1] for col in cur.fetchall()]
            if 'is_read' not in columns:
                cur.execute("ALTER TABLE notifications ADD COLUMN is_read INTEGER DEFAULT 0")
                conn.commit()
                return 0  # No unread notifications if column was just added
        except:
            pass
        
        cur.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,))
        count = cur.fetchone()[0]
        conn.close()
        
        print(f"🔢 User {user_id} has {count} unread notifications")
        return count
        
    except Exception as e:
        print(f"❌ Error getting unread notification count: {e}")
        return 0

def clear_all_notifications(user_id):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        print(f"✅ Cleared all notifications for user {user_id}")
        return True
    except Exception as e:
        print(f"❌ Error clearing all notifications: {e}")
        return False

def clear_read_notifications(user_id):
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Ensure is_read column exists
        try:
            cur.execute("PRAGMA table_info(notifications)")
            columns = [col[1] for col in cur.fetchall()]
            if 'is_read' not in columns:
                cur.execute("ALTER TABLE notifications ADD COLUMN is_read INTEGER DEFAULT 0")
                conn.commit()
                return True  # No read notifications to clear if column was just added
        except:
            pass
        
        cur.execute("DELETE FROM notifications WHERE user_id = ? AND is_read = 1", (user_id,))
        conn.commit()
        conn.close()
        print(f"✅ Cleared read notifications for user {user_id}")
        return True
    except Exception as e:
        print(f"❌ Error clearing read notifications: {e}")
        return False

# Emergency function to recreate notifications table if needed
def recreate_notifications_table():
    """Completely recreate the notifications table with correct schema"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Drop existing table
        cur.execute("DROP TABLE IF EXISTS notifications")
        
        # Create new table with correct schema
        cur.execute("""
            CREATE TABLE notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                related_listing_id INTEGER,
                related_user_id INTEGER,
                is_read INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(related_listing_id) REFERENCES listings(id) ON DELETE CASCADE,
                FOREIGN KEY(related_user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()
        conn.close()
        print("✅ Notifications table recreated successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error recreating notifications table: {e}")
        return False

# Debug function to check database state
def debug_notifications():
    """Debug function to check notifications table state"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Check notifications table structure
        cur.execute("PRAGMA table_info(notifications)")
        columns = cur.fetchall()
        print("Notifications table columns:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # Check all notifications
        cur.execute("SELECT * FROM notifications")
        all_notifications = cur.fetchall()
        print(f"Total notifications in database: {len(all_notifications)}")
        for notif in all_notifications:
            print(f"  ID: {notif['id']}, User: {notif['user_id']}, Title: {notif['title']}")
        
        conn.close()
    except Exception as e:
        print(f"Debug error: {e}")