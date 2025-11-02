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
        data.get("visibility", "everyone"), # <-- Changed "anyone" to "everyone" for consistency
        data.get("lat"),
        data.get("lng"),
        data.get("address_text"),
    ))
    conn.commit()
    lid = cur.lastrowid
    conn.close()
    return lid

# --- MODIFIED for Feature 3 (NGO Mode) ---
def get_available_listings(user_id):
    conn = get_conn()
    cur = conn.cursor()
    
    # Get the current user's type
    user_cur = conn.cursor()
    user_cur.execute("SELECT user_type FROM users WHERE id = ?", (user_id,))
    user_row = user_cur.fetchone()
    user_type = user_row['user_type'] if user_row else "Individual"
    
    # Build the dynamic query
    query = "SELECT * FROM listings WHERE status = 'AVAILABLE'"
    
    if user_type == "NGO":
        # NGOs see both 'everyone' and 'ngo_only' listings
        query += " AND (visibility = 'everyone' OR visibility = 'ngo_only')"
    else:
        # All other users see only 'everyone' listings
        query += " AND visibility = 'everyone'"
        
    query += " ORDER BY created_at DESC"
    
    cur.execute(query)
    rows = cur.fetchall()
    conn.close()
    return rows
# --- END MODIFICATION ---

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
        
        # --- MODIFIED FOR FEATURE 1 ---
        # Added status column to the INSERT
        cur.execute("""
            INSERT INTO claims (listing_id, receiver_id, expires_at, status) 
            VALUES (?, ?, ?, 'RESERVED');
        """, (listing_id, receiver_id, expires_at))
        # --- END MODIFICATION ---
        
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


# --- START: Added for Feature 2 (Ratings) ---

def create_reviews_table_if_not_exists():
    """Utility function to create the reviews table on app startup."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id INTEGER NOT NULL,
                reviewer_id INTEGER NOT NULL,
                reviewee_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(claim_id) REFERENCES claims(id),
                FOREIGN KEY(reviewer_id) REFERENCES users(id),
                FOREIGN KEY(reviewee_id) REFERENCES users(id),
                UNIQUE(claim_id, reviewer_id)
            )
        """)
        conn.commit()
        conn.close()
        print("✅ Reviews table checked/created successfully.")
        return True
    except Exception as e:
        print(f"❌ Error creating reviews table: {e}")
        return False

def create_review(claim_id, reviewer_id, reviewee_id, rating, comment):
    """Inserts a new review into the database."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO reviews (claim_id, reviewer_id, reviewee_id, rating, comment)
            VALUES (?, ?, ?, ?, ?)
        """, (claim_id, reviewer_id, reviewee_id, rating, comment))
        conn.commit()
        review_id = cur.lastrowid
        conn.close()
        return review_id
    except sqlite3.IntegrityError:
        # This will happen if they try to review twice (due to the UNIQUE constraint)
        return None
    except Exception as e:
        print(f"❌ Error creating review: {e}")
        return None

def get_reviews_for_user(user_id):
    """Gets all reviews *about* a specific user."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        # Join with users to get the reviewer's name
        cur.execute("""
            SELECT r.*, u.name as reviewer_name
            FROM reviews r
            JOIN users u ON r.reviewer_id = u.id
            WHERE r.reviewee_id = ?
            ORDER BY r.created_at DESC
        """, (user_id,))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"❌ Error getting reviews: {e}")
        return []

def check_review_exists(claim_id, reviewer_id):
    """Checks if a user has already reviewed a specific claim."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM reviews
            WHERE claim_id = ? AND reviewer_id = ?
        """, (claim_id, reviewer_id))
        row = cur.fetchone()
        conn.close()
        return row is not None
    except Exception as e:
        print(f"❌ Error checking review: {e}")
        return False

# --- END: Added for Feature 2 (Ratings) ---


# --- START: Added for Feature 1 (Gamification) ---

def alter_claims_table_if_needed():
    """Adds the status column to the claims table if it doesn't exist."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(claims)")
        columns = [col[1] for col in cur.fetchall()]
        
        if 'status' not in columns:
            cur.execute("ALTER TABLE claims ADD COLUMN status TEXT DEFAULT 'RESERVED'")
            conn.commit()
            print("✅ Added 'status' column to 'claims' table.")
        
        conn.close()
    except Exception as e:
        print(f"❌ Error altering 'claims' table: {e}")

def create_gamification_tables_if_not_exists():
    """Creates the user_stats, badges, and user_badges tables."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # User Stats Table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_stats (
            user_id INTEGER PRIMARY KEY,
            donations_made INTEGER DEFAULT 0,
            claims_received INTEGER DEFAULT 0,
            impact_points INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)
        
        # Badges Table (Master list of all possible badges)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            icon TEXT NOT NULL,
            required_stat TEXT NOT NULL,
            required_value INTEGER NOT NULL
        )
        """)
        
        # User Badges Table (Links users to the badges they've earned)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            badge_id INTEGER NOT NULL,
            earned_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(badge_id) REFERENCES badges(id) ON DELETE CASCADE,
            UNIQUE(user_id, badge_id)
        )
        """)
        
        conn.commit()
        
        # Pre-populate the badges table if it's empty
        cur.execute("SELECT COUNT(*) FROM badges")
        if cur.fetchone()[0] == 0:
            badges_to_add = [
                ('First Donation', 'Made your first donation', '🎁', 'donations_made', 1),
                ('Good Samaritan', 'Made 5 donations', '❤️', 'donations_made', 5),
                ('Community Hero', 'Made 10 donations', '🦸', 'donations_made', 10),
                ('First-Timer', 'Received your first item', '👍', 'claims_received', 1),
                ('Community Member', 'Received 5 items', '🤝', 'claims_received', 5),
                ('Point Hoarder', 'Earned 100 impact points', '💰', 'impact_points', 100),
            ]
            cur.executemany("""
                INSERT INTO badges (name, description, icon, required_stat, required_value)
                VALUES (?, ?, ?, ?, ?)
            """, badges_to_add)
            conn.commit()
            print("🏆 Populated default badges.")
            
        conn.close()
        print("✅ Gamification tables checked/created successfully.")
        
    except Exception as e:
        print(f"❌ Error creating gamification tables: {e}")

def get_user_stats(user_id):
    """Gets a user's stats, creating a new row if one doesn't exist."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Ensure a stats row exists for this user
        cur.execute("INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)", (user_id,))
        conn.commit()
        
        # Retrieve the stats
        cur.execute("SELECT * FROM user_stats WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else {
            "user_id": user_id, 
            "donations_made": 0, 
            "claims_received": 0, 
            "impact_points": 0
        }
        
    except Exception as e:
        print(f"❌ Error getting user stats: {e}")
        return {
            "user_id": user_id, 
            "donations_made": 0, 
            "claims_received": 0, 
            "impact_points": 0
        }

def get_user_badges(user_id):
    """Gets all badges (name, icon, desc) earned by a user."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT b.name, b.description, b.icon
            FROM user_badges ub
            JOIN badges b ON ub.badge_id = b.id
            WHERE ub.user_id = ?
            ORDER BY ub.earned_at DESC
        """, (user_id,))
        rows = cur.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"❌ Error getting user badges: {e}")
        return []

def check_and_award_badges(user_id):
    """
    Checks a user's stats against all badges and awards new ones.
    Creates notifications for new badges.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        stats = get_user_stats(user_id)
        
        # Get all potential badges
        cur.execute("SELECT * FROM badges")
        all_badges = [dict(row) for row in cur.fetchall()]
        
        # Get all earned badge IDs
        cur.execute("SELECT badge_id FROM user_badges WHERE user_id = ?", (user_id,))
        earned_badge_ids = {row['badge_id'] for row in cur.fetchall()}
        
        new_badges_awarded = []
        
        for badge in all_badges:
            if badge['id'] not in earned_badge_ids:
                stat_to_check = badge['required_stat']
                if stats.get(stat_to_check, 0) >= badge['required_value']:
                    # Award the badge
                    try:
                        cur.execute(
                            "INSERT INTO user_badges (user_id, badge_id) VALUES (?, ?)", 
                            (user_id, badge['id'])
                        )
                        conn.commit()
                        new_badges_awarded.append(badge)
                    except sqlite3.IntegrityError:
                        # User already has this badge (race condition, safe to ignore)
                        pass
                    except Exception as e:
                        print(f"Error awarding badge: {e}")

        conn.close()
        
        # Create notifications (outside the main DB connection loop)
        for badge in new_badges_awarded:
            print(f"🎉 Awarding badge '{badge['name']}' to user {user_id}")
            create_notification(
                user_id=user_id,
                type="badge",
                title="Badge Unlocked!",
                message=f"You've earned the **{badge['icon']} {badge['name']}** badge: *{badge['description']}*"
            )
            
    except Exception as e:
        print(f"❌ Error in check_and_award_badges: {e}")

def complete_claim_and_award_points(claim_id, donor_id, receiver_id):
    """
    Marks a claim as 'COMPLETED' and updates stats for both users.
    This is the main trigger for gamification.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Start transaction
        cur.execute("BEGIN;")
        
        # 1. Update the claim status
        cur.execute("UPDATE claims SET status = 'COMPLETED' WHERE id = ? AND status = 'RESERVED'", (claim_id,))
        
        if cur.rowcount == 0:
            # Claim was not in 'RESERVED' state (maybe already completed)
            conn.rollback()
            conn.close()
            return False
        
        # 2. Ensure stats rows exist
        cur.execute("INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)", (donor_id,))
        cur.execute("INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)", (receiver_id,))
        
        # 3. Update stats
        # Donor: +1 donation, +10 points
        cur.execute("""
            UPDATE user_stats 
            SET donations_made = donations_made + 1, impact_points = impact_points + 10
            WHERE user_id = ?
        """, (donor_id,))
        
        # Receiver: +1 claim, +5 points
        cur.execute("""
            UPDATE user_stats 
            SET claims_received = claims_received + 1, impact_points = impact_points + 5
            WHERE user_id = ?
        """, (receiver_id,))
        
        # Commit transaction
        conn.commit()
        conn.close()
        
        # 4. Check for new badges (outside the transaction)
        check_and_award_badges(donor_id)
        check_and_award_badges(receiver_id)
        
        print(f"✅ Claim {claim_id} completed. Stats updated for Donor {donor_id} and Receiver {receiver_id}.")
        return True
        
    except Exception as e:
        print(f"❌ Error in complete_claim: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

# --- END: Added for Feature 1 (Gamification) ---


# --- START: Added for Feature 3 (NGO Mode) ---

def alter_listings_table_for_visibility():
    """Adds the visibility column to the listings table if it doesn't exist."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(listings)")
        columns = [col[1] for col in cur.fetchall()]
        
        if 'visibility' not in columns:
            cur.execute("ALTER TABLE listings ADD COLUMN visibility TEXT DEFAULT 'everyone'")
            conn.commit()
            print("✅ Added 'visibility' column to 'listings' table.")
        
        conn.close()
    except Exception as e:
        print(f"❌ Error altering 'listings' table for visibility: {e}")

# --- END: Added for Feature 3 (NGO Mode) ---
