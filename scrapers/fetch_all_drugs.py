"""
Fetch ALL ~13,500 drugs from openFDA API.
Resumable: If stopped/crashed, run again — continues from where it left off.
"""

import requests
import json
import time
import os

OUTPUT = "data/fda_drugs_bulk.jsonl"
BASE_URL = "https://api.fda.gov/drug/label.json"
TARGET = 13500   # GitHub owner claimed 13,511
BATCH = 1000
TIMEOUT = 120    # 2 minute timeout 
MAX_RETRIES = 3  


def get_existing_count():
    """Count already fetched lines (for resume)."""
    if not os.path.exists(OUTPUT):
        return 0
    count = 0
    with open(OUTPUT, "r", encoding="utf-8") as f:
        for _ in f:
            count += 1
    return count


def fetch_drugs():
    existing = get_existing_count()
    skip = existing
    total_written = existing
    
    print(f"{'='*60}")
    print(f"🚀 Fetching drugs from openFDA...")
    if existing > 0:
        print(f"♻️  Resuming from {existing} existing drugs (skip={skip})")
    print(f"🎯 Target: {TARGET} drugs")
    print(f"{'='*60}")
    
    mode = "a" if existing > 0 else "w"
    
    with open(OUTPUT, mode, encoding="utf-8") as f:
        while skip < TARGET:
            url = f"{BASE_URL}?limit={BATCH}&skip={skip}"
            print(f"\n[Skip {skip}] Fetching {BATCH} drugs...")
            
            success = False
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    r = requests.get(url, timeout=TIMEOUT)
                    
                    if r.status_code == 200:
                        data = r.json()
                        results = data.get("results", [])
                        
                        if not results:
                            print("✅ No more results from API. All drugs fetched!")
                            success = True
                            break
                        
                        for drug in results:
                            f.write(json.dumps(drug, ensure_ascii=False) + "\n")
                            total_written += 1
                        
                        print(f"   ✓ Got {len(results)}. Total: {total_written}")
                        skip += len(results)
                        success = True
                        break
                        
                    elif r.status_code == 429:
                        print(f"   ⚠️ Rate limited (attempt {attempt}). Waiting 10 sec...")
                        time.sleep(10)
                        continue
                    else:
                        print(f"   ❌ Error {r.status_code}: {r.text[:100]}")
                        break
                        
                except requests.exceptions.Timeout:
                    print(f"   ⏱️ Timeout (attempt {attempt}/{MAX_RETRIES}). Retrying in 5s...")
                    time.sleep(5)
                    continue
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    break
            
            if not success:
                print("\n❌ Failed after retries. Run this script again to resume!")
                break
            
            time.sleep(1.0)  # Rate limit respect
    
    print(f"\n{'='*60}")
    print(f"✅ Done! Total drugs saved: {total_written}")
    print(f"📁 File: {OUTPUT}")
    print(f"{'='*60}")


if __name__ == "__main__":
    fetch_drugs()