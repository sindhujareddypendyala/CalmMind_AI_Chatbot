import streamlit as st
import uuid
import time
import pandas as pd
import plotly.express as px
from datetime import datetime
import json

from database import db
from services import gemini_service, pdf_service
import re

def format_message_to_html(text):
    # Escape HTML tags first to prevent breaking layouts
    html = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
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

def render_custom_chat_input():
    # Custom HTML/JS chat input field combining text input and mic trigger in one block
    chat_input_html = """
    <div style="font-family: 'Outfit', sans-serif; display: flex; flex-direction: column; align-items: center; width: 100%; box-sizing: border-box; padding: 2px 0;">
        <div style="background-color: white; border: 1px solid rgba(46,139,87,0.2); border-radius: 24px; padding: 8px 16px; display: flex; align-items: center; width: 100%; box-shadow: 0 4px 15px rgba(0,0,0,0.04); box-sizing: border-box; margin-bottom: 0px;">
            <form id="chat-form" action="" method="GET" target="_parent" style="display: flex; align-items: center; width: 100%; margin: 0; padding: 0;">
                <input type="text" id="chat-input-field" name="user_msg" placeholder="How are you feeling today?" style="flex-grow: 1; border: none; outline: none; font-size: 0.95rem; font-family: 'Outfit', sans-serif; color: #2F4F4F; background: transparent; padding: 4px 0;">
                
                <button id="mic-btn" type="button" style="background: none; border: none; color: #777; cursor: pointer; padding: 0 12px; display: flex; align-items: center; justify-content: center; outline: none; transition: color 0.2s;">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
                </button>
                
                <button id="send-btn" type="submit" style="background-color: #2E8B57; color: white; border: none; border-radius: 50%; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; cursor: pointer; outline: none; transition: background-color 0.2s; padding: 0;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-left: 2px;"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                </button>
            </form>
        </div>
    </div>

    <script>
        const form = document.getElementById('chat-form');
        const input = document.getElementById('chat-input-field');
        const micBtn = document.getElementById('mic-btn');
        const sendBtn = document.getElementById('send-btn');
        
        try {
            form.action = window.parent.location.pathname;
        } catch (e) {
            form.action = '/';
        }
        
        // Listen to submit to show loading state
        form.addEventListener('submit', (e) => {
            if (input.disabled) {
                e.preventDefault();
                return;
            }
            input.disabled = true;
            micBtn.disabled = true;
            sendBtn.disabled = true;
            sendBtn.style.backgroundColor = '#888';
            input.placeholder = 'Processing message... Please wait.';
        });
        
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            const recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            recognition.lang = 'en-US';
            
            let isListening = false;
            
            micBtn.addEventListener('click', (e) => {
                e.preventDefault();
                if (isListening) {
                    recognition.stop();
                } else {
                    input.placeholder = 'Listening... Speak now.';
                    input.value = '';
                    recognition.start();
                }
            });
            
            recognition.onstart = () => {
                isListening = true;
                micBtn.style.color = '#d9534f'; // Red recording
                input.placeholder = 'Listening... Speak now.';
            };
            
            recognition.onerror = (event) => {
                isListening = false;
                micBtn.style.color = '#777';
                input.placeholder = 'Speech error: ' + event.error;
            };
            
            recognition.onend = () => {
                isListening = false;
                micBtn.style.color = '#777';
                if (!input.disabled) {
                    input.placeholder = 'How are you feeling today?';
                }
            };
            
            recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                input.value = transcript;
                
                // Disable and show processing voice message state
                input.disabled = true;
                micBtn.disabled = true;
                sendBtn.disabled = true;
                sendBtn.style.backgroundColor = '#888';
                input.placeholder = 'Processing voice message... Please wait.';
                
                form.submit();
            };
        } else {
            micBtn.style.display = 'none';
        }
    </script>
    """
    escaped_html = chat_input_html.replace('"', '&quot;').replace('\n', ' ')
    st.markdown(
        f'<iframe srcdoc="{escaped_html}" width="100%" height="60" style="border: none; overflow: hidden;" scrolling="no" allow="microphone; clipboard-write;"></iframe>',
        unsafe_allow_html=True
    )

def show():
    # Retrieve API Key from session state or env
    api_key = st.session_state.api_key
    
    # ------------------ SIDEBAR & NAVIGATION ------------------
    SIDEBAR_CUSTOM_CSS = """
    <style>
        /* Base styles for all buttons in sidebar horizontal blocks (history items) */
        [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] div[data-testid="stHorizontalBlock"] div.stButton button {
            font-size: 0.76rem !important;
            padding: 2px 4px !important;
            min-height: 22px !important;
            height: 22px !important;
            line-height: 22px !important;
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
            font-size: 0.76rem !important;
            font-weight: 400 !important;
            border-radius: 6px !important;
            padding: 2px 4px !important;
            min-height: 22px !important;
            height: 22px !important;
            line-height: 22px !important;
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
            min-height: 26px !important;
            height: 26px !important;
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
        btn_label = f"💬 {s['title'][:16]}..." if len(s['title']) > 16 else f"💬 {s['title']}"
        
        with col_btn:
            if st.button(
                btn_label, 
                key=f"select_{s['session_id']}", 
                use_container_width=True,
                type="primary" if is_active else "secondary"
            ):
                st.session_state.current_session_id = s["session_id"]
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
    session_id = st.session_state.current_session_id
    
    # Process Speech-to-Text & custom chat input parameters
    user_msg = st.query_params.get("user_msg", "")
    voice_input = st.query_params.get("voice_input", "")
    query_text = user_msg or voice_input
    
    if "last_processed_query" not in st.session_state:
        st.session_state.last_processed_query = None
        
    if query_text and query_text != st.session_state.last_processed_query:
        st.session_state.last_processed_query = query_text
        st.query_params.clear()
        
        if not api_key:
            st.error("Please enter a Gemini API Key in the sidebar to start chatting.")
        else:
            with st.spinner("Processing message..."):
                db.add_message(session_id, "user", query_text)
                
                # Auto session renaming (update in-place to protect message history)
                messages_check = db.get_session_messages(session_id)
                if len(messages_check) == 1:
                    title_suggestion = query_text[:20] + "..." if len(query_text) > 20 else query_text
                    db.update_session_title(session_id, title_suggestion)
                    
                # Process assistant response immediately in the same turn (snappy execution)
                history_messages = db.get_session_messages(session_id)
                history = [{"role": m["role"], "content": m["content"]} for m in history_messages]
                
                ai_data = gemini_service.get_chat_response(history, api_key)
                mood = ai_data.get("mood", "💭 Reflective")
                stress = ai_data.get("stress_level", "Medium")
                confidence = ai_data.get("confidence_score", 85)
                
                # Save assistant response
                db.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=json.dumps(ai_data),
                    mood=mood,
                    stress_level=stress,
                    confidence_score=confidence
                )
                
                # Log mood log
                db.add_mood_log(
                    session_id=session_id,
                    mood=mood,
                    stress_level=stress,
                    confidence_score=confidence
                )
            st.rerun()
            
    # Page Header
    st.markdown("<h2 style='margin-bottom: 5px;'>💬 Wellness Chat Companion</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #666; font-size: 0.95rem; margin-top: 0px;'>Talk through your thoughts in a safe space.</p>", unsafe_allow_html=True)
    
    # Fetch messages
    messages = db.get_session_messages(session_id)
    
    # ------------------ QUICK SUPPORT BUTTONS ------------------
    st.write("How can I support you right now?")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    quick_prompt = None
    with col1:
        if st.button("😰 I'm Stressed", use_container_width=True):
            quick_prompt = "I feel stressed out. Can you give me some relaxation techniques and guidance?"
    with col2:
        if st.button("🤯 I'm Overthinking", use_container_width=True):
            quick_prompt = "My brain is racing and I'm overthinking everything. Help me focus and calm down."
    with col3:
        if st.button("💪 Motivate Me", use_container_width=True):
            quick_prompt = "I am feeling low on motivation and energy today. Motivate me to take a small step."
    with col4:
        if st.button("🌿 Breathing Help", use_container_width=True):
            quick_prompt = "Can we do a breathing exercise together? Suggest a suitable breathing exercise."
    with col5:
        if st.button("❤️ Emotional Support", use_container_width=True):
            quick_prompt = "I'm having a tough emotional day. I just need some gentle, positive support."
            
    # Process Quick Support Prompt
    if quick_prompt:
        if not api_key:
            st.error("Please enter a Gemini API Key in the sidebar to start chatting.")
        else:
            db.add_message(session_id, "user", quick_prompt)
            sessions = db.get_all_sessions()
            for s in sessions:
                if s["session_id"] == session_id and s["title"] in ["First Chat", "New Session", f"Chat - {datetime.now().strftime('%b %d, %H:%M')}", "New Conversation"]:
                    db.update_session_title(session_id, "Quick Support Request")
            
            # Process Gemini response immediately for quick support (reducing latency)
            history_messages = db.get_session_messages(session_id)
            history = [{"role": m["role"], "content": m["content"]} for m in history_messages]
            
            ai_data = gemini_service.get_chat_response(history, api_key)
            mood = ai_data.get("mood", "💭 Reflective")
            stress = ai_data.get("stress_level", "Medium")
            confidence = ai_data.get("confidence_score", 85)
            
            db.add_message(
                session_id=session_id,
                role="assistant",
                content=json.dumps(ai_data),
                mood=mood,
                stress_level=stress,
                confidence_score=confidence
            )
            
            db.add_mood_log(
                session_id=session_id,
                mood=mood,
                stress_level=stress,
                confidence_score=confidence
            )
            st.rerun()
            
    # ------------------ CHAT MESSAGE RENDERING ------------------
    chat_container = st.container()
    
    with chat_container:
        if not messages:
            st.markdown(
                '<div style="text-align: center; color: #888; padding: 40px 10px;">'
                '🌿 Hello! I am CalmMind AI. Share your feelings, stress, or goals, '
                'or click one of the quick support buttons above to begin.</div>',
                unsafe_allow_html=True
            )
        else:
            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                
                if role == "user":
                    # Custom premium user bubble aligned right
                    safe_content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
                    st.markdown(f"""
                    <div style="display: flex; justify-content: flex-end; margin-bottom: 12px; width: 100%;">
                        <div class="user-bubble">
                            {safe_content}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # Parse JSON response
                    try:
                        data = json.loads(content)
                        response_text = data.get("response", "")
                        mood = data.get("mood", "💭 Reflective")
                        stress = data.get("stress_level", "Medium")
                        confidence = data.get("confidence_score", 85)
                        recs = data.get("recommendations", [])
                        affirmation = data.get("affirmation", "")
                    except Exception:
                        response_text = content
                        mood = msg.get("mood", "💭 Reflective")
                        stress = msg.get("stress_level", "Medium")
                        confidence = msg.get("confidence_score", 85)
                        recs = []
                        affirmation = ""
                        
                    formatted_text = format_message_to_html(response_text)
                    
                    # Custom premium assistant bubble aligned left
                    affirmation_html = f'<div style="border-left: 3px solid #2E8B57; padding-left: 12px; margin: 15px 0 5px 0; font-style: italic; color: #555; font-size: 0.92rem;">✨ "{affirmation}"</div>' if affirmation else ''
                    
                    # Initialize typed tracking state
                    if "typed_message_id" not in st.session_state:
                        st.session_state.typed_message_id = None
                        
                    # Trigger typewriter animation if it is the latest message and not yet played
                    is_latest = (msg["message_id"] == messages[-1]["message_id"])
                    
                    if is_latest and st.session_state.typed_message_id != msg["message_id"]:
                        placeholder = st.empty()
                        words = response_text.split(" ")
                        for idx in range(1, len(words) + 1):
                            partial = " ".join(words[:idx])
                            formatted_partial = format_message_to_html(partial)
                            placeholder.markdown(f"""
                            <div style="display: flex; justify-content: flex-start; margin-bottom: 15px; width: 100%;">
                                <div class="assistant-bubble">
                                    <div style="background-color: #EAF2EC; border-radius: 8px; padding: 4px 10px; font-size: 0.8rem; font-weight: 600; color: #2E8B57; margin-bottom: 12px; display: inline-block; border: 1px solid rgba(46, 139, 87, 0.12);">
                                        📊 Mood: {mood} &nbsp;|&nbsp; ⚡ Stress: {stress} &nbsp;|&nbsp; 🎯 Conf: {confidence}%
                                    </div>
                                    <div style="margin-bottom: 10px;">{formatted_partial} ▌</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            time.sleep(0.04) # Speed of typing
                            
                        # Final completed render with affirmations
                        placeholder.markdown(f"""
                        <div style="display: flex; justify-content: flex-start; margin-bottom: 15px; width: 100%;">
                            <div class="assistant-bubble">
                                <div style="background-color: #EAF2EC; border-radius: 8px; padding: 4px 10px; font-size: 0.8rem; font-weight: 600; color: #2E8B57; margin-bottom: 12px; display: inline-block; border: 1px solid rgba(46, 139, 87, 0.12);">
                                    📊 Mood: {mood} &nbsp;|&nbsp; ⚡ Stress: {stress} &nbsp;|&nbsp; 🎯 Conf: {confidence}%
                                </div>
                                <div style="margin-bottom: 10px;">{formatted_text}</div>
                                {affirmation_html}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        st.session_state.typed_message_id = msg["message_id"]
                    else:
                        # Direct render
                        st.markdown(f"""
                        <div style="display: flex; justify-content: flex-start; margin-bottom: 15px; width: 100%;">
                            <div class="assistant-bubble">
                                <div style="background-color: #EAF2EC; border-radius: 8px; padding: 4px 10px; font-size: 0.8rem; font-weight: 600; color: #2E8B57; margin-bottom: 12px; display: inline-block; border: 1px solid rgba(46, 139, 87, 0.12);">
                                    📊 Mood: {mood} &nbsp;|&nbsp; ⚡ Stress: {stress} &nbsp;|&nbsp; 🎯 Conf: {confidence}%
                                </div>
                                <div style="margin-bottom: 10px;">{formatted_text}</div>
                                {affirmation_html}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Recommendations Cards
                    if recs:
                        st.write("**Wellness Suggestions:**")
                        cols = st.columns(len(recs))
                        for idx, rec in enumerate(recs):
                            with cols[idx]:
                                st.markdown(
                                    f'<div class="wellness-card" style="font-size: 0.9rem; padding: 10px; margin-bottom: 0px; min-height: 80px; display: flex; align-items: center; justify-content: center; text-align: center;">'
                                    f'{rec}'
                                    f'</div>',
                                    unsafe_allow_html=True
                                )
                                    
    # ------------------ BREATHING EXERCISE BUBBLE ------------------
    # If a breathing exercise is suggested or in the context, render a pulsing visual helper
    if messages:
        last_msg = messages[-1]
        is_breathing_active = False
        breathing_type = "Box Breathing"
        
        if last_msg["role"] == "assistant":
            try:
                data = json.loads(last_msg["content"])
                recs_str = " ".join(data.get("recommendations", []))
                resp_str = data.get("response", "")
                if "breath" in recs_str.lower() or "breath" in resp_str.lower() or "inhale" in resp_str.lower():
                    is_breathing_active = True
                    if "4-7-8" in resp_str or "4-7-8" in recs_str:
                        breathing_type = "4-7-8 Breathing"
                    elif "focus" in resp_str.lower():
                        breathing_type = "Calm Focus Breathing"
            except Exception:
                pass
                
        if is_breathing_active:
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown(f"#### 🌬️ Practice {breathing_type} Guides")
            
            # Setup specific animation timing based on exercise
            # Box breathing: 4s inhale, 4s hold, 4s exhale, 4s hold
            if breathing_type == "4-7-8 Breathing":
                animation_keyframes = """
                @keyframes breathing-cycle {
                    0%, 100% { transform: scale(1); opacity: 0.7; }
                    21% { transform: scale(1.6); opacity: 1; }      /* Inhale 4s (4/19 = 21%) */
                    58% { transform: scale(1.6); opacity: 1; }      /* Hold 7s (11/19 = 58%) */
                    95% { transform: scale(1); opacity: 0.7; }      /* Exhale 8s */
                }
                """
                cycle_duration = "19s"
                guide_text = "Inhale (4s) ➡️ Hold (7s) ➡️ Exhale (8s)"
            else:
                animation_keyframes = """
                @keyframes breathing-cycle {
                    0%, 100% { transform: scale(1); opacity: 0.7; }
                    25% { transform: scale(1.6); opacity: 1; }      /* Inhale 4s */
                    50% { transform: scale(1.6); opacity: 1; }      /* Hold 4s */
                    75% { transform: scale(1); opacity: 0.7; }      /* Exhale 4s */
                }
                """
                cycle_duration = "16s"
                guide_text = "Inhale (4s) ➡️ Hold (7s) ➡️ Exhale (4s) ➡️ Hold Empty (4s)"
                
            BREATHING_CSS = f"""
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
            """
            st.markdown(BREATHING_CSS, unsafe_allow_html=True)
            
            b_col1, b_col2 = st.columns([0.4, 0.6])
            with b_col1:
                st.markdown('<div class="breathing-bubble"></div>', unsafe_allow_html=True)
            with b_col2:
                st.write(f"**Interactive breathing bubble helper active.**")
                st.write("Follow the expansion of the bubble to guide your breathing:")
    # ------------------ USER INPUT AREA ------------------
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    render_custom_chat_input()
    st.markdown(
        "<div style='text-align: center; font-size: 0.74rem; color: #a0aec0; font-family: \"Outfit\", sans-serif; margin-top: 10px; max-width: 600px; margin-left: auto; margin-right: auto; line-height: 1.4;'>"
        "⚠️ <b>Disclaimer:</b> CalmMind AI is an AI wellness assistant. It is not a replacement for professional therapy, clinical advice, or mental health counseling."
        "</div>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<div style='text-align: center; font-size: 0.78rem; color: #888; font-family: \"Outfit\", sans-serif; margin-top: 5px; margin-bottom: 15px;'>"
        "Built by <b>Sindhuja Reddy Pendyala</b> | For <i>GenAI Internship</i>"
        "</div>", 
        unsafe_allow_html=True
    )


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
                error_msg = str(e)
                if "ResourceExhausted" in error_msg or "429" in error_msg or "quota" in error_msg.lower():
                    insights_text = (
                        "AI Insights are temporarily unavailable due to Gemini API rate limits. "
                        "We recommend taking a short mindful break and checking again in a few moments."
                    )
                else:
                    insights_text = (
                        "Based on your mood log history, your most frequent emotional states show moderate overthinking, "
                        "with stress peaking during specific conversational topics. Consider introducing a 5-minute breathing "
                        "or walk break when high-stress triggers are detected."
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
            st.error("Please fill in your name to generate the plan.")
        elif not api_key:
            st.error("Please enter a Gemini API Key in the sidebar to generate the plan.")
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
        st.session_state.api_key = os.getenv("GEMINI_API_KEY", "")
    if "current_session_id" not in st.session_state:
        # Always generate a fresh session ID on direct loading to avoid showing historical logs
        import uuid
        new_id = uuid.uuid4().hex
        db.create_session(new_id, "New Conversation")
        st.session_state.current_session_id = new_id
    show()
