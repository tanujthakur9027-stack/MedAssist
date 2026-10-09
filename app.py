"""
MedAssist — Rural Health Companion
Streamlit app with Disease Info, Drug Info, Symptom Checker
"""

import os
import sys
import json
import re
import traceback
from dotenv import load_dotenv
import uuid
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

import streamlit as st
from PIL import Image

try:
    import pytesseract
except ImportError:
    pytesseract = None

# ═══ MEDICAL TESTS DATABASE ═══
@st.cache_data
def load_medical_tests():
    """Load scraped medical test data from JSON files."""
    possible_paths = [
        os.path.join(BASE_DIR, "data", "medical_tests.json"),
        os.path.join(BASE_DIR, "scrapers", "medlineplus_medical_tests.json"),
        os.path.join(BASE_DIR, "scrapers", "medical_tests.json"),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            try:
                print(f"[MedicalTests] Trying: {path}")
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    print(f"[MedicalTests] Loaded JSON type: {type(data)}")

                    # Format 1: {"tests": [{"name": "...", ...}]}
                    if isinstance(data, dict) and "tests" in data:
                        tests_list = data["tests"]
                        result = {t.get("name", "").lower(): t for t in tests_list if t.get("name")}
                        print(f"[MedicalTests] Dict format with 'tests' key: {len(result)} tests")
                        return result

                    # Format 2: [{"name": "...", ...}] (direct list)
                    elif isinstance(data, list):
                        result = {t.get("name", "").lower(): t for t in data if isinstance(t, dict) and t.get("name")}
                        print(f"[MedicalTests] List format: {len(result)} tests")
                        return result

                    # Format 3: {"Test Name": {...}}
                    elif isinstance(data, dict):
                        result = {k.lower(): v for k, v in data.items() if isinstance(v, dict)}
                        print(f"[MedicalTests] Dict format: {len(result)} tests")
                        return result

            except json.JSONDecodeError as e:
                print(f"[MedicalTests] JSON decode error in {path}: {e}")
            except Exception as e:
                print(f"[MedicalTests] Error loading {path}: {e}")

    print("[MedicalTests] No valid medical_tests.json found")
    return {}

medical_tests_db = load_medical_tests()
print(f"[MedicalTests] Final loaded: {len(medical_tests_db)} tests")


def get_fallback_tests(disease_name: str, medical_tests_db: dict, min_tests: int = 8):
    """Find related tests by keyword matching if LLM returns too few."""
    if not medical_tests_db or not disease_name:
        return []

    disease_lower = disease_name.lower()

    # Auto-extract keywords from disease name
    keywords = [w for w in disease_lower.split() if len(w) > 2]

    # Disease-specific expanded keywords
    expanded_keywords = set(keywords)
    common_medical = ['blood', 'urine', 'x-ray', 'test', 'scan', 'culture', 
                      'panel', 'count', 'function', 'level', 'screening', 'exam']
    expanded_keywords.update(common_medical)

    # Add related medical terms based on disease name
    if 'diabetes' in disease_lower:
        expanded_keywords.update(['glucose', 'a1c', 'hba1c', 'sugar', 'insulin', 'lipid', 'kidney'])
    elif 'asthma' in disease_lower or 'lung' in disease_lower:
        expanded_keywords.update(['spirometry', 'lung', 'breath', 'pulmonary', 'peak flow', 'chest', 'x-ray'])
    elif 'heart' in disease_lower or 'cardiac' in disease_lower:
        expanded_keywords.update(['cholesterol', 'ecg', 'troponin', 'echo', 'stress', 'lipid'])
    elif 'kidney' in disease_lower or 'renal' in disease_lower:
        expanded_keywords.update(['creatinine', 'bun', 'urinalysis', 'gfr', 'protein', 'albumin'])
    elif 'liver' in disease_lower or 'hepat' in disease_lower:
        expanded_keywords.update(['bilirubin', 'alt', 'ast', 'hepatitis', 'prothrombin'])
    elif 'thyroid' in disease_lower:
        expanded_keywords.update(['tsh', 't3', 't4', 'thyroxine', 'antibody'])
    elif 'cancer' in disease_lower or 'tumor' in disease_lower:
        expanded_keywords.update(['biopsy', 'marker', 'mammography', 'colonoscopy', 'psa', 'cea'])
    elif 'blood' in disease_lower:
        expanded_keywords.update(['cbc', 'hemoglobin', 'hematocrit', 'platelet', 'wbc', 'rbc'])
    elif 'pneumonia' in disease_lower or 'chest' in disease_lower:
        expanded_keywords.update(['chest', 'x-ray', 'sputum', 'culture', 'blood', 'oxygen'])
    elif 'arthritis' in disease_lower or 'joint' in disease_lower:
        expanded_keywords.update(['rheumatoid', 'anti-ccp', 'crp', 'esr', 'ana', 'uric', 'x-ray'])

    scored_tests = []
    for test_name, test_data in medical_tests_db.items():
        score = 0
        test_text = (test_name + ' ' + 
                    str(test_data.get('description', '')) + ' ' + 
                    str(test_data.get('why_done', ''))).lower()

        for kw in expanded_keywords:
            if kw in test_text:
                score += 3

        if score > 0:
            scored_tests.append((score, test_name))

    scored_tests.sort(reverse=True)
    return [name for _, name in scored_tests[:min_tests]]


env_path = os.path.join(BASE_DIR, 'config', '.env')
load_dotenv(env_path)
sys.path.insert(0, os.path.join(BASE_DIR, "agents"))
sys.path.insert(0, os.path.join(BASE_DIR, "core"))


def normalize_name(s: str) -> str:
    """Normalize test name for fuzzy matching."""
    import re
    s = s.lower()
    s = re.sub(r'[()\[\]{}]', '', s)
    s = re.sub(r'[^a-z0-9]', '', s)
    return s


# ---------------------------------------------------------------------------
# Module imports with graceful degradation
# ---------------------------------------------------------------------------
import_errors = []

# Disease Info
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from disease_info_module_complete.disease_info import DiseaseInfoRetriever, format_disease_info
    DISEASE_MODULE_OK = True
except Exception as e:
    import_errors.append(f"disease_info: {str(e)}")
    DISEASE_MODULE_OK = False

# RAG / Symptom Checker
try:
    from agents.rag_retriever import RAGRetriever
    RAG_MODULE_OK = True
except Exception as e:
    import_errors.append(f"rag_retriever: {str(e)}")
    RAG_MODULE_OK = False

# Drug Info
try:
    from agents.drug_info_agent import DrugInfoAgent 
    DRUG_MODULE_OK = True
except Exception as e:
    import_errors.append(f"drug_info_agent: {str(e)}")
    DRUG_MODULE_OK = False

# Translation
try:
    from agents.translation_agent import translate_text as agent_translate
    TRANSLATION_OK = True
except Exception as e:
    import_errors.append(f"translation_agent: {str(e)}")
    TRANSLATION_OK = False

# Voice Output (TTS)
try:
    from voice.voice_output_agent import VoiceOutputAgent
    TTS_AVAILABLE = True
except Exception as e:
    TTS_AVAILABLE = False
    print(f"[TTS] Not available: {e}")


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="MedAssist — Rural Health Companion",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Handle query params for test selection
query_params = st.query_params
if "selected_test" in query_params:
    raw_key = query_params["selected_test"]
    if raw_key in medical_tests_db:
        st.session_state.selected_medical_test = raw_key
    else:
        matched = False
        norm_raw = normalize_name(raw_key)
        for db_name in medical_tests_db.keys():
            norm_db = normalize_name(db_name)
            if norm_raw == norm_db or norm_raw in norm_db or norm_db in norm_raw:
                st.session_state.selected_medical_test = db_name
                matched = True
                break
        if not matched:
            st.session_state.selected_medical_test = raw_key
    del st.query_params["selected_test"]
    st.rerun()


# ---------------------------------------------------------------------------
# Custom CSS — Dark theme
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .main { background-color: #0f1117; }
    .stTextInput > div > div > input { background-color: #1a1d24; color: #fafafa; border: 1px solid #2d3436; }
    .stTextArea > div > div > textarea { background-color: #1a1d24; color: #fafafa; border: 1px solid #2d3436; }
    .stSelectbox > div > div { background-color: #1a1d24; color: #fafafa; }
    .stButton > button { background-color: #0984e3; color: white; border-radius: 8px; }
    .stButton > button:hover { background-color: #74b9ff; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { background-color: #1a1d24; color: #b2bec3; border-radius: 8px 8px 0 0; }
    .stTabs [aria-selected="true"] { background-color: #0984e3 !important; color: white !important; }
    h1, h2, h3, h4 { color: #fafafa !important; }
    p, li { color: #b2bec3 !important; }
    .info-card { background-color: #1a1d24; padding: 20px; border-radius: 12px; border-left: 4px solid; margin-bottom: 16px; height: 100%; }
    .warning-card { background-color: #1a1d24; padding: 16px; border-radius: 12px; border-left: 4px solid #e74c3c; margin-bottom: 12px; }
    .success-card { background-color: #1a1d24; padding: 16px; border-radius: 12px; border-left: 4px solid #2ecc71; margin-bottom: 12px; }
    .caption-box { background-color: #16181f; padding: 16px; border-radius: 10px; border: 1px solid #2d3436; color: #dfe6e9; line-height: 1.6; }
    .llm-warning { background-color: #2d1b1b; padding: 12px 16px; border-radius: 8px; border: 1px solid #e74c3c; color: #ff6b6b; margin-bottom: 16px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
def init_session_state():
    defaults = {
        "messages": [],
        "language": "en",
        "location": "",
        "emergency_alert": False,
        "last_input": "",
        "drug_input": "",
        "drug_trigger": False,
        "disease_input": "",
        "disease_trigger": False,
        "disease_result": None,
        "drug_results": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session_state()

# ---------------------------------------------------------------------------
# Language options
# ---------------------------------------------------------------------------
LANGUAGE_OPTIONS = [
    ("English", "en"),
    ("हिन्दी (Hindi)", "hi"),
    ("বাংলা (Bengali)", "bn"),
    ("தமிழ் (Tamil)", "ta"),
    ("తెలుగు (Telugu)", "te"),
    ("मराठी (Marathi)", "mr"),
    ("ગુજરાતી (Gujarati)", "gu"),
    ("ਪੰਜਾਬੀ (Punjabi)", "pa"),
    ("ಕನ್ನಡ (Kannada)", "kn"),
    ("മലയാളം (Malayalam)", "ml"),
    ("ଓଡ଼ିଆ (Odia)", "or"),
    ("اردو (Urdu)", "ur"),
]

# ---------------------------------------------------------------------------
# Translation wrapper
# ---------------------------------------------------------------------------
def translate_text(text: str, target_lang: str = None) -> str:
    if not target_lang:
        target_lang = st.session_state.get("language", "en")
    if target_lang == "en" or not TRANSLATION_OK:
        return text
    try:
        return agent_translate(text, target_lang=target_lang)
    except Exception as e:
        print(f"[Translate] Error: {e}")
        return text

# ---------------------------------------------------------------------------
# Emergency detection
# ---------------------------------------------------------------------------
EMERGENCY_KEYWORDS = [
    "chest pain", "can't breathe", "cant breathe", "difficulty breathing",
    "severe bleeding", "unconscious", "unconsciousness", "heart attack",
    "stroke", "suicide", "suicidal", "poisoning", "poisoned",
    "seizure", "convulsions", "not breathing", "choking",
    "severe burn", "electrocuted", "drowning", "anaphylaxis",
]

def detect_emergency(text: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    return any(kw in text_lower for kw in EMERGENCY_KEYWORDS)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("<h1 style='color:#74b9ff;'>🏥 MedAssist</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#636e72;'>Rural Health Companion</p>", unsafe_allow_html=True)
    st.markdown("---")

    # Language selector
    lang = st.selectbox(
        "🌐 Language / भाषा",
        options=LANGUAGE_OPTIONS,
        format_func=lambda x: x[0],
        index=0,
    )
    st.session_state.language = lang[1]

    # Emergency button
    st.markdown("---")
    if st.button("🚨 EMERGENCY", use_container_width=True):
        st.session_state.emergency_alert = True
        st.error("🚨 Call 108/102 immediately for medical emergency!")


    # Debug imports
    if import_errors:
        st.markdown("---")
        with st.expander("⚠️ Import Errors"):
            for err in import_errors:
                st.code(err)


# ---------------------------------------------------------------------------
# Main Header
# ---------------------------------------------------------------------------
st.markdown("<h1 style='text-align:center;color:#74b9ff;'>🏥 MedAssist</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;color:#636e72;'>Your Rural Health Companion — Disease Info • Drug Info • Symptom Checker</p>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Disease Info", "💊 Drug Info", "📄 Medical Report", "🩺 Symptom Checker",
])


# ========================== TAB 1: DISEASE INFO ==========================
with tab1:
    st.markdown("<h2 style='color:#fafafa;'>🔍 Disease Information</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#b2bec3;'>Search for diseases to get symptoms, tests, precautions, and treatment info.</p>", unsafe_allow_html=True)

    if not DISEASE_MODULE_OK:
        st.error("❌ Disease info module not available. Check import errors in sidebar.")
    else:
        
        if "disease_retriever" not in st.session_state:
            st.session_state.disease_retriever = DiseaseInfoRetriever(top_k=5)
        if "disease_cache" not in st.session_state:
            st.session_state.disease_cache = {}
        
        retriever = st.session_state.disease_retriever

        # Handle example button clicks before creating the widget
        auto_search = False
        if '_pending_disease' in st.session_state:
            default_disease_value = st.session_state._pending_disease
            del st.session_state._pending_disease
            auto_search = True
        else:
            default_disease_value = ""

        disease_name = st.text_input(
            "Enter disease name:",
            value=default_disease_value,
            placeholder="e.g., Diabetes, Asthma, Pneumonia, Arthritis...",
            key="disease_input"
        )

        col_search, _ = st.columns([1, 5])
        with col_search:
            disease_search_clicked = st.button("🔍 Look Up", use_container_width=True)

        # Quick example buttons
        st.markdown('<p style="color:#636e72;font-size:0.85rem;">Quick examples:</p>', unsafe_allow_html=True)
        ex_cols = st.columns(5)
        disease_examples = ["Diabetes", "Asthma", "Pneumonia", "Arthritis", "Coronavirus"]
        for i, ex in enumerate(disease_examples):
            with ex_cols[i]:
                if st.button(ex, key=f"dis_ex_{ex}", use_container_width=True):
                    st.session_state._pending_disease = ex
                    st.rerun()

        # ===== FETCH & STORE RESULT =====
        if (disease_search_clicked or auto_search) and disease_name and disease_name.strip():
            if detect_emergency(disease_name):
                st.error("🚨 EMERGENCY DETECTED: If this is a real emergency, call 108/102 immediately!")

            cache_key = disease_name.strip().lower()

            if cache_key in st.session_state.disease_cache:
                st.info("📋 Loading from cache...")
                st.session_state.disease_result = st.session_state.disease_cache[cache_key]
                if "selected_medical_test" in st.session_state:
                    del st.session_state.selected_medical_test
            else:
                with st.spinner(f"🔍 Searching for **{disease_name}**... Please wait"):
                    try:
                        info = retriever.get_structured_info(disease_name.strip())
                        result = format_disease_info(info)
                        st.session_state.disease_result = result
                        
                        # save in cache 
                        st.session_state.disease_cache[cache_key] = result
                        
                        if "selected_medical_test" in st.session_state:
                            del st.session_state.selected_medical_test
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        st.code(traceback.format_exc())

        # ===== DISPLAY RESULT =====
        if st.session_state.get("disease_result"):
            data = st.session_state.disease_result

            # Translate if not English
            if st.session_state.language != "en" and TRANSLATION_OK:
                try:
                    for key in ["description", "when_to_see_doctor"]:
                        if data.get(key) and isinstance(data[key], str):
                            data[key] = agent_translate(data[key], target_lang=st.session_state.language)
                    for key in ["symptoms", "diagnostic_tests", "precautions", "treatment", "risk_factors"]:
                        if data.get(key) and isinstance(data[key], list):
                            translated = []
                            for item in data[key]:
                                if isinstance(item, str) and item.strip():
                                    translated.append(agent_translate(item, target_lang=st.session_state.language))
                                else:
                                    translated.append(item)
                            data[key] = translated
                except Exception as e:
                    print(f"[App] Disease translation failed: {e}")

            # LLM Fallback Warning
            desc = data.get('description', '')
            if 'LLM processing failed' in desc or data.get('confidence', '').lower() == 'low':
                st.markdown("""
                <div class="llm-warning">
                    ⚠️ <strong>LLM Not Available:</strong> Results are from fallback extraction and may be incomplete. 
                    Set <code>GROQ_API_KEY</code> or <code>GOOGLE_API_KEY</code> environment variable for better results.
                </div>
                """, unsafe_allow_html=True)

            st.markdown(f"<h3 style='color:#fafafa;margin-top:20px;'>{data['disease_name']}</h3>", unsafe_allow_html=True)
            st.markdown(f"<p style='color:#fdcb6e;'>Confidence: {data['confidence'].upper()}</p>", unsafe_allow_html=True)

            # ===== TEST DETAIL VIEW =====
            if st.session_state.get("selected_medical_test"):
                test_key = st.session_state.selected_medical_test
                test_data = medical_tests_db.get(test_key, {})

                # Fuzzy match if exact not found
                if not test_data:
                    norm_key = normalize_name(test_key)
                    for db_name, db_data in medical_tests_db.items():
                        norm_db = normalize_name(db_name)
                        if norm_key == norm_db or norm_key in norm_db or norm_db in norm_key:
                            test_data = db_data
                            test_key = db_name
                            break


                # Word overlap match
                if not test_data:
                    key_words = set(re.sub(r'[^a-z0-9\s]', '', test_key.lower()).split())
                    best_match = None
                    best_score = 0
                    for db_name, db_data in medical_tests_db.items():
                        db_words = set(re.sub(r'[^a-z0-9\s]', '', db_name.lower()).split())
                        common = key_words & db_words
                        if common:
                            score = len(common) / max(len(key_words), len(db_words))
                            if score > best_score:
                                best_score = score
                                best_match = (db_name, db_data)
                    if best_match and best_score > 0.3:
                        test_key, test_data = best_match

                st.markdown("---")
                back_col, title_col = st.columns([1, 4])
                with back_col:
                    if st.button("← Back to Disease", key="back_to_disease", use_container_width=True):
                        del st.session_state.selected_medical_test
                        st.rerun()
                with title_col:
                    display_name = test_data.get('name', test_key.title()) if test_data else test_key.title()
                    st.markdown(f"<h3 style='color: #ccd6f6; margin: 0;'>🔬 {display_name}</h3>", unsafe_allow_html=True)

                if test_data:
                    d1, d2 = st.columns(2)
                    with d1:
                        desc_text = test_data.get('description', test_data.get('summary', test_data.get('about', 'No description available.')))
                        st.markdown(f"""
                        <div class="info-card" style="border-left-color: #74b9ff;">
                            <h4 style="color:#74b9ff;margin:0 0 8px 0;">📝 About</h4>
                            <p style="color:#b2bec3;margin:0;">{desc_text}</p>
                        </div>
                        """, unsafe_allow_html=True)

                        why_text = test_data.get('why_done', test_data.get('why_its_done', test_data.get('purpose', '')))
                        if why_text:
                            st.markdown(f"""
                            <div class="info-card" style="border-left-color: #55efc4;">
                                <h4 style="color:#55efc4;margin:0 0 8px 0;">🎯 Why It's Done</h4>
                                <p style="color:#b2bec3;margin:0;">{why_text}</p>
                            </div>
                            """, unsafe_allow_html=True)

                    with d2:
                        prep_text = test_data.get('how_you_prepare', test_data.get('preparation', ''))
                        if prep_text:
                            st.markdown(f"""
                            <div class="info-card" style="border-left-color: #fdcb6e;">
                                <h4 style="color:#fdcb6e;margin:0 0 8px 0;">⚠️ Preparation</h4>
                                <p style="color:#b2bec3;margin:0;">{prep_text}</p>
                            </div>
                            """, unsafe_allow_html=True)

                        proc_text = test_data.get('what_happens', test_data.get('what_you_can_expect', test_data.get('procedure', '')))
                        if proc_text:
                            st.markdown(f"""
                            <div class="info-card" style="border-left-color: #a29bfe;">
                                <h4 style="color:#a29bfe;margin:0 0 8px 0;">🔍 Procedure</h4>
                                <p style="color:#b2bec3;margin:0;">{proc_text}</p>
                            </div>
                            """, unsafe_allow_html=True)

                    results_text = test_data.get('normal_values', test_data.get('results', test_data.get('what_results_mean', '')))
                    if results_text:
                        st.markdown(f"""
                        <div class="info-card" style="border-left-color: #00b894;">
                            <h4 style="color:#00b894;margin:0 0 8px 0;">✅ Results & Normal Range</h4>
                            <p style="color:#b2bec3;margin:0;">{results_text}</p>
                        </div>
                        """, unsafe_allow_html=True)

                    risks_text = test_data.get('risks_complications', test_data.get('risks', test_data.get('side_effects', '')))
                    if risks_text:
                        st.markdown(f"""
                        <div class="info-card" style="border-left-color: #ff6b6b;">
                            <h4 style="color:#ff6b6b;margin:0 0 8px 0;">⚠️ Risks</h4>
                            <p style="color:#b2bec3;margin:0;">{risks_text}</p>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    # Test not in database
                    st.markdown("""
                    <div class="info-card" style="border-left-color: #fdcb6e;">
                        <h4 style="color:#fdcb6e;margin:0 0 8px 0;">ℹ️ Test Information</h4>
                        <p style="color:#b2bec3;margin:0;">
                            This test is commonly recommended for the searched condition, but detailed information 
                            is not available in the local database yet. Please consult a healthcare provider or 
                            search on MedlinePlus for complete details about this test.
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("---")

            # ===== DISEASE CARDS (only show if no test selected) =====
            if not st.session_state.get("selected_medical_test"):
                card_configs = [
                    ("📖 Description", data['description'], "#74b9ff"),
                    ("🛡️ Precautions", data['precautions'], "#55efc4"),
                    ("🤒 Symptoms", data['symptoms'], "#ff6b6b"),
                    ("💊 Treatment", data['treatment'], "#fdcb6e"),
                    ("🩺 When to See a Doctor", data['when_to_see_doctor'], "#00cec9"),
                ]

                for i in range(0, len(card_configs), 2):
                    c1, c2 = st.columns(2)
                    title, content, color = card_configs[i]
                    with c1:
                        if isinstance(content, list):
                            content_html = "".join([f"<li style='margin-bottom:6px;'>{item}</li>" for item in content])
                            content_html = f"<ul style='margin:0;padding-left:18px;'>{content_html}</ul>"
                        else:
                            content_html = f"<p style='margin:0;'>{content}</p>"
                        st.markdown(f"""
                        <div class="info-card" style="border-left-color: {color};">
                            <h4 style="color:{color};margin:0 0 12px 0;font-size:1.1rem;">{title}</h4>
                            <div style="color:#b2bec3;">{content_html}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    if i + 1 < len(card_configs):
                        title, content, color = card_configs[i + 1]
                        with c2:
                            if isinstance(content, list):
                                content_html = "".join([f"<li style='margin-bottom:6px;'>{item}</li>" for item in content])
                                content_html = f"<ul style='margin:0;padding-left:18px;'>{content_html}</ul>"
                            else:
                                content_html = f"<p style='margin:0;'>{content}</p>"
                            st.markdown(f"""
                            <div class="info-card" style="border-left-color: {color};">
                                <h4 style="color:{color};margin:0 0 12px 0;font-size:1.1rem;">{title}</h4>
                                <div style="color:#b2bec3;">{content_html}</div>
                            </div>
                            """, unsafe_allow_html=True)

                # ===== DIAGNOSTIC TESTS (CLICKABLE LINKS) =====
                diagnostic_tests = data.get('diagnostic_tests', [])

                # Handle string responses
                if isinstance(diagnostic_tests, str):
                    if any(bad in diagnostic_tests.lower() for bad in ['see source', 'not available', 'consult', 'doctor', 'details']):
                        diagnostic_tests = []
                    else:
                        diagnostic_tests = [t.strip() for t in diagnostic_tests.split(',') if t.strip()]

                # Filter out bad/generic entries
                filtered_tests = []
                for t in diagnostic_tests:
                    t_lower = t.lower().strip()
                    if len(t_lower) < 3:
                        continue
                    if any(bad in t_lower for bad in ['see source', 'not available', 'consult your', 'healthcare provider', 'for more information']):
                        continue
                    filtered_tests.append(t)
                diagnostic_tests = filtered_tests

                # Fallback if too few tests
                if len(diagnostic_tests) < 3 and medical_tests_db:
                    fallback = get_fallback_tests(data.get('disease_name', disease_name), medical_tests_db)
                    existing = set(t.lower().strip() for t in diagnostic_tests)
                    for test in fallback:
                        if test.lower().strip() not in existing:
                            diagnostic_tests.append(test.title().replace('-', ' '))
                            if len(diagnostic_tests) >= 10:
                                break

                if diagnostic_tests:
                    st.markdown("""
                    <div class="info-card" style="border-left-color: #a29bfe; padding-bottom: 8px;">
                        <h4 style="color: #a29bfe; margin: 0 0 8px 0; font-size:1.1rem;">🔬 Diagnostic Tests</h4>
                        <p style="color: #636e72; font-size: 0.8rem; margin: 0;">Click any test to view details</p>
                    </div>
                    """, unsafe_allow_html=True)

                    test_cols = st.columns(2)
                    for idx, test in enumerate(diagnostic_tests):
                        test_key_raw = test.lower().strip()
                        with test_cols[idx % 2]:
                            test_key = test_key_raw
                            test_data = medical_tests_db.get(test_key)

                            # Fuzzy match
                            if not test_data:
                                for db_name, db_data in medical_tests_db.items():
                                    if normalize_name(test_key_raw) in normalize_name(db_name) or normalize_name(db_name) in normalize_name(test_key_raw):
                                        test_data = db_data
                                        test_key = db_name
                                        break

                            if st.button(
                                f"🔬 {test}", 
                                key=f"diag_test_{idx}_{test_key[:15]}",
                                use_container_width=False,
                                type="secondary"
                            ):
                                st.session_state.selected_medical_test = test_key
                                st.rerun()

                # ===== RISK FACTORS =====
                risk_content = data.get('risk_factors', [])
                if risk_content:
                    if isinstance(risk_content, list):
                        risk_html = "".join([f"<li style='margin-bottom:6px;'>{item}</li>" for item in risk_content])
                        risk_html = f"<ul style='margin:0;padding-left:18px;'>{risk_html}</ul>"
                    else:
                        risk_html = f"<p style='margin:0;'>{risk_content}</p>"
                    st.markdown(f"""
                    <div class="info-card" style="border-left-color: #fab1a0;">
                        <h4 style="color:#fab1a0;margin:0 0 12px 0;font-size:1.1rem;">📊 Risk Factors</h4>
                        <div style="color:#b2bec3;">{risk_html}</div>
                    </div>
                    """, unsafe_allow_html=True)

                # Sources
                if data.get('sources'):
                    st.markdown("<p style='color:#636e72;font-size:0.85rem;'>📚 Sources:</p>", unsafe_allow_html=True)
                    for src in data['sources']:
                        st.markdown(f"<p style='color:#636e72;font-size:0.8rem;'>• {src.get('title', 'Unknown')} — {src.get('url', 'N/A')}</p>", unsafe_allow_html=True)

                # Related topics
                if data.get('related_topics'):
                    st.markdown(f"<p style='color:#636e72;font-size:0.85rem;'>🔗 Related: {', '.join(data['related_topics'])}</p>", unsafe_allow_html=True)

                # ===== READ ALOUD =====
                st.markdown("---")
                st.markdown("<h4 style='color:#74b9ff;'>🔊 Read Aloud</h4>", unsafe_allow_html=True)
                if TTS_AVAILABLE:
                    speech_parts = [
                        f"Disease: {data.get('disease_name', '')}",
                        f"Description: {data.get('description', '')}",
                        f"Symptoms: {data.get('symptoms', '')}",
                        f"Precautions: {data.get('precautions', '')}",
                        f"Treatment: {data.get('treatment', '')}",
                        f"When to see a doctor: {data.get('when_to_see_doctor', '')}",
                    ]
                    speech_text = " . ".join(str(p) for p in speech_parts if p)
                    speech_text = re.sub(r'<[^>]+>', '', speech_text)
                    speech_text = speech_text.replace("**", "").replace("•", ",").replace("\n", " ")[:450]
                    if st.button("🔊 Listen", key="listen_disease_btn", use_container_width=True):
                        with st.spinner("Generating audio..."):
                            try:
                                tts = VoiceOutputAgent()
                                audio_path = tts.text_to_speech(speech_text, output_path="voice_disease.mp3")
                                if audio_path and os.path.exists(audio_path):
                                    st.audio(audio_path, format="audio/mp3")
                                else:
                                    st.warning("Could not generate audio.")
                            except Exception as e:
                                st.error(f"TTS error: {e}")
                else:
                    st.info("🔇 Text-to-Speech not available. Install gTTS: pip install gTTS")                    


# ========================== TAB 2: DRUG INFO ==========================
with tab2:
    st.markdown("<h2 style='color: #ccd6f6; margin-bottom: 8px;'>💊 Drug Information</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #8892b0; margin-bottom: 20px;'>Search by drug name or ask a question like 'What medicine helps with hypertension?'</p>", unsafe_allow_html=True)

    # [FIX 1] Initialize session state for drug audio at the top of tab2
    if "drug_audio_path" not in st.session_state:
        st.session_state.drug_audio_path = None

    drug_input = st.text_input(
        "Enter drug name or question:",
        placeholder="e.g., Paracetamol, or 'medicine for high blood pressure'...",
        key="drug_search"
    )

    # Quick example buttons
    st.markdown("<p style='color: #8892b0; font-size: 0.85rem; margin-bottom: 8px;'>Quick examples:</p>", unsafe_allow_html=True)
    drug_examples = ["Paracetamol", "Ibuprofen", "medicine for diabetes", "cough syrup", "Aspirin"]
    dex_cols = st.columns(5)
    for idx, ex in enumerate(drug_examples):
        with dex_cols[idx]:
            if st.button(ex, key=f"drug_ex_{idx}", use_container_width=True):
                st.session_state.drug_search_value = ex
                st.rerun()

    if "drug_search_value" in st.session_state:
        drug_input = st.session_state.drug_search_value
        del st.session_state.drug_search_value

    # [FIX 2] When new search happens, clear old audio so previous audio doesn't play for new query
    if st.button("🔍 Search Drug", use_container_width=False, type="primary"):
        if not drug_input or not drug_input.strip():
            st.warning("Please enter a drug name or question.")
        elif not DRUG_MODULE_OK:
            st.error("❌ Drug info module not available. Check import errors in sidebar.")
        else:
            # Clear previous audio when starting a new search
            st.session_state.drug_audio_path = None

            with st.spinner(f"Searching for '{drug_input}'..."):
                try:
                    if "drug_agent" not in st.session_state:
                        st.session_state.drug_agent = DrugInfoAgent()

                    result = st.session_state.drug_agent.answer(drug_input)

                    if result["type"] == "error":
                        st.error(result["message"])
                    elif result["type"] == "not_found":
                        st.warning(result["message"])
                    else:
                        answer_text = result.get("answer", "No information available.")

                        # Translate if not English
                        if st.session_state.language != "en" and TRANSLATION_OK:
                            try:
                                answer_text = agent_translate(answer_text, target_lang=st.session_state.language)
                            except Exception as e:
                                print(f"[App] Drug translation failed: {e}")

                        # Store the final answer text in session state so we can use it for audio later
                        st.session_state.drug_answer_text = answer_text

                        st.markdown(f"""
                        <div style="background: rgba(102,126,234,0.08); border: 1px solid rgba(102,126,234,0.2); border-radius: 12px; padding: 20px; margin-bottom: 24px;">
                            <p style="color: #ccd6f6; line-height: 1.7; margin: 0; white-space: pre-wrap; font-size: 1rem;">{answer_text}</p>
                        </div>
                        """, unsafe_allow_html=True)

                        # Sources
                        sources = result.get("sources", [])
                        if sources:
                            st.markdown("<h4 style='color: #ccd6f6; margin-top: 20px;'>📚 Sources</h4>", unsafe_allow_html=True)
                            seen = set()
                            for s in sources:
                                name = s.get("drug_name", "Unknown") if isinstance(s, dict) else str(s)
                                if name in seen or name == "Unknown Drug":
                                    continue
                                seen.add(name)
                                st.markdown(f"<p style='color: #8892b0;'>• {name}</p>", unsafe_allow_html=True)

                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    st.info("Make sure drug_info_agent.py and drug_qa_backend.py are properly configured.")

    # [FIX 3] Display Read Aloud section OUTSIDE the search button block
    # This ensures the audio player stays visible after page rerun
    if "drug_answer_text" in st.session_state and st.session_state.drug_answer_text:
        st.markdown("---")
        st.markdown("<h4 style='color: #ccd6f6;'>🔊 Read Aloud</h4>", unsafe_allow_html=True)

        if TTS_AVAILABLE:
            # Button to generate audio
            if st.button("🔊 Listen", key="listen_drug_btn", use_container_width=True):
                with st.spinner("Generating audio..."):
                    try:
                        tts = VoiceOutputAgent()
                        import re
                        speech_text = re.sub(r'<[^>]+>', '', str(st.session_state.drug_answer_text))
                        speech_text = speech_text.replace("**", "").replace("•", ",").replace("\n", " ")[:450]

                        audio_path = tts.text_to_speech(speech_text, output_path="voice_drug.mp3")
                        
                        # [FIX 4] Store the generated audio path in session state
                        if audio_path and os.path.exists(audio_path):
                            st.session_state.drug_audio_path = audio_path
                            # Force rerun so audio player appears below the button
                            st.rerun()
                        else:
                            st.warning("Could not generate audio.")
                    except Exception as e:
                        st.error(f"TTS error: {e}")

            # [FIX 5] Play audio from session state — this runs EVERY rerun, not just inside button click
            if st.session_state.drug_audio_path and os.path.exists(st.session_state.drug_audio_path):
                st.audio(st.session_state.drug_audio_path, format="audio/mp3")
        else:
            st.info("🔇 Text-to-Speech not available. Install gTTS: pip install gTTS")


# ========================== TAB 3: MEDICAL REPORT ==========================
with tab3:
    st.markdown("<h2 style='color:#fafafa;'>📄 Medical Report Analyzer</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color:#b2bec3;'>Upload a medical report (PDF or Image). We will explain it in simple language.</p>", unsafe_allow_html=True)

    uploaded_file = st.file_uploader("Upload Report (PDF or Image)", type=["pdf", "png", "jpg", "jpeg","webp"])

    if uploaded_file is not None:
        temp_path = os.path.join(BASE_DIR, "temp_report_" + uploaded_file.name)
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        with st.spinner("📖 Reading your report..."):
            try:
                sys.path.insert(0, os.path.join(BASE_DIR, "reports"))
                from report_analyzer import extract_from_pdf, extract_from_image, get_structured_analysis

                if uploaded_file.name.lower().endswith(".pdf"):
                    raw_text = extract_from_pdf(temp_path)
                else:
                    raw_text = extract_from_image(temp_path)

                if raw_text.startswith("PDF extraction error") or raw_text.startswith("OCR error"):
                    st.error(raw_text)
                elif len(raw_text) < 20:
                    st.warning("Could not read text from the file. Please upload a clearer image or PDF.")
                else:
                    with st.spinner("🤖 Analyzing report..."):
                        analysis = get_structured_analysis(raw_text, language=st.session_state.language)

                    # Summary
                    summary_text = analysis.get('summary', '').strip()
                    if not summary_text:
                        summary_text = "Report analyzed. Key findings are listed below."

                    st.markdown(f"""
                    <div class="info-card" style="border-left-color: #74b9ff;">
                        <h4 style="color:#74b9ff;margin:0 0 12px 0;">📝 Summary</h4>
                        <p style="color:#b2bec3;margin:0;">{summary_text}</p>
                    </div>
                    """, unsafe_allow_html=True)

                    # Values Found
                    values = analysis.get("values_found", {})
                    if values:
                        st.markdown("<h4 style='color:#fafafa;'>📊 Values Found</h4>", unsafe_allow_html=True)
                        v_cols = st.columns(3)
                        for idx, (test_name, val) in enumerate(values.items()):
                            with v_cols[idx % 3]:
                                st.markdown(f"""
                                <div style="background:#1a1d24;padding:10px;border-radius:8px;text-align:center;margin-bottom:8px;">
                                    <p style="color:#636e72;font-size:0.75rem;margin:0;">{test_name}</p>
                                    <p style="color:#74b9ff;font-size:1.1rem;font-weight:600;margin:0;">{val}</p>
                                </div>
                                """, unsafe_allow_html=True)

                    # Problems
                    problems = analysis.get("problems", [])
                    if problems:
                        st.markdown("<h4 style='color:#fafafa;'>⚠️ Problems Found</h4>", unsafe_allow_html=True)
                        for p in problems:
                            st.markdown(f"""
                            <div class="warning-card">
                                <p style="color:#ff6b6b;margin:0;">• {p}</p>
                            </div>
                            """, unsafe_allow_html=True)

                    # Recommendations
                    recs = analysis.get("recommendations", [])
                    if recs:
                        st.markdown("<h4 style='color:#fafafa;'>✅ What To Do</h4>", unsafe_allow_html=True)
                        for r in recs:
                            st.markdown(f"<p style='color:#b2bec3;'>• {r}</p>", unsafe_allow_html=True)

                    # Diet & Lifestyle
                    diet = analysis.get("diet_lifestyle", [])
                    if diet:
                        st.markdown("<h4 style='color:#fafafa;'>🥗 Diet & Lifestyle</h4>", unsafe_allow_html=True)
                        for d in diet:
                            st.markdown(f"<p style='color:#b2bec3;'>• {d}</p>", unsafe_allow_html=True)

                    # When to see doctor
                    doc = analysis.get("when_to_see_doctor", "")
                    if doc:
                        st.markdown(f"""
                        <div class="info-card" style="border-left-color: #fdcb6e;">
                            <h4 style="color:#fdcb6e;margin:0 0 12px 0;">🩺 When To See Doctor</h4>
                            <p style="color:#b2bec3;margin:0;">{doc}</p>
                        </div>
                        """, unsafe_allow_html=True)

                    # Read Aloud
                    st.markdown("---")
                    st.markdown("<h4 style='color:#74b9ff;'>🔊 Read Aloud</h4>", unsafe_allow_html=True)

                    if TTS_AVAILABLE:
                        speech = f"Report Summary. {analysis.get('summary', '')}"
                        if problems:
                            speech += " Problems found: " + ". ".join(problems)
                        if recs:
                            speech += " What to do: " + ". ".join(recs[:3])
                        speech += f" When to see doctor: {doc}"
                        speech = speech.replace("**", "").replace("•", ",")[:450]

                        if st.button("🔊 Listen", key="listen_report_btn", use_container_width=True):
                            with st.spinner("Generating audio..."):
                                try:
                                    tts = VoiceOutputAgent()
                                    ap = tts.text_to_speech(speech, output_path="voice_report.mp3")
                                    if ap and os.path.exists(ap):
                                        st.audio(ap, format="audio/mp3")
                                    else:
                                        st.warning("Could not generate audio.")
                                except Exception as e:
                                    st.error(f"TTS error: {e}")
                    else:
                        st.info("🔇 Text-to-Speech not available. Install gTTS: pip install gTTS")

            except Exception as e:
                st.error(f"Error analyzing report: {str(e)}")
                st.code(traceback.format_exc())
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)


# ========================== TAB 4: SYMPTOM CHECKER ==========================
with tab4:
    st.markdown("<h2 style='color: #ccd6f6; margin-bottom: 8px;'>🩺 Symptom Checker</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #8892b0; margin-bottom: 20px;'>Describe your symptoms and get possible conditions with confidence scores.</p>", unsafe_allow_html=True)

    symptom_input = st.text_area(
        "Describe your symptoms:",
        placeholder="e.g., I have fever, cough, cold, and vomiting for 3 days...",
        height=100,
        key="symptom_input"
    )

    # Quick symptom buttons
    st.markdown("<p style='color: #8892b0; font-size: 0.85rem; margin-bottom: 8px;'>Quick add:</p>", unsafe_allow_html=True)
    quick_symptoms = ["Fever", "Cough", "Headache", "Vomiting", "Stomach Pain"]
    qs_cols = st.columns(5)
    for idx, sym in enumerate(quick_symptoms):
        with qs_cols[idx]:
            if st.button(sym, key=f"qs_{idx}", use_container_width=True):
                current = st.session_state.get("symptom_input", "")
                st.session_state.symptom_input = f"{current}, {sym}".strip(", ")
                st.rerun()

    if st.button("🔍 Check Symptoms", use_container_width=False, type="primary"):
        if not symptom_input or not symptom_input.strip():
            st.warning("Please describe your symptoms.")
        else:
            with st.spinner("Analyzing your symptoms..."):
                try:
                    if "symptom_checker" not in st.session_state:
                        from agents.symptom_checker_agent import SymptomCheckerAgent
                        st.session_state.symptom_checker = SymptomCheckerAgent()

                    result = st.session_state.symptom_checker.predict(symptom_input, language=st.session_state.language)

                    if result["type"] == "emergency":
                        st.error(result["message"])
                        st.info("🚑 Call emergency services immediately!")

                    elif result["type"] == "error":
                        st.warning(result["message"])

                    else:
                        # Detected Symptoms
                        st.markdown(f"""
                        <div style="background: rgba(102,126,234,0.08); border-radius: 8px; padding: 12px; margin-bottom: 16px;">
                            <p style="color: #8892b0; margin: 0;"><b>Detected Symptoms:</b> {', '.join(result['symptoms'])}</p>
                            {f"<p style='color: #8892b0; margin: 4px 0 0 0;'><b>Duration:</b> {result['duration']} days</p>" if result['duration'] else ""}
                        </div>
                        """, unsafe_allow_html=True)

                        # Predictions with confidence
                        st.markdown("<h4 style='color: #ccd6f6;'>📊 Possible Conditions</h4>", unsafe_allow_html=True)

                        for i, pred in enumerate(result["predictions"][:3], 1):
                            if pred["confidence"] >= 70:
                                color, bg, border = "#ff6b6b", "rgba(255,107,107,0.1)", "rgba(255,107,107,0.3)"
                            elif pred["confidence"] >= 40:
                                color, bg, border = "#fdcb6e", "rgba(253,203,110,0.1)", "rgba(253,203,110,0.3)"
                            else:
                                color, bg, border = "#74b9ff", "rgba(116,185,255,0.1)", "rgba(116,185,255,0.3)"

                            bar_width = int(pred["confidence"])

                            st.markdown(f"""
                            <div style="background: {bg}; border: 1px solid {border}; border-radius: 12px; padding: 16px; margin-bottom: 12px;">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                    <h5 style="color: {color}; margin: 0; font-size: 1.1rem;">{i}. {pred['disease']}</h5>
                                    <span style="color: {color}; font-weight: 600; font-size: 1.2rem;">{pred['confidence']}%</span>
                                </div>
                                <div style="background: rgba(255,255,255,0.1); border-radius: 6px; height: 8px; overflow: hidden; margin-bottom: 8px;">
                                    <div style="background: {color}; width: {bar_width}%; height: 100%; border-radius: 6px;"></div>
                                </div>
                                <p style="color: #8892b0; font-size: 0.85rem; margin: 0;">
                                    <b>Matched:</b> {', '.join(pred['matched_symptoms'])}<br>
                                    <b>Urgency:</b> {pred['urgency'].upper()} | <b>Typical Duration:</b> {pred['duration_hint']}
                                </p>
                            </div>
                            """, unsafe_allow_html=True)

                        # Recommended Tests
                        st.markdown("---")
                        st.markdown("<h4 style='color: #ccd6f6;'>🔬 Recommended Tests</h4>", unsafe_allow_html=True)

                        all_tests = []
                        seen_tests = set()
                        for pred in result["predictions"][:3]:
                            for test in pred.get("recommended_tests", []):
                                if test not in seen_tests:
                                    all_tests.append((test, pred["disease"]))
                                    seen_tests.add(test)

                        if all_tests:
                            for test_name, from_disease in all_tests[:6]:
                                test_key = test_name.lower().strip()

                                if test_key in medical_tests_db:
                                    if st.button(
                                        f"🔬 {test_name}",
                                        key=f"rec_test_{test_key[:20]}_{from_disease[:10]}",
                                        use_container_width=True,
                                        type="secondary",
                                        help=f"Recommended for {from_disease}"
                                    ):
                                        st.session_state.selected_medical_test = test_key
                                        st.rerun()
                                else:
                                    st.markdown(f"""
                                    <div style="display: inline-block; background: rgba(102,126,234,0.15); border: 1px solid rgba(102,126,234,0.3); border-radius: 20px; padding: 6px 14px; margin: 4px 4px 4px 0; color: #b2bec3; font-size: 0.85rem;">
                                        🔬 {test_name} <span style="color: #636e72;">({from_disease})</span>
                                    </div>
                                    """, unsafe_allow_html=True)
                        else:
                            st.info("No specific tests recommended. Consult a doctor.")

                        # Explanation
                        if result.get("explanation"):
                            st.markdown("---")
                            st.markdown("<h4 style='color: #ccd6f6;'>📝 Analysis</h4>", unsafe_allow_html=True)
                            st.markdown(f"<p style='color: #b2bec3; line-height: 1.6;'>{result['explanation']}</p>", unsafe_allow_html=True)

                        # Disclaimer
                        st.markdown("""
                        <div style="background: rgba(255,107,107,0.05); border: 1px solid rgba(255,107,107,0.2); border-radius: 8px; padding: 12px; margin-top: 16px;">
                            <p style="color: #ff6b6b; margin: 0; font-size: 0.85rem;">
                                ⚠️ <b>Disclaimer:</b> This is not a medical diagnosis. These predictions are based on symptom matching only. 
                                Always consult a qualified doctor for proper diagnosis and treatment.
                            </p>
                        </div>
                        """, unsafe_allow_html=True)

                        # Read Aloud
                        st.markdown("---")
                        st.markdown("<h4 style='color: #ccd6f6;'>🔊 Read Aloud</h4>", unsafe_allow_html=True)

                        if TTS_AVAILABLE:
                            speech_parts = [f"Symptom analysis results."]
                            if result['predictions']:
                                speech_parts.append(f"Top prediction: {result['predictions'][0]['disease']} with {result['predictions'][0]['confidence']}% confidence.")
                                if len(result['predictions']) > 1:
                                    speech_parts.append(f"Second possibility: {result['predictions'][1]['disease']} with {result['predictions'][1]['confidence']}% confidence.")
                            speech_text = " ".join(speech_parts)
                            speech_text = speech_text.replace("**", "").replace("•", ",")[:450]

                            if st.button("🔊 Listen", key="listen_symptom_btn", use_container_width=True):
                                with st.spinner("Generating audio..."):
                                    try:
                                        tts = VoiceOutputAgent()
                                        audio_path = tts.text_to_speech(speech_text, output_path="voice_symptom.mp3")
                                        if audio_path and os.path.exists(audio_path):
                                            st.audio(audio_path, format="audio/mp3")
                                        else:
                                            st.warning("Could not generate audio.")
                                    except Exception as e:
                                        st.error(f"TTS error: {e}")
                        else:
                            st.info("🔇 Text-to-Speech not available. Install gTTS: pip install gTTS")

                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    st.code(traceback.format_exc())


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<p style='text-align:center;color:#636e72;font-size:0.8rem;'>🏥 MedAssist © 2026 — For informational purposes only. Not a substitute for professional medical advice.</p>", unsafe_allow_html=True)