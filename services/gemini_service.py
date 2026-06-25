import os
import json
import re
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
You are CalmMind AI, a polished, emotionally intelligent mental wellness chatbot companion.
Your tagline is "Your Personal Mental Wellness Companion".

Product behavior:
1. Read the full conversation and respond to the LAST user message in context.
2. If the user uses follow-up language such as "it", "this", "that", "I don't know if I will succeed", infer the active concern from the recent conversation.
3. Sound warm, natural, specific, and practical. Do not sound like a script.
4. Focus on emotional support first, then practical next steps.
5. Do not repeat the same style of response or the same recommendations across turns.
6. Keep the response concise: usually 3-6 sentences. Avoid long lectures.
7. Stay within mental wellness, emotional wellbeing, stress, anxiety, confidence, motivation, burnout, productivity, relationships, habits, and daily wellbeing.
8. DOMAIN RESTRICTION: If the user asks about anything unrelated to mental wellness, reply with the exact phrase:
   "I'm specifically designed to support mental wellness and emotional wellbeing. Please ask me a wellness-related question."

Response structure:
1. Acknowledge the actual emotion or situation.
2. Show you understand the user's specific context.
3. Offer grounded support.
4. Give 2-3 personalized next steps in recommendations.

Examples of good specificity:
- If the user failed an interview, discuss disappointment, learning from setbacks, confidence rebuilding, and one practical reflection step. Do not jump to breathing.
- If the user feels lonely, discuss connection, support systems, self-compassion, and one small outreach step.
- If the user is anxious or panicking, grounding and breathing can be appropriate.
- If the user discusses goals repeatedly, naturally mention the Personalized Wellness Planner.
- If the user discusses stress, mention the breathing helper only when stress feels physical, acute, or overwhelming.

Mood detection:
Choose exactly one mood from this list based on the user's latest message and recent context:
     - "😊 Happy"
     - "😔 Sad"
     - "😰 Anxious"
     - "😡 Angry"
     - "🤯 Overwhelmed"
     - "💪 Motivated"
     - "😴 Tired"
     - "😐 Neutral"

Recommendation rules:
- Return 2-3 recommendations only.
- Make each recommendation specific to the user's situation.
- Breathing exercises are allowed only for anxiety, panic, acute stress, overwhelm, or explicit breathing requests.
- Do not recommend breathing for interview failure, loneliness, motivation, confidence, sadness, career setbacks, or general reflection unless the user says they feel physically anxious.
- Include a natural feature suggestion only when relevant:
  * Stress/anxiety: suggest the breathing helper in chat.
  * Repeated goals/routines/habits: suggest the Personalized Wellness Planner.
  * Mood patterns: suggest checking Mood Analytics.
  * Emotional processing: suggest a short journal-style reflection in the chat.

Return only JSON matching the schema. No markdown outside JSON.

"""

CONNECTION_ERROR_RESPONSE = "I'm having a temporary difficulty connecting right now. Please try again in a moment."

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
        try:
            import streamlit as st
            key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            key = ""
    if not key:
        raise ValueError("Gemini API Key is missing. Please set it in .env or enter it in the sidebar.")
    return genai.Client(api_key=key)


def _contains_any(text: str, keywords: List[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _clean_response_text(text: str) -> str:
    """Remove accidental HTML fragments from model or stored responses."""
    cleaned = str(text or "")
    cleaned = re.sub(r"</?\s*(div|span|p|br|script|style|iframe)[^>]*>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"&lt;/?\s*(div|span|p|br|script|style|iframe)[^&]*&gt;", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _connection_error_payload() -> dict:
    return {
        "response": CONNECTION_ERROR_RESPONSE,
        "mood": "😐 Neutral",
        "stress_level": "Low",
        "confidence_score": 0.0,
        "recommendations": [],
        "affirmation": "",
    }


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
        mood = "🤯 Overwhelmed" if _contains_any(lowered, ["overwhelmed", "too much", "can't handle"]) else "😰 Anxious"
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
        mood = "🤯 Overwhelmed"
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
        mood = "😐 Neutral"
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

    return {
        "response": response,
        "mood": mood,
        "stress_level": stress,
        "confidence_score": 82.0,
        "recommendations": recommendations,
        "affirmation": affirmation,
    }


def _message_allows_breathing(latest_query: str, mood: str) -> bool:
    lowered = str(latest_query or "").lower()
    return (
        mood in {"😰 Anxious", "🤯 Overwhelmed"}
        or _contains_any(
            lowered,
            [
                "anxious", "anxiety", "panic", "overwhelmed", "can't breathe",
                "breathing", "breath", "calm down", "racing thoughts",
            ],
        )
    )


def _infer_mood_from_text(latest_query: str) -> str:
    lowered = str(latest_query or "").lower()
    if _contains_any(lowered, ["happy", "grateful", "proud", "excited", "better", "good today"]):
        return "😊 Happy"
    if _contains_any(lowered, ["sad", "lonely", "alone", "cry", "failed", "rejected", "hurt", "disappointed"]):
        return "😔 Sad"
    if _contains_any(lowered, ["anxious", "anxiety", "panic", "worried", "nervous", "scared"]):
        return "😰 Anxious"
    if _contains_any(lowered, ["angry", "mad", "frustrated", "irritated", "annoyed"]):
        return "😡 Angry"
    if _contains_any(lowered, ["overwhelmed", "overthinking", "too much", "pressure", "can't handle", "racing"]):
        return "🤯 Overwhelmed"
    if _contains_any(lowered, ["motivate", "motivation", "goal", "productive", "confidence", "succeed"]):
        return "💪 Motivated"
    if _contains_any(lowered, ["tired", "exhausted", "drained", "sleepy", "burnout", "burned out"]):
        return "😴 Tired"
    return "😐 Neutral"


def _normalize_chat_response(data: dict, latest_query: str) -> dict:
    """Keep model output on-brand, valid, and less repetitive."""
    valid_moods = {
        "😊 Happy", "😔 Sad", "😰 Anxious", "😡 Angry",
        "🤯 Overwhelmed", "💪 Motivated", "😴 Tired", "😐 Neutral",
    }

    if not isinstance(data, dict):
        data = {}

    response = _clean_response_text(data.get("response", ""))
    if not response:
        response = "I hear you. Tell me a little more about what feels hardest right now, and we can sort through it together."

    mood = str(data.get("mood", "") or "").strip()
    mood_aliases = {
        "🤯 Overthinking": "🤯 Overwhelmed",
        "💭 Reflective": _infer_mood_from_text(latest_query),
    }
    mood = mood_aliases.get(mood, mood)
    if mood not in valid_moods or mood == "😐 Neutral":
        inferred = _infer_mood_from_text(latest_query)
        if inferred != "😐 Neutral":
            mood = inferred
    if mood not in valid_moods:
        mood = "😐 Neutral"

    stress = str(data.get("stress_level", "") or "").strip().title()
    if stress not in {"Low", "Medium", "High"}:
        stress = "High" if mood in {"😰 Anxious", "🤯 Overwhelmed"} else "Medium" if mood in {"😔 Sad", "😡 Angry", "😴 Tired"} else "Low"

    try:
        confidence = float(data.get("confidence_score", 82.0))
    except (TypeError, ValueError):
        confidence = 82.0
    confidence = max(0.0, min(100.0, confidence))

    raw_recommendations = data.get("recommendations", [])
    if not isinstance(raw_recommendations, list):
        raw_recommendations = []

    allows_breathing = _message_allows_breathing(latest_query, mood)
    recommendations = []
    seen = set()
    for item in raw_recommendations:
        text = _clean_response_text(item)
        if not text:
            continue
        lowered = text.lower()
        if not allows_breathing and any(term in lowered for term in ("breath", "inhale", "exhale", "box breathing", "4-7-8")):
            continue
        normalized = lowered.rstrip(".")
        if normalized in seen:
            continue
        seen.add(normalized)
        recommendations.append(text)
        if len(recommendations) == 3:
            break

    if not recommendations:
        if mood == "😔 Sad":
            recommendations = [
                "Write down what hurt and what you needed in that moment.",
                "Reach out to one safe person with a simple check-in.",
                "Choose one small comforting action for the next 10 minutes.",
            ]
        elif mood == "😰 Anxious":
            recommendations = [
                "Name three facts you know for sure right now.",
                "Try one grounding cycle: look around and name five things you can see.",
                "Break the worry into one next action you can control.",
            ]
        elif mood == "🤯 Overwhelmed":
            recommendations = [
                "Pick the single most urgent task and pause the rest for now.",
                "Make a two-column list: what is in your control and what is not.",
                "Use the breathing helper only if your body feels tense or panicky.",
            ]
        elif mood == "💪 Motivated":
            recommendations = [
                "Choose a five-minute starter task.",
                "Remove one distraction before beginning.",
                "Use the Wellness Planner if this goal needs a daily routine.",
            ]
        else:
            recommendations = [
                "Name the strongest feeling in one word.",
                "Choose one kind next step you can take today.",
            ]

    affirmation = _clean_response_text(data.get("affirmation", ""))
    if not affirmation:
        affirmation = "I can take this one step at a time."

    return {
        "response": response,
        "mood": mood,
        "stress_level": stress,
        "confidence_score": confidence,
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
        print("[ERROR] Gemini API key is missing.")
        return _connection_error_payload()
    
    # 2. Format history prompt
    recent_messages = messages[-10:]
    prior_messages = recent_messages[:-1]
    history_prompt = (
        "Conversation context follows. Preserve continuity, infer the current concern from recent turns, "
        "avoid repeating earlier recommendations, and respond to the LAST user message only.\n\n"
    )
    for msg in prior_messages:
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
                    temperature=0.85
                )
            )
            data = json.loads(response.text)
            data = _normalize_chat_response(data, latest_query)
            
            # Double check domain restriction
            refusal_phrase = "I'm specifically designed to support mental wellness and emotional wellbeing"
            if refusal_phrase in data.get("response", ""):
                data["mood"] = "😐 Neutral"
                data["stress_level"] = "Low"
                data["confidence_score"] = 100.0
                data["recommendations"] = ["Share a stress, emotion, habit, or wellbeing concern."]
                data["affirmation"] = "I focus my mind on positive wellness conversations."
                
            return data
            
        except Exception as e:
            error_msg = str(e)
            print(f"[ERROR] Error generating content with {model_name}: {type(e).__name__}: {e}")
            if model_name == "gemini-flash-latest":
                return _connection_error_payload()

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
