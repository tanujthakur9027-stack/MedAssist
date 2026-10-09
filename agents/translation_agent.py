"""
Translation agent.

Purpose: MedlinePlus only returns English (or Spanish) content. Rural users
need the final response in their own language. This module translates text
into Hindi (or any other language) using the free Google Translate backend
via the deep-translator library.

Install requirement:
    pip install deep-translator

Note: This needs an internet connection at runtime (it calls Google's
translation service). If there is no internet, translation will fail —
handle that failure by falling back to the original English text, so the
user still gets an answer.
"""

from deep_translator import GoogleTranslator

# Languages the user can choose from, mapped to Google Translate's language codes.
# Add more entries here if you need to support additional Indian languages.
SUPPORTED_LANGUAGES = {
    "1": ("Hindi", "hi"),
    "2": ("Bengali", "bn"),
    "3": ("Tamil", "ta"),
    "4": ("Telugu", "te"),
    "5": ("Marathi", "mr"),
    "6": ("Gujarati", "gu"),
    "7": ("Punjabi", "pa"),
    "8": ("Kannada", "kn"),
    "9": ("Malayalam", "ml"),
    "10": ("Odia", "or"),
    "11": ("Urdu", "ur"),
    "12": ("English (no translation)", "en"),
}


def prompt_language_choice() -> str:
    """
    Shows a numbered menu of supported languages and asks the user to pick
    one. Returns the language code (e.g. 'hi') for the chosen language.
    Keeps asking until a valid number is entered.
    """
    print("\nApni bhasha chunein / Select your language:")
    for key, (name, _) in SUPPORTED_LANGUAGES.items():
        print(f"  {key}. {name}")

    while True:
        choice = input("Number daalein: ").strip()
        if choice in SUPPORTED_LANGUAGES:
            name, code = SUPPORTED_LANGUAGES[choice]
            print(f"Selected: {name}\n")
            return code
        print("Galat choice, dobara try karein.")


# MedlinePlus field names that contain readable text worth translating.
# We skip fields like 'url' and 'mesh' (medical vocabulary code, not prose).
TRANSLATABLE_FIELDS = ["title", "altTitle", "FullSummary", "snippet"]


def translate_text(text: str, target_lang: str = "hi") -> str:
    """
    Translates a single string into the target language.
    Falls back to the original text if translation fails for any reason
    (no internet, API limit, empty text, etc.) so the pipeline never breaks.
    """
    if not text:
        return text
    try:
        return GoogleTranslator(source="en", target=target_lang).translate(text)
    except Exception as e:
        # Don't crash the whole pipeline over a translation failure —
        # log it and return the original English text instead.
        print(f"[translation_agent] Warning: translation failed ({e}). Returning original text.")
        return text


def translate_pipeline_output(pipeline_output: dict, target_lang: str = "hi") -> dict:
    """
    Takes the full pipeline output (from pipeline.run_pipeline) and translates
    the human-readable fields inside 'results', plus the safety messages.
    Returns a new dict — does not modify the original in place.
    """
    if pipeline_output.get("status") != "ok":
        return pipeline_output

    translated_results = []
    for item in pipeline_output.get("results", []):
        new_item = dict(item)  # copy so we don't mutate the original
        for field in TRANSLATABLE_FIELDS:
            if field in new_item:
                new_item[field] = translate_text(new_item[field], target_lang)
        translated_results.append(new_item)

    pipeline_output["results"] = translated_results

    if pipeline_output.get("safety_message"):
        pipeline_output["safety_message"] = translate_text(pipeline_output["safety_message"], target_lang)
    if pipeline_output.get("disclaimer"):
        pipeline_output["disclaimer"] = translate_text(pipeline_output["disclaimer"], target_lang)

    return pipeline_output


if __name__ == "__main__":
    # Quick manual test — needs internet to actually call Google Translate
    sample = "A fever is a body temperature that is higher than normal."
    print(f"Original: {sample}")
    print(f"Translated: {translate_text(sample)}")