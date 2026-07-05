import streamlit as st
import streamlit.components.v1 as components
import os
import base64
from generator.engine import generate_name_pdf

# 1. Page Config & Full-Bleed Layout Setup
st.set_page_config(page_title="GeoSpell", page_icon="🌍", layout="wide")

# 2. Premium CSS Injection (Golden/White/Black Theme & Absolute Positioning)
st.markdown("""
    <style>
        /* Force absolute dark background across the entire app */
        gapp-root, .stApp, header, [data-testid="stHeader"] {
            background-color: #000000 !important;
            color: #ffffff !important;
        }
        
        /* Hide default Streamlit decoration lines and padding */
        [data-testid="stDecoration"] { display: none !important; }
        .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }

        /* Navigation Header & Gradient Text */
        .nav-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 4% 10px 4%;
            font-family: 'Inter', sans-serif;
        }
        
        /* Yellow-White Gradient for Text */
        .nav-logo, h1, h2, h3 {
            background: linear-gradient(90deg, #FFFFFF 0%, #FFD700 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 900;
        }
        .nav-logo {
            font-size: 2.5rem;
            letter-spacing: -1px;
        }
        
        .nav-links a {
            color: #aaaaaa;
            text-decoration: none;
            margin-left: 30px;
            font-size: 0.95rem;
            font-weight: 500;
            transition: color 0.3s;
        }
        .nav-links a:hover { color: #FFD700; }

        /* 
           Make Text Box Fully Transparent and Overlay it on the globe 
           Using negative margin to pull it up over the 3D canvas
        */
        div[data-testid="stTextInput"] {
            margin-top: -160px !important; /* Pulls the text box up over the globe */
            z-index: 999 !important;
            position: relative !important;
        }
        
        /* Target the exact Streamlit baseweb classes to strip the gray background */
        div[data-baseweb="input"], div[data-baseweb="base-input"] {
            background-color: transparent !important;
        }
        
        div[data-testid="stTextInput"] div[data-baseweb="input"] {
            background-color: transparent !important;
            border: 1px dashed rgba(255, 215, 0, 0.4) !important;
            border-radius: 24px !important;
            transition: all 0.3s ease;
        }
        
        div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
            border-color: rgba(255, 215, 0, 0.9) !important;
            background-color: rgba(255, 215, 0, 0.05) !important;
        }
        
        div[data-testid="stTextInput"] input {
            color: #FFD700 !important;
            font-size: 1.3rem !important;
            text-align: center !important;
            letter-spacing: 2px;
            font-family: 'Courier New', monospace;
            background-color: transparent !important;
        }
        
        /* Hide the native Streamlit input field label */
        div[data-testid="stTextInput"] label { display: none !important; }

        /* Seamless Minimalist Generate Button - Also pulled up to stay under the text box */
        div.stButton {
            z-index: 999 !important;
            position: relative !important;
        }
        div.stButton > button {
            background: transparent !important;
            border: 1px solid rgba(255, 215, 0, 0.4) !important;
            color: #FFD700 !important;
            border-radius: 30px !important;
            padding: 10px 40px !important;
            font-size: 1.1rem !important;
            font-weight: 400 !important;
            letter-spacing: 1px !important;
            transition: all 0.3s ease !important;
            margin: 0 auto !important;
            display: block !important;
        }
        div.stButton > button:hover {
            background: rgba(255, 215, 0, 0.08) !important;
            border-color: #FFD700 !important;
            color: #FFFFFF !important;
            transform: translateY(-2px) !important;
        }
        div.stButton > button:active { transform: translateY(1px) !important; }
    </style>
""", unsafe_allow_html=True)

# Helper Function to Render PDF Preview 
def show_pdf(file_path):
    with open(file_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="100%" height="700" type="application/pdf" style="border: 1px solid rgba(255, 215, 0, 0.2); border-radius: 12px; margin-top:40px;">'
    st.markdown(pdf_display, unsafe_allow_html=True)

# --- 3. Custom Nav Header ---
st.markdown("""
    <div class="nav-container">
        <div class="nav-logo">GEO-SPELL</div>
        <div class="nav-links">
            <a href="https://www.linkedin.com/in/rasik-preet-nahar/" target="_blank">LinkedIn</a>
            <a href="https://github.com/bilsrk" target="_blank">Github</a>
            <a href="#" target="_blank">About me</a>
        </div>
    </div>
""", unsafe_allow_html=True)

# --- 4. The Golden Plexus/Matrix Globe Component ---
components.html(
    """
    <div id="canvas-container" style="width: 100%; height: 650px; background-color: transparent; overflow: hidden; display: flex; justify-content: center; align-items: center;"></div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        const container = document.getElementById('canvas-container');
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(55, container.clientWidth / container.clientHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        
        renderer.setSize(container.clientWidth, container.clientHeight);
        container.appendChild(renderer.domElement);

        const globeGroup = new THREE.Group();
        scene.add(globeGroup);

        const particleCount = 500;
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(particleCount * 3);
        const radius = 2.2; // Slightly reduced to ensure it doesn't clip

        for (let i = 0; i < particleCount; i++) {
            const phi = Math.acos(-1 + (2 * i) / particleCount);
            const theta = Math.sqrt(particleCount * Math.PI) * phi;

            positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
            positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
            positions[i * 3 + 2] = radius * Math.cos(phi);
        }

        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        
        const pMaterial = new THREE.PointsMaterial({
            color: 0xffd700, 
            size: 0.045,
            transparent: true,
            opacity: 0.9
        });
        const particleSystem = new THREE.Points(geometry, pMaterial);
        globeGroup.add(particleSystem);

        const lineMaterial = new THREE.LineBasicMaterial({
            color: 0xcca500, 
            transparent: true,
            opacity: 0.3
        });

        const lineGeometry = new THREE.BufferGeometry();
        const linePositions = [];

        for (let i = 0; i < particleCount; i++) {
            const vA = new THREE.Vector3(positions[i*3], positions[i*3+1], positions[i*3+2]);
            for (let j = i + 1; j < particleCount; j++) {
                const vB = new THREE.Vector3(positions[j*3], positions[j*3+1], positions[j*3+2]);
                if (vA.distanceTo(vB) < 0.6) {
                    linePositions.push(vA.x, vA.y, vA.z);
                    linePositions.push(vB.x, vB.y, vB.z);
                }
            }
        }

        lineGeometry.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));
        const networkLines = new THREE.LineSegments(lineGeometry, lineMaterial);
        globeGroup.add(networkLines);

        const shellGeo = new THREE.SphereGeometry(radius * 1.01, 20, 20);
        const shellMat = new THREE.MeshBasicMaterial({
            color: 0x886600, 
            wireframe: true,
            transparent: true,
            opacity: 0.06
        });
        const shellMesh = new THREE.Mesh(shellGeo, shellMat);
        globeGroup.add(shellMesh);

        // Pulled the camera further back to fix the top/bottom clipping
        camera.position.z = 5.5; 
        globeGroup.rotation.x = 0.3; 

        function animate() {
            requestAnimationFrame(animate);
            globeGroup.rotation.y += 0.002;
            renderer.render(scene, camera);
        }
        animate();

        window.addEventListener('resize', () => {
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
        });
    </script>
    """,
    height=650, 
)

# --- 5. Inputs Layout Block ---
layout_left, layout_center, layout_right = st.columns([1.2, 2, 1.2])

with layout_center:
    # Text Input 
    user_name = st.text_input(
        label="", 
        placeholder="ENTER NAME", 
        max_chars=15
    )
    
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    
    # Seamless Generate Button 
    generate_pressed = st.button("Generate", use_container_width=True)

st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

# --- 6. Generator Logic Execution & PDF Delivery ---
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