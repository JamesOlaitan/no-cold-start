"""
Turns a whisper's text into spoken audio with ElevenLabs.

The voice isn't flat for every whisper. A fact about someone's dog just
having surgery should sound a little more careful and emotional than a
fact about their favorite coffee order. We get that by turning the fact's
urgency number into the ElevenLabs stability/style settings: less
stability and more style for high-urgency facts, and the reverse for
routine ones.
"""

import os

import requests

MODEL_ID = "eleven_flash_v2_5"
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs stock "Rachel" voice


def voice_settings_for_urgency(urgency: float) -> dict:
    urgency = max(0.0, min(1.0, urgency))
    return {
        "stability": 0.75 - (0.45 * urgency),
        "style": 0.15 + (0.65 * urgency),
        "similarity_boost": 0.8,
        "use_speaker_boost": True,
    }


def speak(text: str, urgency: float = 0.5) -> bytes:
    api_key = os.environ["ELEVENLABS_API_KEY"]
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE_ID

    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json={
            "text": text,
            "model_id": MODEL_ID,
            "voice_settings": voice_settings_for_urgency(urgency),
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.content
