"""Live speech-to-text via the browser's built-in recognition (Chrome / Edge). No installs, no API key.
The component returns the speaker-labelled lines; Python turns them into 'Customer:/Agent:' text."""
from pathlib import Path

import streamlit.components.v1 as components

_component = components.declare_component("speech_recorder", path=str(Path(__file__).parent / "speech_recorder"))

LANGUAGES = {"English (India)": "en-IN", "English (US)": "en-US", "English (UK)": "en-GB",
             "Hindi": "hi-IN", "Tamil": "ta-IN", "Telugu": "te-IN"}


def speech_recorder(key: str, lang: str = "en-IN"):
    return _component(lang=lang, key=key, default=None)


def lines_to_text(lines: list[dict]) -> str:
    return "\n".join(f"{'Customer' if l['speaker'] == 'customer' else 'Agent'}: {l['text'].strip()}"
                     for l in lines if l.get("text", "").strip())
