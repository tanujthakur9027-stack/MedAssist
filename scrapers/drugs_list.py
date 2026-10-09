"""
Extended list of essential medicines for rural India.
Based on WHO Essential Medicines List + Indian context.
"""

EXTENDED_DRUGS = [
    # Pain & Fever
    "paracetamol",
    "acetaminophen",
    "ibuprofen",
    "aspirin",
    "diclofenac",
    
    # Antibiotics
    "amoxicillin",
    "ciprofloxacin",
    "azithromycin",
    "metronidazole",
    "doxycycline",
    
    # Diabetes
    "metformin",
    "insulin",
    "glibenclamide",
    
    # Blood Pressure
    "amlodipine",
    "atenolol",
    "losartan",
    
    # Vitamins & Supplements
    "vitamin d",
    "vitamin b12",
    "folic acid",
    "iron supplements",
    "zinc",
    "calcium",
    
    # ORS & Digestion
    "ors",
    "omeprazole",
    "ranitidine",
    "domperidone",
    
    # Allergy & Cold
    "cetirizine",
    "chlorpheniramine",
    "salbutamol",
    
    # Skin
    "betamethasone",
    "clotrimazole",
    "calamine",
    
    # Mental Health
    "alprazolam",
    "sertraline",
    
    # Emergency
    "nitroglycerin",
    "epinephrine"
]

print(f"Total drugs to fetch: {len(EXTENDED_DRUGS)}")