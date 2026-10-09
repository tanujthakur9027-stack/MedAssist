"""
Parse MedlinePlus XML → data/health_topics.json
Strips HTML tags + Filters English only
"""

import xml.etree.ElementTree as ET
import json
import os
import re
import html

XML_FILE = "data/mplus_topics_2026-07-24.xml"
OUTPUT = "data/health_topics.json"

def strip_html(text):
    """Remove HTML tags and decode HTML entities."""
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Decode HTML entities: &amp; → &, &lt; → <, etc.
    text = html.unescape(text)
    # Clean extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_english_topic(topic):
    """Check if topic is English (not Spanish)."""
    # Check language attribute
    lang = topic.get("language", "").lower()
    if lang and lang != "english":
        return False
    
    # Check URL for spanish
    url = topic.get("url", "").lower()
    if "spanish" in url or "espanol" in url:
        return False
    
    # Check title for common Spanish indicators
    title = topic.get("title", "").lower()
    spanish_indicators = ["en español", "spanish", "versión en español"]
    if any(ind in title for ind in spanish_indicators):
        return False
    
    return True

def parse():
    if not os.path.exists(XML_FILE):
        print(f"❌ {XML_FILE} not found!")
        return
    
    print("Parsing XML (HTML strip + English only)...")
    tree = ET.parse(XML_FILE)
    root = tree.getroot()
    
    topics = []
    skipped_spanish = 0
    skipped_empty = 0
    
    for topic in root.findall("health-topic"):
        # Skip non-English topics
        if not is_english_topic(topic):
            skipped_spanish += 1
            continue
        
        title = (topic.get("title") or "").strip()
        if not title:
            skipped_empty += 1
            continue
        
        data = {
            "title": title,
            "url": (topic.get("url") or "").strip(),
            "summary": "",
            "also_called": [],
            "sections": [],
            "groups": []
        }
        
        # Full summary with HTML stripped
        s = topic.find("full-summary")
        if s is not None and s.text:
            data["summary"] = strip_html(s.text)
        
        # Also called
        for a in topic.findall("also-called"):
            if a.text: 
                data["also_called"].append(strip_html(a.text))
        
        # Sections with HTML stripped
        for sec in topic.findall("section"):
            c = sec.find("content")
            content = ""
            if c is not None and c.text:
                content = strip_html(c.text)
            
            data["sections"].append({
                "title": strip_html(sec.get("title", "")),
                "content": content
            })
        
        # Groups
        for g in topic.findall("group"):
            if g.text: 
                data["groups"].append(strip_html(g.text))
        
        topics.append(data)
    
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump({"count": len(topics), "topics": topics}, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Done! {len(topics)} English topics saved to {OUTPUT}")
    print(f"   Skipped Spanish: {skipped_spanish}")
    print(f"   Skipped empty: {skipped_empty}")

if __name__ == "__main__":
    parse()