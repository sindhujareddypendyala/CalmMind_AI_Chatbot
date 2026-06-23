import os
import json
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv
from services.crisis_detector import detect_crisis, crisis_chat_response

load_dotenv()

# Define Pydantic schemas for Gemini Structured Output
class ChatResponseSchema(BaseModel):
    response: str
    mood: str
    stress_level: str
    confidence_score: float
    recommendations: List[str]
    affirmation: str

class BreathingExerciseSchema(BaseModel):
    name: str
    instructions: str
    duration: str
    benefits: str

class WellnessPlanSchema(BaseModel):
    morning_routine: List[str]
    afternoon_routine: List[str]
    evening_routine: List[str]
    affirmation: str
    breathing_exercise: BreathingExerciseSchema
    weekly_guidance: List[str]

# System instructions to lock the bot to the mental wellness domain
SYSTEM_INSTRUCTION = """
You are CalmMind AI, a professional, empathetic mental wellness chatbot companion. 
Your tagline is "Your Personal Mental Wellness Companion".

Core Instructions:
1. Actively support the user's mental wellness journey by providing empathetic, supportive, and mindfulness-based guidance.
2. Focus strictly on topics related to mental wellness, stress management, anxiety, overthinking, emotional wellness, motivation, self-confidence, productivity, burnout, and daily wellbeing.
3. DOMAIN RESTRICTION: If the user asks about anything unrelated to mental wellness (e.g., coding, programming, IT, software, stock prices, weather, recipes, mathematics, history, general knowledge, general web queries), you MUST reply with the exact phrase:
   "I'm specifically designed to support mental wellness and emotional wellbeing. Please ask me a wellness-related question."
4. For every user message, analyze and return a structured JSON matching the provided schema:
   - "response": Your empathetic, responsive, and supportive chatbot response. Keep it conversational and kind.
   - "mood": The detected mood of the user. Choose exactly one:
     - "😊 Happy"
     - "😔 Sad"
     - "😰 Anxious"
     - "😡 Angry"
     - "🤯 Overthinking"
     - "💪 Motivated"
     - "😴 Tired"
     - "💭 Reflective"
     - "😐 Neutral"
   - "stress_level": "Low", "Medium", or "High"
   - "confidence_score": An integer percentage between 0 and 100 representing your confidence in mood detection.
   - "recommendations": A list of 2-3 specific, actionable wellness recommendations. You MUST align the recommendations directly with the user's challenge:
     * Suggest breathing exercises (e.g., "Practice Box Breathing", "4-7-8 Breathing", "Calm Focus Breathing") ONLY if the user shows stress, anxiety, or overthinking. Do NOT suggest breathing exercises for every single input.
     * Suggest other coping strategies for other states, e.g. "Practice positive self-talk", "Write down 3 things you are grateful for", "Set one small achievable goal today", "Take a short screen break", or "Try a self-compassion journal entry".
   - "affirmation": A personalized positive affirmation matching their current state.

You MUST respond strictly in the JSON format matching the schema provided. Do not include any other markdown formatting outside of the JSON block.
"""

CRISIS_RESPONSE = {
    "response": "I hear how much pain you are in right now, and I want you to know that you are not alone. Your life is valuable, and there is support available. Please reach out to someone who can help. You can connect with the Suicide & Crisis Lifeline by calling or texting 988 (available 24/7, free, and confidential in the US/Canada), or contact emergency services. If you have family, friends, or a professional you trust, please consider reaching out to them right now. They want to support you.",
    "mood": "😔 Sad",
    "stress_level": "High",
    "confidence_score": 100.0,
    "recommendations": [
        "☎️ Call or Text 988 (Crisis Lifeline)",
        "❤️ Contact a family member, friend, or trusted adult",
        "🏠 Connect with emergency services or visit the nearest ER"
    ],
    "affirmation": "You are not alone, and there is hope. Please let someone support you today."
}

def is_crisis_query(text: str) -> bool:
    """Detects self-harm and crisis keywords to bypass AI generation."""
    query = text.lower()
    keywords = [
        "want to die", "kill myself", "suicide", "suicidal", "end my life",
        "harm myself", "self-harm", "want to end it all", "don't want to live",
        "better off dead", "cutting myself", "please kill me"
    ]
    return any(kw in query for kw in keywords)

def get_client(api_key: str = None) -> genai.Client:
    """Configures and returns the GenAI client."""
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("Gemini API Key is missing. Please set it in .env or enter it in the sidebar.")
    return genai.Client(api_key=key)

def get_chat_response(messages: list, api_key: str = None) -> dict:
    """
    Sends the chat history to Gemini and retrieves a structured response.
    messages: list of dicts containing 'role' (user/assistant) and 'content'
    """
    latest_query = messages[-1]["content"]
    
    # 1. Self-harm / crisis check
    crisis_result = detect_crisis(latest_query)
    if crisis_result.get("is_crisis"):
        return crisis_chat_response(crisis_result)
        
    client = get_client(api_key)
    
    # 2. Format history prompt
    history_prompt = "You are in a conversation. Read the history and respond to the LAST user message in the required JSON format.\n\n"
    for msg in messages[:-1]:
        role_label = "User" if msg["role"] == "user" else "Assistant"
        content = msg["content"]
        try:
            parsed = json.loads(content)
            content_text = parsed.get("response", content)
        except Exception:
            content_text = content
            
        history_prompt += f"{role_label}: {content_text}\n"
    
    history_prompt += f"User: {latest_query}\n"
    history_prompt += "Assistant response (JSON):"
    
    # 3. Model call with fallback from gemini-2.5-flash to gemini-flash-latest
    for model_name in ["gemini-2.5-flash", "gemini-flash-latest"]:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=history_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ChatResponseSchema,
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.7
                )
            )
            data = json.loads(response.text)
            
            # Double check domain restriction
            refusal_phrase = "I'm specifically designed to support mental wellness and emotional wellbeing"
            if refusal_phrase in data.get("response", ""):
                data["mood"] = "😐 Neutral"
                data["stress_level"] = "Low"
                data["confidence_score"] = 100.0
                data["recommendations"] = ["💡 Ask a wellness query", "🧘 Breathe deeply for 10 seconds"]
                data["affirmation"] = "I focus my mind on positive wellness conversations."
                
            return data
            
        except Exception as e:
            error_msg = str(e)
            if model_name == "gemini-flash-latest":
                # Final fallback in case API fails
                fallback_text = "I am here to support you. Let's take a deep breath together."
                if "API key not valid" in error_msg or "API_KEY_INVALID" in error_msg or "invalid api key" in error_msg.lower():
                    fallback_text = "Your Gemini API Key appears to be invalid. Please check the key in your .env or sidebar."
                elif "ResourceExhausted" in error_msg or "429" in error_msg or "quota" in error_msg.lower():
                    fallback_text = "I'm currently receiving a high volume of requests. Please take a deep breath and wait a moment before sending your next message."
                    
                return {
                    "response": fallback_text,
                    "mood": "💭 Reflective",
                    "stress_level": "Medium",
                    "confidence_score": 75.0,
                    "recommendations": ["🌿 Practice Box Breathing", "📝 Journal your thoughts"],
                    "affirmation": "You are capable of navigating whatever comes your way."
                }

def generate_wellness_plan(user_data: dict, api_key: str = None) -> dict:
    """
    Generates a personalized wellness plan based on user onboarding form.
    """
    client = get_client(api_key)
    
    prompt = f"""
    Create a highly personalized, structured Wellness Plan in JSON format for this user:
    Name: {user_data.get('name')}
    Occupation: {user_data.get('occupation')}
    Current Stress Level: {user_data.get('stress_level')}
    Average Sleep Hours: {user_data.get('sleep_hours')}
    Current Challenge: {user_data.get('challenge')}
    Wellness Goal: {user_data.get('goal')}
    """
    
    for model_name in ["gemini-2.5-flash", "gemini-flash-latest"]:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=WellnessPlanSchema,
                    system_instruction="You are a professional wellness coach. Create daily routines and custom daily affirmations in JSON.",
                    temperature=0.5
                )
            )
            return json.loads(response.text)
        except Exception as e:
            if model_name == "gemini-flash-latest":
                # Fallback structure
                return {
                    "morning_routine": ["Stretch and hydrate", "Spend 5 minutes in silent reflection", "Plan your wellness intentions"],
                    "afternoon_routine": ["Take a short 10-minute walk", "Perform deep breathing", "Hydrate and stretch"],
                    "evening_routine": ["Disconnect from digital screens 1 hour before bed", "Write down 3 gratitudes", "Practice abdominal breathing"],
                    "affirmation": "I prioritize my wellbeing, one breath at a time.",
                    "breathing_exercise": {
                        "name": "Box Breathing",
                        "instructions": "Inhale for 4 seconds, hold for 4 seconds, exhale for 4 seconds, hold empty for 4 seconds.",
                        "duration": "5 minutes",
                        "benefits": "Reduces cortisol and calms the nervous system."
                    },
                    "weekly_guidance": [
                        "Establish small sleep boundaries.",
                        "Dedicate 10 minutes mid-day to mindful breathing.",
                        "Celebrate small wins towards emotional goals."
                    ]
                }
