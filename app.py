import streamlit as st
import os
from dotenv import load_dotenv
from database.db import init_db

# Load environment variables
load_dotenv()


def get_configured_api_key():
    """Read Gemini key from environment or Streamlit Cloud secrets."""
    key = os.getenv("GEMINI_API_KEY", "")
    if key:
        return key
    try:
        return st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        return ""

# Initialize Database
init_db()

# Page configuration
st.set_page_config(
    page_title="CalmMind AI - Your Personal Mental Wellness Companion",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed"  # Start collapsed so home page is clean
)

# Initialize Session States
if "page" not in st.session_state:
    # Route directly to Chat page if query params are present (prevents reload redirects to Home)
    if "user_msg" in st.query_params or "session_id" in st.query_params:
        st.session_state.page = "Chat"
    else:
        st.session_state.page = "Home"

if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

if "api_key" not in st.session_state:
    st.session_state.api_key = get_configured_api_key()

# Global CSS Injection for Styling and Custom Layout
GLOBAL_CSS = """
<style>
    /* Premium fonts and palette overrides */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"], .stApp {
        font-family: 'Outfit', sans-serif;
        background-color: #FAFAF7;
        color: #2F4F4F;
    }
    
    /* Hide default Streamlit page elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Style headers */
    h1, h2, h3, h4, h5, h6 {
        color: #2F4F4F !important;
        font-weight: 600 !important;
    }
    
    /* Button custom styling */
    div.stButton > button {
        background-color: #2E8B57 !important;
        color: white !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 500 !important;
        border-radius: 20px !important;
        border: none !important;
        padding: 0.5rem 1.8rem !important;
        box-shadow: 0 4px 6px rgba(46, 139, 87, 0.15) !important;
        transition: all 0.2s ease-in-out !important;
    }
    div.stButton > button:hover {
        background-color: #246B43 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 12px rgba(46, 139, 87, 0.25) !important;
    }
    div.stButton > button:active {
        transform: translateY(0px) !important;
    }
    
    /* Input border customization */
    .stTextInput>div>div>input {
        border-radius: 12px !important;
        border: 1px solid #E2E8F0 !important;
        color: #2F4F4F !important;
    }
    .stTextInput>div>div>input:focus {
        border-color: #2E8B57 !important;
        box-shadow: 0 0 0 1px #2E8B57 !important;
    }
    
    /* Style cards */
    .wellness-card {
        background-color: #FFFFFF;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.04);
        border: 1px solid rgba(46, 139, 87, 0.08);
        margin-bottom: 1rem;
        transition: transform 0.2s ease;
    }
    .wellness-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(46, 139, 87, 0.08);
    }
</style>
"""
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# Page Router
def run_app():
    if st.session_state.page == "Home":
        from pages import home
        home.show()
    elif st.session_state.page == "Chat":
        from pages import chat
        chat.show()

if __name__ == "__main__":
    run_app()
