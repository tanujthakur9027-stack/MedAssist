"""
Text-to-Speech (TTS) agent.
"""
from gtts import gTTS
import os


class VoiceOutputAgent:
    def __init__(self):
        pass

    def text_to_speech(self, text: str, lang_code: str = "en", output_path: str = "response.mp3"):
        if not text:
            print("❌ No text provided for TTS.")
            return None

        # gTTS limit — truncate to avoid failure
        MAX_CHARS = 500
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS].rsplit(' ', 1)[0] + "..."

        try:
            tts = gTTS(text=text, lang=lang_code, slow=False)
            tts.save(output_path)
            print(f"✅ Audio saved to {output_path}")
            return os.path.abspath(output_path)
        except Exception as e:
            print(f"❌ TTS failed: {e}")
            return None


if __name__ == "__main__":
    agent = VoiceOutputAgent()
    agent.text_to_speech("This is a test.", lang_code="en")