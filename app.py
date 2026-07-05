import streamlit as st
import streamlit.components.v1 as components
import os
import base64
import fitz
from generator.engine import generate_name_pdf

# Helper function to read frontend assets cleanly
def load_frontend_asset(filename):
    with open(f"frontend/{filename}", "r", encoding="utf-8") as f:
        return f.read()

# Helper Function to Render PDF Preview as a Safe Image
def show_pdf(file_path):
    doc = fitz.open(file_path)
    page = doc.load_page(0)
    pix = page.get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")
    base64_img = base64.b64encode(img_bytes).decode('utf-8')
    
    img_display = f"""
    <div style="display: flex; justify-content: center; margin-top: 30px; margin-bottom: 20px;">
        <div style="
            width: 100%; 
            max-width: 450px; 
            border: 1px solid rgba(255, 215, 0, 0.4); 
            border-radius: 16px; 
            box-shadow: 0px 10px 30px rgba(255, 215, 0, 0.2); 
            overflow: hidden;
            background-color: #111111;
        ">
            <img src="data:image/png;base64,{base64_img}" width="100%" style="display: block; border: none;">
        </div>
    </div>
    """
    st.markdown(img_display, unsafe_allow_html=True)

# 1. Page Config
st.set_page_config(page_title="GeoSpell", page_icon="🌍", layout="wide")

# 2. Inject CSS & Header
st.markdown(f"<style>{load_frontend_asset('style.css')}</style>", unsafe_allow_html=True)
st.markdown(load_frontend_asset('header.html'), unsafe_allow_html=True)

# 3. Render 3D Globe Component
components.html(load_frontend_asset('globe.html'), height=650)

# 4. Input Layout Block
layout_left, layout_center, layout_right = st.columns([1.2, 2, 1.2])
with layout_center:
    user_name = st.text_input(label="", placeholder="ENTER NAME", max_chars=15)
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    generate_pressed = st.button("Generate", use_container_width=True)

st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

# 5. Generator Logic & PDF Delivery
if generate_pressed:
    if user_name.strip():
        target_name = user_name.upper().replace(" ", "")
        output_pdf = f"{target_name}_Generated.pdf"
        
        with st.spinner('🛰️ Aligning golden matrix coordinates...'):
            try:
                generate_name_pdf(target_name, base_folder="nasa_alphabet_database", output_folder=".")
                if os.path.exists(output_pdf):
                    show_pdf(output_pdf)
                    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
                    
                    dl_l, dl_c, dl_r = st.columns([1, 2, 1])
                    with dl_c:
                        with open(output_pdf, "rb") as pdf_file:
                            st.download_button(
                                label="Download Document",
                                data=pdf_file,
                                file_name=output_pdf,
                                mime="application/pdf",
                                use_container_width=True
                            )
                else:
                    st.error("Document pipeline failure. Check cluster server logs.")
            except Exception as e:
                st.error(f"Error compiling document matrices: {e}")
    else:
        st.warning("Input buffer empty. Supply target text strings.")

# 6. Inject Footer
st.markdown(load_frontend_asset('footer.html'), unsafe_allow_html=True)