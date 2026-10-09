# 🩺 MedAssist

> **AI-Powered Rural Health Information & Diagnostic Assistant**

MedAssist is an intelligent, multilingual healthcare information system designed to bridge the medical knowledge gap in rural and underserved areas. Built with **Python** and **Streamlit**, it combines **Retrieval-Augmented Generation (RAG)**, **Large Language Models (LLM)**, and **voice-enabled interfaces** to deliver accurate, accessible health information in **12 Indian languages**.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-ff4b4b)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Demo](#-demo)
- [Technology Stack](#-technology-stack)
- [Data Sources](#-data-sources)
- [Installation](#-installation)
- [Usage](#-usage)
- [Project Structure](#-project-structure)
- [Module Descriptions](#-module-descriptions)
- [Environment Variables](#-environment-variables)
- [Screenshots](#-screenshots)
- [Future Roadmap](#-future-roadmap)
- [Medical Disclaimer](#-medical-disclaimer)
- [Contributing](#-contributing)
- [License](#-license)
- [Acknowledgements](#-acknowledgements)

---

## 🎯 Overview

In India, over **600 million people** live in rural areas with limited access to qualified doctors. MedAssist addresses this challenge by providing:

- 🔍 **Instant disease information** with symptoms, diagnostic tests, precautions, and treatment
- 💊 **Drug lookup** with dosage, side effects, and interaction details
- 📄 **Medical report analysis** via OCR and AI summarization
- 🩺 **Symptom-based disease prediction** with confidence scoring
- 🗣️ **Voice output** for illiterate and visually impaired users
- 🌐 **12-language translation** for non-English speaking populations

All information is sourced from **authoritative medical databases** (MedlinePlus, OpenFDA) and processed through a robust **fallback architecture** that ensures reliability even with intermittent connectivity.

---

## ✨ Features

### 🔍 1. Disease Information Lookup
- Search any disease by name (e.g., Diabetes, Asthma, Pneumonia)
- Retrieves structured data: **Description, Symptoms, Diagnostic Tests, Precautions, Treatment, Risk Factors, When to See Doctor**
- **Clickable diagnostic test buttons** — click any test to see full details (preparation, procedure, normal values, risks)
- Smart **drug-label filtering** prevents FDA medication guides from contaminating disease results
- **Fuzzy test matching** handles variations like "A1C" → "Hemoglobin A1C (HbA1c) Test"
- Auto-fallback to keyword-based test retrieval if LLM returns insufficient results

### 💊 2. Drug Information Query
- Search by **generic name** (Paracetamol) or **brand name** (Crocin)
- **Fuzzy spelling correction** and brand→generic resolution
- Search by **symptom** (e.g., "medicine for fever")
- Returns: **Indications, Dosage, Side Effects, Warnings, Drug Interactions**
- Powered by the **OpenFDA API** for authoritative drug data

### 📄 3. Medical Report Analyzer
- Upload **PDF** or **Image** reports
- **OCR text extraction** (PyPDF2 / pdfplumber / PIL)
- AI-powered analysis returns:
  - Executive summary
  - Abnormal values detected
  - Possible health concerns
  - Diet & lifestyle recommendations
  - When to consult a specialist

### 🩺 4. Symptom Checker
- Describe symptoms in **natural language** (e.g., "I have fever, cough, and headache for 3 days")
- **NLP-based symptom extraction** with lemmatization
- Returns **Top 3 predicted diseases** with:
  - Confidence score (color-coded: 🔴 ≥70%, 🟡 40-69%, 🔵 <40%)
  - Matched symptoms
  - Urgency level (Critical / High / Medium / Low)
  - Recommended diagnostic tests (clickable)
- **Emergency detection**: automatically alerts for chest pain, unconsciousness, severe bleeding

### 🗣️ 5. Voice Output (Text-to-Speech)
- **"Listen" button** on every tab
- Converts all displayed text to **audio** using Google Text-to-Speech (gTTS)
- Supports all **12 translated languages**
- Essential for **illiterate** and **visually impaired** users
- Max **450 characters** per audio clip

### 🌐 6. Multilingual Translation
- Sidebar language selector
- **12 Indian languages** supported:
  - Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Punjabi, Kannada, Malayalam, Odia, Urdu, English
- All medical content is translated: descriptions, symptoms, drug info, report analysis

---

## 🎬 Demo

```bash
# Run the application
streamlit run app.py
```

The app opens at `http://localhost:8501` with four tabs and a sidebar for language/voice controls.

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Streamlit (Python) | Interactive web UI with 4 tabs |
| **LLM Engine** | Groq API | Fast inference (qwen-27b, gpt-oss-120b, gpt-oss-20b) |
| **Vector DB** | ChromaDB + SentenceTransformers | RAG retrieval from MedlinePlus |
| **Embeddings** | all-MiniLM-L6-v2 | 384-dimension semantic search vectors |
| **OCR** | PyPDF2 / pdfplumber / PIL | Medical report text extraction |
| **TTS** | gTTS (Google Text-to-Speech) | Audio output in multiple languages |
| **Translation** | Custom Translation Agent | 12 Indian languages support |
| **Data Storage** | JSON + ChromaDB | Medical tests & article storage |
| **Scraping** | BeautifulSoup + Requests | MedlinePlus data ingestion |

### Python Dependencies

```
streamlit
requests
chromadb
sentence-transformers
python-dotenv
gTTS
PyPDF2
pdfplumber
Pillow
pandas
numpy
```

---

## 📚 Data Sources

### 1. MedlinePlus (NIH — National Library of Medicine)
- **Source**: [medlineplus.gov](https://medlineplus.gov)
- **Content**: 500+ health topic articles
- **Process**: XML downloaded → English-only topics extracted → Parsed into ChromaDB vector embeddings
- **Use**: Powers the Disease Information tab via RAG

### 2. OpenFDA API (FDA Drug Labels)
- **Source**: [open.fda.gov](https://open.fda.gov)
- **Content**: Structured JSON drug labels, medication guides, prescribing information
- **Fields**: Active ingredients, dosage, warnings, side effects, interactions
- **Use**: Powers the Drug Information tab and Drug QA Backend

### 3. Web Scraping (Medical Tests Database)
- **Source**: MedlinePlus Medical Tests section
- **Content**: 1000+ medical tests
- **Fields per test**: Name, Description, Why It's Done, Preparation, Procedure, Normal Values, Risks
- **Use**: Enables clickable Diagnostic Tests with detailed test information

---

## 🚀 Installation

### Prerequisites
- Python 3.10 or higher
- pip package manager
- Git

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/medassist.git
cd medassist
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Create a `.env` file in the `config/` directory:

```env
# Choose your LLM provider: tinyllama | groq | gemini
LLM_PROVIDER=groq

# Groq API Key (Get from: https://console.groq.com)
GROQ_API_KEY=your_groq_api_key_here

# Gemini API Key (Get from: https://aistudio.google.com/app/apikey)
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: For embeddings
HUGGINGFACE_API_KEY=your_huggingface_key_here
```

### Step 5: Prepare the Database

```bash
# Populate ChromaDB with MedlinePlus articles
python scripts/add_medical_tests_to_rag.py

# Verify the setup
python scripts/verify_rag.py
```

### Step 6: Run the Application

```bash
streamlit run app.py
```

The application will be available at **http://localhost:8501**

---

## 📖 Usage

### Disease Information
1. Click the **"🔍 Disease Info"** tab
2. Type a disease name (e.g., "Diabetes") or click a quick example button
3. View structured cards: Description, Symptoms, Diagnostic Tests, Precautions, Treatment, Risk Factors
4. Click any **diagnostic test button** to see detailed test information
5. Click **"🔊 Listen"** to hear the content in your selected language

### Drug Information
1. Click the **"💊 Drug Info"** tab
2. Enter a drug name (generic or brand) or symptom
3. View: Indications, Dosage, Side Effects, Warnings, Interactions

### Medical Report Analysis
1. Click the **"📄 Medical Report"** tab
2. Upload a **PDF** or **Image** of your medical report
3. View AI-generated: Summary, Abnormal Values, Recommendations, Diet Advice

### Symptom Checker
1. Click the **"🩺 Symptom Checker"** tab
2. Describe your symptoms in natural language
3. View **Top 3 predicted diseases** with confidence scores and recommended tests

### Language & Voice
- Use the **sidebar** to select your preferred language
- Click **"🔊 Listen"** on any result to hear audio output
- Use the **microphone button** for voice input (if enabled)

---

## 📂 Project Structure

```
MedAssist/
│
├── app.py                              # Main Streamlit application (4 tabs)
├── requirements.txt                    # Python dependencies
│
├── config/
│   └── .env                            # API keys and configuration
│
├── data/
│   ├── medical_tests.json              # 1000+ medical tests database
│   └── medlineplus_articles.json       # Scraped articles backup
│
├── disease_info_module_complete/
│   ├── disease_info.py                 # DiseaseInfoRetriever class
│   └── chroma_db/                      # Vector database storage
│
├── agents/
│   ├── drug_info_agent.py              # DrugInfoAgent class
│   ├── drug_qa_backend.py              # Drug database engine
│   ├── symptom_checker_agent.py        # SymptomCheckerAgent class
│   ├── translation_agent.py            # 12-language translator
│   └── rag_retriever.py                # General RAG retriever
│
├── reports/
│   └── report_analyzer.py             # PDF/Image OCR + LLM analysis
│
├── voice/
│   ├── voice_output_agent.py           # TTS (gTTS)
│   └── voice_input_agent.py            # STT (speech recognition)
│
├── scrapers/
│   ├── medical_tests_scraper.py        # MedlinePlus test scraper
│   └── medlineplus_scraper.py          # Article scraper
│
└── scripts/                            # Utility scripts
    ├── add_medical_tests_to_rag.py     # Populate ChromaDB
    ├── check_db.py                     # DB diagnostics
    └── verify_rag.py                   # RAG verification
```

---

## 🔧 Module Descriptions

### Disease Information Module (`disease_info.py`)
- **`DiseaseInfoRetriever`** — Main class for disease lookup
- **`search_disease()`** — Vector search with embedding similarity + keyword fallback
- **`_call_llm()`** — Groq API caller with 3-model fallback chain
- **`_parse_json()`** — Robust JSON parser (removes markdown, comments, trailing commas)
- **`_is_drug_label_doc()`** — Filters out FDA drug labels from search results
- **`_clean_output()`** — Post-processing for asthma/coronavirus drug-phrase removal

### Drug Information Module (`drug_info_agent.py`, `drug_qa_backend.py`)
- **`DrugInfoAgent`** — Query router and answer formatter
- **`get_name()`** — Fuzzy matching: brand → generic name resolution
- **`get_all_text()`** — Returns complete drug monograph
- **`get_indications_text()`** — Returns "what is this medicine for"
- **`search()`** — Symptom-to-drug search with TF-IDF/BM25 scoring
- **`get_by_name()`** — Returns structured dict with all drug fields

### Report Analyzer (`report_analyzer.py`)
- **`extract_from_pdf()`** — PDF text extraction
- **`extract_from_image()`** — Image OCR pipeline
- **`get_structured_analysis()`** — LLM-based report summarization

### Symptom Checker (`symptom_checker_agent.py`)
- **`predict()`** — Main entry: emergency detection → symptom extraction → disease matching
- **`_extract_symptoms()`** — NLP extraction with lemmatization
- **`_extract_duration()`** — Parses "for 3 days" → numeric duration
- **`_get_urgency()`** — Classifies severity (critical/high/medium/low)
- **`_get_tests()`** — Maps disease to recommended diagnostic tests

### Utility Modules
- **`TranslationAgent`** — 12-language medical text translator
- **`VoiceOutputAgent`** — gTTS-based text-to-speech (max 450 chars)
- **`VoiceInputAgent`** — Speech-to-text for hands-free input
- **`RAG Retriever`** — General-purpose retrieval for open-ended queries

---

## 🔐 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | ✅ Yes | Groq API key for LLM inference |
| `GEMINI_API_KEY` | ⚠️ Optional | Google Gemini API key (alternative LLM) |
| `HUGGINGFACE_API_KEY` | ⚠️ Optional | HuggingFace token for embeddings |
| `LLM_PROVIDER` | ✅ Yes | Set to `groq` (or `gemini` / `tinyllama`) |

---

## 📸 Screenshots

> *Add screenshots of your application here*

| Tab | Preview |
|-----|---------|
| Disease Info | ![Disease Tab](screenshots/disease_tab.png) |
| Drug Info | ![Drug Tab](screenshots/drug_tab.png) |
| Report Analyzer | ![Report Tab](screenshots/report_tab.png) |
| Symptom Checker | ![Symptom Tab](screenshots/symptom_tab.png) |

---

## 🗺️ Future Roadmap

### Short Term
- [ ] **Offline Mode** — Download ChromaDB + local LLM for no-internet usage
- [ ] **WhatsApp Bot** — Deploy as conversational bot for feature-phone users
- [ ] **Offline TTS** — Replace gTTS with local Indic TTS engines
- [ ] **Doctor Appointment Booking** — Integration with local clinic scheduling

### Long Term
- [ ] **Image Analysis** — Skin rash, eye redness detection via computer vision
- [ ] **Telemedicine Integration** — Direct video consultation with doctors
- [ ] **Health Records** — Persistent user history with trend tracking
- [ ] **Disease Outbreak Detection** — Aggregate symptom data for epidemiology

---

## ⚠️ Medical Disclaimer

**MedAssist is an informational tool and does NOT provide medical diagnosis.**

- Always consult a **qualified healthcare professional** for medical advice, diagnosis, or treatment.
- In case of **emergency**, call **108/102** immediately.
- Do not use this application as a substitute for professional medical care.
- The information provided is sourced from MedlinePlus and OpenFDA, but may not cover all individual cases.

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgements

- **MedlinePlus** — National Library of Medicine for health topic data
- **OpenFDA** — U.S. Food & Drug Administration for drug label data
- **Groq** — For fast LLM inference API
- **Streamlit** — For the intuitive Python-based web framework
- **SentenceTransformers** — For efficient semantic embeddings
- **Google Text-to-Speech (gTTS)** — For multilingual voice output

---

<div align="center">

**Made with ❤️ for Rural India**

[🌐 Website](#) · [📧 Email](#) · [🐛 Issues](../../issues) · [💡 Discussions](../../discussions)

</div>
