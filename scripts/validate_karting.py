import re

# Validation Configuration
VALID_CATEGORIES = [
    'Go-kart track', 
    'Amusement center', 
    'Car racing track', 
    'Theme park', 
    'Sports complex',
    'Indoor playground',
    'Event venue',
    'Karting',     # Internal category
    'SIM Racing'   # Internal category
]

INVALID_KEYWORDS = [
    'shop', 'store', 'boutique', 'hotel', 'diner', 
    'cafe', 'mall', 'hospital', 'school', 'church', 'supermarket',
    'garage', 'repair', 'car wash', 'parking', 'magasin', 'boutique', 'hôtel', 'restaurant',
    'motocross', 'moto', 'bike', 'bicycle', 'golf', 'tennis', 'football', 'soccer', 'gym', 'pool', 'dance'
]

REQUIRED_KEYWORDS = [
    'kart', 'circuit', 'racing', 'track', 'bahn', 'baan', 'piste', 'sim', 'planet', 'f1', 'grand prix', 'karting',
    'speedpark', 'loisirs', 'multisport', 'unlimited'
]

def is_valid_karting(name, category, snippet=""):
    """
    Strict validation to ensure the location is karting-related.
    Uses regex word boundaries to avoid partial matches (e.g., 'mall' in 'Mallory').
    """
    if not name or str(name).lower() == 'nan':
        return False
        
    name_low = str(name).lower()
    cat_low = str(category).lower()
    snippet_low = str(snippet).lower()
    
    # 1. Exclusion Check (High Confidence)
    # We exclude if an invalid keyword is present (as a whole word) AND 'kart' is NOT present.
    has_invalid_name = any(re.search(rf'\b{re.escape(kw)}\b', name_low) for kw in INVALID_KEYWORDS)
    if has_invalid_name:
        if not re.search(rf'\bkart', name_low): # Allowing 'karting', 'karts', etc.
            return False
            
    # 2. Internal Category Pass
    # If it's already labeled as Karting or SIM Racing, it's likely valid unless trash name.
    if cat_low in ['karting', 'sim racing']:
        return True

    # 3. Category Check
    is_valid_category = any(cat in cat_low for cat in [c.lower() for c in VALID_CATEGORIES])
    
    # 4. Keyword Check (Name or Snippet)
    # For required keywords, we allow partial matches (e.g., "Speedkart", "BattleKart")
    has_required_kw = any(re.search(re.escape(kw), name_low) for kw in REQUIRED_KEYWORDS) or \
                      any(re.search(re.escape(kw), snippet_low) for kw in REQUIRED_KEYWORDS)
    
    # 5. Final Logic
    if has_required_kw:
        return True
        
    if is_valid_category:
        return True
        
    return False

if __name__ == "__main__":
    # Test cases
    print(f"Spa-Francorchamps (Car racing track): {is_valid_karting('Spa-Francorchamps', 'Car racing track')}")
    print(f"McDonald's (Restaurant): {is_valid_karting('McDonalds', 'Restaurant')}")
    print(f"TeamSport London (Go-kart track): {is_valid_karting('TeamSport London', 'Go-kart track')}")
    print(f"Karts & Parts (Shop): {is_valid_karting('Karts & Parts', 'Bicycle Shop')}") # Should fail if just shop
    print(f"Bunnings (Hardware Store): {is_valid_karting('Bunnings', 'Hardware Store')}")
