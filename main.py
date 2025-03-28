import streamlit as st
import pf_full_code
import bank_full_code
import esic_full_code
import archival_full_code
import base64

# Set page config
st.set_page_config(page_title="Core Integra", page_icon=":office:", layout="wide")

# Path to logo
logo_path = "C:/CORE INTEGRIA/logo.jpg"  # Change if needed

# ---------- CSS ---------- #

# Login page CSS (including logo box)
login_css = """
    <style>
    #MainMenu, header, footer {visibility: hidden;}
    .login-box {
        background-color: #ffffff;
        padding: 40px 30px;
        border-radius: 12px;
        box-shadow: 0px 4px 15px rgba(0, 0, 0, 0.1);
        text-align: center;
        max-width: 400px;
        margin: 0 auto;
    }

    .login-box img {
        width: 130px;
        margin-bottom: 20px;
        border-radius: 10px;
        box-shadow: 0 0 10px rgba(0, 0, 0, 0.05);
    }

    .login-title {
        color: #004D7C;
        font-size: 24px;
        font-weight: 600;
        margin-bottom: 25px;
    }

    .stTextInput > div > div > input {
        border-radius: 6px;
        padding: 10px;
        border: 1px solid #ccc;
    }

    .stButton > button {
        background-color: #004D7C;
        color: white;
        font-weight: 500;
        padding: 10px 16px;
        border: none;
        border-radius: 6px;
        margin-top: 20px;
    }

    .stButton > button:hover {
        background-color: #5F9EA0;
    }
    </style>
"""

# Sidebar CSS
sidebar_css = """
    <style>
    #MainMenu, header, footer {visibility: hidden;}
    .block-container {padding-top: 1rem;}
    .stButton > button {
        background-color: #004D7C;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 16px;
        font-size: 15px;
        margin: 8px 0;
        width: 100%;
    }
    .stButton > button:hover {
        background-color: #5F9EA0;
    }
    </style>
"""

# ---------- Utility ---------- #

def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

# ---------- App Logic ---------- #

def main():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'selected_section' not in st.session_state:
        st.session_state.selected_section = None

    if not st.session_state.authenticated:
        show_login_page()
    else:
        st.markdown(sidebar_css, unsafe_allow_html=True)
        show_sidebar()
        show_selected_dashboard()

def show_login_page():
    st.markdown(login_css, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"""
            <div class="login-box">
                <img src="data:image/jpeg;base64,{get_base64_image(logo_path)}" />
                <div class="login-title">Welcome to Core Integra</div>
        """, unsafe_allow_html=True)

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if username == "admin" and password == "password":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid username or password")

        st.markdown("</div>", unsafe_allow_html=True)

def show_sidebar():
    with st.sidebar:
        st.image(logo_path, width=160)
        st.markdown("---")

        if st.button("PF"):
            st.session_state.selected_section = 'pf'

        if st.button("BANK"):
            st.session_state.selected_section = 'bank'

        if st.button("ESIC"):
            st.session_state.selected_section = 'esic'

        if st.button("ARCHIVAL"):
            st.session_state.selected_section = 'archival'

        st.markdown("---")
        if st.button("LOGOUT"):
            st.session_state.authenticated = False
            st.session_state.selected_section = None
            st.rerun()

def show_selected_dashboard():
    section = st.session_state.selected_section

    if section == 'pf':
        pf_full_code.run_pf_section()
    elif section == 'bank':
        bank_full_code.run_bank_section()
    elif section == 'esic':
        esic_full_code.run_esic_section()
    elif section == 'archival':
        archival_full_code.run_archival_section()
    else:
        st.subheader("Welcome! Use the sidebar to choose a section.")

if __name__ == "__main__":
    main()
