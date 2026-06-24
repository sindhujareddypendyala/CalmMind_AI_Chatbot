import os
import json
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List
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


def _contains_any(text: str, keywords: List[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _is_unrelated_query(text: str) -> bool:
    """Best-effort local domain guard used only when Gemini is unavailable."""
    wellness_keywords = [
        "feel", "feeling", "mood", "stress", "stressed", "anxiety", "anxious",
        "panic", "sad", "lonely", "angry", "overthinking", "tired", "sleep",
        "burnout", "motivation", "motivated", "confidence", "calm", "breathe",
        "breathing", "mind", "mental", "emotion", "emotional", "wellness",
        "therapy", "therapist", "journal", "habit", "focus", "relax",
    ]
    unrelated_keywords = [
        "code", "coding", "program", "python", "java", "javascript", "bug",
        "stock", "weather", "recipe", "math", "calculate", "history",
        "capital of", "news", "sports", "movie", "song", "translate",
    ]
    return (
        _contains_any(text, unrelated_keywords)
        and not _contains_any(text, wellness_keywords)
    )


def _build_local_wellness_response(latest_query: str, reason: str = "") -> dict:
    """Create a useful response when Gemini is unavailable or returns invalid data."""
    text = str(latest_query or "").strip()
    lowered = text.lower()

    if _is_unrelated_query(lowered):
        return {
            "response": (
                "I'm specifically designed to support mental wellness and "
                "emotional wellbeing. Please ask me a wellness-related question."
            ),
            "mood": "😐 Neutral",
            "stress_level": "Low",
            "confidence_score": 100.0,
            "recommendations": [
                "💡 Share how this is affecting your wellbeing",
                "📝 Reframe your question around stress, emotions, or habits",
            ],
            "affirmation": "I can choose conversations that support my wellbeing.",
        }

    if _contains_any(lowered, ["panic", "anxious", "anxiety", "worried", "nervous", "fear"]):
        mood = "😰 Anxious"
        stress = "High" if _contains_any(lowered, ["panic", "can't breathe", "overwhelmed"]) else "Medium"
        response = (
            "That sounds really unsettling. Try to bring your attention to this moment: "
            "name one thing you can see, one thing you can feel, and one thing you can hear. "
            "You do not have to solve everything at once; the first step is helping your body feel a little safer."
        )
        recommendations = [
            "🌬️ Practice 4-7-8 Breathing for 3 rounds",
            "🧭 Use the 3-3-3 grounding technique",
            "📝 Write the main worry and one next step",
        ]
        affirmation = "I can slow this moment down and meet it one breath at a time."
    elif _contains_any(lowered, ["stress", "stressed", "pressure", "overwhelmed", "too much"]):
        mood = "😰 Anxious"
        stress = "High" if _contains_any(lowered, ["overwhelmed", "too much", "can't handle"]) else "Medium"
        response = (
            "It makes sense that you feel stretched if a lot is landing on you at once. "
            "Let's reduce the load mentally: pick the one thing that needs attention first, "
            "then give yourself permission to pause the rest for a few minutes."
        )
        recommendations = [
            "🌿 Practice Box Breathing for 2 minutes",
            "✅ Choose one small task to finish first",
            "☕ Take a 5-minute screen and posture break",
        ]
        affirmation = "I am allowed to move through today one manageable step at a time."
    elif _contains_any(lowered, ["overthinking", "racing", "spiral", "can't stop thinking", "ruminating"]):
        mood = "🤯 Overthinking"
        stress = "Medium"
        response = (
            "A racing mind can make every thought feel urgent, even when it is not. "
            "Try separating facts from fears: what do you know for sure, and what is your mind predicting? "
            "That small separation can make the next step clearer."
        )
        recommendations = [
            "📝 Make a two-column facts vs. fears note",
            "⏱️ Set a 10-minute worry timer, then redirect",
            "🌬️ Try Calm Focus Breathing",
        ]
        affirmation = "My thoughts are signals, not commands."
    elif _contains_any(lowered, ["sad", "low", "down", "cry", "lonely", "hurt", "heartbroken"]):
        mood = "😔 Sad"
        stress = "Medium"
        response = (
            "I'm sorry you're carrying that. You do not need to force yourself to be positive right now; "
            "being honest about feeling low is already a gentle act of care. "
            "What would feel most supportive in the next 10 minutes: rest, expression, or connection?"
        )
        recommendations = [
            "📝 Write one paragraph without judging it",
            "❤️ Message someone safe with a simple check-in",
            "🌤️ Do one small comforting action",
        ]
        affirmation = "My feelings deserve care, and I can be gentle with myself."
    elif _contains_any(lowered, ["angry", "mad", "frustrated", "irritated", "annoyed"]):
        mood = "😡 Angry"
        stress = "Medium"
        response = (
            "That frustration sounds real. Before reacting, give the feeling a little space so it does not have to drive. "
            "You might ask: what boundary, need, or disappointment is underneath this anger?"
        )
        recommendations = [
            "🚶 Step away for 5 minutes if you can",
            "📝 Write what you wish you could say",
            "💬 Use one clear 'I feel...' sentence",
        ]
        affirmation = "I can listen to my anger without letting it control my choices."
    elif _contains_any(lowered, ["tired", "exhausted", "sleepy", "drained", "burnout", "burned out"]):
        mood = "😴 Tired"
        stress = "Medium"
        response = (
            "Your energy sounds low, so the kindest plan is a smaller plan. "
            "Instead of pushing harder, choose the minimum useful next step and protect a pocket of recovery time."
        )
        recommendations = [
            "🔋 Pick one low-effort priority",
            "💧 Drink water and stretch for 2 minutes",
            "🌙 Set a gentle wind-down time tonight",
        ]
        affirmation = "Rest is part of progress, not a failure of discipline."
    elif _contains_any(lowered, ["motivate", "motivation", "lazy", "procrastinating", "procrastinate", "stuck"]):
        mood = "💪 Motivated"
        stress = "Low"
        response = (
            "Feeling stuck does not mean you lack discipline; it usually means the next step is too large or too vague. "
            "Shrink it until it feels almost too easy, then start there."
        )
        recommendations = [
            "🎯 Define a 5-minute starter task",
            "✅ Celebrate completion, not perfection",
            "📌 Remove one distraction before starting",
        ]
        affirmation = "Small starts count, and I can build momentum gently."
    elif _contains_any(lowered, ["happy", "good", "great", "grateful", "proud", "better"]):
        mood = "😊 Happy"
        stress = "Low"
        response = (
            "I'm glad there is some lightness here. Take a second to notice what helped create it, "
            "because naming what works makes it easier to return to later."
        )
        recommendations = [
            "📝 Note one thing that supported this mood",
            "🌱 Repeat one healthy choice tomorrow",
            "❤️ Share the good moment with someone you trust",
        ]
        affirmation = "I am allowed to notice and enjoy good moments."
    else:
        mood = "💭 Reflective"
        stress = "Low"
        response = (
            "I'm listening. From what you shared, it may help to slow down and name what is most present for you right now: "
            "a feeling, a thought, or a need. Once you name it, we can choose a small next step."
        )
        recommendations = [
            "📝 Name the strongest feeling in one word",
            "🎯 Choose one kind next step",
            "🌿 Take a short mindful pause",
        ]
        affirmation = "I can meet myself honestly and move forward with care."

    if reason in {"missing_key", "api_error"}:
        response = (
            "I can't reach the AI service right now, but I can still support you. "
            + response
        )
    elif reason == "invalid_key":
        response = (
            "Your Gemini API key looks invalid, so I'm using local support for now. "
            + response
        )
    elif reason == "quota":
        response = (
            "The AI service is busy or out of quota right now, so I'm using local support for now. "
            + response
        )

    return {
        "response": response,
        "mood": mood,
        "stress_level": stress,
        "confidence_score": 82.0,
        "recommendations": recommendations,
        "affirmation": affirmation,
    }


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
        
    try:
        client = get_client(api_key)
    except ValueError:
        return _build_local_wellness_response(latest_query, reason="missing_key")
    
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
            print(f"[DEBUG] Error generating content with {model_name}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            if model_name == "gemini-flash-latest":
                if "API key not valid" in error_msg or "API_KEY_INVALID" in error_msg or "invalid api key" in error_msg.lower():
                    return _build_local_wellness_response(latest_query, reason="invalid_key")
                if "ResourceExhausted" in error_msg or "429" in error_msg or "quota" in error_msg.lower():
                    return _build_local_wellness_response(latest_query, reason="quota")

                return _build_local_wellness_response(latest_query, reason="api_error")

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
