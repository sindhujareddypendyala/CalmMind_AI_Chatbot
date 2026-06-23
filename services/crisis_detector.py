"""Rule-based crisis detection for CalmMind chat messages."""

import re
from typing import Any, Dict, List, Sequence, Tuple


CRISIS_TYPES = {
    "NONE": "none",
    "SUICIDE": "suicide_ideation",
    "SELF_HARM": "self_harm_intent",
    "DISTRESS": "severe_emotional_distress",
}

# Patterns intentionally focus on first-person language to reduce false positives
# for general questions or messages about another person.
SUICIDE_PATTERNS: Sequence[Tuple[str, str, int]] = (
    (r"\b(?:i\s+)?(?:want|wish|need)\s+to\s+die\b", "desire to die", 45),
    (r"\b(?:i(?:'m|\s+am)\s+)?suicidal\b", "suicidal ideation", 50),
    (r"\b(?:kill|end)\s+myself\b", "intent to end life", 55),
    (r"\bend\s+my\s+life\b", "intent to end life", 55),
    (r"\btake\s+my\s+own\s+life\b", "intent to end life", 55),
    (r"\b(?:don't|do\s+not)\s+want\s+to\s+(?:be\s+alive|live)\b", "desire not to live", 45),
    (r"\bwish\s+i\s+(?:was|were)\s+dead\b", "wish to be dead", 45),
    (r"\bbetter\s+off\s+(?:if\s+i\s+(?:was|were)\s+dead|without\s+me)\b", "perceived burdensomeness", 40),
    (r"\bno\s+(?:reason|point)\s+(?:for\s+me\s+)?to\s+(?:live|keep\s+living)\b", "loss of desire to live", 45),
    (r"\b(?:planning|plan|planned)\s+(?:to|how\s+to)\s+(?:die|kill\s+myself|end\s+my\s+life)\b", "suicide plan", 65),
)

SELF_HARM_PATTERNS: Sequence[Tuple[str, str, int]] = (
    (r"\b(?:want|need|going|plan|planning|about)\s+to\s+(?:hurt|harm|cut|burn)\s+myself\b", "self-harm intent", 55),
    (r"\b(?:hurt|harm|cut|burn)\s+myself\b", "self-harm statement", 45),
    (r"\bself[\s-]?harm(?:ing)?\b", "self-harm language", 35),
    (r"\b(?:urge|urges)\s+to\s+(?:hurt|harm|cut|burn)\s+myself\b", "self-harm urge", 55),
    (r"\b(?:started|start|relapsed|relapsing)\s+(?:cutting|self[\s-]?harming)\b", "recent self-harm", 50),
)

DISTRESS_PATTERNS: Sequence[Tuple[str, str, int]] = (
    (r"\bi\s+(?:can't|cannot)\s+take\s+(?:this|it)\s+anymore\b", "unable to cope", 32),
    (r"\bi\s+(?:can't|cannot)\s+go\s+on\b", "unable to continue", 35),
    (r"\bi(?:'m|\s+am)\s+(?:completely|utterly|totally)?\s*hopeless\b", "severe hopelessness", 32),
    (r"\bthere(?:'s|\s+is)\s+no\s+hope\b", "severe hopelessness", 30),
    (r"\bi(?:'m|\s+am)\s+(?:having|in)\s+(?:a\s+)?(?:mental\s+)?breakdown\b", "mental breakdown", 32),
    (r"\b(?:everything|life)\s+(?:feels|is)\s+unbearable\b", "unbearable distress", 35),
    (r"\bi\s+feel\s+trapped\s+(?:and|with)\s+no\s+way\s+out\b", "feeling trapped", 35),
    (r"\bnothing\s+matters\s+anymore\b", "profound despair", 28),
    (r"\bi(?:'m|\s+am)\s+(?:inconsolable|devastated|desperate)\b", "severe emotional distress", 28),
)

IMMEDIACY_PATTERNS = (
    r"\bright\s+now\b",
    r"\btonight\b",
    r"\btoday\b",
    r"\bsoon\b",
    r"\bgoing\s+to\b",
    r"\babout\s+to\b",
    r"\b(?:have|made|wrote)\s+(?:a\s+)?(?:plan|note)\b",
    r"\b(?:pills|weapon|gun|knife|rope)\b",
)

# These phrases commonly negate current personal intent. They lower confidence but
# do not completely suppress detection because context can still be ambiguous.
NEGATION_PATTERNS = (
    r"\bi\s+(?:do\s+not|don't)\s+(?:want|plan|intend)\s+to\s+(?:die|kill|hurt|harm|cut)\b",
    r"\bi(?:'m|\s+am)\s+not\s+(?:suicidal|going\s+to\s+hurt\s+myself)\b",
    r"\bi\s+would\s+never\s+(?:kill|hurt|harm)\s+myself\b",
)


def _find_matches(
    text: str,
    patterns: Sequence[Tuple[str, str, int]],
) -> Tuple[List[str], int]:
    indicators: List[str] = []
    score = 0

    for pattern, label, weight in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            if label not in indicators:
                indicators.append(label)
            score += weight

    return indicators, score


def detect_crisis(message: Any) -> Dict[str, Any]:
    """Analyze one user message and return a JSON-serializable crisis result."""
    text = str(message or "").strip()

    result: Dict[str, Any] = {
        "is_crisis": False,
        "crisis_type": CRISIS_TYPES["NONE"],
        "severity": "Low",
        "confidence_score": 0,
        "requires_immediate_support": False,
        "matched_indicators": [],
    }

    if not text:
        return result

    suicide_indicators, suicide_score = _find_matches(text, SUICIDE_PATTERNS)
    self_harm_indicators, self_harm_score = _find_matches(text, SELF_HARM_PATTERNS)
    distress_indicators, distress_score = _find_matches(text, DISTRESS_PATTERNS)

    has_immediacy = any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in IMMEDIACY_PATTERNS
    )
    has_negation = any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in NEGATION_PATTERNS
    )

    scores = {
        CRISIS_TYPES["SUICIDE"]: suicide_score,
        CRISIS_TYPES["SELF_HARM"]: self_harm_score,
        CRISIS_TYPES["DISTRESS"]: distress_score,
    }
    indicators = {
        CRISIS_TYPES["SUICIDE"]: suicide_indicators,
        CRISIS_TYPES["SELF_HARM"]: self_harm_indicators,
        CRISIS_TYPES["DISTRESS"]: distress_indicators,
    }

    crisis_type = max(scores, key=scores.get)
    score = scores[crisis_type]

    if score == 0:
        return result

    if has_immediacy and crisis_type in {
        CRISIS_TYPES["SUICIDE"],
        CRISIS_TYPES["SELF_HARM"],
    }:
        score += 20

    if has_negation:
        score -= 30

    score = max(0, min(99, score))

    # Explicit suicide/self-harm language remains safety-relevant at a lower
    # confidence. Severe distress requires a stronger phrase match.
    threshold = 25 if crisis_type != CRISIS_TYPES["DISTRESS"] else 28
    is_crisis = score >= threshold

    if not is_crisis:
        result["confidence_score"] = score
        return result

    if crisis_type == CRISIS_TYPES["SUICIDE"]:
        severity = "Critical"
    elif crisis_type == CRISIS_TYPES["SELF_HARM"]:
        severity = "Critical" if has_immediacy else "High"
    else:
        severity = "High"

    return {
        "is_crisis": True,
        "crisis_type": crisis_type,
        "severity": severity,
        "confidence_score": score,
        "requires_immediate_support": (
            crisis_type
            in {CRISIS_TYPES["SUICIDE"], CRISIS_TYPES["SELF_HARM"]}
            or has_immediacy
        ),
        "matched_indicators": indicators[crisis_type],
    }


def crisis_chat_response(detection: Dict[str, Any]) -> Dict[str, Any]:
    """Map detector output to the chatbot's existing response schema."""
    crisis_type = detection.get("crisis_type")

    if crisis_type == CRISIS_TYPES["DISTRESS"]:
        response = (
            "I'm really sorry you're carrying this much right now. You deserve "
            "support, and you do not have to handle this moment alone. Please "
            "contact someone you trust or a mental health professional now. If "
            "you feel you may hurt yourself or cannot stay safe, contact local "
            "emergency services or a crisis helpline immediately."
        )
        recommendations = [
            "📞 Tell someone you trust how intense this feels",
            "🏥 Contact a mental health professional",
            "🌬️ Place your feet on the floor and take slow breaths",
        ]
        affirmation = "This painful moment can change, and you deserve support through it."
    else:
        response = (
            "Thank you for telling me. Your safety matters most right now, and "
            "you do not have to face this alone. Please move away from anything "
            "you could use to hurt yourself and contact a trusted person, mental "
            "health professional, crisis helpline, or local emergency service "
            "now. If you are in immediate danger, call emergency services or go "
            "to the nearest emergency department."
        )
        recommendations = [
            "📞 Contact someone you trust and ask them to stay with you",
            "🏥 Contact a crisis helpline or emergency service now",
            "🛡️ Move away from anything you could use to hurt yourself",
        ]
        affirmation = "You matter, and immediate support is available."

    return {
        "response": response,
        "mood": "😔 Sad",
        "stress_level": "High",
        "confidence_score": int(detection.get("confidence_score", 95)),
        "recommendations": recommendations,
        "affirmation": affirmation,
    }
