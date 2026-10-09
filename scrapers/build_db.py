"""
Merge health_topics.json + fda_drugs_bulk.jsonl → medassist_complete.json
Keeps ALL drugs (no deduplication). Reads .jsonl line-by-line.
"""

import json
import os
import re
import html

HEALTH_FILE = "data/health_topics.json"
DRUGS_FILE = "data/fda_drugs_bulk.jsonl"  # ⬅️ JSON Lines format
OUTPUT = "data/medassist_complete.json"


def strip_html(text):
    if not text or not isinstance(text, str):
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def clean_drug_field(value):
    if isinstance(value, list):
        value = value[0] if value else ""
    if not isinstance(value, str):
        return ""
    cleaned = strip_html(value)
    return cleaned if cleaned and cleaned.lower() != "null" else ""


def build():
    # ===== HEALTH TOPICS =====
    print("Loading health topics...")
    with open(HEALTH_FILE, "r", encoding="utf-8") as f:
        health = json.load(f)["topics"]

    health_topics = {}
    for t in health:
        parts = [t["summary"]] + [f"{s['title']}: {s['content']}" for s in t["sections"] if s["content"]]
        content = "\n\n".join(parts)

        health_topics[t["title"].lower()] = {
            "source": "MedlinePlus XML",
            "results_count": 1,
            "results": [{
                "title": t["title"],
                "FullSummary": content[:2000],
                "snippet": t["summary"][:500],
                "url": t["url"]
            }]
        }

    # ===== DRUGS (ALL 14K from .jsonl) =====
    drugs = {}
    
    if os.path.exists(DRUGS_FILE):
        print(f"Loading drugs from {DRUGS_FILE} (streaming)...")
        count = 0
        
        with open(DRUGS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    result = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                openfda = result.get("openfda", {})
                
                brand = clean_drug_field(openfda.get("brand_name", ""))
                generic = clean_drug_field(openfda.get("generic_name", ""))
                substance = clean_drug_field(openfda.get("substance_name", ""))
                
                # Fallback names
                name = generic or brand or substance
                if not name:
                    spl = result.get("spl_product_data_elements", [""])
                    if isinstance(spl, list) and spl:
                        name = clean_drug_field(spl[0])
                if not name:
                    name = result.get("set_id", f"drug_{count}")[:20]
                
                # UNIQUE KEY: name + count (keeps 200mg, 500mg, etc. separate)
                key = f"{name.lower().strip()}_{count}"
                
                purpose = clean_drug_field(result.get("purpose", ""))
                indications = clean_drug_field(result.get("indications_and_usage", ""))
                warnings = clean_drug_field(result.get("warnings", ""))
                dosage = clean_drug_field(result.get("dosage_and_administration", ""))
                do_not_use = clean_drug_field(result.get("do_not_use", ""))
                stop_use = clean_drug_field(result.get("stop_use", ""))
                
                drugs[key] = {
                    "source": "openFDA",
                    "results_count": 1,
                    "results": [{
                        "brand_name": brand,
                        "generic_name": generic,
                        "substance_name": substance,
                        "purpose": purpose,
                        "indications_and_usage": indications,
                        "warnings": warnings,
                        "dosage_and_administration": dosage,
                        "do_not_use": do_not_use,
                        "stop_use": stop_use
                    }]
                }
                count += 1
                
                if count % 1000 == 0:
                    print(f"  Processed {count} drugs...")
        
        print(f"  Loaded {count} drugs (ALL variants kept)")
    else:
        print(f"❌ {DRUGS_FILE} not found!")

    # ===== MERGE =====
    db = {
        "metadata": {
            "project": "MedAssist",
            "sources": ["MedlinePlus XML", "openFDA Bulk API"],
            "total_health_topics": len(health_topics),
            "total_drugs": len(drugs),
            "total_data_points": len(health_topics) + len(drugs)
        },
        "health_topics": health_topics,
        "drugs": drugs
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"✅ DATABASE READY!")
    print(f"{'='*50}")
    print(f"Health Topics: {len(health_topics)}")
    print(f"Drugs: {len(drugs)}")
    print(f"TOTAL: {len(health_topics) + len(drugs)}")
    print(f"{'='*50}")


if __name__ == "__main__":
    build()