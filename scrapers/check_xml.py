"""Check XML structure - run this first"""
import xml.etree.ElementTree as ET

tree = ET.parse("data/mplus_topics_2026-07-24.xml")
root = tree.getroot()

print("Root tag:", root.tag)
print("Total children:", len(root))

# Check namespace
ns = None
if root.tag.startswith('{'):
    ns = root.tag.split('}')[0].strip('{')
    print("Namespace detected:", ns)

# Count topics by iteration (100% accurate)
count = 0
for elem in root.iter():
    tag = elem.tag.split('}')[-1] if elem.tag.startswith('{') else elem.tag
    if tag == 'health-topic':
        count += 1

print(f"\n✅ ACTUAL TOTAL TOPICS IN XML: {count}")
print("If this shows 13000+, name issue in parser.")