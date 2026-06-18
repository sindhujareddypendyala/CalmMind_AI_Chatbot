import json
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Define the standard system instruction for the chatbot
SYSTEM_INSTRUCTION = """
You are CalmMind AI, a professional, empathetic mental wellness chatbot companion. 
Your tagline is "Your Personal Mental Wellness Companion".

Core Instructions:
1. Actively support the user's mental wellness journey by providing empathetic, supportive, and mindfulness-based guidance.
2. Focus strictly on topics related to mental wellness, stress management, anxiety, overthinking, emotional wellness, motivation, self-confidence, productivity, burnout, and daily wellbeing.
3. DOMAIN RESTRICTION: If the user asks about anything unrelated to mental wellness (e.g., coding, programming, IT, software, stock prices, weather, recipes, mathematics, history, general knowledge, general web queries), you MUST reply with the exact phrase:
   "I'm specifically designed to support mental wellness and emotional wellbeing. Please ask me a wellness-related question."
4. For every user message, you must analyze and return:
   - "response": Your empathetic chatbot response.
   - "mood": The detected mood of the user. Choose exactly one of these:
     - "😊 Happy"
     - "😔 Sad"
     - "😰 Anxious"
     - "😡 Angry"
     - "🤯 Overthinking"
     - "💪 Motivated"
     - "😴 Tired"
     - "💭 Reflective"
     - "😐 Neutral" (Fallback if mood doesn't fit the above)
   - "stress_level": "Low", "Medium", or "High"
   - "confidence_score": An integer percentage between 0 and 100 representing your confidence in this mood detection.
    - "recommendations": A list of 2-3 specific, actionable wellness recommendations. You MUST align the recommendations directly with the user's detected wellness challenge:
      * If the user shows signs of STRESS, you MUST recommend "🌬️ Practice Box Breathing".
      * If the user shows signs of ANXIETY, you MUST recommend "🌬️ Practice 4-7-8 Breathing".
      * If the user shows signs of OVERTHINKING, you MUST recommend "🌬️ Practice Calm Focus Breathing".
      * Otherwise, suggest general mindfulness exercises like "🧘 Mindfulness Exercise", "🚶 Take a 5-minute walk", or "📝 Write down your thoughts".
    - "affirmation": A personalized positive affirmation matching their current state.

You MUST respond ONLY in a valid JSON object matching this schema:
{
  "response": "chatbot's textual response",
  "mood": "😊 Happy" | "😔 Sad" | "😰 Anxious" | "😡 Angry" | "🤯 Overthinking" | "💪 Motivated" | "😴 Tired" | "💭 Reflective" | "😐 Neutral",
  "stress_level": "Low" | "Medium" | "High",
  "confidence_score": 92,
  "recommendations": ["Recommendation 1", "Recommendation 2"],
  "affirmation": "positive affirmation string"
}
Do not include any other markdown formatting outside of the JSON block.
"""

def configure_api(api_key=None):
    """Configures the google-generativeai library."""
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("Gemini API Key is missing. Please set it in .env or enter it in the sidebar.")
    genai.configure(api_key=key)

def get_chat_response(messages, api_key=None):
    """
    Sends the chat history to Gemini and retrieves a structured response.
    messages: list of dicts containing 'role' (user/assistant) and 'content'
    """
    configure_api(api_key)
    
    # Try using gemini-1.5-flash (higher free-tier limits: 1500 req/day), fallback to gemini-2.5-flash if unavailable
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=SYSTEM_INSTRUCTION
        )
    except Exception:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=SYSTEM_INSTRUCTION
        )
        
    # Format messages for the API
    # We will construct a clean history string to feed to the model to ensure it follows JSON output rules.
    history_prompt = "You are in a conversation. Read the history and respond to the LAST user message in the required JSON format.\n\n"
    
    for msg in messages[:-1]:
        role_label = "User" if msg["role"] == "user" else "Assistant"
        # Since the assistant responses in DB might be JSON or pure text (if we store them),
        # let's extract the actual response field from JSON if it is stored as JSON, or use it as is.
        content = msg["content"]
        try:
            parsed = json.loads(content)
            content_text = parsed.get("response", content)
        except Exception:
            content_text = content
            
        history_prompt += f"{role_label}: {content_text}\n"
    
    # Add the latest user message
    latest_user_content = messages[-1]["content"]
    history_prompt += f"User: {latest_user_content}\n"
    history_prompt += "Assistant response (JSON):"
    
    try:
        response = model.generate_content(
            history_prompt,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.7
            }
        )
        data = json.loads(response.text)
        return data
    except Exception as e:
        # Fallback in case generation or JSON parsing fails (e.g. rate limit, quota exceeded, safety filters)
        error_msg = str(e)
        if "API key not valid" in error_msg or "API_KEY_INVALID" in error_msg or "invalid api key" in error_msg.lower():
            fallback_text = "Your Gemini API Key appears to be invalid or unconfigured. Please check the GEMINI_API_KEY in your .env file."
        elif "ResourceExhausted" in error_msg or "429" in error_msg or "quota" in error_msg.lower():
            fallback_text = "I'm currently receiving a high volume of requests. Please take a deep breath and wait a moment before sending your next message."
        else:
            try:
                fallback_text = response.text if ('response' in locals() and response and hasattr(response, 'text') and response.text) else "I am here to support you. Let's take a deep breath together."
            except Exception:
                fallback_text = "I am here to support you. Let's take a deep breath together."
            
        return {
            "response": fallback_text,
            "mood": "💭 Reflective",
            "stress_level": "Medium",
            "confidence_score": 75,
            "recommendations": ["🌿 Practice Box Breathing", "📝 Journal your thoughts"],
            "affirmation": "You are capable of navigating whatever comes your way."
        }

def generate_wellness_plan(user_data, api_key=None):
    """
    Generates a personalized wellness plan based on user onboarding form.
    user_data: dict of Name, Occupation, Stress Level, Sleep Hours, Current Challenge, Wellness Goal
    """
    configure_api(api_key)
    
    prompt = f"""
    You are a professional wellness coach. Create a highly personalized, beautiful, and structured Wellness Plan in JSON format for this user:
    
    Name: {user_data.get('name')}
    Occupation: {user_data.get('occupation')}
    Current Stress Level: {user_data.get('stress_level')}
    Average Sleep Hours: {user_data.get('sleep_hours')}
    Current Challenge: {user_data.get('challenge')}
    Wellness Goal: {user_data.get('goal')}
    
    Generate a JSON response containing:
    1. "morning_routine": A list of 3 sequential steps for a great morning routine tailored to their stress, challenge, and goals.
    2. "afternoon_routine": A list of 3 sequential steps for their afternoon routine.
    3. "evening_routine": A list of 3 sequential steps for their evening routine.
    4. "affirmation": A powerful, custom daily affirmation.
    5. "breathing_exercise": A dict with:
       - "name": Name of recommended breathing exercise (e.g. "Box Breathing", "4-7-8 Breathing", "Calm Focus Breathing")
       - "instructions": Multi-step instructions.
       - "duration": Duration (e.g. "5 minutes")
       - "benefits": Key health/mental benefit.
    6. "weekly_guidance": A list of 3 specific tips/strategies for the week to help them achieve their wellness goal.
    
    You MUST respond ONLY in valid JSON format matching this schema:
    {{
      "morning_routine": ["Step 1", "Step 2", "Step 3"],
      "afternoon_routine": ["Step 1", "Step 2", "Step 3"],
      "evening_routine": ["Step 1", "Step 2", "Step 3"],
      "affirmation": "Custom positive affirmation",
      "breathing_exercise": {{
         "name": "Exercise Name",
         "instructions": "Step-by-step instructions",
         "duration": "5 minutes",
         "benefits": "Explanation of benefits"
      }},
      "weekly_guidance": ["Tip 1", "Tip 2", "Tip 3"]
    }}
    Do not include any other text outside the JSON.
    """
    
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
    except Exception:
        model = genai.GenerativeModel("gemini-2.5-flash")
        
    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.5
            }
        )
        return json.loads(response.text)
    except Exception as e:
        # Fallback structure in case of rate limit, safety filters, or API errors
        error_msg = str(e)
        fallback_affirmation = "I prioritize my wellbeing, one breath at a time."
        if "API key not valid" in error_msg or "API_KEY_INVALID" in error_msg or "invalid api key" in error_msg.lower():
            fallback_affirmation = "Please verify your GEMINI_API_KEY in your .env file. The key is invalid."
        elif "ResourceExhausted" in error_msg or "429" in error_msg or "quota" in error_msg.lower():
            fallback_affirmation = "The system is currently busy. Please retry generating your plan in a few seconds."
            
        return {
            "morning_routine": ["Stretch and hydrate", "Spend 5 minutes in silent reflection", "Plan your top 3 wellness intentions for the day"],
            "afternoon_routine": ["Take a short 10-minute walk", "Perform deep breathing exercises", "Hydrate and stretch"],
            "evening_routine": ["Disconnect from digital screens 1 hour before bed", "Write down 3 things you are grateful for", "Practice deep abdominal breathing"],
            "affirmation": fallback_affirmation,
            "breathing_exercise": {
                "name": "Box Breathing",
                "instructions": "Inhale for 4 seconds, hold for 4 seconds, exhale for 4 seconds, hold empty for 4 seconds. Repeat 4 times.",
                "duration": "5 minutes",
                "benefits": "Reduces cortisol, calms the nervous system, and improves concentration."
            },
            "weekly_guidance": [
                "Establish small, manageable sleep boundaries to increase rest.",
                "Dedicate 10 minutes mid-day to mindful breathing.",
                "Celebrate small wins towards your emotional goals."
            ]
        }
