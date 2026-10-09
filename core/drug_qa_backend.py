"""
Drug QA Backend — Natural Language Drug Search
Searches FDA drug data by condition, symptoms, or questions.
"""

import json
import os
import re
from typing import List, Dict, Optional

import requests


class DrugQABackend:
    def __init__(self, data_path=None):
        self.drugs = []
        self.last_error = None
        self._api_cache = {}
        self._load_data(data_path)

    def _load_data(self, path=None):
        if path is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            possible_paths = [
                os.path.join(base, "data", "fda_drugs_bulk.jsonl"),
                os.path.join(base, "data", "processed", "fda_drugs_bulk.jsonl"),
                os.path.join(base, "fda_drugs_bulk.jsonl"),
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    path = p
                    break

        if not path or not os.path.exists(path):
            print("[DrugQA] WARNING: fda_drugs_bulk.jsonl not found!")
            return

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    self.drugs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        print(f"[DrugQA] Loaded {len(self.drugs)} drugs from {path}")

    def _normalize(self, text):
        if not text:
            return ""
        return str(text).lower()

    def _get_name(self, drug: dict) -> str:
        """Bulletproof name extraction."""
        for key in ["name", "brand_name", "generic_name", "drug_name", "product_name"]:
            val = drug.get(key)
            if val and str(val).strip():
                s = str(val).strip()
                if s.lower() not in ["none", "null", "nan", ""]:
                    return s
        
        openfda = drug.get("openfda", {}) or {}
        for key in ["brand_name", "generic_name", "substance_name", "manufacturer_name"]:
            val = openfda.get(key)
            if isinstance(val, list):
                for item in val:
                    if item and str(item).strip():
                        s = str(item).strip()
                        if s.lower() not in ["none", "null", "nan", ""]:
                            return s
            elif isinstance(val, str) and val.strip():
                s = val.strip()
                if s.lower() not in ["none", "null", "nan", ""]:
                    return s
        
        return "Unknown Drug"

    def _get_all_text(self, drug: dict) -> str:
        """Extract ALL searchable text."""
        parts = []
        
        for key in ["name", "brand_name", "generic_name", "drug_name", "active_ingredient", "purpose", "description"]:
            if drug.get(key):
                parts.append(str(drug.get(key)))
        
        openfda = drug.get("openfda", {}) or {}
        for key in ["brand_name", "generic_name", "substance_name", "manufacturer_name"]:
            val = openfda.get(key)
            if isinstance(val, list):
                parts.extend(str(v) for v in val if v)
            elif val:
                parts.append(str(val))
        
        for key in ["indications_and_usage", "uses", "warnings", "warnings_and_cautions", 
                    "dosage_and_administration", "dosage", "description", "precautions"]:
            if drug.get(key):
                parts.append(str(drug.get(key)))
        
        return " ".join(parts).lower()

    def _get_indications_text(self, drug: dict) -> str:
        """Get just indications text for focused matching."""
        ind = (
            str(drug.get("indications_and_usage", "")) + " " +
            str(drug.get("purpose", "")) + " " +
            str(drug.get("uses", "")) + " " +
            str(drug.get("description", ""))
        )
        return ind.lower()

    def search(self, query: str, top_n: int = 10) -> List[Dict]:
        if not query or not query.strip():
            return []

        q = self._normalize(query)
        
        # Known drug classes for direct matching
        antihypertensives = ["losartan", "olmesartan", "lisinopril", "amlodipine", 
                            "hydrochlorothiazide", "valsartan", "irbesartan", 
                            "telmisartan", "prazosin", "doxazosin", "atenolol",
                            "metoprolol", "carvedilol", "nebivolol", "benazepril",
                            "enalapril", "quinapril", "ramipril", "captopril"]
        
        antidiabetics = ["metformin", "glipizide", "glyburide", "sitagliptin",
                        "linagliptin", "empagliflozin", "dapagliflozin",
                        "liraglutide", "insulin", "glimepiride", "pioglitazone"]
        
        scored = []

        for drug in self.drugs:
            name = self._get_name(drug).lower()
            
            # Skip cosmetics
            skip = ["sunscreen", "cosmetic", "makeup", "lipstick", "shampoo", 
                   "soap", "moisturizer", "spf", "cleanser", "fragrance"]
            if any(s in name for s in skip):
                continue

            # Get all text
            all_text = self._get_all_text(drug)
            
            score = 0.0

            # Direct keyword match
            if q in all_text:
                score += 50

            # Known drug class boost
            if "hypertension" in q or "blood pressure" in q:
                for drug_name in antihypertensives:
                    if drug_name in name:
                        score += 100  # Massive boost for known antihypertensives
            
            if "diabetes" in q or "sugar" in q:
                for drug_name in antidiabetics:
                    if drug_name in name:
                        score += 100

            # Word matching
            q_words = set(q.split())
            text_words = set(all_text.split())
            score += len(q_words & text_words) * 5

            # Name match
            if q in name:
                score += 30

            if score > 0:
                scored.append((score, drug))

        scored.sort(key=lambda x: x[0], reverse=True)
        
        # DEBUG
        print(f"[DrugQA] Query: '{q}' | Matches: {len(scored)} | Top 5 scores: {[s[0] for s in scored[:5]]}")
        print(f"[DrugQA] Top 5 names: {[self._get_name(s[1]) for s in scored[:5]]}")

        if scored:
            self.last_error = None
            return [x[1] for x in scored[:top_n]]
        return self._search_openfda(query, top_n)

    def _search_openfda(self, query: str, top_n: int) -> List[Dict]:
        normalized = re.sub(r"[^a-z0-9 -]", " ", query.lower())
        normalized = " ".join(normalized.split())
        if not normalized or len(normalized) > 80:
            return []

        stop_words = {
            "a", "an", "can", "for", "help", "i", "is", "me", "medicine",
            "medicines", "medication", "medications", "my", "of", "should",
            "take", "the", "to", "treat", "treatment", "used", "what", "which",
            "with",
        }
        search_terms = [term for term in normalized.split() if term not in stop_words]
        if search_terms:
            normalized = " ".join(search_terms)

        aliases = {"paracetamol": "acetaminophen"}
        normalized = aliases.get(normalized, normalized)
        if normalized in self._api_cache:
            return self._api_cache[normalized][:top_n]

        fields = (
            "openfda.generic_name",
            "openfda.brand_name",
            "openfda.substance_name",
            "indications_and_usage",
            "purpose",
        )
        search = " OR ".join(f'{field}:"{normalized}"' for field in fields)
        try:
            response = requests.get(
                "https://api.fda.gov/drug/label.json",
                params={"search": search, "limit": top_n},
                timeout=12,
            )
            if response.status_code == 404:
                self.last_error = None
                self._api_cache[normalized] = []
                return []
            response.raise_for_status()
            results = response.json().get("results", [])
            self.last_error = None
            self._api_cache[normalized] = results
            return results
        except (requests.RequestException, ValueError) as exc:
            self.last_error = str(exc)
            print(f"[DrugQA] OpenFDA request failed: {exc}")
            return []

    def get_by_name(self, name: str) -> Optional[Dict]:
        if not name:
            return None
        name_lower = name.lower().strip()
        for drug in self.drugs:
            d_name = self._get_name(drug)
            if d_name and (name_lower in d_name.lower() or d_name.lower() in name_lower):
                return drug
        results = self._search_openfda(name, 1)
        return results[0] if results else None