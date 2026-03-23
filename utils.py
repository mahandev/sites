import re

KNOWN_CITIES = [
    "pune", "mumbai", "nashik", "nagpur", "aurangabad", "thane",
    "kolhapur", "solapur", "satara", "navi mumbai", "vasai", "virar",
    "delhi", "bangalore", "bengaluru", "hyderabad", "chennai",
    "ahmedabad", "surat", "jaipur", "lucknow", "kanpur", "indore",
]

KNOWN_STATES = [
    "maharashtra", "gujarat", "rajasthan", "karnataka", "telangana",
    "tamil nadu", "uttar pradesh", "madhya pradesh", "west bengal", "delhi",
]


def normalize_phone(phone: str) -> str:
    """Return last 10 digits of an Indian phone number."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("91") and len(digits) >= 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) >= 11:
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits


def extract_city(full_address: str) -> str:
    """Extract city name from a comma-separated address string."""
    full_address = full_address or ""
    parts = [p.strip() for p in full_address.split(",") if p.strip()]

    # Pass 1: direct city name match
    for part in parts:
        if any(c in part.lower() for c in KNOWN_CITIES):
            return part.strip()

    # Pass 2: find state, take part immediately before it
    for i, part in enumerate(parts):
        if any(s in part.lower() for s in KNOWN_STATES):
            if i >= 1:
                return parts[i - 1].strip()

    # Pass 3: original fallback
    return parts[-3] if len(parts) >= 3 else (parts[-1] if parts else "")
