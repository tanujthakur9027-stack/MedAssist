"""
Drug Info Agent — Natural Language Drug Q&A
Returns clean, notebook-style answers.
"""

import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core"))

try:
    from drug_qa_backend import DrugQABackend
except Exception as e:
    print(f"[DrugAgent] Backend import error: {e}")
    DrugQABackend = None

try:
    from llm import LLMClient
except Exception as e:
    print(f"[DrugAgent] LLM import error: {e}")
    LLMClient = None


class DrugInfoAgent:
    def __init__(self):
        self.backend = DrugQABackend() if DrugQABackend else None
        self.llm = LLMClient() if LLMClient else None

    def is_question(self, text):
        text = text.lower().strip()
        q_words = [
            "what", "which", "how", "best", "medicine", "drug", "treatment",
            "for", "help", "with", "ke liye", "kaunsi", "konsi", "dawai",
            "tablet", "capsule", "syrup", "injection", "can i", "should i",
            "is it safe", "can i take", "compare", "vs", "difference",
            "used for", "benefits of", "side effects of"
        ]
        words = text.split()
        if len(words) > 2:
            for qw in q_words:
                if qw in words:
                    return True
        return False

    def _get_drug_name(self, drug):
        """Bulletproof name extraction — NEVER returns chemical junk."""
        
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
        
        # NEVER use chemical ingredient lists as name
        return "Unknown Drug"

    def _clean_text(self, text):
        """Remove HTML tags and clean FDA text."""
        if not text:
            return ""
        if isinstance(text, list):
            text = " ".join(str(x) for x in text if x)
        text = str(text)
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace("['", "").replace("']", "").replace("[\"", "").replace("\"]", "")
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def answer(self, query):
        query = query.strip()
        if not query:
            return {"type": "error", "message": "Please enter a drug name or question.", "drugs": []}

        if not self.backend:
            return {"type": "error", "message": "Drug database not loaded.", "drugs": []}

        # CASE 1: Direct drug name
        if not self.is_question(query):
            drug = self.backend.get_by_name(query)
            if drug:
                return self._format_direct(drug, query)

        # CASE 2: Natural language question
        results = self.backend.search(query, top_n=10)
        print(f"[DrugAgent] Backend returned {len(results)} drugs")
        
        if not results:
            return {
                "type": "not_found",
                "query": query,
                "drugs": [],
                "message": f"No relevant FDA data found for '{query}'. Try a specific drug name."
            }

        # Build context for LLM (notebook-style)
        context_parts = []
        drug_cards = []
        
        for drug in results:
            name = self._get_drug_name(drug)
            
            # Skip cosmetics ONLY — nothing else
            skip = ["sunscreen", "cosmetic", "makeup", "lipstick", "shampoo", "soap", "moisturizer", "spf", "cleanser", "fragrance"]
            if any(k in name.lower() for k in skip):
                continue

            # Extract text from ANY available field
            all_text = (
                str(drug.get("indications_and_usage", "")) + " " +
                str(drug.get("purpose", "")) + " " +
                str(drug.get("uses", "")) + " " +
                str(drug.get("description", "")) + " " +
                str(drug.get("warnings", "")) + " " +
                str(drug.get("dosage_and_administration", ""))
            )
            indications = self._clean_text(all_text)
            
    
            if not indications or indications == "":
                indications = f"{name} is a medication used for related conditions."

            # For context
            context_parts.append(f"Drug: {name}\nWhat it's used for: {indications[:400]}")
            
            # For cards
            drug_cards.append({
                "name": name,
                "indications": indications[:500] + "..." if len(indications) > 500 else indications,
                "warnings": self._clean_text(drug.get("warnings") or drug.get("warnings_and_cautions") or "")[:300],
                "dosage": self._clean_text(drug.get("dosage_and_administration") or drug.get("dosage") or "")[:300],
                "source": "openFDA"
            })
        
        # DEBUG
        print(f"[DrugAgent] Built {len(drug_cards)} drug cards out of {len(results)} results")
        
        # Ensure at least 5 cards
        if len(drug_cards) < 5 and len(results) > len(drug_cards):
            # Add more from remaining results
            for drug in results[5:]:
                if len(drug_cards) >= 5:
                    break
                name = self._get_drug_name(drug)
                skip = ["sunscreen", "cosmetic", "makeup", "lipstick", "shampoo", "soap", "moisturizer", "spf", "cleanser", "fragrance"]
                if any(k in name.lower() for k in skip):
                    continue
                all_text = (
                    str(drug.get("indications_and_usage", "")) + " " +
                    str(drug.get("purpose", "")) + " " +
                    str(drug.get("uses", "")) + " " +
                    str(drug.get("description", ""))
                )
                indications = self._clean_text(all_text)
                drug_cards.append({
                    "name": name,
                    "indications": indications[:500] + "..." if len(indications) > 500 else indications,
                    "source": "openFDA"
                })

        if not drug_cards:
            return {
                "type": "not_found",
                "query": query,
                "drugs": [],
                "message": f"No relevant medications found for '{query}'."
            }

        context = "\n\n".join(context_parts)

        # Try LLM for nice formatting
        # Try LLM for EXACT notebook-style formatting
        llm_answer = None
        if self.llm:
            try:
                prompt = f"""You are a medication information assistant. Use ONLY the context below. Do not use outside knowledge.

Format your answer EXACTLY like this example:

The following medications are indicated for the treatment of hypertension:

**LOSARTAN POTASSIUM AND HYDROCHLOROTHIAZIDE**
What it's used for: LOSARTAN POTASSIUM AND HYDROCHLOROTHIAZIDE - What it's used for: [brief description from context]

**OLMESARTAN MEDOXOMIL AND AMLODIPINE BESYLATE AND HYDROCHLOROTHIAZIDE**
What it's used for: OLMESARTAN MEDOXOMIL AND AMLODIPINE BESYLATE AND HYDROCHLOROTHIAZIDE - What it's used for: [brief description from context]

For any personal decisions regarding medication, it is always recommended to consult with a doctor or pharmacist.

Now do the same for this query: {query}

CONTEXT:
{context}

Answer:"""
                llm_answer = self.llm.generate(prompt)
            except Exception as e:
                print(f"[DrugAgent] LLM failed: {e}")

        # If LLM fails, build EXACT notebook-style answer manually
        if not llm_answer:
            lines = [f"The following medications are indicated for the treatment of {query}:\n"]
            for card in drug_cards[:5]:
                lines.append(f"**{card['name']}**")
                lines.append(f"What it's used for: {card['name']} - What it's used for: {card['indications'][:300]}\n")
            lines.append("For any personal decisions regarding medication, it is always recommended to consult with a doctor or pharmacist.")
            llm_answer = "\n".join(lines)

        return {
            "type": "qa",
            "query": query,
            "answer": llm_answer,
            "drugs": drug_cards,
            "sources": [{"drug_name": d["name"]} for d in drug_cards],
            "message": f"Found {len(drug_cards)} relevant medication(s).",
            "source": "openFDA (U.S. Food & Drug Administration)"
        }

    def _format_direct(self, drug, query):
        """Format direct drug lookup."""
        name = self._get_drug_name(drug)
        indications = self._clean_text(drug.get("indications_and_usage") or drug.get("purpose") or "Not available.")
        warnings = self._clean_text(drug.get("warnings") or drug.get("warnings_and_cautions") or "Consult doctor before use.")
        dosage = self._clean_text(drug.get("dosage_and_administration") or drug.get("dosage") or "As directed by physician.")

        # Try LLM for nice formatting
        llm_answer = None
        if self.llm:
            try:
                prompt = f"""You are a medication information assistant.
Use ONLY the context below. Provide a brief summary of this drug (3-4 lines).
Include what it's used for and key warnings. End with: "Consult a doctor before taking."

Drug: {name}
Used for: {indications}
Warnings: {warnings}
Dosage: {dosage}

Summary:"""
                llm_answer = self.llm.generate(prompt)
            except Exception as e:
                print(f"[DrugAgent] LLM failed for direct: {e}")

        if not llm_answer:
            llm_answer = f"**{name}**\n\nUsed for: {indications[:300]}\n\nWarnings: {warnings[:300]}\n\nConsult a doctor before taking any medication."

        return {
            "type": "direct",
            "query": query,
            "answer": llm_answer,
            "drugs": [{
                "name": name,
                "indications": indications,
                "warnings": warnings,
                "dosage": dosage,
                "source": "openFDA"
            }],
            "sources": [{"drug_name": name}],
            "message": f"Showing FDA data for {name}.",
            "source": "openFDA"
        }


# Backward compatibility
def get_drug_info(drug_name):
    agent = DrugInfoAgent()
    return agent.answer(drug_name)