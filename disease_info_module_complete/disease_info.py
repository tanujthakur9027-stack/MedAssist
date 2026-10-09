"""
Disease Info Module — Auto-detects collection, no session state conflicts
"""

import os
import sys
import json
import re
from typing import Dict, List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env from project root
_script_dir = os.path.dirname(os.path.abspath(__file__))
for _env_path in [
    os.path.join(_script_dir, "..", "config", ".env"),
    os.path.join(_script_dir, "..", "..", "config", ".env"),
    os.path.join(_script_dir, "config", ".env"),
    "../config/.env",
    "../../config/.env",
]:
    if os.path.exists(_env_path):
        load_dotenv(_env_path, override=True)
        print(f"[DiseaseInfo] Loaded .env from: {_env_path}")
        break

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# LLM imports
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GEMINI_OK = True
except ImportError:
    GEMINI_OK = False

try:
    from langchain_groq import ChatGroq
    GROQ_OK = True
except ImportError:
    GROQ_OK = False

try:
    from core.llm import LLMClient
    LLMCLIENT_OK = True
except ImportError:
    LLMCLIENT_OK = False
# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_CHROMA_PATHS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "chroma_db"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "chroma_rag_db"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "vector_db"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "chroma_db"),
    "./data/chroma_db",
    "./data/chroma_rag_db",
    "./data/vector_db",
    "./chroma_db",
    "../data/chroma_db",
    "../chroma_db",
]


@dataclass
class DiseaseInfo:
    disease_name: str
    description: str
    symptoms: List[str]
    diagnostic_tests: List[str]
    precautions: List[str]
    treatment: List[str]
    risk_factors: List[str]
    when_to_see_doctor: str
    sources: List[Dict[str, str]]
    related_topics: List[str]
    confidence: str


class DiseaseInfoRetriever:
    """Auto-detects ChromaDB path and collection name."""

    def __init__(self, top_k: int = 5):
        self.top_k = top_k
        self.llm_provider = os.environ.get("LLM_PROVIDER", "groq")
        self._collection = None
        self._client = None
        self._embedder = None
        self._chroma_path = None
        self._collection_name = None

    def _connect(self):
        if self._collection is not None:
            return

        env_path = os.environ.get("CHROMA_DB_PATH")
        if env_path and os.path.exists(env_path):
            self._chroma_path = env_path
        else:
            for path in _CHROMA_PATHS:
                if os.path.exists(path):
                    self._chroma_path = os.path.abspath(path)
                    break

        if not self._chroma_path:
            raise RuntimeError(f"ChromaDB not found. Searched: {_CHROMA_PATHS}")

        try:
            self._client = chromadb.PersistentClient(
                path=self._chroma_path,
                settings=Settings(anonymized_telemetry=False)
            )
        except Exception as e:
            err_msg = str(e).lower()
            if "already exists" in err_msg or "different settings" in err_msg:
                self._client = chromadb.PersistentClient(path=self._chroma_path)
            else:
                raise

        collections = self._client.list_collections()
        if not collections:
            raise RuntimeError(f"No collections found in {self._chroma_path}")

        preferred = ["medassist_rag", "medlineplus_topics", "medlineplus_health", "health_topics", "medlineplus"]
        for name in preferred:
            if any(c.name == name for c in collections):
                self._collection_name = name
                break

        if not self._collection_name:
            self._collection_name = collections[0].name

        self._collection = self._client.get_collection(name=self._collection_name)
        doc_count = self._collection.count()
        print(f"[DiseaseInfo] Path: {self._chroma_path} | Collection: {self._collection_name} | Docs: {doc_count}")

    def _get_embedder(self):
        if self._embedder is None:
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
        return self._embedder

    # ===== DRUG LABEL FILTER =====
    def _is_drug_label_doc(self, title: str, content: str) -> bool:
        """Skip FDA drug labels, medication guides, and product inserts."""
        if not title and not content:
            return False

        title_lower = title.lower() if title else ""
        content_lower = (content or "").lower()

        title_keywords = [
            "fda", "drug label", "medication guide", "prescribing information",
            "fda-approved", "patient information", "drug facts", "package insert"
        ]
        if any(sk in title_lower for sk in title_keywords):
            return True

        content_red_flags = [
            "this product is", "this product is not", "use only after diagnosis",
            "not a fast acting", "rescue inhaler", "intended to complement, not replace",
            "initial worsening of symptoms", "stop use and ask a doctor",
            "physician should always be consulted to rule out serious causes",
            "drug facts", "active ingredient", "inactive ingredient",
            "dosage and administration", "warnings and precautions",
            "ask a doctor before use", "do not use more than directed",
            "when using this product", "keep out of reach of children",
            "if pregnant or breast-feeding", "tAMPER EVIDENT", "distributed by",
            "purpose expectorant", "nasal decongestant", "mucus relief"
        ]

        red_flag_count = sum(1 for flag in content_red_flags if flag in content_lower)
        if red_flag_count >= 2:
            return True

        if content_lower.strip().startswith("this product"):
            return True

        return False

    # ===== CONTENT RELEVANCE FILTER =====
    def _is_content_relevant(self, disease_name: str, title: str, content: str) -> bool:
        """Filter out docs about unrelated conditions."""
        disease_lower = disease_name.lower()
        title_lower = title.lower() if title else ""
        content_lower = (content or "").lower()

        if disease_lower in ["coronavirus", "covid", "covid-19"]:
            if any(h in title_lower for h in ["heart", "cardiac", "angioplasty", "coronary", "myocardial"]):
                return False
            heart_terms = ["heart", "cardiac", "angioplasty", "coronary", "myocardial", "chest pain", "rapid heartbeat"]
            covid_terms = ["covid", "coronavirus", "sars", "pandemic", "covid-19"]
            heart_mentions = sum(content_lower.count(t) for t in heart_terms)
            covid_mentions = sum(content_lower.count(t) for t in covid_terms)
            if heart_mentions > covid_mentions:
                return False

        if disease_lower == "asthma":
            if "inhaler" in title_lower and "asthma" not in title_lower:
                return False
            if any(x in content_lower for x in ["mucus relief", "expectorant", "nasal decongestant", "dextromethorphan"]):
                return False

        return True

    def search_disease(self, disease_name: str) -> List[Dict]:
        self._connect()
        doc_count = self._collection.count()
        print(f"[DEBUG] Total documents: {doc_count}")

        if doc_count == 0:
            return self._keyword_search(disease_name)

        embedder = self._get_embedder()

        query_variations = [
            f"{disease_name} disease symptoms diagnosis treatment",
            f"{disease_name} overview",
            disease_name,
        ]

        documents = []
        seen_titles = set()

        for query in query_variations:
            if len(documents) >= self.top_k:
                break

            query_embedding = embedder.encode([query]).tolist()
            try:
                results = self._collection.query(
                    query_embeddings=query_embedding,
                    n_results=self.top_k * 4,
                    include=["documents", "metadatas", "distances"]
                )
            except Exception as e:
                continue

            if results.get("documents") and results["documents"][0]:
                for i in range(len(results["ids"][0])):
                    meta = results["metadatas"][0][i]
                    title = meta.get("title", "Unknown") if meta else "Unknown"
                    content = results["documents"][0][i] or ""

                    if self._is_drug_label_doc(title, content):
                        print(f"[DEBUG] Skipping drug label: {title}")
                        continue

                    if not self._is_content_relevant(disease_name, title, content):
                        print(f"[DEBUG] Skipping irrelevant: {title}")
                        continue

                    title_lower = title.lower()
                    disease_lower = disease_name.lower()
                    related_terms = {
                        "coronavirus": ["covid", "coronavirus", "sars", "covid-19"],
                        "asthma": ["asthma", "asthmatic"],
                        "diabetes": ["diabetes", "diabetic", "blood sugar"],
                        "cancer": ["cancer", "tumor", "oncology", "carcinoma"],
                        "hypertension": ["hypertension", "blood pressure", "high blood pressure"],
                        "pneumonia": ["pneumonia", "lung infection"],
                        "migraine": ["migraine", "headache"],
                        "arthritis": ["arthritis", "joint"],
                    }
                    allowed_terms = related_terms.get(disease_lower, [disease_lower])
                    title_relevant = any(term in title_lower for term in allowed_terms)

                    if not title_relevant and len(documents) >= 2:
                        continue

                    if title in seen_titles:
                        continue
                    seen_titles.add(title)

                    try:
                        related = json.loads(meta.get("related_topics", "[]")) if meta else []
                    except:
                        related = []

                    documents.append({
                        "content": content,
                        "title": title,
                        "url": meta.get("url", "") if meta else "",
                        "distance": results["distances"][0][i] if results.get("distances") else 0.5,
                        "related_topics": related,
                        "summary_text": content,
                    })

        documents.sort(key=lambda x: x["distance"])
        print(f"[DEBUG] After filters: {len(documents)} docs")

        if not documents:
            documents = self._keyword_search(disease_name)

        return documents

    def _keyword_search(self, disease_name: str, limit: int = 10) -> List[Dict]:
        try:
            all_data = self._collection.get(include=["documents", "metadatas"])
            docs = all_data.get("documents", []) or []
            metas = all_data.get("metadatas", []) or []

            if not docs:
                print("[DEBUG] No documents in collection for keyword search")
                return []

            keywords = disease_name.lower().split()
            keywords_set = set(keywords)
            for kw in list(keywords_set):
                if kw.endswith('s'):
                    keywords_set.add(kw[:-1])
                else:
                    keywords_set.add(kw + 's')

            scored = []
            for doc, meta in zip(docs, metas):
                if not doc:
                    continue

                title = meta.get("title", "") if meta else ""
                content = doc or ""

                if self._is_drug_label_doc(title, content):
                    continue

                if not self._is_content_relevant(disease_name, title, content):
                    continue

                text = (content + " " + str(meta)).lower()
                title_lower = title.lower()

                score = 0
                for kw in keywords_set:
                    if kw in title_lower:
                        score += 10
                    if kw in text:
                        score += 2
                    if kw[:4] in title_lower:
                        score += 3

                if score > 0:
                    scored.append((score, doc, meta))

            scored.sort(key=lambda x: x[0], reverse=True)

            results = []
            seen = set()
            for score, doc, meta in scored[:limit]:
                title = meta.get("title", "Unknown") if meta else "Unknown"
                if title in seen:
                    continue
                seen.add(title)
                try:
                    related = json.loads(meta.get("related_topics", "[]")) if meta else []
                except:
                    related = []
                results.append({
                    "content": doc,
                    "title": title,
                    "url": meta.get("url", "") if meta else "",
                    "distance": 0.5,
                    "related_topics": related,
                    "summary_text": doc,
                })
            return results
        except Exception as e:
            print(f"[DiseaseInfo] Keyword fallback failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _build_prompt(self, disease_name: str, docs: List[Dict]) -> str:
        context = "\n\n---\n\n".join([
            f"TOPIC: {doc['title']}\n{doc['summary_text']}"
            for doc in docs[:8]
        ])

        return f"""You are MedAssist, a rural health information assistant.
Answer STRICTLY from the provided MedlinePlus sources below.
NEVER use outside medical knowledge.

RULES:
1. If sources do NOT discuss "{disease_name}", write "Information not available in sources." for EVERY field.
2. IGNORE drug labels or product inserts (text starting with "This product", "Ask a doctor before use", etc.).
3. List only COMMON and PRIMARY symptoms, tests, treatment for "{disease_name}".
4. Return ONLY valid JSON. No markdown, no explanations, no comments.

REQUIRED JSON FORMAT:
{{
    "disease_name": "{disease_name}",
    "description": "2-3 sentence overview from sources ONLY. Never leave empty.",
    "symptoms": ["symptom 1", "symptom 2", "symptom 3"],
    "diagnostic_tests": ["Test 1", "Test 2", "Test 3", "Test 4", "Test 5", "Test 6", "Test 7", "Test 8"],
    "precautions": ["precaution 1", "precaution 2"],
    "treatment": ["treatment 1", "treatment 2"],
    "risk_factors": ["risk 1", "risk 2"],
    "when_to_see_a_doctor": "guidance from sources. Never leave empty.",
    "confidence": "high"
}}

IMPORTANT FOR diagnostic_tests:
- Return 8 to 12 specific real medical test names.
- Examples: A1C Test, Fasting Blood Glucose, Oral Glucose Tolerance Test, Lipid Panel, Complete Blood Count, Thyroid Function Test, Microalbumin Test, Creatinine Test, Urinalysis, Electrolyte Panel, Chest X-Ray, Spirometry.
- Do NOT use generic names like "blood test" or "urine test".

SOURCES:
{context}
"""

    def _call_llm(self, prompt: str) -> str:
        import os, requests, time

        if LLMCLIENT_OK:
            try:
                client = LLMClient()
                result = client.generate(prompt)
                print(f"[DEBUG] LLMClient success! Response preview: {result[:200]}")
                return result
            except Exception as e:
                print(f"[DEBUG] LLMClient failed: {e}, trying direct requests...")

        api_key = os.environ.get("GROQ_API_KEY")
        print(f"[DEBUG] API Key first 10 chars: {api_key[:10] if api_key else 'NONE'}")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set - check config/.env")

        models = ["qwen/qwen3.6-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]

        for model_name in models:
            # Exponential backoff: 1s, 2s, 4s wait
            for attempt in range(3):
                try:
                    resp = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={
                            "model": model_name,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.1,
                            "max_tokens": 4096,
                        },
                        timeout=60
                    )
                    print(f"[DEBUG] Model: {model_name} | Attempt: {attempt+1} | Status: {resp.status_code}")

                    if resp.status_code == 401:
                        raise RuntimeError("Invalid GROQ_API_KEY - 401 Unauthorized")
                    if resp.status_code == 404:
                        print(f"[DEBUG] Model {model_name} not found, trying next...")
                        break
                    if resp.status_code == 429:
                        wait = 2 ** attempt  # 1s, 2s, 4s
                        print(f"[LLM] Rate limited, waiting {wait}s...")
                        time.sleep(wait)
                        continue
                    if resp.status_code == 400:
                        err_data = resp.json()
                        err_msg = err_data.get('error', {}).get('message', 'Unknown 400')
                        print(f"[DEBUG] 400 error: {err_msg}")
                        break

                    resp.raise_for_status()
                    data = resp.json()

                    if "choices" not in data:
                        err = data.get('error', {}).get('message', str(data))
                        raise RuntimeError(f"API error: {err}")

                    raw = data["choices"][0]["message"]["content"]
                    print(f"[DEBUG] Success with {model_name}! Response preview: {raw[:200]}")
                    return raw

                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    wait = 2 ** attempt
                    print(f"[DEBUG] Connection/Timeout error: {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                    if attempt == 2:
                        print(f"[DEBUG] {model_name} failed after 3 attempts.")
                
                except Exception as e:
                    print(f"[DEBUG] {model_name} attempt {attempt+1} failed: {e}")
                    if attempt == 2:
                        continue
                    time.sleep(1)

        raise RuntimeError("All Groq models failed. Check console.groq.com for available models.")

    def _parse_json(self, text: str) -> Dict:
        if not text:
            return {}

        text = text.strip()
        print(f"[DEBUG] Parsing JSON, text length: {len(text)}")

        # Try direct parse first
        try:
            return json.loads(text)
        except:
            pass

        # Try extracting from markdown code blocks
        patterns = [
            r'```(?:json)?\s*(.*?)\s*```',
            r'```\s*(.*?)\s*```',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1).strip())
                except:
                    pass

        # Try finding JSON object between first { and last }
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                candidate = text[start:end+1]
                # Remove any // comments
                candidate = re.sub(r'//.*$', '', candidate, flags=re.MULTILINE)
                # Remove trailing commas before } or ]
                candidate = re.sub(r',(\s*[}\]])', r'\1', candidate)
                return json.loads(candidate)
        except:
            pass

        # Try cleaning common LLM artifacts
        cleaned = text
        cleaned = re.sub(r'^[^{]*', '', cleaned)  # Remove everything before first {
        cleaned = re.sub(r'[^}]*$', '', cleaned)  # Remove everything after last }
        cleaned = re.sub(r'//.*$', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
        try:
            return json.loads(cleaned)
        except:
            pass

        print(f"[DEBUG] FAILED to parse JSON. Raw text preview:\n{text[:500]}...")
        return {}

    def _sanitize_list_field(self, parsed: Dict, field: str):
        """Ensure a field is a list. If it is a string, wrap it. If missing or invalid, set default."""
        val = parsed.get(field)
        if isinstance(val, str):
            parsed[field] = [val]
        elif not isinstance(val, list):
            parsed[field] = ["Information not available in sources."]

    def _clean_output(self, parsed: Dict, disease_name: str):
        """Remove known incorrect or bad patterns from LLM output."""
        disease_lower = disease_name.lower()

        # ===== CORONAVIRUS/COVID CLEANUP =====
        if disease_lower in ["coronavirus", "covid", "covid-19"]:
            heart_keywords = ["chest pain", "rapid heartbeat", "heart attack",
                            "angina", "cardiac arrest", "heart failure",
                            "heart tests", "cardiac catheterization", "angioplasty",
                            "coronary", "myocardial", "stent", "cardiac ct", "cardiac"]

            for field in ["symptoms", "diagnostic_tests", "treatment", "precautions", "risk_factors"]:
                if field not in parsed:
                    continue
                items = parsed[field]
                if isinstance(items, list):
                    parsed[field] = [
                        item for item in items
                        if not any(hk in item.lower() for hk in heart_keywords)
                    ]
                    if not parsed[field]:
                        parsed[field] = ["Information not available in sources."]

            for key in ["when_to_see_a_doctor", "when_to_see_doctor"]:
                wtd = parsed.get(key, "")
                if isinstance(wtd, str) and any(hk in wtd.lower() for hk in heart_keywords):
                    parsed[key] = "If you have COVID-19 symptoms such as fever, cough, or difficulty breathing, consult your healthcare provider."

        if disease_lower == "asthma":
            drug_phrases = [
                "ask a doctor before use", "stop use and ask", "this product is",
                "not a fast acting", "rescue inhaler", "intended to complement",
                "initial worsening", "use only after diagnosis", "not replace",
                "mucus relief", "expectorant", "nasal decongestant", "dextromethorphan",
                "do not use more than directed", "when using this product",
                "keep out of reach of children", "if pregnant or breast-feeding",
                "tAMPER EVIDENT", "distributed by"
            ]

            for field in ["symptoms", "diagnostic_tests", "treatment", "precautions", "risk_factors"]:
                val = parsed.get(field)
                if isinstance(val, list):
                    parsed[field] = [
                        item for item in val
                        if not any(dp in item.lower() for dp in drug_phrases)
                    ]
                    if not parsed[field]:
                        parsed[field] = ["Information not available in sources."]

            for key in ["description", "when_to_see_a_doctor", "when_to_see_doctor"]:
                val = parsed.get(key, "")
                if isinstance(val, str) and any(dp in val.lower() for dp in drug_phrases):
                    parsed[key] = "Information not available in sources."

    def get_structured_info(self, disease_name: str) -> DiseaseInfo:
        docs = self.search_disease(disease_name)

        if not docs:
            return DiseaseInfo(
                disease_name=disease_name,
                description="No information found in the database. The disease may not be in our MedlinePlus collection, or the database might be empty. Try checking the Symptom Checker tab instead.",
                symptoms=["Data not available"],
                diagnostic_tests=["Data not available"],
                precautions=["Data not available"],
                treatment=["Data not available"],
                risk_factors=["Data not available"],
                when_to_see_doctor="Please consult a healthcare provider.",
                sources=[],
                related_topics=[],
                confidence="low"
            )

        llm_response = None
        parsed = {}

        try:
            llm_response = self._call_llm(self._build_prompt(disease_name, docs))
            print(f"[DEBUG] LLM response length: {len(llm_response) if llm_response else 0}")
            parsed = self._parse_json(llm_response)
            print(f"[DEBUG] Parsed keys: {list(parsed.keys())}")
        except Exception as e:
            print(f"[DEBUG] LLM call failed: {e}")
            return self._fallback(disease_name, docs, str(e))

        if not parsed or "description" not in parsed:
            print("[DEBUG] LLM returned empty or invalid JSON, using fallback")
            return self._fallback(disease_name, docs, "Invalid JSON from LLM")

        # Sanitize list fields
        for field in ["symptoms", "diagnostic_tests", "precautions", "treatment", "risk_factors"]:
            self._sanitize_list_field(parsed, field)

        # ===== CLEAN OUTPUT (REMOVE BAD PATTERNS) =====
        self._clean_output(parsed, disease_name)

        sources = [{"title": d["title"], "url": d["url"]} for d in docs[:3]]
        related = []
        for d in docs:
            for rt in d.get("related_topics", [])[:2]:
                if isinstance(rt, dict) and rt.get("title"):
                    related.append(rt["title"])
                elif isinstance(rt, str):
                    related.append(rt)
        related = list(set(related))[:5]

        when_to_see = parsed.get("when_to_see_a_doctor") or parsed.get("when_to_see_doctor", "Consult a doctor.")

        return DiseaseInfo(
            disease_name=parsed.get("disease_name", disease_name),
            description=parsed.get("description", "Information not available."),
            symptoms=parsed.get("symptoms", []) or ["See sources"],
            diagnostic_tests=parsed.get("diagnostic_tests", []) or ["See sources"],
            precautions=parsed.get("precautions", []) or ["See sources"],
            treatment=parsed.get("treatment", []) or ["See sources"],
            risk_factors=parsed.get("risk_factors", []) or ["See sources"],
            when_to_see_doctor=when_to_see,
            sources=sources,
            related_topics=related,
            confidence=parsed.get("confidence", "medium")
        )

    def _fallback(self, disease_name: str, docs: List[Dict], error: str) -> DiseaseInfo:
        combined = " ".join([d["content"] for d in docs[:3]])
        sources = [{"title": d["title"], "url": d["url"]} for d in docs[:3]]
        return DiseaseInfo(
            disease_name=disease_name,
            description=f"Extracted from MedlinePlus sources. (LLM processing failed: {error})",
            symptoms=self._extract(combined, ["symptom", "sign", "feel", "experience"]),
            diagnostic_tests=self._extract(combined, ["test", "diagnosis", "screening", "exam"]),
            precautions=["See MedlinePlus sources for precautions"],
            treatment=self._extract(combined, ["treatment", "medicine", "therapy", "medication", "drug"]),
            risk_factors=self._extract(combined, ["risk", "cause", "factor", "increase"]),
            when_to_see_doctor="Please consult a healthcare provider.",
            sources=sources,
            related_topics=[],
            confidence="low"
        )

    def _extract(self, text: str, keywords: List[str]) -> List[str]:
        sentences = re.split(r'[.!?]\s+', text)
        found = []
        for sent in sentences:
            s = sent.lower()
            if any(kw in s for kw in keywords) and len(sent.strip()) > 10:
                found.append(sent.strip())
        return found[:5] if found else ["See sources for details"]


def format_disease_info(info: DiseaseInfo) -> Dict:
    return {
        "disease_name": info.disease_name,
        "description": info.description,
        "symptoms": info.symptoms,
        "diagnostic_tests": info.diagnostic_tests,
        "precautions": info.precautions,
        "treatment": info.treatment,
        "risk_factors": info.risk_factors,
        "when_to_see_doctor": info.when_to_see_doctor,
        "sources": info.sources,
        "related_topics": info.related_topics,
        "confidence": info.confidence
    }