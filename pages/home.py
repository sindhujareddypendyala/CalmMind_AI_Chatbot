import streamlit as st
import os

def show():
    # Page layout columns
    col1, col2 = st.columns([1.1, 0.9], gap="large")
    
    # CSS Animation specifically for the Home Page elements
    HOME_CSS = """
    <style>
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .hero-container {
            animation: fadeInUp 1.2s cubic-bezier(0.16, 1, 0.3, 1) forwards;
            padding-top: 10%;
        }
        
        .hero-title {
            font-size: 3.5rem !important;
            font-weight: 700 !important;
            color: #2E8B57 !important;
            line-height: 1.2 !important;
            margin-bottom: 0.5rem !important;
        }
        
        .hero-tagline {
            font-size: 1.6rem !important;
            font-weight: 400 !important;
            color: #2F4F4F !important;
            margin-bottom: 2rem !important;
        }
        
        .hero-desc {
            font-size: 1.1rem !important;
            color: #4A5568 !important;
            line-height: 1.7 !important;
            margin-bottom: 2.5rem !important;
        }
        
        .image-container {
            animation: fadeInUp 1.5s cubic-bezier(0.16, 1, 0.3, 1) forwards;
            display: flex;
            justify-content: center;
            align-items: center;
            padding-top: 5%;
        }
        
        .image-container img {
            border-radius: 24px;
            box-shadow: 0 10px 30px rgba(46, 139, 87, 0.08);
            border: 1px solid rgba(46, 139, 87, 0.05);
            max-width: 100%;
            height: auto;
        }
    </style>
    """
    st.markdown(HOME_CSS, unsafe_allow_html=True)
    
    with col1:
        st.markdown('<div class="hero-container">', unsafe_allow_html=True)
        st.markdown('<h1 class="hero-title">🧠 CalmMind AI</h1>', unsafe_allow_html=True)
        st.markdown('<p class="hero-tagline">Your Personal Mental Wellness Companion</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="hero-desc">CalmMind AI helps you manage stress, anxiety, overthinking, emotional wellness, '
            'motivation, and daily wellbeing through AI-powered conversations and personalized '
            'wellness recommendations. Start your mindful journey today.</p>',
            unsafe_allow_html=True
        )
        
        # Start Chat button click handler
        if st.button("🚀 Start Chat", use_container_width=False):
            import uuid
            from database import db
            new_id = uuid.uuid4().hex
            db.create_session(new_id, "New Conversation")
            st.session_state.current_session_id = new_id
            st.session_state.page = "Chat"
            st.rerun()
            
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col2:
        st.markdown('<div class="image-container">', unsafe_allow_html=True)
        image_path = os.path.join("assets", "chatbot_image.png")
        if os.path.exists(image_path):
            st.image(image_path, use_container_width=True)
        else:
            # Fallback illustration using a beautiful SVG if the image copy failed
            st.markdown("""
                <svg width="400" height="400" viewBox="0 0 400 400" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="200" cy="200" r="180" fill="#EAF2EC" />
                    <circle cx="200" cy="200" r="140" fill="#2E8B57" fill-opacity="0.1" />
                    <path d="M200 120C170 120 150 145 150 175C150 215 200 260 200 260C200 260 250 215 250 175C250 145 230 120 200 120Z" fill="#2E8B57" />
                    <circle cx="185" cy="170" r="4" fill="white" />
                    <circle cx="215" cy="170" r="4" fill="white" />
                    <path d="M190 190Q200 198 210 190" stroke="white" stroke-width="2" stroke-linecap="round"/>
                </svg>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    show()
