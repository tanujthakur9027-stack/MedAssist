"""
config/settings.py
Central configuration for MedAssist
"""

import os
from dotenv import load_dotenv
from core.llm import LLMProvider

load_dotenv()

class Settings:
    # LLM Configuration
    DEFAULT_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "groq")
    
    @staticmethod
    def get_llm_provider():
        provider_map = {
            "tinyllama": LLMProvider.TINYLLAMA,
            "groq": LLMProvider.GROQ,
            "gemini": LLMProvider.GEMINI
        }
        return provider_map.get(Settings.DEFAULT_PROVIDER.lower(), LLMProvider.GROQ)
    
    # Paths
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")
    PROCESSED_DATA_DIR = os.path.join(DATA_DIR, "processed")
    VECTOR_DB_DIR = os.path.join(DATA_DIR, "vector_db")
    
    # MedlinePlus Data Files
    HEALTH_TOPICS_FILE = os.path.join(RAW_DATA_DIR, "medlineplus_health_topics.xml")
    DRUGS_FILE = os.path.join(RAW_DATA_DIR, "medlineplus_drugs.xml")
    MEDICAL_TESTS_FILE = os.path.join(RAW_DATA_DIR, "medlineplus_medical_tests.json")
    
    # Vector DB
    CHROMA_DB_PATH = os.path.join(VECTOR_DB_DIR, "chroma_db")
    
    # Safety
    MIN_GROUNDING_SCORE = 0.25  # Minimum context similarity required
    MAX_RESPONSE_TIME = 30      # seconds

settings = Settings()