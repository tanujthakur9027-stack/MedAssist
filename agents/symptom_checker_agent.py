"""
Symptom Checker Agent — Predicts diseases from symptoms with confidence scores
"""

import os
import json
import re
from typing import List, Dict, Tuple
from difflib import get_close_matches

# LLM
try:
    from core.llm import LLMClient
    LLM_OK = True
except Exception as e:
    LLM_OK = False
    print(f"[SymptomChecker] LLM not available: {e}")

# Translation
try:
    from agents.translation_agent import translate_text as agent_translate
    TRANSLATION_OK = True
except Exception as e:
    TRANSLATION_OK = False
    print(f"[SymptomChecker] Translation not available: {e}")
    def agent_translate(text, target_lang="en"):
        return text


class SymptomCheckerAgent:
    def __init__(self):
        self.disease_db = self._load_database()
        self.symptom_aliases = self._build_symptom_aliases()
        self.llm = LLMClient() if LLM_OK else None

    def _load_database(self) -> Dict:
        """Load disease-symptom database."""
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "symptom_disease_db.json"
        )
        if os.path.exists(db_path):
            with open(db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return self._get_default_database()

    def _get_default_database(self) -> Dict:
        return {
            "Malaria": {
                "symptoms": ["fever", "chills", "sweating", "headache", "nausea", "vomiting", "body ache", "fatigue"],
                "urgency": "high", "duration_hint": "7-14 days",
                "recommended_tests": ["Blood Smear Test", "Rapid Diagnostic Test (RDT)", "Complete Blood Count (CBC)"]
            },
            "Dengue": {
                "symptoms": ["fever", "severe headache", "pain behind eyes", "joint pain", "muscle pain", "rash", "nausea", "vomiting"],
                "urgency": "high", "duration_hint": "2-7 days",
                "recommended_tests": ["Dengue NS1 Antigen Test", "IgG/IgM Antibody Test", "Complete Blood Count (CBC)", "Platelet Count"]
            },
            "Typhoid": {
                "symptoms": ["fever", "headache", "abdominal pain", "constipation", "diarrhea", "weakness", "loss of appetite", "rash"],
                "urgency": "high", "duration_hint": "7-14 days",
                "recommended_tests": ["Widal Test", "Typhidot Test", "Blood Culture", "Stool Culture"]
            },
            "Pneumonia": {
                "symptoms": ["cough", "fever", "chills", "difficulty breathing", "chest pain", "fatigue", "sweating", "loss of appetite"],
                "urgency": "high", "duration_hint": "1-3 weeks",
                "recommended_tests": ["Chest X-Ray", "Sputum Culture", "Pulse Oximetry", "Complete Blood Count (CBC)"]
            },
            "COVID-19": {
                "symptoms": ["fever", "cough", "cold", "loss of taste", "loss of smell", "sore throat", "body ache", "fatigue"],
                "urgency": "high", "duration_hint": "7-14 days",
                "recommended_tests": ["RT-PCR Test", "Rapid Antigen Test", "Chest CT Scan", "C-Reactive Protein (CRP)"]
            },
            "Common Cold": {
                "symptoms": ["cough", "cold", "sneezing", "runny nose", "sore throat", "mild fever", "headache", "fatigue"],
                "urgency": "low", "duration_hint": "3-7 days",
                "recommended_tests": ["No specific test needed", "Physical examination"]
            },
            "Influenza (Flu)": {
                "symptoms": ["fever", "cough", "sore throat", "runny nose", "body ache", "headache", "chills", "fatigue", "vomiting"],
                "urgency": "medium", "duration_hint": "5-7 days",
                "recommended_tests": ["Rapid Influenza Diagnostic Test (RIDT)", "RT-PCR for Influenza", "Chest X-Ray (if complications)"]
            },
            "Diabetes": {
                "symptoms": ["frequent urination", "excessive thirst", "unexplained weight loss", "fatigue", "blurred vision", "slow healing", "frequent infections"],
                "urgency": "medium", "duration_hint": "chronic",
                "recommended_tests": ["Fasting Blood Sugar", "HbA1c Test", "Oral Glucose Tolerance Test (OGTT)", "Urine Test"]
            },
            "Hypertension": {
                "symptoms": ["headache", "dizziness", "shortness of breath", "chest pain", "visual changes", "nosebleed"],
                "urgency": "medium", "duration_hint": "chronic",
                "recommended_tests": ["Blood Pressure Monitoring", "ECG", "Lipid Profile", "Kidney Function Test"]
            },
            "Appendicitis": {
                "symptoms": ["stomach pain", "nausea", "vomiting", "fever", "loss of appetite", "swelling abdomen"],
                "urgency": "high", "duration_hint": "emergency",
                "recommended_tests": ["Ultrasound", "CT Scan", "Complete Blood Count (CBC)", "Urine Test"]
            },
            "Food Poisoning": {
                "symptoms": ["vomiting", "diarrhea", "stomach pain", "nausea", "fever", "weakness"],
                "urgency": "medium", "duration_hint": "1-3 days",
                "recommended_tests": ["Stool Culture", "Blood Test", "Physical Examination"]
            },
            "Urinary Tract Infection": {
                "symptoms": ["burning urination", "frequent urination", "lower abdominal pain", "fever", "cloudy urine"],
                "urgency": "medium", "duration_hint": "3-7 days",
                "recommended_tests": ["Urine Analysis", "Urine Culture", "Ultrasound (if recurrent)"]
            },
            "Tuberculosis": {
                "symptoms": ["cough", "coughing blood", "chest pain", "fever", "night sweats", "weight loss", "fatigue"],
                "urgency": "high", "duration_hint": "weeks to months",
                "recommended_tests": ["Chest X-Ray", "Sputum AFB Smear", "GeneXpert MTB/RIF", "Mantoux Test (TB Skin Test)"]
            },
            "Jaundice": {
                "symptoms": ["yellow skin", "yellow eyes", "dark urine", "pale stool", "abdominal pain", "itching", "nausea", "fever"],
                "urgency": "high", "duration_hint": "2-8 weeks",
                "recommended_tests": ["Liver Function Test (LFT)", "Bilirubin Test", "Hepatitis B Surface Antigen (HBsAg)", "Ultrasound"]
            },
            "Hepatitis": {
                "symptoms": ["jaundice", "yellow eyes", "dark urine", "abdominal pain", "nausea", "vomiting", "loss of appetite", "fever"],
                "urgency": "high", "duration_hint": "2-4 weeks",
                "recommended_tests": ["Liver Function Test (LFT)", "Hepatitis Panel (A, B, C)", "Ultrasound", "PT/INR"]
            },
            "Gastroenteritis": {
                "symptoms": ["diarrhea", "vomiting", "stomach pain", "nausea", "fever", "headache"],
                "urgency": "medium", "duration_hint": "1-3 days",
                "recommended_tests": ["Stool Routine Examination", "Stool Culture", "Complete Blood Count (CBC)"]
            },
            "Chickenpox": {
                "symptoms": ["itchy rash", "fluid filled blisters", "fever", "fatigue", "loss of appetite"],
                "urgency": "low", "duration_hint": "5-10 days",
                "recommended_tests": ["Physical Examination", "PCR Test (if needed)", "Tzanck Smear"]
            },
            "Measles": {
                "symptoms": ["fever", "dry cough", "runny nose", "red eyes", "rash", "sore throat"],
                "urgency": "medium", "duration_hint": "7-10 days",
                "recommended_tests": ["Physical Examination", "Measles IgM Antibody Test", "Complete Blood Count (CBC)"]
            },
            "Migraine": {
                "symptoms": ["severe headache", "nausea", "vomiting", "sensitivity to light", "sensitivity to sound"],
                "urgency": "low", "duration_hint": "4-72 hours",
                "recommended_tests": ["CT Scan or MRI (to rule out other causes)", "Physical Examination"]
            },
            "Anemia": {
                "symptoms": ["fatigue", "weakness", "pale skin", "shortness of breath", "dizziness", "cold hands"],
                "urgency": "medium", "duration_hint": "varies",
                "recommended_tests": ["Complete Blood Count (CBC)", "Hemoglobin Test", "Iron Studies", "Vitamin B12 Test"]
            },
            "Asthma": {
                "symptoms": ["shortness of breath", "chest tightness", "wheezing", "cough", "difficulty breathing"],
                "urgency": "high", "duration_hint": "chronic",
                "recommended_tests": ["Spirometry", "Peak Flow Test", "Chest X-Ray", "Allergy Test"]
            }
        }

    def _build_symptom_aliases(self) -> Dict[str, str]:
        aliases = {
            " feverhigh": "fever", "hot body": "fever", "temperature": "fever",
            "dry cough": "cough", "wet cough": "cough", "persistent cough": "cough",
            "runny nose": "cold", "blocked nose": "cold", "stuffy nose": "cold", "sneezing": "cold",
            "throwing up": "vomiting", "puke": "vomiting", "nausea": "vomiting",
            "stomach ache": "stomach pain", "belly pain": "stomach pain", "tummy pain": "stomach pain",
            "body pain": "body ache", "muscle pain": "body ache", "joint pain": "body ache",
            "head pain": "headache", "throbbing head": "headache",
            "shortness of breath": "difficulty breathing", "breathlessness": "difficulty breathing", "wheezing": "difficulty breathing",
            "tired": "fatigue", "tiredness": "fatigue", "weakness": "fatigue", "no energy": "fatigue",
            "not eating": "loss of appetite", "no hunger": "loss of appetite",
            "painful urination": "burning urination", "pain while peeing": "burning urination",
            "yellow eyes": "jaundice", "yellow skin": "jaundice",
            "skin rash": "itchy rash", "red spots": "itchy rash", "blisters": "itchy rash",
            "loose motion": "diarrhea", "loose stools": "diarrhea",
        }
        return aliases

    def _normalize_symptom(self, symptom: str) -> str:
        symptom = symptom.lower().strip()
        if symptom in self.symptom_aliases:
            return self.symptom_aliases[symptom]
        matches = get_close_matches(symptom, list(self.symptom_aliases.keys()), n=1, cutoff=0.8)
        if matches:
            return self.symptom_aliases[matches[0]]
        return symptom

    def parse_symptoms(self, text: str) -> Tuple[List[str], int]:
        text_lower = text.lower()
        duration = None
        duration_patterns = [
            r'(\d+)\s*(?:day|days|din)', r'(\d+)\s*(?:week|weeks|hafte)',
            r'for\s+(\d+)', r'since\s+(\d+)', r'last\s+(\d+)',
        ]
        for pattern in duration_patterns:
            match = re.search(pattern, text_lower)
            if match:
                duration = int(match.group(1))
                break
        
        common_symptoms = [
            "fever", "cough", "cold", "vomiting", "nausea", "headache", "body ache",
            "stomach pain", "diarrhea", "fatigue", "weakness", "loss of appetite",
            "sore throat", "runny nose", "difficulty breathing", "chest pain",
            "rash", "itching", "jaundice", "yellow eyes", "chills", "sweating",
            "dizziness", "burning urination", "constipation", "back pain",
            "joint pain", "muscle pain", "blurred vision", "weight loss",
            "swelling", "bleeding", "confusion", "seizures", "fainting"
        ]
        
        found_symptoms = []
        for symptom in common_symptoms:
            if symptom in text_lower:
                found_symptoms.append(symptom)
        
        for alias, standard in self.symptom_aliases.items():
            if alias in text_lower and standard not in found_symptoms:
                found_symptoms.append(standard)
        
        return list(dict.fromkeys(found_symptoms)), duration

    def _calculate_confidence(self, user_symptoms: List[str], disease_symptoms: List[str]) -> float:
        if not disease_symptoms:
            return 0.0
        user_set = set(user_symptoms)
        disease_set = set(disease_symptoms)
        matched = user_set.intersection(disease_set)
        disease_coverage = len(matched) / len(disease_set) if disease_set else 0
        user_coverage = len(matched) / len(user_set) if user_set else 0
        confidence = (disease_coverage * 0.7) + (user_coverage * 0.3)
        if len(matched) >= 3: confidence += 0.05
        if len(matched) >= 5: confidence += 0.05
        return min(confidence * 100, 95.0)

    def predict(self, user_input: str, language="en") -> Dict:
        symptoms, duration = self.parse_symptoms(user_input)
        
        if not symptoms:
            return {
                "type": "error",
                "message": "No recognizable symptoms found. Please describe your symptoms clearly.",
                "predictions": []
            }
        
        emergency_symptoms = ["chest pain", "difficulty breathing", "severe bleeding", 
                             "unconscious", "seizures", "fainting", "blue lips"]
        if any(s in symptoms for s in emergency_symptoms):
            return {
                "type": "emergency",
                "message": "🚨 EMERGENCY: Your symptoms require immediate medical attention. Please call emergency services or go to the nearest hospital.",
                "predictions": [],
                "symptoms": symptoms
            }
        
        predictions = []
        for disease_name, info in self.disease_db.items():
            score = self._calculate_confidence(symptoms, info["symptoms"])
            if score > 15:
                matched = list(set(symptoms).intersection(set(info["symptoms"])))
                predictions.append({
                    "disease": disease_name,
                    "confidence": round(score, 1),
                    "matched_symptoms": matched,
                    "all_symptoms": info["symptoms"],
                    "urgency": info["urgency"],
                    "duration_hint": info["duration_hint"],
                    "recommended_tests": info.get("recommended_tests", ["Consult a doctor for recommended tests"])
                })
        
        predictions.sort(key=lambda x: x["confidence"], reverse=True)
        top_predictions = predictions[:5]
        
        explanation = self._generate_explanation(symptoms, top_predictions, duration)
        
        result = {
            "type": "success",
            "symptoms": symptoms,
            "duration": duration,
            "predictions": top_predictions,
            "explanation": explanation,
            "message": f"Found {len(top_predictions)} possible condition(s) based on your symptoms."
        }
        
        # ═══ TRANSLATE IF NOT ENGLISH ═══
        if language != "en" and TRANSLATION_OK:
            try:
                if result.get("explanation"):
                    result["explanation"] = agent_translate(result["explanation"], target_lang=language)
                if result.get("message"):
                    result["message"] = agent_translate(result["message"], target_lang=language)
                for pred in result.get("predictions", []):
                    if pred.get("disease"):
                        pred["disease"] = agent_translate(pred["disease"], target_lang=language)
            except Exception as e:
                print(f"[SymptomChecker] Translation failed: {e}")
        
        result["language"] = language
        return result

    def _generate_explanation(self, symptoms: List[str], predictions: List[Dict], duration: int = None) -> str:
        if not self.llm or len(predictions) == 0:
            return self._fallback_explanation(predictions)
        try:
            prompt = f"""You are a friendly health assistant. A user has these symptoms: {', '.join(symptoms)}.
Duration: {duration if duration else 'Not specified'} days.
Top predictions:
"""
            for i, p in enumerate(predictions[:3], 1):
                prompt += f"{i}. {p['disease']} ({p['confidence']}% confidence) — matched symptoms: {', '.join(p['matched_symptoms'])}\n"
            prompt += """
Write a brief 3-4 sentence explanation in simple language. Mention:
- Which disease seems most likely and why
- What symptoms matched
- A reminder to see a doctor
Do NOT diagnose. Use cautious language like "may indicate" or "could be related to".
"""
            return self.llm.generate(prompt)
        except Exception as e:
            return self._fallback_explanation(predictions)

    def _fallback_explanation(self, predictions: List[Dict]) -> str:
        if not predictions:
            return "Please consult a doctor for proper evaluation."
        lines = [f"Based on your symptoms, **{predictions[0]['disease']}** seems most likely ({predictions[0]['confidence']}% match)."]
        if len(predictions) > 1:
            lines.append(f"Other possibilities include **{predictions[1]['disease']}** ({predictions[1]['confidence']}%).")
        lines.append(f"Matching symptoms: {', '.join(predictions[0]['matched_symptoms'])}.")
        lines.append("⚠️ This is not a diagnosis. Please consult a doctor for proper evaluation.")
        return " ".join(lines)


def get_symptom_checker():
    return SymptomCheckerAgent()


if __name__ == "__main__":
    agent = SymptomCheckerAgent()
    result = agent.predict("I have fever, cough, cold, vomiting for 3 days")
    import json
    print(json.dumps(result, indent=2))