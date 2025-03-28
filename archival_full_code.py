import streamlit as st

def run_archival_section():
    st.subheader("🗄️ Archival Dashboard")
    uploaded_file = st.file_uploader("Upload Archival File", type=["pdf", "xlsx"])
    if uploaded_file:
        st.success(f"Uploaded: {uploaded_file.name}")
