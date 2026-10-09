"""
Medical Report Analyzer — Simple Language for Rural Patients
Extracts text from PDF/Image → finds abnormal values → explains in plain Hindi/English mix
"""

import os
import re
import html

try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
try:
    from agents.translation_agent import translate_text
    TRANSLATION_OK = True
except Exception as e:
    print(f"[ReportAnalyzer] Translation import error: {e}")
    TRANSLATION_OK = False
    def translate_text(text, target_lang="en"):
        return text
# Windows Tesseract path (optional)
TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# Lazy LLM init 
_llm = None

def _get_llm():
    global _llm
    if _llm is not None:
        return _llm
    
    try:
        # Try LLMClient (auto-fallback GROQ → GEMINI)
        from core.llm import LLMClient
        _llm = LLMClient()
        print("[ReportAnalyzer] LLMClient loaded")
        return _llm
    except Exception as e1:
        print(f"[ReportAnalyzer] LLMClient failed: {e1}")
        try:
            # Fallback  FreeLLM
            from core.llm import FreeLLM
            _llm = FreeLLM()
            print("[ReportAnalyzer] FreeLLM loaded")
            return _llm
        except Exception as e2:
            print(f"[ReportAnalyzer] FreeLLM failed: {e2}")
            return None


# ═══════════════════════════════════════════════════════════════════
# NORMAL RANGES DATABASE (for reference + LLM context)
# ═════════════════════════════════════════════════════════════════==

NORMAL_RANGES = """
COMMON TEST NORMAL RANGES (for reference):
• Blood Pressure (BP): Less than 120/80 mmHg. 120-139/80-89 is elevated. 140/90+ is high.
• Fasting Blood Sugar: 70-100 mg/dL normal. 100-125 prediabetes. 126+ diabetes.
• PP / Random Blood Sugar: Less than 140 mg/dL normal. 140-199 prediabetes. 200+ high.
• Hemoglobin (Male): 13.5-17.5 g/dL. (Female): 12.0-15.5 g/dL. Below 12 is low (anemia).
• WBC (TLC): 4,000-11,000 per cmm. High means infection. Low means weak immunity.
• Platelets: 1,50,000-4,50,000 per cmm. Below 1,50,000 is low.
• Creatinine: 0.7-1.3 mg/dL. High means kidney problem.
• Urea: 7-20 mg/dL.
• Total Cholesterol: Less than 200 mg/dL. 200-239 borderline. 240+ high.
• LDL (Bad Cholesterol): Less than 100 mg/dL. 100-129 near ideal. 130-159 borderline. 160+ high.
• HDL (Good Cholesterol): Above 40 mg/dL (male), above 50 (female). Higher is better.
• Triglycerides: Less than 150 mg/dL. 150-199 borderline. 200+ high.
• Uric Acid: 3.5-7.2 mg/dL (male), 2.4-6.0 (female).
• Bilirubin: 0.1-1.2 mg/dL.
• SGPT (ALT): 7-56 U/L. High means liver stress.
• SGOT (AST): 5-40 U/L.
• Thyroid TSH: 0.4-4.0 mIU/L.
• Vitamin D: 30-100 ng/mL. Below 20 deficient.
• Vitamin B12: 200-900 pg/mL. Below 200 deficient.
• BMI: 18.5-24.9 normal. 25-29.9 overweight. 30+ obese.
• Pulse/Heart Rate: 60-100 beats per minute.
• SpO2 (Oxygen): 95-100% normal. Below 90 is dangerous.
• ESR: 0-15 mm/hr (male), 0-20 (female).
"""

# ═══════════════════════════════════════════════════════════════════
# TEXT EXTRACTION
# ═════════════════════════════════════════════════════════════════==

def extract_from_pdf(pdf_path):
    if not PDF_AVAILABLE:
        return "PDF extraction error: pdfplumber not installed. Run: pip install pdfplumber"
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                pt = page.extract_text()
                if pt:
                    text += pt + "\n"
        return text.strip()
    except Exception as e:
        return f"PDF extraction error: {str(e)}"


def extract_from_image(image_path):
    if not OCR_AVAILABLE:
        return "OCR error: pytesseract or PIL not installed. Run: pip install pytesseract pillow"
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        return f"OCR error: {str(e)}"


def clean_text(raw_text):
    text = re.sub(r'\n+', '\n', raw_text)
    text = re.sub(r'\s+', ' ', text)
    # Remove common OCR artifacts
    text = re.sub(r'[_]{3,}', '', text)
    return text.strip()


# ═══════════════════════════════════════════════════════════════════
# VALUE EXTRACTION (Regex backup — even if LLM fails)
# ═════════════════════════════════════════════════════════════════==

VALUE_PATTERNS = {
    "Blood Pressure": r'\b(?:bp|blood\s*pressure)\b[^\d]*(\d{2,3})\s*(?:[/\\]\s*(\d{2,3}))?',
    "Fasting Sugar": r'\b(?:fasting\s*blood\s*sugar|fbs|fasting\s*glucose)\b[^\d]*(\d{2,3}(?:[.,]\d+)?)',
    "PP Sugar": r'\b(?:pp\s*blood\s*sugar|ppbs|post\s*prandial)\b[^\d]*(\d{2,3}(?:[.,]\d+)?)',
    "Random Sugar": r'\b(?:random\s*blood\s*sugar|rbs)\b[^\d]*(\d{2,3}(?:[.,]\d+)?)',
    "Hemoglobin": r'\b(?:hb|hemoglobin|haemoglobin)\b[^\d]*(\d{1,2}(?:[.,]\d+)?)',
    "WBC": r'\b(?:wbc|tlc|total\s*leukocyte)\b[^\d]*(\d{1,2}(?:[.,]\d+)?)\s*(?:thousand|k)?',
    "Platelets": r'\b(?:platelet|plt)\b[^\d]*(\d{2,3}(?:,\d{3})?)',
    "Creatinine": r'\b(?:creatinine)\b[^\d]*(\d+[.,]?\d*)',
    "Urea": r'\b(?:urea|blood\s*urea)\b[^\d]*(\d+[.,]?\d*)',
    "Total Cholesterol": r'\b(?:total\s*cholesterol|cholesterol\s*total)\b[^\d]*(\d+[.,]?\d*)',
    "LDL": r'\b(?:ldl|low\s*density)\b[^\d]*(\d+[.,]?\d*)',
    "HDL": r'\b(?:hdl|high\s*density)\b[^\d]*(\d+[.,]?\d*)',
    "Triglycerides": r'\b(?:triglycerides)\b[^\d]*(\d+[.,]?\d*)',
    "Uric Acid": r'\b(?:uric\s*acid)\b[^\d]*(\d+[.,]?\d*)',
    "Bilirubin": r'\b(?:bilirubin|total\s*bilirubin)\b[^\d]*(\d+[.,]?\d*)',
    "SGPT": r'\b(?:sgpt|alt)\b[^\d]*(\d+[.,]?\d*)',
    "SGOT": r'\b(?:sgot|ast)\b[^\d]*(\d+[.,]?\d*)',
    "TSH": r'\b(?:tsh|thyroid)\b[^\d]*(\d+[.,]?\d*)',
    "Vitamin D": r'\b(?:vitamin\s*d|25[\-\s]?oh\s*vitamin\s*d)\b[^\d]*(\d+[.,]?\d*)',
    "Vitamin B12": r'\b(?:vitamin\s*b12|cobalamin)\b[^\d]*(\d+[.,]?\d*)',
    "SpO2": r'\b(?:spo2|oxygen\s*saturation|sao2)\b[^\d]*(\d{2,3})',
    "Pulse": r'\b(?:pulse|heart\s*rate)\b[:\s]*(\d{2,3})',
    "Temperature": r'\b(?:temperature|temp)\b[^\d]*(\d{2,3}(?:[.,]\d+)?)',
    "Respiratory Rate": r'\b(?:respiratory\s*rate|respiratory\s*rt|resp\s*rate)\b[^\d]*(\d{2,3})',
}


def extract_values(text):
    """Extract numeric values from report using regex with overlap protection."""
    found = {}
    text_lower = text.lower()
    used_spans = []  # Track matched positions to avoid reuse
    
    for test_name, pattern in VALUE_PATTERNS.items():
        for match in re.finditer(pattern, text_lower, re.IGNORECASE):
            groups = match.groups()
            
            # Check if this match overlaps with already used ones
            match_start = match.start()
            match_end = match.end()
            
            overlap = False
            for used_start, used_end in used_spans:
                if not (match_end <= used_start or match_start >= used_end):
                    overlap = True
                    break
            
            if overlap:
                continue
            
            # Build value from captured groups
            if groups:
                parts = [g.strip().replace(",", ".") for g in groups if g and g.strip()]
                if len(parts) == 2:
                    val = f"{parts[0]}/{parts[1]}"
                elif len(parts) == 1:
                    val = parts[0]
                else:
                    continue
            else:
                val = match.group(0).strip()
            
            if val:
                found[test_name] = val
                used_spans.append((match_start, match_end))
                break  # Only first non-overlapping match per test
    
    return found


# ═══════════════════════════════════════════════════════════════════
# LLM ANALYSIS
# ═════════════════════════════════════════════════════════════════==

def analyze_report(report_text):
    """
    Analyze report in simple language.
    Returns structured dict.
    """
    if len(report_text) < 20:
        return {
            "summary": "Could not read the report properly. Please upload a clearer image or PDF.",
            "problems": [],
            "recommendations": [],
            "diet_lifestyle": [],
            "when_to_see_doctor": "Please consult a doctor with the original report.",
            "values_found": {},
            "raw_response": ""
        }

    # Extract values via regex first
    extracted_values = extract_values(report_text)
    values_str = "\n".join([f"• {k}: {v}" for k, v in extracted_values.items()]) or "No numeric values could be automatically extracted."

    llm = _get_llm()
    if llm is None:
        return {
            "summary": "AI analysis is currently unavailable. Basic values extracted from report are shown below.",
            "problems": ["AI service temporarily unavailable."],
            "recommendations": ["Please consult a doctor for proper interpretation."],
            "diet_lifestyle": ["Eat a balanced diet.", "Stay hydrated.", "Get adequate sleep."],
            "when_to_see_doctor": "If you feel unwell or have any symptoms, see a doctor immediately.",
            "values_found": extracted_values,
            "raw_response": ""
        }

    prompt = f"""You are a friendly village health assistant. Explain the medical report in VERY SIMPLE language that a 10th-class student or rural patient can understand.

NORMAL RANGES FOR REFERENCE:
{NORMAL_RANGES}

EXTRACTED VALUES FROM REPORT:
{values_str}

FULL REPORT TEXT:
\"\"\"{report_text[:4000]}\"\"\"

INSTRUCTIONS:
1. Use simple words. Avoid medical jargon. If you must use a medical word, explain it in brackets.
2. For EVERY abnormal value, say clearly: "Your [test] is [high/low]. Normal range is [X-Y]."
3. Tell what food to EAT MORE and what to AVOID for each problem.
4. Give 2-3 home remedies if safe.
5. NEVER diagnose a disease. Only explain what the numbers mean.
6. If report is normal, say clearly: "Your report looks mostly normal."

OUTPUT FORMAT (follow exactly):

REMEMBER:
- SUMMARY must be 2-3 sentences. Do not leave it empty.
- List EVERY problem with exact numbers from the report.
- WHAT TO DO must have at least 3 bullet points.
- DIET must have Eat/Avoid/Lifestyle tips.
- WHEN TO SEE DOCTOR must be specific.
SUMMARY:
[2-3 simple sentences about overall report]

PROBLEMS FOUND:
- [Problem 1: e.g., Your BP is 140/90. Normal is less than 120/80. This is slightly high.]
- [Problem 2: e.g., Your fasting sugar is 110. Normal is 70-100. This is borderline high.]
- [If all normal: "No major problems found. Your report looks good."]

WHAT TO DO:
- [Action 1: e.g., Reduce salt in food. Avoid pickles and papad.]
- [Action 2: e.g., Walk 30 minutes daily.]
- [Action 3: e.g., Take medicines on time if doctor prescribed.]

DIET & LIFESTYLE:
- [Eat: e.g., Eat more green vegetables, dal, and fruits.]
- [Avoid: e.g., Avoid oily food, sweets, and cold drinks.]
- [Lifestyle: e.g., Sleep 7-8 hours. Do not take stress.]

WHEN TO SEE DOCTOR:
[If report is normal: "Routine checkup is fine. See doctor if you feel any symptoms."]
[If abnormal: "Please show this report to a doctor within 1 week. If you have chest pain, severe headache, or difficulty breathing, go immediately."]

ANSWER:"""

    try:
        response = llm.generate(prompt)
    except Exception as e:
        print(f"[ReportAnalyzer] LLM error: {e}")
        return {
            "summary": "Could not analyze with AI. Values found in report are shown below.",
            "problems": [f"AI analysis failed: {str(e)}"],
            "recommendations": ["Please consult a doctor with your report."],
            "diet_lifestyle": ["Maintain healthy diet.", "Exercise regularly."],
            "when_to_see_doctor": "Consult a doctor for proper report interpretation.",
            "values_found": extracted_values,
            "raw_response": ""
        }

    parsed = parse_sections(response)
    parsed["values_found"] = extracted_values
    parsed["raw_response"] = response
    return parsed


def parse_sections(text):
    """Parse LLM response into structured sections."""
    sections = {
        "summary": "",
        "problems": [],
        "recommendations": [],
        "diet_lifestyle": [],
        "when_to_see_doctor": "",
        "raw_response": text
    }
    
    current_key = None
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        upper = line.upper()
        
        # Detect section headers
        if "SUMMARY" in upper and len(upper) < 30:
            current_key = "summary"
            continue
        elif "PROBLEM" in upper and len(upper) < 40:
            current_key = "problems"
            continue
        elif ("WHAT TO DO" in upper or "RECOMMENDATION" in upper or "ACTION" in upper) and len(upper) < 40:
            current_key = "recommendations"
            continue
        elif ("DIET" in upper or "LIFESTYLE" in upper or "FOOD" in upper) and len(upper) < 40:
            current_key = "diet_lifestyle"
            continue
        elif ("WHEN TO SEE DOCTOR" in upper or "DOCTOR" in upper or "URGENT" in upper) and len(upper) < 50:
            current_key = "when_to_see_doctor"
            continue
        elif "IMPORTANT NOTE" in upper:
            current_key = "important_note"
            continue
        
        # Content lines
        if current_key == "summary":
            sections["summary"] += line + " "
        elif current_key in ("problems", "recommendations", "diet_lifestyle"):
            # Bullet points, numbers, or plain text
            if line.startswith('-') or line.startswith('•') or re.match(r'^\d+[\.\)]', line):
                clean = re.sub(r'^[-•\d\.\)\s]+', '', line).strip()
                if clean:
                    sections[current_key].append(clean)
            elif len(line) > 10 and current_key != "problems":
                # For recommendations/diet, also accept plain sentences if no bullets
                sections[current_key].append(line)
        elif current_key == "when_to_see_doctor":
            sections["when_to_see_doctor"] += line + " "
    
    sections["summary"] = sections["summary"].strip()
    sections["when_to_see_doctor"] = sections["when_to_see_doctor"].strip()
    
    # Fallback: if summary is empty, use first 2-3 sentences of raw response
    if not sections["summary"]:
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        sections["summary"] = " ".join(sentences[:2]) if sentences else "Report analysis completed."
    
    return sections


def get_structured_analysis(report_text, language="en"):
    """Full pipeline: clean → analyze (English) → translate if needed."""
    cleaned = clean_text(report_text)
    analysis = analyze_report(cleaned)
    
    # ═══ TRANSLATE TO HINDI/OTHER LANGUAGE ═══
    if language != "en" and TRANSLATION_OK:
        try:
            # Translate string fields
            for key in ["summary", "when_to_see_doctor", "raw_response"]:
                if analysis.get(key) and isinstance(analysis[key], str):
                    analysis[key] = translate_text(analysis[key], target_lang=language)
            
            # Translate list fields
            for key in ["problems", "recommendations", "diet_lifestyle"]:
                if analysis.get(key) and isinstance(analysis[key], list):
                    translated = []
                    for item in analysis[key]:
                        if isinstance(item, str) and item.strip():
                            translated.append(translate_text(item, target_lang=language))
                        else:
                            translated.append(item)
                    analysis[key] = translated
                    
        except Exception as e:
            print(f"[ReportAnalyzer] Translation failed: {e}")
            # Keep English as fallback
    
    analysis["language"] = language
    return analysis

# ═════════════════════════════════════════════════════════════════==
# Quick test
# ═════════════════════════════════════════════════════════════════==

if __name__ == "__main__":
    sample = """
    Patient: Ram Singh
    BP: 145/92 mmHg
    Fasting Blood Sugar: 142 mg/dL
    Hemoglobin: 10.2 g/dL
    TLC: 12,500 /cmm
    """
    result = get_structured_analysis(sample)
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))