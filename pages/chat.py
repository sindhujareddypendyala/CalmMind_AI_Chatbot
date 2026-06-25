import streamlit as st
import streamlit.components.v1 as components
import uuid
import time
import pandas as pd
import plotly.express as px
from datetime import datetime
import json

from database import db
from services import gemini_service, pdf_service
import re

def clean_response_text(text):
    """Remove accidental HTML fragments before displaying chat content."""
    cleaned = str(text or "")
    cleaned = re.sub(r"</?\s*(div|span|p|br|script|style|iframe)[^>]*>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"&lt;/?\s*(div|span|p|br|script|style|iframe)[^&]*&gt;", " ", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def format_message_to_html(text):
    # Escape HTML tags first to prevent breaking layouts
    html = clean_response_text(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    # Replace double line breaks with paragraph breaks
    html = html.replace("\n\n", "<br><br>").replace("\n", "<br>")
    
    # Replace markdown bold **text** -> <b>text</b>
    html = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", html)
    
    # Replace bullet lists * or - -> •
    lines = html.split("<br>")
    for i, line in enumerate(lines):
        line_strip = line.strip()
        if line_strip.startswith("* ") or line_strip.startswith("- "):
            lines[i] = "• " + line_strip[2:]
    html = "<br>".join(lines)
    
    return html

def render_custom_chat_input(session_id, processing=False):
    """Render Streamlit's cloud-safe chat composer."""
    message = st.chat_input(
        "CalmMind is thinking..." if processing else "How are you feeling today?",
        disabled=processing,
        key=f"chat_input_{session_id}",
    )
    if message and str(message).strip():
        st.session_state.pending_native_message = str(message).strip()
        st.session_state.current_session_id = session_id
        st.rerun()


def _message_value(message, key, default=None):
    """Read values from sqlite rows or dictionaries."""
    try:
        value = message[key]
        return default if value is None else value
    except (KeyError, TypeError, IndexError):
        return default


def _conversation_title_from_message(first_message):
    """Create a meaningful chat title instead of a truncated prompt preview."""
    text = re.sub(r"\s+", " ", str(first_message or "")).strip().lower()
    title_rules = [
        (("placement", "campus", "job offer"), "Placement Anxiety"),
        (("interview", "rejected", "selection"), "Interview Setback"),
        (("exam", "test", "marks", "grade", "study"), "Exam Stress"),
        (("career", "job", "work", "manager", "office"), "Career Concerns"),
        (("lonely", "alone", "friend", "relationship"), "Loneliness Support"),
        (("motivate", "motivation", "lazy", "procrastinat"), "Motivation Support"),
        (("confidence", "self doubt", "succeed", "failure"), "Confidence Support"),
        (("anxious", "anxiety", "panic", "worried", "nervous"), "Anxiety Support"),
        (("stress", "stressed", "pressure", "overwhelmed"), "Stress Support"),
        (("tired", "exhausted", "sleep", "burnout", "drained"), "Burnout Support"),
        (("angry", "frustrated", "mad", "irritated"), "Anger Support"),
        (("sad", "cry", "hurt", "down", "disappointed"), "Emotional Support"),
        (("goal", "habit", "routine", "plan"), "Wellness Goals"),
        (("happy", "grateful", "proud", "better"), "Positive Reflection"),
    ]

    for keywords, title in title_rules:
        if any(keyword in text for keyword in keywords):
            return title

    return "Daily Reflection" if text else "New Conversation"


def _unique_title_from_first_message(session_id, first_message, max_length=28):
    """Create a compact, unique session title from the first user message."""
    base_title = _conversation_title_from_message(first_message)[:max_length].rstrip(" .,-")
    existing_titles = {
        str(session["title"])
        for session in db.get_all_sessions()
        if session["session_id"] != session_id
    }

    candidate = base_title
    duplicate_number = 2
    while candidate in existing_titles:
        suffix = f" ({duplicate_number})"
        available = max(1, max_length - len(suffix))
        candidate = f"{base_title[:available].rstrip()}{suffix}"
        duplicate_number += 1

    return candidate


def _render_user_bubble(content):
    safe_content = (
        str(content)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )
    st.markdown(
        f"""
        <div style="display: flex; justify-content: flex-end; margin-bottom: 12px; width: 100%;">
            <div class="user-bubble">{safe_content}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _assistant_data(message):
    """Normalize a stored assistant message into the current response schema."""
    content = _message_value(message, "content", "")
    try:
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Assistant content is not a JSON object")
        parsed["response"] = clean_response_text(parsed.get("response", ""))
        parsed["affirmation"] = clean_response_text(parsed.get("affirmation", ""))
        recommendations = parsed.get("recommendations", [])
        if isinstance(recommendations, list):
            parsed["recommendations"] = [
                clean_response_text(item)
                for item in recommendations
                if clean_response_text(item)
            ]
        return parsed
    except (json.JSONDecodeError, TypeError, ValueError):
        return {
            "response": clean_response_text(content),
            "mood": _message_value(message, "mood", "😐 Neutral"),
            "stress_level": _message_value(message, "stress_level", "Medium"),
            "confidence_score": _message_value(message, "confidence_score", 85),
            "recommendations": [],
            "affirmation": "",
        }


def _assistant_bubble_html(data, response_html):
    mood = data.get("mood", "😐 Neutral")
    stress = data.get("stress_level", "Medium")
    confidence = data.get("confidence_score", 85)
    affirmation = str(data.get("affirmation", "") or "")
    affirmation_html = ""
    if affirmation:
        safe_affirmation = format_message_to_html(affirmation)
        affirmation_html = (
            '<div style="border-left:3px solid #2E8B57;padding-left:12px;'
            'margin:15px 0 5px 0;font-style:italic;color:#555;'
            'font-size:0.92rem;">'
            f'✨ "{safe_affirmation}"</div>'
        )

    return (
        '<div style="display:flex;justify-content:flex-start;margin-bottom:15px;width:100%;">'
        '<div class="assistant-bubble">'
        '<div style="background-color:#EAF2EC;border-radius:8px;padding:4px 10px;'
        'font-size:0.8rem;font-weight:600;color:#2E8B57;margin-bottom:12px;'
        'display:inline-block;border:1px solid rgba(46,139,87,0.12);">'
        f'📊 Mood: {mood} &nbsp;|&nbsp; ⚡ Stress: {stress} &nbsp;|&nbsp; 🎯 Conf: {confidence}%'
        '</div>'
        f'<div style="margin-bottom:10px;">{response_html}</div>'
        f'{affirmation_html}'
        '</div>'
        '</div>'
    )


def _render_assistant_response(data, animate=False):
    """Render one assistant response with CSS animation only."""
    response_text = str(data.get("response", "") or "")
    recommendations = data.get("recommendations", [])
    if not isinstance(recommendations, list):
        recommendations = []

    st.markdown(
        _assistant_bubble_html(
            data,
            format_message_to_html(response_text),
        ),
        unsafe_allow_html=True,
    )

    if recommendations:
        st.write("**Wellness Suggestions:**")
        columns = st.columns(len(recommendations))
        for index, recommendation in enumerate(recommendations):
            with columns[index]:
                safe_recommendation = format_message_to_html(str(recommendation))
                st.markdown(
                    '<div class="wellness-card" style="font-size: 0.9rem; '
                    'padding: 10px; margin-bottom: 0px; min-height: 80px; '
                    'display: flex; align-items: center; justify-content: center; '
                    f'text-align: center;">{safe_recommendation}</div>',
                    unsafe_allow_html=True,
                )


def _render_thinking_bubble(placeholder):
    placeholder.markdown(
        """
        <div style="display: flex; justify-content: flex-start; margin-bottom: 15px; width: 100%;">
            <div class="assistant-bubble" style="padding: 14px 20px;">
                <span style="color: #2E8B57; font-weight: 600;">🌿 CalmMind is thinking</span>
                <span class="thinking-dots"><span>.</span><span>.</span><span>.</span></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _recommended_breathing_type(data):
    """Return a breathing type only when recommendations explicitly include one."""
    recommendations = data.get("recommendations", []) if isinstance(data, dict) else []
    if not isinstance(recommendations, list):
        return None

    recommendation_text = " ".join(str(item) for item in recommendations).lower()
    breathing_terms = ("breath", "inhale", "exhale")
    if not any(term in recommendation_text for term in breathing_terms):
        return None
    if "4-7-8" in recommendation_text:
        return "4-7-8 Breathing"
    if "calm focus" in recommendation_text or "focus breathing" in recommendation_text:
        return "Calm Focus Breathing"
    return "Box Breathing"


def _render_breathing_widget(data):
    breathing_type = _recommended_breathing_type(data)
    if not breathing_type:
        return

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(f"#### 🌬️ Practice {breathing_type} Guide")

    if breathing_type == "4-7-8 Breathing":
        animation_keyframes = """
        @keyframes breathing-cycle {
            0%, 100% { transform: scale(1); opacity: 0.7; }
            21% { transform: scale(1.6); opacity: 1; }
            58% { transform: scale(1.6); opacity: 1; }
            95% { transform: scale(1); opacity: 0.7; }
        }
        """
        cycle_duration = "19s"
        guide_text = "Inhale (4s) ➡️ Hold (7s) ➡️ Exhale (8s)"
    else:
        animation_keyframes = """
        @keyframes breathing-cycle {
            0%, 100% { transform: scale(1); opacity: 0.7; }
            25% { transform: scale(1.6); opacity: 1; }
            50% { transform: scale(1.6); opacity: 1; }
            75% { transform: scale(1); opacity: 0.7; }
        }
        """
        cycle_duration = "16s"
        guide_text = "Inhale (4s) ➡️ Hold (4s) ➡️ Exhale (4s) ➡️ Hold Empty (4s)"

    st.markdown(
        f"""
        <style>
            {animation_keyframes}
            .breathing-bubble {{
                width: 120px;
                height: 120px;
                border-radius: 50%;
                background: radial-gradient(circle, #2E8B57 0%, #EAF2EC 100%);
                box-shadow: 0 0 25px rgba(46, 139, 87, 0.35);
                animation: breathing-cycle {cycle_duration} infinite ease-in-out;
                margin: 20px auto;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    bubble_column, guide_column = st.columns([0.4, 0.6])
    with bubble_column:
        st.markdown('<div class="breathing-bubble"></div>', unsafe_allow_html=True)
    with guide_column:
        st.write("**Interactive breathing bubble helper active.**")
        st.write("Follow the expansion of the bubble to guide your breathing:")
        st.write(guide_text)


def _auto_scroll_to_latest():
    """Smoothly move the parent Streamlit page to the latest chat content."""
    components.html(
        """
        <script>
            window.setTimeout(() => {
                const doc = window.parent.document;
                const anchors = doc.querySelectorAll('[data-calmind-chat-bottom="true"]');
                const anchor = anchors[anchors.length - 1];
                if (anchor) {
                    anchor.scrollIntoView({ behavior: 'smooth', block: 'end' });
                }
            }, 80);
        </script>
        """,
        height=0,
        width=0,
    )

def show():
    # Retrieve API Key from session state or env
    api_key = st.session_state.api_key
    
    # ------------------ SIDEBAR & NAVIGATION ------------------
    SIDEBAR_CUSTOM_CSS = """
    <style>
        /* Base styles for all buttons in sidebar horizontal blocks (history items) */
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div[data-testid="stHorizontalBlock"] div.stButton button {
            font-size: 0.72rem !important;
            padding: 1px 3px !important;
            min-height: 18px !important;
            height: 18px !important;
            line-height: 18px !important;
            border-radius: 6px !important;
            margin-bottom: 0px !important;
            background-color: transparent !important;
            border: none !important;
            color: #4A5568 !important;
            text-align: left !important;
            justify-content: flex-start !important;
            box-shadow: none !important;
            transition: all 0.15s !important;
            width: 100% !important;
        }
        
        /* Re-style only the New Chat button (direct child elements not in horizontal blocks) */
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div.stButton button {
            background-color: #2E8B57 !important;
            color: white !important;
            font-size: 0.95rem !important;
            font-weight: 500 !important;
            border-radius: 20px !important;
            padding: 8px 16px !important;
            min-height: 40px !important;
            height: 40px !important;
            justify-content: center !important;
            text-align: center !important;
            box-shadow: 0 4px 6px rgba(46, 139, 87, 0.15) !important;
            margin-bottom: 15px !important;
            width: 100% !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div.stButton button:hover {
            background-color: #246B43 !important;
            color: white !important;
        }
        
        /* Override specifically for history items inside horizontal blocks to prevent them from taking New Chat styles */
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div[data-testid="stHorizontalBlock"] div.stButton button {
            background-color: transparent !important;
            color: #4A5568 !important;
            font-size: 0.72rem !important;
            font-weight: 400 !important;
            border-radius: 6px !important;
            padding: 1px 3px !important;
            min-height: 18px !important;
            height: 18px !important;
            line-height: 18px !important;
            text-align: left !important;
            justify-content: flex-start !important;
            box-shadow: none !important;
            width: 100% !important;
        }
        
        /* Row container styled as a small, compact chatgpt-like card (flat, borderless) */
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div[data-testid="stHorizontalBlock"] {
            background-color: transparent !important;
            border: none !important;
            border-radius: 6px !important;
            padding: 0px 4px !important;
            margin: 0px 0px 2px 0px !important;
            transition: all 0.15s ease-in-out !important;
            box-shadow: none !important;
            display: flex !important;
            align-items: center !important;
            gap: 0px !important;
            min-height: 20px !important;
            height: 20px !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div[data-testid="stHorizontalBlock"]:hover {
            background-color: rgba(46, 139, 87, 0.05) !important;
        }
        
        /* Active selected chat row style */
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div[data-testid="stHorizontalBlock"]:has(button[kind="primary"]) {
            background-color: rgba(46, 139, 87, 0.1) !important;
        }
        
        /* Collapse all default Streamlit padding, margin and vertical blocks inside sidebar horizontal blocks */
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div[data-testid="stHorizontalBlock"] div[data-testid="column"] {
            padding: 0px !important;
            margin: 0px !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div[data-testid="stHorizontalBlock"] div[data-testid="stVerticalBlock"] {
            padding: 0px !important;
            margin: 0px !important;
            gap: 0px !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div[data-testid="stHorizontalBlock"] .element-container {
            margin: 0px !important;
            padding: 0px !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div[data-testid="stHorizontalBlock"] .stButton {
            margin: 0px !important;
            padding: 0px !important;
        }
        
        /* Active text styling */
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div[data-testid="stHorizontalBlock"] button[kind="primary"] {
            color: #2E8B57 !important;
            font-weight: 600 !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div[data-testid="stHorizontalBlock"]:hover div[data-testid="column"]:first-of-type button {
            color: #2E8B57 !important;
        }
        
        /* Custom styled delete trash icon in column 2 */
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-child(2) div.stButton button {
            opacity: 0 !important;
            transition: opacity 0.2s !important;
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: #888 !important;
            padding: 0px !important;
            min-height: 20px !important;
            height: 20px !important;
            width: auto !important;
            justify-content: center !important;
            text-align: center !important;
            margin: 0px !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div[data-testid="stHorizontalBlock"]:hover div[data-testid="column"]:nth-child(2) div.stButton button {
            opacity: 1 !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-child(2) div.stButton button:hover {
            color: #d9534f !important;
            background-color: rgba(217, 83, 79, 0.1) !important;
        }
        
        /* Custom styled bubbles */
        .user-bubble {
            background-color: #2E8B57;
            color: white;
            padding: 12px 18px;
            border-radius: 20px 20px 4px 20px;
            max-width: 75%;
            box-shadow: 0 3px 10px rgba(46, 139, 87, 0.12);
            font-size: 0.95rem;
            line-height: 1.5;
            word-wrap: break-word;
        }
        .assistant-bubble {
            background-color: #FFFFFF;
            color: #2F4F4F;
            padding: 18px 22px;
            border-radius: 20px 20px 20px 4px;
            max-width: 80%;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03);
            border: 1px solid rgba(46, 139, 87, 0.08);
            font-size: 0.95rem;
            line-height: 1.6;
            word-wrap: break-word;
        }
        .thinking-dots span {
            display: inline-block;
            color: #2E8B57;
            font-size: 1.1rem;
            animation: thinking-pulse 1.2s infinite;
        }
        .thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
        .thinking-dots span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes thinking-pulse {
            0%, 60%, 100% { opacity: 0.25; transform: translateY(0); }
            30% { opacity: 1; transform: translateY(-2px); }
        }
    </style>
    """
    st.markdown(SIDEBAR_CUSTOM_CSS, unsafe_allow_html=True)
    
    st.sidebar.markdown(
        "<h1 style='text-align: center; color: #2E8B57; font-size: 2rem; margin-bottom: 0px;'>🧠 CalmMind AI</h1>", 
        unsafe_allow_html=True
    )
    st.sidebar.markdown(
        "<p style='text-align: center; color: #666; font-size: 0.85rem; margin-top: 0px; margin-bottom: 20px;'>Your Wellness Companion</p>", 
        unsafe_allow_html=True
    )
    
    # Navigation Radio Buttons
    view = st.sidebar.radio(
        "Navigation",
        ["💬 Chat Companion", "📊 Mood Analytics", "📅 Wellness Planner", "🏡 Back to Home"],
        label_visibility="collapsed"
    )
    
    st.sidebar.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
    
    # New Chat Button
    if st.sidebar.button("➕ New Chat", use_container_width=True):
        new_id = uuid.uuid4().hex
        db.create_session(new_id, f"Chat - {datetime.now().strftime('%b %d, %H:%M')}")
        st.session_state.current_session_id = new_id
        st.session_state.auto_scroll = False
        st.rerun()
        
    st.sidebar.markdown("<p style='font-size: 0.9rem; font-weight: 600; color: #666;'>📜 Previous Chats</p>", unsafe_allow_html=True)
    
    # Fetch all sessions
    sessions = db.get_all_sessions()
    
    # Sidebar Chat List container
    st.sidebar.markdown('<div style="max-height: 250px; overflow-y: auto;">', unsafe_allow_html=True)
    for s in sessions:
        col_btn, col_del = st.sidebar.columns([0.85, 0.15])
        
        # Highlight active session
        is_active = st.session_state.current_session_id == s["session_id"]
        # Small compact titles (making title size fit better)
        btn_label = f"💬 {s['title'][:18]}..." if len(s['title']) > 18 else f"💬 {s['title']}"
        
        with col_btn:
            if st.button(
                btn_label, 
                key=f"select_{s['session_id']}", 
                use_container_width=True,
                type="primary" if is_active else "secondary"
            ):
                st.session_state.current_session_id = s["session_id"]
                st.session_state.auto_scroll = True
                # Safeguard: prevent typewriter replay on switching
                s_messages = db.get_session_messages(s["session_id"])
                if s_messages:
                    st.session_state.typed_message_id = s_messages[-1]["message_id"]
                st.rerun()
                
        with col_del:
            if st.button("🗑️", key=f"del_{s['session_id']}", help="Delete chat"):
                db.delete_session(s["session_id"])
                if st.session_state.current_session_id == s["session_id"]:
                    st.session_state.current_session_id = None
                st.rerun()
    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    

            
    # Page Redirection
    if view == "🏡 Back to Home":
        st.session_state.page = "Home"
        st.rerun()
        
    # Prioritize session_id from query parameters if present (e.g. from iframe form submission)
    session_id_param = st.query_params.get("session_id", "")
    if session_id_param:
        st.session_state.current_session_id = session_id_param
        
    # Ensure a session is active if on Chat tab
    if not st.session_state.current_session_id and sessions:
        st.session_state.current_session_id = sessions[0]["session_id"]
    elif not st.session_state.current_session_id and not sessions:
        # Auto-create if empty
        new_id = uuid.uuid4().hex
        db.create_session(new_id, "First Chat")
        st.session_state.current_session_id = new_id
        
    # ------------------ ROUTE SUB-PAGES ------------------
    if view == "💬 Chat Companion":
        render_chat_companion(api_key)
    elif view == "📊 Mood Analytics":
        render_mood_analytics(api_key)
    elif view == "📅 Wellness Planner":
        render_wellness_planner(api_key)


# ==================== 1. CHAT COMPANION ====================
def render_chat_companion(api_key):
    if "auto_scroll" not in st.session_state:
        st.session_state.auto_scroll = False
    if "last_processed_query" not in st.session_state:
        st.session_state.last_processed_query = None

    session_id = st.session_state.current_session_id

    # Read custom text input without processing it before the chat is visible.
    user_msg = st.query_params.get("user_msg", "")
    native_msg = st.session_state.pop("pending_native_message", "")
    query_text = str(native_msg or user_msg or "").strip()
    pending_message = None

    if query_text:
        if query_text != st.session_state.last_processed_query:
            pending_message = query_text
            st.session_state.last_processed_query = query_text
            for key in ("user_msg", "session_id"):
                if key in st.query_params:
                    del st.query_params[key]
    else:
        # Allow the user to intentionally send the same text again later.
        st.session_state.last_processed_query = None

    st.markdown(
        "<h2 style='margin-bottom: 5px;'>💬 Wellness Chat Companion</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color: #666; font-size: 0.95rem; margin-top: 0px;'>"
        "Talk through your thoughts in a safe space.</p>",
        unsafe_allow_html=True,
    )

    messages = db.get_session_messages(session_id)

    # Upgrade old generic titles when their first user message is available.
    first_stored_user_message = next(
        (
            _message_value(message, "content", "")
            for message in messages
            if _message_value(message, "role") == "user"
        ),
        None,
    )
    current_session = next(
        (
            session
            for session in db.get_all_sessions()
            if session["session_id"] == session_id
        ),
        None,
    )
    if first_stored_user_message and current_session:
        current_title = str(current_session["title"])
        generic_title = (
            current_title in {"First Chat", "New Session", "New Conversation"}
            or current_title.startswith("Chat - ")
            or current_title.startswith("Quick Support Re")
        )
        if generic_title:
            db.update_session_title(
                session_id,
                _unique_title_from_first_message(
                    session_id,
                    first_stored_user_message,
                ),
            )

    # Quick Support is an empty-chat starter only.
    quick_support_placeholder = st.empty()
    quick_prompt = None
    if len(messages) == 0 and pending_message is None:
        with quick_support_placeholder.container():
            st.write("How can I support you right now?")
            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                if st.button("😰 I'm Stressed", use_container_width=True):
                    quick_prompt = (
                        "I feel stressed out. Can you give me some relaxation "
                        "techniques and guidance?"
                    )
            with col2:
                if st.button("🤯 I'm Overthinking", use_container_width=True):
                    quick_prompt = (
                        "My brain is racing and I'm overthinking everything. "
                        "Help me focus and calm down."
                    )
            with col3:
                if st.button("💪 Motivate Me", use_container_width=True):
                    quick_prompt = (
                        "I am feeling low on motivation and energy today. "
                        "Motivate me to take a small step."
                    )
            with col4:
                if st.button("🌿 Breathing Help", use_container_width=True):
                    quick_prompt = (
                        "Can we do a breathing exercise together? Suggest a "
                        "suitable breathing exercise."
                    )
            with col5:
                if st.button("❤️ Emotional Support", use_container_width=True):
                    quick_prompt = (
                        "I'm having a tough emotional day. I just need some "
                        "gentle, positive support."
                    )

    if quick_prompt:
        pending_message = quick_prompt
        quick_support_placeholder.empty()

    # Render all stored messages before making any Gemini request.
    chat_container = st.container()
    with chat_container:
        if not messages and pending_message is None:
            st.markdown(
                '<div style="text-align: center; color: #888; padding: 40px 10px;">'
                "🌿 Hello! I am CalmMind AI. Share your feelings, stress, or goals, "
                "or click one of the quick support buttons above to begin.</div>",
                unsafe_allow_html=True,
            )
        else:
            for message in messages:
                role = _message_value(message, "role")
                if role == "user":
                    _render_user_bubble(_message_value(message, "content", ""))
                    continue

                data = _assistant_data(message)
                message_id = _message_value(message, "message_id")
                is_latest = (
                    message_id == _message_value(messages[-1], "message_id")
                )
                should_animate = (
                    pending_message is None
                    and not st.session_state.get("disable_replay_animation", False)
                    and is_latest
                    and st.session_state.get("typed_message_id") != message_id
                )
                _render_assistant_response(data, animate=should_animate)
                if should_animate:
                    st.session_state.typed_message_id = message_id

    # Only show the persisted breathing helper when the latest saved response
    # explicitly recommends a breathing exercise and no newer turn is pending.
    if messages and pending_message is None:
        last_message = messages[-1]
        if _message_value(last_message, "role") == "assistant":
            _render_breathing_widget(_assistant_data(last_message))

    # These containers are deliberately created before the input. Filling them
    # later keeps the newest turn above the bottom-pinned composer.
    live_turn_container = st.container()
    live_breathing_container = st.container()

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    input_placeholder = st.empty()
    with input_placeholder.container():
        render_custom_chat_input(session_id, processing=pending_message is not None)

    st.markdown(
        '<div style="text-align: center; font-size: 0.74rem; color: #a0aec0; '
        'font-family: "Outfit", sans-serif; margin-top: 10px; max-width: '
        '600px; margin-left: auto; margin-right: auto; line-height: 1.4;">'
        "⚠️ <b>Disclaimer:</b> CalmMind AI is an AI wellness assistant. It is "
        "not a replacement for professional therapy, clinical advice, or "
        "mental health counseling.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="text-align: center; font-size: 0.78rem; color: #888; '
        'font-family: "Outfit", sans-serif; margin-top: 5px; '
        'margin-bottom: 15px;">Built by <b>Sindhuja Reddy Pendyala</b> | '
        "For <i>GenAI Internship</i></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div data-calmind-chat-bottom="true" style="height: 1px;"></div>',
        unsafe_allow_html=True,
    )

    if pending_message is not None:
        is_first_user_message = not any(
            _message_value(message, "role") == "user"
            for message in messages
        )

        db.add_message(session_id, "user", pending_message)
        if is_first_user_message:
            db.update_session_title(
                session_id,
                _unique_title_from_first_message(
                    session_id,
                    pending_message,
                ),
            )

        with live_turn_container:
            _render_user_bubble(pending_message)
            thinking_placeholder = st.empty()
            _render_thinking_bubble(thinking_placeholder)

        _auto_scroll_to_latest()

        try:
            history_messages = db.get_session_messages(session_id)
            history = [
                {
                    "role": _message_value(message, "role"),
                    "content": _message_value(message, "content", ""),
                }
                for message in history_messages
            ]
            ai_data = gemini_service.get_chat_response(history, api_key)

            mood = ai_data.get("mood", "😐 Neutral")
            stress = ai_data.get("stress_level", "Medium")
            confidence = ai_data.get("confidence_score", 85)

            db.add_message(
                session_id=session_id,
                role="assistant",
                content=json.dumps(ai_data),
                mood=mood,
                stress_level=stress,
                confidence_score=confidence,
            )
            db.add_mood_log(
                session_id=session_id,
                mood=mood,
                stress_level=stress,
                confidence_score=confidence,
            )

            saved_messages = db.get_session_messages(session_id)
            if saved_messages:
                st.session_state.typed_message_id = _message_value(
                    saved_messages[-1],
                    "message_id",
                )

            thinking_placeholder.empty()
            with thinking_placeholder.container():
                _render_assistant_response(ai_data, animate=True)

            with live_breathing_container:
                _render_breathing_widget(ai_data)

        except Exception as exc:
            print(f"[ERROR] Chat response failed: {type(exc).__name__}: {exc}")
            thinking_placeholder.empty()
            ai_data = {
                "response": "I'm having a temporary difficulty connecting right now. Please try again in a moment.",
                "mood": "😐 Neutral",
                "stress_level": "Low",
                "confidence_score": 0.0,
                "recommendations": [],
                "affirmation": "",
            }
            db.add_message(
                session_id=session_id,
                role="assistant",
                content=json.dumps(ai_data),
                mood=ai_data["mood"],
                stress_level=ai_data["stress_level"],
                confidence_score=ai_data["confidence_score"],
            )
            with thinking_placeholder.container():
                _render_assistant_response(ai_data, animate=False)

        st.session_state.auto_scroll = False
        _auto_scroll_to_latest()
        st.rerun()
        
    elif st.session_state.get("auto_scroll"):
        st.session_state.auto_scroll = False
        _auto_scroll_to_latest()
# ==================== 2. MOOD ANALYTICS ====================
def render_mood_analytics(api_key):
    st.markdown("<h2>📊 Mood Tracking & Analytics</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #666; font-size: 0.95rem; margin-top: 0px;'>Observe your emotional trends and stress patterns over time.</p>", unsafe_allow_html=True)
    
    # Retrieve mood logs
    logs = db.get_mood_logs()
    
    if not logs:
        st.info("No logs available yet. Engage in chat companion conversations to start tracking your mood!")
        return
        
    # Build dataframe
    df = pd.DataFrame([dict(l) for l in logs])
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Map stress to numerical value for continuous plotting
    stress_mapping = {"Low": 1, "Medium": 2, "High": 3}
    df['Stress Num'] = df['stress_level'].map(stress_mapping)
    
    # Layout grids
    col1, col2 = st.columns(2, gap="large")
    
    with col1:
        st.subheader("📈 Stress Level Trends")
        # Line plot for stress
        fig_stress = px.line(
            df, 
            x='timestamp', 
            y='Stress Num', 
            title='Stress Levels over Time',
            labels={'timestamp': 'Date & Time', 'Stress Num': 'Stress level (1=Low, 2=Medium, 3=High)'},
            markers=True,
            line_shape='linear',
            color_discrete_sequence=['#2E8B57']
        )
        fig_stress.update_yaxes(tickvals=[1, 2, 3], ticktext=["Low", "Medium", "High"])
        fig_stress.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#2F4F4F')
        )
        st.plotly_chart(fig_stress, use_container_width=True)
        
    with col2:
        st.subheader("📊 Mood Distribution")
        # Count values for moods
        mood_counts = df['mood'].value_counts().reset_index()
        mood_counts.columns = ['Mood', 'Frequency']
        
        fig_mood = px.bar(
            mood_counts,
            y='Mood',
            x='Frequency',
            title='Mood Frequency Log',
            orientation='h',
            color='Frequency',
            color_continuous_scale=px.colors.sequential.Greens
        )
        fig_mood.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#2F4F4F')
        )
        st.plotly_chart(fig_mood, use_container_width=True)
        
    st.markdown("<hr>", unsafe_allow_html=True)
    st.subheader("✨ AI Wellness Insights")
    
    # Generate insights from history using Gemini
    if len(df) > 0:
        # Construct summary logs to prompt Gemini
        summary_log_str = ""
        for index, row in df.tail(10).iterrows():
            summary_log_str += f"- Time: {row['timestamp'].strftime('%b %d, %H:%M')}, Mood: {row['mood']}, Stress Level: {row['stress_level']}\n"
            
        with st.spinner("Generating personalized insights..."):
            prompt = f"""
            Analyze the following mood log history:
            {summary_log_str}
            
            Identify:
            1. Most common mood
            2. Stress trends
            3. Emotional patterns
            
            Generate a short, beautiful, and empathetic wellness guidance paragraph (2-3 sentences max) outlining suggestions or patterns you observe. Start directly with the summary, speaking directly to the user (use "you" and "your"). Do not include headers.
            """
            try:
                # Fallback to model API call
                try:
                    import google.generativeai as genai
                    model = genai.GenerativeModel("gemini-1.5-flash")
                except Exception:
                    model = genai.GenerativeModel("gemini-2.5-flash")
                    
                response = model.generate_content(prompt)
                insights_text = response.text
            except Exception as e:
                print(f"[ERROR] Wellness insights failed: {type(e).__name__}: {e}")
                insights_text = (
                    "I'm having a temporary difficulty connecting right now. Please try again in a moment. "
                    "For now, notice your recent mood pattern and choose one small support action for today."
                )
                
            st.markdown(
                f'<div class="wellness-card" style="border-left: 4px solid #2E8B57;">'
                f'<p style="font-size: 1.05rem; line-height: 1.6; color: #2F4F4F;">{insights_text}</p>'
                f'</div>',
                unsafe_allow_html=True
            )


# ==================== 3. WELLNESS PLANNER ====================
def render_wellness_planner(api_key):
    st.markdown("<h2>📅 Personalized Wellness Planner</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #666; font-size: 0.95rem; margin-top: 0px;'>Establish a structured wellness plan for your daily routine.</p>", unsafe_allow_html=True)
    
    # Forms
    with st.form("wellness_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("Name:", placeholder="Enter your name")
            occupation = st.text_input("Occupation:", placeholder="e.g. Student, Engineer, Teacher")
            stress_level = st.selectbox("Current Stress Level:", ["Low", "Medium", "High"])
            
        with col2:
            sleep_hours = st.slider("Average Sleep Hours:", 3.0, 12.0, 7.0, 0.5)
            goal = st.selectbox(
                "Primary Wellness Goal:", 
                ["Manage Anxiety", "Reduce Stress", "Stop Overthinking", "Improve Work-Life Balance", "Boost Energy & Motivation"]
            )
            challenge = st.text_input("Current Challenge:", placeholder="e.g., Burnout at work, exam pressure")
            
        submitted = st.form_submit_button("✨ Generate My Wellness Plan")
        
    if submitted:
        if not name:
            st.info("Add your name so the plan can feel more personal.")
        elif not api_key:
            st.info("I'm having a temporary difficulty connecting right now. Please try again in a moment.")
        else:
            user_data = {
                "name": name,
                "occupation": occupation,
                "stress_level": stress_level,
                "sleep_hours": sleep_hours,
                "goal": goal,
                "challenge": challenge
            }
            
            with st.spinner("Creating your custom wellness routines and exercises..."):
                plan = gemini_service.generate_wellness_plan(user_data, api_key)
                
                # Save to session state so it persists during page actions
                st.session_state.wellness_user_data = user_data
                st.session_state.wellness_plan = plan
                
    # If plan exists in session state, render it
    if "wellness_plan" in st.session_state:
        plan = st.session_state.wellness_plan
        user_data = st.session_state.wellness_user_data
        
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(f"### 📋 Wellness Plan for {user_data['name']}")
        
        # Display routines in columns
        col_m, col_a, col_e = st.columns(3)
        
        with col_m:
            st.markdown(
                '<div class="wellness-card" style="height: 100%;">'
                '<h4 style="color: #2E8B57;">🌅 Morning Routine</h4>'
                + "".join([f"<p style='font-size: 0.95rem; margin-bottom: 5px;'>🌱 {step}</p>" for step in plan.get('morning_routine', [])]) +
                '</div>',
                unsafe_allow_html=True
            )
            
        with col_a:
            st.markdown(
                '<div class="wellness-card" style="height: 100%;">'
                '<h4 style="color: #2E8B57;">☀ Afternoon Routine</h4>'
                + "".join([f"<p style='font-size: 0.95rem; margin-bottom: 5px;'>🌱 {step}</p>" for step in plan.get('afternoon_routine', [])]) +
                '</div>',
                unsafe_allow_html=True
            )
            
        with col_e:
            st.markdown(
                '<div class="wellness-card" style="height: 100%;">'
                '<h4 style="color: #2E8B57;">🌙 Evening Routine</h4>'
                + "".join([f"<p style='font-size: 0.95rem; margin-bottom: 5px;'>🌱 {step}</p>" for step in plan.get('evening_routine', [])]) +
                '</div>',
                unsafe_allow_html=True
            )
            
        # Breathing exercise recommendation
        st.markdown("#### 🌬️ Recommended Breathing Exercise")
        b_ex = plan.get('breathing_exercise', {})
        
        st.markdown(
            f'<div class="wellness-card">'
            f'<h5>🌿 {b_ex.get("name", "N/A")}</h5>'
            f'<p><b>Instructions:</b> {b_ex.get("instructions", "N/A")}</p>'
            f'<p><b>Duration:</b> {b_ex.get("duration", "N/A")} &nbsp;|&nbsp; <b>Benefits:</b> {b_ex.get("benefits", "N/A")}</p>'
            f'</div>',
            unsafe_allow_html=True
        )
        
        # Affirmation & Weekly Guidance
        col_aff, col_gui = st.columns(2)
        with col_aff:
            st.markdown(
                f'<div class="wellness-card" style="height: 100%; background-color: #EAF2EC; border: 1px solid #2E8B57;">'
                f'<h5 style="color: #2E8B57;">💬 Daily Affirmation</h5>'
                f'<p style="font-size: 1.1rem; font-style: italic; text-align: center; padding: 15px 0;">"{plan.get("affirmation", "")}"</p>'
                f'</div>',
                unsafe_allow_html=True
            )
        with col_gui:
            st.markdown(
                '<div class="wellness-card" style="height: 100%;">'
                '<h5>📅 Weekly Wellness Guidance</h5>'
                + "".join([f"<p style='font-size: 0.95rem; margin-bottom: 5px;'>📌 {guidance}</p>" for guidance in plan.get('weekly_guidance', [])]) +
                '</div>',
                unsafe_allow_html=True
            )
            
        # PDF Exporter Button
        st.markdown("<div style='text-align: center; margin-top: 20px;'>", unsafe_allow_html=True)
        
        with st.spinner("Compiling plan PDF..."):
            pdf_bytes = pdf_service.generate_wellness_pdf(user_data, plan)
            
        st.download_button(
            label="📥 Download Wellness Plan (PDF)",
            data=pdf_bytes,
            file_name=f"Wellness_Plan_{user_data['name'].replace(' ', '_')}.pdf",
            mime="application/pdf"
        )
        st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    import os
    if "api_key" not in st.session_state:
        try:
            st.session_state.api_key = os.getenv("GEMINI_API_KEY", "") or st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            st.session_state.api_key = os.getenv("GEMINI_API_KEY", "")
    if "current_session_id" not in st.session_state:
        # Always generate a fresh session ID on direct loading to avoid showing historical logs
        import uuid
        new_id = uuid.uuid4().hex
        db.create_session(new_id, "New Conversation")
        st.session_state.current_session_id = new_id
    show()
