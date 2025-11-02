# maps_utils.py
import streamlit as st
import requests
from urllib.parse import urlencode

def get_api_key():
    try:
        return st.secrets["google_api_key"]
    except Exception:
        return None

def reverse_geocode(lat, lng):
    key = get_api_key()
    if not key:
        return None
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lng}&key={key}"
    r = requests.get(url, timeout=10)
    if r.ok:
        data = r.json()
        if data.get("results"):
            return data["results"][0]["formatted_address"]
    return None

def static_map_url(lat, lng, width=400, height=180, zoom=15):
    key = get_api_key()
    if not key:
        return None
    params = {
        "center": f"{lat},{lng}",
        "zoom": zoom,
        "size": f"{width}x{height}",
        "markers": f"color:red|{lat},{lng}",
        "key": key
    }
    return "https://maps.googleapis.com/maps/api/staticmap?" + urlencode(params)

def directions_url(origin_lat, origin_lng, dest_lat, dest_lng):
    return f"https://www.google.com/maps/dir/?api=1&origin={origin_lat},{origin_lng}&destination={dest_lat},{dest_lng}&travelmode=driving"
