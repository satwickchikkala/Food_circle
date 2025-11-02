import streamlit as st
from auth import register_user, get_user_by_email, verify_password, get_user_by_id
from db import (
    create_listing,
    get_available_listings,
    atomic_claim_listing,
    get_listing_by_id,
    expire_old_listings,
    get_conn,
    create_notification,
    get_user_notifications,
    mark_notification_as_read,
    get_unread_notification_count,
    clear_all_notifications,
    clear_read_notifications
)
from maps_utils import reverse_geocode, static_map_url, directions_url
from email_utils import send_email
from pathlib import Path
import datetime
from auth import get_user_by_id
from streamlit_geolocation import streamlit_geolocation
import re
import sqlite3

def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def fix_database_schema():
    """Add missing columns to existing database"""
    try:
        db_path = Path("data/community.db")
        if db_path.exists():
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            
            # Check if is_read column exists in notifications table
            c.execute("PRAGMA table_info(notifications)")
            columns = [col[1] for col in c.fetchall()]
            
            if 'is_read' not in columns:
                c.execute("ALTER TABLE notifications ADD COLUMN is_read INTEGER DEFAULT 0")
                print("Added is_read column to notifications table")
            
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"Error fixing database schema: {e}")

# Add this function to your app.py after the imports
def debug_database_structure():
    """Debug function to check the current database structure"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Check if notifications table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'")
        table_exists = cur.fetchone()
        
        if not table_exists:
            print("⚠ NOTIFICATIONS TABLE DOES NOT EXIST!")
            return False
            
        # Check notifications table columns
        cur.execute("PRAGMA table_info(notifications)")
        columns = cur.fetchall()
        print("📋 Notifications table columns:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # Check if is_read column exists
        has_is_read = any(col[1] == 'is_read' for col in columns)
        print(f"✅ is_read column exists: {has_is_read}")
        
        # Check all notifications
        cur.execute("SELECT * FROM notifications")
        all_notifications = cur.fetchall()
        print(f"📊 Total notifications in database: {len(all_notifications)}")
        
        for notif in all_notifications:
            notif_dict = dict(notif)
            print(f"  📝 ID: {notif_dict.get('id')}, User: {notif_dict.get('user_id')}, "
                  f"Title: {notif_dict.get('title')}, Read: {notif_dict.get('is_read', 'N/A')}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"⚠ Debug error: {e}")
        return False

# Call this function at the start of your app, after fix_database_schema()
debug_database_structure()

# Fix database schema before anything else
fix_database_schema()

st.set_page_config(page_title="Community Surplus Food", layout="wide")

# Enhanced CSS styling
st.markdown("""
<style>
    /* Main app styling */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        margin-block-end: 2rem;
        text-align: center;
        color: white;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
    }
    
    .main-header h1 {
        font-size: 2.5rem !important;
        margin: 0 !important;
        font-weight: 700;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .main-header p {
        font-size: 1.2rem;
        margin-block-start: 0.5rem;
        opacity: 0.9;
    }
    
    /* Login form styling */
    .login-title {
        text-align: center;
        font-size: 2rem;
        color: #667eea;
        margin-block-end: 2rem;
        font-weight: 600;
    }
    
    .register-title {
        text-align: center;
        font-size: 2rem;
        color: #ff8c00;
        margin-block-end: 2rem;
        font-weight: 600;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
    }
    
    .sidebar-user-info {
        background: rgba(255,255,255,0.15);
        padding: 1.5rem;
        border-radius: 15px;
        margin-block-end: 2rem;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.2);
    }
    
    .sidebar-user-name {
        color: white;
        font-size: 1.1rem;
        font-weight: 600;
        margin-block-end: 0.5rem;
    }
    
    .sidebar-user-email {
        color: rgba(255,255,255,0.8);
        font-size: 0.9rem;
    }
    
    .notification-badge {
        background: #ff4757;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-inline-start: 0.5rem;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.1); }
        100% { transform: scale(1); }
    }
    
    /* Enhanced buttons */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.8rem 2rem;
        border-radius: 25px;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
    }
    
    /* Navigation buttons */
    .nav-button-container {
        margin: 1rem 0;
    }
    
    .nav-button {
        inline-size: 100%;
        padding: 1rem;
        border-radius: 15px;
        border: none;
        margin: 0.5rem 0;
        font-weight: 600;
        font-size: 1rem;
        cursor: pointer;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: flex-start;
    }
    
    .nav-home {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        color: white;
    }
    
    .nav-listings {
        background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
        color: white;
    }
    
    .nav-claims {
        background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
        color: white;
    }
    
    .nav-admin {
        background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
        color: #333;
    }
    
    .nav-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
    }
    
    .nav-icon {
        margin-inline-end: 0.8rem;
        font-size: 1.2rem;
    }
    
    /* Form styling */
    .stTextInput > div > div > input {
        border-radius: 10px;
        border: 2px solid #e0e6ff;
        padding: 0.8rem;
        transition: all 0.3s ease;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    /* Welcome section styling */
    .feature-card {
        background: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        margin: 1rem 0;
        border-inline-start: 4px solid #667eea;
        transition: all 0.3s ease;
    }
    
    .feature-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 30px rgba(0,0,0,0.15);
    }
    
    .feature-icon {
        font-size: 3rem;
        margin-block-end: 1rem;
    }
    
    .feature-title {
        font-size: 1.3rem;
        font-weight: 600;
        color: #333;
        margin-block-end: 0.5rem;
    }
    
    .feature-desc {
        color: #666;
        line-height: 1.6;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------
# Helpers
# -------------------------------
def init_session_state():
    for k, v in {"user": None, "page": "home", "detected_lat": None, "detected_lng": None, "detected_address": None, "confirming_claim_id": None, "listing_success_message": None}.items():
        if k not in st.session_state:
            st.session_state[k] = v

# Run expiry cleanup (best-effort)
now_iso = datetime.datetime.utcnow().isoformat()
try:
    expire_old_listings(now_iso)
except Exception:
    pass

init_session_state()

# -------------------------------
# Navigation
# -------------------------------
# Enhanced header
st.markdown("""
<div class="main-header">
    <h1>🍽️ Food Circle</h1>
    <p>Reducing food waste, building community connections</p>
</div>
""", unsafe_allow_html=True)

if st.session_state.user:
    user = dict(st.session_state.user)
    
    # Get unread notification count
    try:
        unread_count = get_unread_notification_count(user["id"])
        badge = f'<span class="notification-badge">{unread_count}</span>' if unread_count > 0 else ""
    except Exception as e:
        badge = ""
        print(f"Error getting notification count: {e}")
    
    # Enhanced sidebar user info
    st.sidebar.markdown(f"""
    <div class="sidebar-user-info">
        <div class="sidebar-user-name">👤 {user.get('name') or 'Welcome!'}</div>
        <div class="sidebar-user-email">📧 {user.get('email')}</div>
        {f'<div style="margin-block-start: 0.5rem;">📬 Notifications {badge}</div>' if badge else ''}
    </div>
    """, unsafe_allow_html=True)
    
    # Enhanced navigation
    st.sidebar.markdown("### 🚀 Navigation")
    
    sidebar_options = ["Home", "My Listings", "My Claims", "Admin"]
    option_icons = ["🏠", "📝", "🛒", "⚙️"]
    option_classes = ["nav-home", "nav-listings", "nav-claims", "nav-admin"]
    
    # Only update page if not on donor/receiver
    if st.session_state.page not in ["donor", "receiver"]:
        try:
            current_index = sidebar_options.index(st.session_state.page.capitalize())
        except ValueError:
            current_index = 0
        
        # Custom navigation buttons
        for i, (option, icon, css_class) in enumerate(zip(sidebar_options, option_icons, option_classes)):
            if st.sidebar.button(f"{icon} {option}", key=f"nav_{option.lower()}", use_container_width=True):
                st.session_state.page = option.lower()
                st.rerun()
    
    # Enhanced logout button
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.user = None
        st.session_state.page = "home"
        st.rerun()
else:
    st.session_state.page = "home"

# -------------------------------
# Auth Pages
# -------------------------------
def login_ui():
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="login-title">🔐 Welcome Back!</h2>', unsafe_allow_html=True)
    
    # Welcome message
    st.markdown("""
    <div style="text-align: center; margin-block-end: 2rem;">
        <p style="font-size: 1.1rem; color: #666;">
            Sign in to your account to start sharing or finding surplus food in your community
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("login"):
        email = st.text_input("📧 Email Address", key="login_email", placeholder="Enter your email address")
        password = st.text_input("🔒 Password", type="password", key="login_password", placeholder="Enter your password")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            submitted = st.form_submit_button("🚀 Sign In", use_container_width=True)
        
        if submitted:
            if not is_valid_email(email):
                st.error("📧 Please enter a valid email address.")
            else:
                user_row = get_user_by_email(email)
                if user_row and verify_password(password, user_row["password_hash"]):
                    st.session_state.user = dict(user_row)
                    st.success("🎉 Welcome back! Logging you in...")
                    needs_profile = (not st.session_state.user.get("name")) or (not st.session_state.user.get("user_type"))
                    if needs_profile:
                        st.session_state.page = "profile_setup"
                    else:
                        st.session_state.page = "home"
                    st.rerun()
                else:
                    st.error("❌ Invalid email or password. Please try again.")
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Divider
    st.markdown("---")
    
    # Register section
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="text-align: center; margin: 2rem 0;">
            <p style="color: #666; margin-block-end: 1rem;">Don't have an account yet?</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("✨ Create New Account", use_container_width=True):
            st.session_state.show_register = True

def register_ui():
    st.markdown('<h2 class="register-title">✨ Join Our Community!</h2>', unsafe_allow_html=True)
    
    # Welcome message for registration
    st.markdown("""
    <div style="text-align: center; margin-block-end: 2rem;">
        <p style="font-size: 1.1rem; color: #666;">
            Create your account to start making a difference in your community
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.info("🚀 Quick setup! Only email and password required. You can complete your profile after signing in.")
    
    with st.form("register"):
        email = st.text_input("📧 Email Address", key="reg_email", placeholder="Enter your email address")
        password = st.text_input("🔒 Password", type="password", key="reg_password", placeholder="Create a strong password")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            submitted = st.form_submit_button("🎉 Create Account", use_container_width=True)
        
        if submitted:
            if not email or not password:
                st.error("📝 Please fill in both email and password fields.")
            elif not is_valid_email(email):
                st.error("📧 Please enter a valid email address.")
            else:
                uid = register_user("", email, password, None, None)
                if uid:
                    st.success("🎉 Account created successfully! Please sign in below.")
                    st.session_state.show_register = False
                else:
                    st.error("⚠️ This email is already registered. Try signing in instead.")
    
    # Back to login
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="text-align: center; margin: 2rem 0;">
            <p style="color: #666; margin-block-end: 1rem;">Already have an account?</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🔐 Back to Sign In", use_container_width=True):
            st.session_state.show_register = False

# -------------------------------
# Home/Auth display (NEW LOGIC)
# -------------------------------
if not st.session_state.user:
    if "show_register" not in st.session_state:
        st.session_state.show_register = False

    if st.session_state.show_register:
        register_ui()
    else:
        login_ui()
    st.stop()

# Refresh session user from DB
try:
    user = get_user_by_id(st.session_state.user["id"])
    st.session_state.user = dict(user)
except Exception:
    st.warning("Session refresh failed – please login again.")
    st.session_state.user = None
    st.rerun()

# -------------------------------
# Home Page (NEW)
# -------------------------------
# In app.py, replace your existing home_page function with this one

def home_page():
    st.header("Welcome to Community Surplus Food Sharing!")
    st.markdown("Choose your action below:")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🍲 Donor Dashboard", use_container_width=True):
            st.session_state.page = "donor"
            st.rerun()
    with col2:
        if st.button("🛒 Receiver Dashboard", use_container_width=True):
            st.session_state.page = "receiver"
            st.rerun()
    
    # Notification Section
    st.markdown("---")
    st.subheader("📬 Notifications")
    
    # Get notifications
    try:
        notifications = get_user_notifications(st.session_state.user["id"])
        unread_count = get_unread_notification_count(st.session_state.user["id"])
        
        if unread_count > 0:
            st.info(f"You have {unread_count} unread notification(s)")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            if st.button("🔄 Refresh Notifications"):
                st.rerun()
        with col2:
            if st.button("✅ Clear Read", help="Remove all read notifications"):
                if clear_read_notifications(st.session_state.user["id"]):
                    st.success("Read notifications cleared!")
                    st.rerun()
                else:
                    st.error("Failed to clear notifications")
        with col3:
            if st.button("🗑️ Clear All", help="Remove all notifications"):
                if clear_all_notifications(st.session_state.user["id"]):
                    st.success("All notifications cleared!")
                    st.rerun()
                else:
                    st.error("Failed to clear notifications")
        
        if not notifications:
            st.write("No notifications yet.")
        else:
            for notification in notifications:
                notif = dict(notification)
                is_read = notif.get("is_read", 0)
                
                if not is_read:
                    st.markdown(f"<div style='background-color: #f0f8ff; padding: 10px; border-radius: 5px; border-inline-start: 4px solid #007bff; margin-block-end: 10px;'>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='padding: 10px; border-radius: 5px; border-inline-start: 4px solid #ccc; margin-block-end: 10px;'>", unsafe_allow_html=True)
                
                st.write(f"**{notif.get('title', 'Notification')}**")
                
                # <<-- THIS IS THE ONLY CHANGE IN THIS FUNCTION -->>
                # Use st.markdown to render the message, allowing the HTML link to be clickable
                st.markdown(notif.get('message', ''), unsafe_allow_html=True)
                
                st.write(f"*{notif.get('created_at', '')}*")
                
                if not is_read:
                    if st.button("Mark as read", key=f"read_{notif['id']}"):
                        mark_notification_as_read(notif['id'])
                        st.rerun()
                
                st.markdown("</div>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error loading notifications: {e}")
        st.info("Please refresh the page or contact support if this persists.")

# -------------------------------
# Donor Page
# -------------------------------
# In app.py, replace your existing donor_page function with this one

def donor_page():
    if st.button("⬅️ Back to Home"):
        st.session_state.page = "home"
        st.rerun()
    st.header("Donor Dashboard – Create a listing")

    # <<-- CHANGE 1: Display the success message if it exists -->>
    if st.session_state.get("listing_success_message"):
        st.success(st.session_state.listing_success_message)
        # Clear the message so it doesn't show again on the next reload
        st.session_state.listing_success_message = None

    st.info("📍 Please use the button below to detect your current location before publishing your listing.")

    loc = streamlit_geolocation()
    if loc and loc.get("latitude") and loc.get("longitude"):
        st.session_state.detected_lat = loc["latitude"]
        st.session_state.detected_lng = loc["longitude"]
        st.session_state.detected_address = reverse_geocode(
            st.session_state.detected_lat, st.session_state.detected_lng
        )
        st.success("Location detected!")
    elif loc is not None:
        st.warning("Could not detect location. Please click on the above button to detect your location.")

    lat = st.session_state.detected_lat
    lng = st.session_state.detected_lng
    address_text = st.session_state.detected_address

    with st.form("new_listing"):
        title = st.text_input("Dish")
        notes = st.text_area("Notes / instructions")
        food_type = st.selectbox("Food type", ["cooked", "packaged"])
        veg_option = st.radio("Veg or Non-Veg", ["Veg", "Non-Veg"])
        veg = veg_option == "Veg" if veg_option else None
        cuisine = st.text_input("Cuisine")
        prepared_at = None
        expiry_at = None
        if food_type == "cooked":
            prepared_at = st.date_input("Prepared on", value=datetime.date.today())
        if food_type == "packaged":
            expiry_at = st.date_input("Expiry date", value=datetime.date.today())
        quantity = st.text_input("Quantity (eg: 5 portions)")
        photo = st.file_uploader("Photo", type=["jpg", "jpeg", "png"])

        address_value = address_text or (f"{lat},{lng}" if lat and lng else "")
        address_input = st.text_input("Address", value=address_value)

        submit_disabled = not (lat and lng)
        if submit_disabled:
            st.warning("You must detect your location before publishing your listing.")

        submitted = st.form_submit_button("Publish listing", disabled=submit_disabled)

        if submitted:
            photo_path = None
            if photo:
                UP = Path("uploads")
                UP.mkdir(exist_ok=True)
                fname = f"{int(datetime.datetime.utcnow().timestamp())}_{photo.name}"
                fpath = UP / fname
                with open(fpath, "wb") as f:
                    f.write(photo.getbuffer())
                photo_path = str(fpath)

            data = {
                "donor_id": st.session_state.user["id"],
                "title": title, "notes": notes, "food_type": food_type, "veg": veg,
                "cuisine": cuisine, "prepared_at": prepared_at.isoformat() if prepared_at else None,
                "expiry_at": expiry_at.isoformat() if expiry_at else None, "quantity": quantity,
                "photo_path": photo_path, "lat": lat, "lng": lng, "address_text": address_input,
            }
            lid = create_listing(data)
            
            # <<-- CHANGE 2: Set the success message in the session state -->>
            st.session_state.listing_success_message = f"✅ Your listing for '{title}' was published successfully!"
            
            st.session_state.detected_lat = None
            st.session_state.detected_lng = None
            st.session_state.detected_address = None
            st.rerun()

# -------------------------------
# Receiver Page
# -------------------------------
# -------------------------------
# Receiver Page
# -------------------------------


def receiver_page():
    if st.button("⬅️ Back to Home"):
        st.session_state.page = "home"
        st.rerun()
    st.header("Receiver – Browse available food")

    listings = get_available_listings()
    L = [dict(r) for r in listings]
    st.subheader(f"{len(L)} available listings")

    for item in L:
        with st.expander(item.get("title") or "Food Available"):
            st.write(item.get("notes"))
            st.write("Veg" if item.get("veg") else "Non-Veg")
            st.write(item.get("address_text") or "Address hidden")
            if item.get("photo_path"):
                try:
                    st.image(item.get("photo_path"), width=250)
                except Exception:
                    pass

            if item.get("lat") and item.get("lng"):
                sm = static_map_url(float(item["lat"]), float(item["lng"]))
                if sm:
                    st.image(sm, caption="Listing Location")

            if st.button("TAKEAWAY", key=f"claim_{item['id']}"):
                claim_id = atomic_claim_listing(item["id"], st.session_state.user["id"], ttl_minutes=60)
                if claim_id:
                    st.success("Reserved! Donor notified.")
                    try:
                        donor = dict(get_user_by_id(item["donor_id"]))
                        receiver = dict(get_user_by_id(st.session_state.user["id"]))

                        # <<-- CHANGE 1: Display donor's phone number as a clickable link -->>
                        donor_phone = donor.get("phone")
                        if donor_phone:
                            # Use st.markdown to render the HTML link
                            st.markdown(f"""
                                <div style="background-color: #e6ffe6; border-left: 5px solid #007bff; padding: 10px; border-radius: 5px; margin: 10px 0; color: black;">
                                    📞 <span style="color: black;">You can contact the donor at:</span> <a href="tel:{donor_phone}">{donor_phone}</a>
                                </div>
                            """, unsafe_allow_html=True)

                        else:
                            st.warning("The donor has not provided a phone number.")
                        
                        print(f"🎯 Creating notification for donor {item['donor_id']} ({donor.get('email')})")
                        
                        # <<-- CHANGE 2: Add receiver's clickable phone link to the notification message -->>
                        receiver_name = receiver.get('name', 'Someone')
                        receiver_phone = receiver.get('phone', 'Not provided')
                        listing_title = item.get('title', '')
                        
                        # Create a clickable link if a phone number exists
                        phone_link_html = f'<a href="tel:{receiver_phone}">{receiver_phone}</a>' if receiver.get('phone') else 'Not provided'
                        
                        notification_title = "Your food has been claimed!"
                        notification_message = f"{receiver_name} wants to take your food: '{listing_title}'. You can contact them at: {phone_link_html}"
                        
                        notification_id = create_notification(
                            user_id=item["donor_id"],
                            type="claim",
                            title=notification_title,
                            message=notification_message,
                            related_listing_id=item["id"],
                            related_user_id=st.session_state.user["id"]
                        )
                        
                        if notification_id:
                            st.success("✅ Notification sent to donor!")
                        else:
                            st.warning("⚠️ Could not create notification (but claim was successful)")
                        
                        # ... (rest of the function is the same)
                        receiver_location = ""
                        loc = streamlit_geolocation()
                        if loc and loc.get("latitude") and loc.get("longitude"):
                            receiver_location = f"{loc['latitude']},{loc['longitude']}"
                        message = (
                            f"Your food listing was claimed!\n\n"
                            f"Receiver Name: {receiver.get('name', 'Unknown')}\n"
                            f"Receiver Email: {receiver.get('email', 'Unknown')}\n"
                            f"Receiver Phone: {receiver.get('phone', 'Unknown')}\n"
                            f"Receiver Location: {receiver_location or 'Not provided'}\n"
                        )
                        if donor.get("email"):
                            send_email(donor["email"], "Your food has been claimed", message)
                            
                    except Exception as e:
                        st.warning(f"Could not send email to donor: {e}")
                        print(f"📧 Email error: {e}")

                    dir_html = f"""
                    <button onclick="getLocation_{item['id']}()" style="padding:10px 14px;">Get Directions</button>
                    <script>
                    function getLocation_{item['id']}() {{
                      navigator.geolocation.getCurrentPosition(success_{item['id']}, error_{item['id']});
                    }}
                    function success_{item['id']}(pos) {{
                      const mapsUrl = `https://www.google.com/maps/dir/?api=1&origin=${{pos.coords.latitude}},${{pos.coords.longitude}}&destination={item['lat']},{item['lng']}&travelmode=driving`;
                      window.open(mapsUrl, "_blank");
                    }}
                    function error_{item['id']}() {{ alert('Unable to retrieve location'); }}
                    </script>
                    """
                    st.components.v1.html(dir_html, height=100)
                else:
                    st.warning("Already claimed.")
# -------------------------------
# My Listings / Claims
# -------------------------------
def my_listings_page():
    st.header("My Listings")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM listings WHERE donor_id=? ORDER BY created_at DESC", (st.session_state.user["id"],))
    rows = cur.fetchall()
    conn.close()
    for r in rows:
        row = dict(r)
        st.markdown(f"""
**Title:** {row.get('title', '')}  
**Notes:** {row.get('notes', '')}  
**Food Type:** {row.get('food_type', '')}  
**Veg:** {'Yes' if row.get('veg') else 'No'}  
**Cuisine:** {row.get('cuisine', '')}  
**Prepared At:** {row.get('prepared_at', '')}  
**Expiry At:** {row.get('expiry_at', '')}  
**Quantity:** {row.get('quantity', '')}  
**Photo Path:** {row.get('photo_path', '')}  
**Address:** {row.get('address_text', '')}  
**Latitude:** {row.get('lat', '')}  
**Longitude:** {row.get('lng', '')}
""")
        st.markdown("---")

def my_claims_page():
    st.header("My Claims")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT claims.*, listings.title, listings.address_text, listings.lat, listings.lng
        FROM claims JOIN listings ON claims.listing_id = listings.id
        WHERE claims.receiver_id=? ORDER BY reserved_at DESC
        """,
        (st.session_state.user["id"],),
    )
    rows = cur.fetchall()
    conn.close()
    for r in rows:
        row = dict(r)
        st.markdown(f"""
**Title:** {row.get('title', '')}  
**Status:** {row.get('status', '')}  
**Reserved At:** {row.get('reserved_at', '')}  
**Expires At:** {row.get('expires_at', '')}  
**Address:** {row.get('address_text', '')}  
**Latitude:** {row.get('lat', '')}  
**Longitude:** {row.get('lng', '')}
""")
        if row.get("lat") and row.get("lng"):
            maps_url = directions_url(
                origin_lat=None,
                origin_lng=None,
                dest_lat=row['lat'],
                dest_lng=row['lng']
            )
            st.markdown(f"**Open in Google Maps** [link]({maps_url})")
        st.markdown("---")

# -------------------------------
# Admin
# -------------------------------
def admin_page():
    st.header("Profile Settings")

    user = st.session_state.user
    st.subheader("Edit Profile")

    # Editable profile fields
    with st.form("profile_edit"):
        name = st.text_input("Full Name", value=user.get("name") or "")
        phone = st.text_input("Phone", value=user.get("phone") or "")
        email = st.text_input("Email", value=user.get("email") or "", disabled=True)
        user_type = st.selectbox(
            "Account type",
            ["Household", "Restaurant", "Event Organizer", "NGO", "Individual"],
            index=["Household", "Restaurant", "Event Organizer", "NGO", "Individual"].index(user.get("user_type") or "Household")
        )
        submitted = st.form_submit_button("Save Changes")
        if submitted:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET name=?, phone=?, user_type=? WHERE id=?",
                (name, phone, user_type, user["id"])
            )
            conn.commit()
            conn.close()
            fresh = get_user_by_id(user["id"])
            st.session_state.user = dict(fresh)
            st.success("Profile updated!")

    st.subheader("Change Password")
    with st.form("change_password"):
        old_pw = st.text_input("Current Password", type="password")
        new_pw = st.text_input("New Password", type="password")
        confirm_pw = st.text_input("Confirm New Password", type="password")
        pw_submit = st.form_submit_button("Change Password")
        if pw_submit:
            if not verify_password(old_pw, user["password_hash"]):
                st.error("Current password is incorrect.")
            elif not new_pw or len(new_pw) < 6:
                st.error("New password must be at least 6 characters.")
            elif new_pw != confirm_pw:
                st.error("New passwords do not match.")
            else:
                # Update password
                conn = get_conn()
                cur = conn.cursor()
                from auth import hash_password
                cur.execute(
                    "UPDATE users SET password_hash=? WHERE id=?",
                    (hash_password(new_pw), user["id"])
                )
                conn.commit()
                conn.close()
                st.success("Password changed successfully!")

def profile_setup_ui():
    st.header("Complete your profile")
    st.markdown("Provide details so others can contact you.")
    with st.form("profile_setup"):
        name = st.text_input("Full Name", value=st.session_state.user.get("name") or "")
        phone = st.text_input("Phone (optional)", value=st.session_state.user.get("phone") or "")
        user_type = st.selectbox("Account type", ["Household", "Restaurant", "Event Organizer", "NGO", "Individual"])
        submitted = st.form_submit_button("Save profile")
        if submitted:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET name=?, phone=?, user_type=? WHERE id=?",
                (name, phone, user_type, st.session_state.user["id"])
            )
            conn.commit()
            conn.close()
            fresh = get_user_by_id(st.session_state.user["id"])
            st.session_state.user = dict(fresh)
            st.success("Profile saved. Redirecting...")
            st.session_state.page = "home"
            st.rerun()

# -------------------------------
# Dispatch
# -------------------------------
pg = st.session_state.page
needs_profile = (not st.session_state.user.get("name")) or (not st.session_state.user.get("user_type"))

if needs_profile and pg != "profile_setup":
    st.session_state.page = "profile_setup"
    pg = "profile_setup"

if "donor" in pg:
    donor_page()
elif "receiver" in pg:
    receiver_page()
elif "my listings" in pg:
    my_listings_page()
elif "my claims" in pg:
    my_claims_page()
elif "admin" in pg:
    admin_page()
elif "profile_setup" in pg:
    profile_setup_ui()
else:
    home_page()