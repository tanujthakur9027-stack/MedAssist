"""
core/llm.py
Multi-LLM Manager supporting TinyLlama (local), Groq, and Gemini 2.5 Flash
"""

import os
import re
from enum import Enum
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# ═════════════════════════════════════════════════════════════════
# FIX: Load .env from config/ folder (not current directory)
# ═════════════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, "config", ".env")

if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
    print(f"[LLM] Loaded .env from: {ENV_PATH}")
else:
    load_dotenv()  # fallback to current dir
    print(f"[LLM] WARNING: {ENV_PATH} not found, trying default .env")

class LLMProvider(Enum):
    TINYLLAMA = "tinyllama"
    GROQ = "groq"
    GEMINI = "gemini"

class LLMManager:
    def __init__(self, provider: LLMProvider = LLMProvider.GROQ):
        self.provider = provider
        self.llm = None
        self._init_model()
    
    def _init_model(self):
        if self.provider == LLMProvider.TINYLLAMA:
            try:
                from langchain_community.llms import Ollama
                self.llm = Ollama(model="tinyllama", temperature=0.3, num_ctx=4096)
                print("✅ TinyLlama loaded")
            except Exception as e:
                raise RuntimeError(f"TinyLlama failed: {e}")
        
        elif self.provider == LLMProvider.GROQ:
            try:
                from langchain_groq import ChatGroq
                api_key = os.getenv("GROQ_API_KEY")
                if not api_key:
                    raise ValueError("GROQ_API_KEY not found in .env")
                
                self.llm = ChatGroq(
                    model="openai/gpt-oss-20b", 
                    temperature=0.2,
                    max_tokens=2048,
                    groq_api_key=api_key
                )
                print("✅ Groq loaded")
            except Exception as e:
                raise RuntimeError(f"Groq failed: {e}")
        
        elif self.provider == LLMProvider.GEMINI:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    raise ValueError("GEMINI_API_KEY not found in .env")
                
                self.llm = ChatGoogleGenerativeAI(
                    model="gemini-2.5-flash",
                    temperature=0.2,
                    max_output_tokens=2048,
                    google_api_key=api_key
                )
                print("✅ Gemini loaded")
            except Exception as e:
                raise RuntimeError(f"Gemini failed: {e}")
    
    def generate(self, prompt: str) -> str:
        if not self.llm:
            raise RuntimeError("LLM not initialized")
        
        try:
            response = self.llm.invoke(prompt)
            if hasattr(response, 'content'):
                return response.content
            return str(response)
        except Exception as e:
            err_str = str(e)
            if "decommissioned" in err_str.lower():
                raise RuntimeError(f"MODEL_DECOMMISSIONED: {err_str}")
            raise RuntimeError(f"LLM_ERROR: {err_str}")
    
    def generate_medical_response(self, symptoms: str, context: str, 
                                   patient_age: Optional[int] = None,
                                   patient_gender: Optional[str] = None) -> Dict[str, Any]:
        pass


# ═════════════════════════════════════════════════════════════════
# LLMClient: Auto-fallback GROQ → GEMINI
# ═════════════════════════════════════════════════════════════════
class LLMClient:
    def __init__(self):
        self._manager = None
        self._provider = None
        self._init_with_fallback()
 
    def _init_with_fallback(self):
        # Try GROQ first
        try:
            self._manager = LLMManager(provider=LLMProvider.GROQ)
            self._provider = "groq"
            print("✅ LLMClient: Using Groq")
            return
        except Exception as e:
            print(f"⚠️ Groq failed: {e}")
        
        # Fallback to GEMINI
        try:
            self._manager = LLMManager(provider=LLMProvider.GEMINI)
            self._provider = "gemini"
            print("✅ LLMClient: Using Gemini (fallback)")
            return
        except Exception as e:
            print(f"⚠️ Gemini failed: {e}")
        
        raise RuntimeError("No LLM available. Check GROQ_API_KEY or GEMINI_API_KEY in config/.env")
 
    def generate(self, prompt: str) -> str:
        try:
            return self._manager.generate(prompt)
        except RuntimeError as e:
            err = str(e)
            if "MODEL_DECOMMISSIONED" in err and self._provider == "groq":
                print("🔄 Auto-switching to Gemini...")
                self._manager = LLMManager(provider=LLMProvider.GEMINI)
                self._provider = "gemini"
                return self._manager.generate(prompt)
            raise


# Backward compatibility
class FreeLLM:
    def __init__(self):
        self._llm = LLMClient()
    
    def predict(self, prompt, temperature=0.7):
        return self._llm.generate(prompt)