"""
Speech-to-Text (STT) agent.
"""
import speech_recognition as sr

LANGUAGE_CODES = {
    "hi": "hi-IN", "bn": "bn-IN", "ta": "ta-IN", "te": "te-IN",
    "mr": "mr-IN", "gu": "gu-IN", "pa": "pa-IN", "kn": "kn-IN",
    "ml": "ml-IN", "or": "or-IN", "ur": "ur-IN", "en": "en-IN",
}


class VoiceInputAgent:
    """Wraps STT functions for app.py compatibility."""

    def __init__(self):
        pass

    def record_and_transcribe(self, lang_code: str = "en", timeout: int = 5, phrase_time_limit: int = 10):
        """Records from mic and returns text."""
        recognizer = sr.Recognizer()
        google_lang = LANGUAGE_CODES.get(lang_code, "en-IN")

        with sr.Microphone() as source:
            print("🎤 Listening...")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)

        try:
            text = recognizer.recognize_google(audio, language=google_lang)
            print(f"✅ Recognized: {text}")
            return text
        except sr.UnknownValueError:
            print("❌ Speech not understood.")
            return ""
        except sr.RequestError as e:
            print(f"❌ Speech service error: {e}")
            return ""

    def transcribe_file(self, audio_path: str, lang_code: str = "en"):
        """Transcribes an audio file."""
        recognizer = sr.Recognizer()
        google_lang = LANGUAGE_CODES.get(lang_code, "en-IN")

        with sr.AudioFile(audio_path) as source:
            audio = recognizer.record(source)

        try:
            return recognizer.recognize_google(audio, language=google_lang)
        except sr.UnknownValueError:
            print("❌ Speech not understood.")
            return ""
        except sr.RequestError as e:
            print(f"❌ Speech service error: {e}")
            return ""


if __name__ == "__main__":
    agent = VoiceInputAgent()
    print(agent.record_and_transcribe())