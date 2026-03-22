import re

KNOWN_CITIES = ["pune", "mumbai", "nashik", "nagpur", "aurangabad", "thane"]


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
    for part in full_address.split(","):
        if any(c in part.lower() for c in KNOWN_CITIES):
            return part.strip()
    parts = [p.strip() for p in full_address.split(",") if p.strip()]
    if len(parts) >= 3:
        return parts[-3]
    return parts[-1] if parts else ""
