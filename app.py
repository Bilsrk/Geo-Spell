import streamlit as st
import streamlit.components.v1 as components
import os
import base64
import json
import re
import fitz
from generator.engine import generate_name_pdf

# --- Helper Functions ---
def parse_dms_to_dd(coor_str):
    """Converts DMS string to Decimal Degrees for Three.js"""
    try:
        clean = re.sub(r'["\s]', '', coor_str)
        pattern = r"(\d+)°(\d+)'([\d\.]+)([NS])(\d+)°(\d+)'([\d\.]+)([EW])"
        match = re.search(pattern, clean)
        if match:
            lat_d, lat_m, lat_s, lat_dir, lon_d, lon_m, lon_s, lon_dir = match.groups()
            lat = float(lat_d) + float(lat_m)/60.0 + float(lat_s)/3600.0
            if lat_dir == 'S': lat = -lat
            lon = float(lon_d) + float(lon_m)/60.0 + float(lon_s)/3600.0
            if lon_dir == 'W': lon = -lon
            return lat, lon
    except Exception:
        pass
    return 0.0, 0.0

def get_globe_markers(target_name=None):
    """Parses metadata.json and filters coordinates based on active name"""
    with open("metadata.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    all_markers = []
    for key, item in data.items():
        lat, lon = parse_dms_to_dd(item["coords"])
        all_markers.append({
            "letter": item["letter"].upper(),
            "location": item["location"],
            "coords_text": item["coords"],
            "lat": lat,
            "lon": lon
        })
    if not target_name: return all_markers

    filtered_markers = []
    name_chars = list(target_name.upper().replace(" ", ""))
    for char in name_chars:
        matches = [m for m in all_markers if m["letter"] == char]
        if matches:
            match_idx = name_chars[:len(filtered_markers)].count(char) % len(matches)
            filtered_markers.append(matches[match_idx])
    return filtered_markers

def load_and_inject_globe(markers_payload):
    with open("frontend/globe.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    json_data = json.dumps(markers_payload)
    return html_content.replace("/*MARKERS_DATA_PLACEHOLDER*/ []", json_data)

def load_frontend_asset(filename):
    with open(f"frontend/{filename}", "r", encoding="utf-8") as f:
        return f.read()

def show_pdf(file_path):
    doc = fitz.open(file_path)
    page = doc.load_page(0)
    pix = page.get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")
    base64_img = base64.b64encode(img_bytes).decode('utf-8')
    img_display = f"""
    <div style="display: flex; justify-content: center; margin-top: 30px; margin-bottom: 20px;">
        <div style="width: 100%; max-width: 450px; border: 1px solid rgba(255, 215, 0, 0.4); border-radius: 16px; box-shadow: 0px 10px 30px rgba(255, 215, 0, 0.2); overflow: hidden; background-color: #111111;">
            <img src="data:image/png;base64,{base64_img}" width="100%" style="display: block; border: none;">
        </div>
    </div>
    """
    st.markdown(img_display, unsafe_allow_html=True)

# --- 1. Page Config & Session State ---
st.set_page_config(page_title="GeoSpell", page_icon="🌍", layout="wide")

if "active_name" not in st.session_state:
    st.session_state.active_name = None
if "pdf_to_show" not in st.session_state:
    st.session_state.pdf_to_show = None

# --- 2. Callback for Enter Key ---
def update_globe_on_enter():
    """Fires immediately when the user presses Enter in the text box"""
    raw_name = st.session_state.user_name_input.strip()
    new_name = raw_name.upper().replace(" ", "") if raw_name else None
    
    # Update globe state and clear the old PDF if the name changed
    if st.session_state.active_name != new_name:
        st.session_state.active_name = new_name
        st.session_state.pdf_to_show = None

# --- 3. Inject CSS & Header ---
st.markdown(f"<style>{load_frontend_asset('style.css')}</style>", unsafe_allow_html=True)
st.markdown(load_frontend_asset('header.html'), unsafe_allow_html=True)

# --- 4. Render 3D Globe Component (Dynamic) ---
current_markers = get_globe_markers(st.session_state.active_name)
globe_html_source = load_and_inject_globe(current_markers)
components.html(globe_html_source, height=650)

# --- 5. Input Layout Block ---
layout_left, layout_center, layout_right = st.columns([1.2, 2, 1.2])
with layout_center:
    user_name = st.text_input(
        label="", 
        placeholder="ENTER NAME", 
        max_chars=15,
        key="user_name_input",           # Attached to the callback
        on_change=update_globe_on_enter  # Triggers immediately on 'Enter'
    )
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    generate_pressed = st.button("Generate", use_container_width=True)

st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

# --- 6. Generator Logic ---
if generate_pressed:
    target_name = st.session_state.active_name
    if target_name:
        output_pdf = f"{target_name}_Generated.pdf"
        
        with st.spinner('🛰️ Aligning golden matrix coordinates...'):
            try:
                generate_name_pdf(target_name, base_folder="nasa_alphabet_database", output_folder=".")
                if os.path.exists(output_pdf):
                    st.session_state.pdf_to_show = output_pdf
                    # We no longer need st.rerun() here! It flows perfectly into Step 7.
                else:
                    st.error("Document pipeline failure. Check cluster server logs.")
            except Exception as e:
                st.error(f"Error compiling document matrices: {e}")
    else:
        st.warning("Input buffer empty. Supply target text strings.")

# --- 7. Persistent PDF Delivery ---
if st.session_state.pdf_to_show and os.path.exists(st.session_state.pdf_to_show):
    show_pdf(st.session_state.pdf_to_show)
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    
    dl_l, dl_c, dl_r = st.columns([1, 2, 1])
    with dl_c:
        with open(st.session_state.pdf_to_show, "rb") as pdf_file:
            st.download_button(
                label="Download Document",
                data=pdf_file,
                file_name=st.session_state.pdf_to_show,
                mime="application/pdf",
                use_container_width=True
            )

# --- 8. Inject Footer ---
st.markdown(load_frontend_asset('footer.html'), unsafe_allow_html=True) 