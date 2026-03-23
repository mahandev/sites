import json
import json as _json
import os
import re
from datetime import datetime
from html import escape
from urllib.parse import quote

from utils import extract_city


DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

HERO_TITLES = {
    "tax": ("Clarity in", "every filing,", "every year."),
    "ca ": ("Numbers handled.", "growth", "guaranteed."),
    "consultant": ("Expert advice,", "trusted", "every time."),
    "gym": ("Train hard.", "recover smart,", "repeat."),
    "fitness": ("Train hard.", "recover smart,", "repeat."),
    "salon": ("Look your", "absolute", "best."),
    "beauty": ("Look your", "absolute", "best."),
    "restaurant": ("Food made", "with love,", "served fresh."),
    "clinic": ("Your health,", "our priority,", "always."),
    "coaching": ("Unlock your", "true", "potential."),
    "interior": ("Spaces that", "feel like", "you."),
    "caterer": ("Flavours that", "celebrate", "every moment."),
    "photographer": ("Moments that", "last", "forever."),
}
DEFAULT_TITLE = ("Serving", "our community,", "with pride.")

SERVICES_MAP = {
    "tax": [
        ("ITR Filing", "Simple to complex income tax returns for individuals, HUF, and businesses. Fast turnaround, zero errors."),
        ("GST Registration & Filing", "End-to-end GST setup and monthly/quarterly return filing."),
        ("Business Compliance", "Company incorporation, ROC filings, and annual compliance - great for startups."),
        ("Financial Advisory", "Tax planning, investment guidance, and personalised financial consulting."),
        ("CA Consultation", "Direct access to chartered accountants for any financial or legal query."),
    ],
    "consultant": [
        ("Tax Filing", "Accurate and timely filing of income tax returns for all types of assessees."),
        ("Tax Planning", "Strategic tax planning to legally minimise your liability and maximise savings."),
        ("GST Services", "GST registration, monthly return filing, and compliance management."),
        ("Business Advisory", "Financial guidance for startups, SMEs, and growing businesses."),
        ("Document Support", "Complete documentation assistance for all government and financial filings."),
    ],
    "gym": [
        ("Personal Training", "One-on-one sessions tailored to your fitness goals and current level."),
        ("Group Classes", "High-energy group workouts - HIIT, Zumba, yoga, and more."),
        ("Nutrition Guidance", "Diet plans designed around your training regimen and goals."),
        ("Membership Plans", "Flexible monthly and annual plans that fit every budget."),
        ("Cardio & Weights", "Fully equipped floor with modern machines and free weights."),
    ],
    "salon": [
        ("Haircut & Styling", "Expert cuts and styling for men, women, and children."),
        ("Colour & Highlights", "Balayage, ombre, global colour - all techniques available."),
        ("Facial & Skincare", "Rejuvenating facials tailored to your skin type."),
        ("Bridal Packages", "Complete bridal makeup and hair packages for your big day."),
        ("Nail Art", "Manicure, pedicure, and creative nail art services."),
    ],
    "restaurant": [
        ("Dine In", "A warm, welcoming space to enjoy freshly prepared meals."),
        ("Takeaway", "Quick and easy takeaway orders - ready when you are."),
        ("Catering", "Event catering for parties, corporate gatherings, and celebrations."),
        ("Home Delivery", "Hot meals delivered straight to your door."),
        ("Private Dining", "Book a private space for special occasions and events."),
    ],
    "clinic": [
        ("General Consultation", "Expert medical consultation for all common health concerns."),
        ("Diagnostics", "On-site diagnostic tests and health screenings."),
        ("Preventive Care", "Regular health check-ups and preventive care programmes."),
        ("Follow-up Care", "Ongoing support and follow-up consultations for chronic conditions."),
        ("Emergency Care", "Prompt attention for urgent medical needs."),
    ],
    "default": [
        ("Professional Service", "High-quality service delivered by experienced professionals."),
        ("Expert Consultation", "Personalised advice from our team of industry experts."),
        ("Fast Turnaround", "We value your time - quick and reliable delivery, always."),
        ("Affordable Pricing", "Transparent pricing with no hidden charges."),
        ("Customer Support", "Always available to answer your queries and assist you."),
    ],
}

SOCIAL_LABELS = {
    "instagram": "Instagram",
    "facebook": "Facebook",
    "twitter": "X",
    "youtube": "YouTube",
    "whatsapp": "WhatsApp",
    "linkedin": "LinkedIn",
}


# ---------------------------------------------------------------------------
# Groq AI personalisation
# ---------------------------------------------------------------------------

def call_groq(business):
    """Single Groq call returning all personalised content as a dict. Returns None on any failure."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    name = business.get("name") or ""
    category = business.get("category") or ""
    address = business.get("full_address") or business.get("address") or ""
    rating = business.get("rating") or "5.0"
    total_reviews = business.get("total_reviews") or "0"
    service_options = business.get("service_options") or []
    reviews = business.get("reviews") or []

    review_digest = " | ".join(
        r.get("text", "")[:120] for r in reviews[:6] if r.get("text")
    )[:600]

    prompt = f"""You are generating content for a professional business website. Return ONLY a valid JSON object with these exact fields:

{{
  "city": "city name extracted from address",
  "area": "local area or neighborhood from address",
  "hero_title": ["line1 (max 4 words)", "em_line (max 4 words)", "line3 (max 4 words)"],
  "hero_subtitle": "1-2 sentences specific to this business, mention city",
  "about_para_1": "2-3 sentences: who they are, what they do, how long serving",
  "about_para_2": "2-3 sentences: reference specific things from reviews, why customers trust them",
  "services": [{{"name": "service name", "desc": "1-line description"}}],
  "usps": ["usp1 (max 4 words)", "usp2 (max 4 words)", "usp3 (max 4 words)"],
  "faq": [{{"q": "question", "a": "1-2 sentence answer"}}]
}}

Rules:
- services: exactly 5 items. Use real scraped services if provided, else infer from category.
- usps: exactly 3, extract from reviews (e.g. "Same-Day Filing", "Home Visits", "GST Specialist")
- faq: exactly 4 questions relevant to this business type
- hero_title: unique to this business, not generic. Line 2 (em_line) is italicised.
- All text in English. Professional, warm tone. No markdown.

Business data:
Name: {name}
Category: {category}
Address: {address}
Rating: {rating} stars ({total_reviews} reviews)
Scraped services: {", ".join(service_options) if service_options else "none"}
Customer reviews: {review_digest if review_digest else "none available"}"""

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=900,
            timeout=10,
            response_format={"type": "json_object"},
        )
        data = _json.loads(resp.choices[0].message.content)
        required = ["city", "area", "hero_title", "about_para_1", "about_para_2",
                    "services", "usps", "faq"]
        if all(k in data for k in required):
            return data
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Slug / address helpers
# ---------------------------------------------------------------------------

def make_slug(name):
    slug = (name or "").lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug


def extract_phone_digits(phone):
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits


def extract_location(full_address):
    parts = [p.strip() for p in (full_address or "").split(",") if p.strip()]
    area = parts[0] if parts else ""
    city = extract_city(full_address)
    return area, city


def logo_html(name):
    words = (name or "").strip().split()
    if not words:
        return "<span>Business</span>"
    if len(words) == 1:
        return f"<span>{escape(words[0])}</span>"
    return f"<span>{escape(words[0])}</span> {escape(' '.join(words[1:]))}"


def category_short(category):
    mapping = {
        "tax": "Tax Expert",
        "ca ": "CA Firm",
        "consultant": "Tax Consultant",
        "gym": "Fitness Expert",
        "salon": "Beauty Expert",
        "restaurant": "Restaurant",
        "clinic": "Healthcare Provider",
        "coaching": "Education Expert",
        "interior": "Interior Designer",
        "caterer": "Catering Expert",
        "photographer": "Photography Expert",
        "tutor": "Education Expert",
    }
    cat_lower = (category or "").lower()
    for key, val in mapping.items():
        if key in cat_lower:
            return val
    return "Local Expert"


def get_hero_title(category):
    cat_lower = (category or "").lower()
    for key, val in HERO_TITLES.items():
        if key in cat_lower:
            return val
    return DEFAULT_TITLE


def services_title(category):
    cat = (category or "").lower()
    if any(k in cat for k in ["tax", "ca ", "consultant", "account"]):
        return "Comprehensive tax &amp;<br>financial services"
    if any(k in cat for k in ["gym", "fitness", "yoga"]):
        return "Training &amp;<br>wellness services"
    if any(k in cat for k in ["salon", "beauty", "spa"]):
        return "Beauty &amp;<br>grooming services"
    if any(k in cat for k in ["restaurant", "food", "cafe"]):
        return "Food &amp;<br>dining experience"
    if any(k in cat for k in ["clinic", "doctor", "health"]):
        return "Healthcare &amp;<br>wellness services"
    return "Professional<br>services we offer"


def get_services(category):
    cat = (category or "").lower()
    if any(k in cat for k in ["tax", "ca ", "account"]):
        return SERVICES_MAP["tax"]
    if "consultant" in cat:
        return SERVICES_MAP["consultant"]
    if any(k in cat for k in ["gym", "fitness"]):
        return SERVICES_MAP["gym"]
    if any(k in cat for k in ["salon", "beauty"]):
        return SERVICES_MAP["salon"]
    if any(k in cat for k in ["restaurant", "food", "cafe"]):
        return SERVICES_MAP["restaurant"]
    if any(k in cat for k in ["clinic", "doctor", "health"]):
        return SERVICES_MAP["clinic"]
    return SERVICES_MAP["default"]


# ---------------------------------------------------------------------------
# HTML builders
# ---------------------------------------------------------------------------

def build_services_html(category, scraped_services=None):
    if scraped_services:
        services = [(s, "") for s in scraped_services[:5]]
    else:
        services = get_services(category)
    html = ""
    for i, (name, desc) in enumerate(services, 1):
        html += (
            "\n        <div class=\"service-item service-card reveal\">"
            f"\n          <span class=\"service-num service-number\">0{i}</span>"
            "\n          <div>"
            f"\n            <p class=\"service-name\">{escape(name)}</p>"
            + (f"\n            <p class=\"service-desc\">{escape(desc)}</p>" if desc else "")
            + "\n          </div>"
            "\n        </div>"
        )
    return html


def build_services_html_from_ai(services):
    html = ""
    for i, svc in enumerate(services[:5], 1):
        name = escape(svc.get("name") or "")
        desc = escape(svc.get("desc") or "")
        html += (
            f"\n        <div class=\"service-item service-card reveal\">"
            f"\n          <span class=\"service-num service-number\">0{i}</span>"
            f"\n          <div>"
            f"\n            <p class=\"service-name\">{name}</p>"
            + (f"\n            <p class=\"service-desc\">{desc}</p>" if desc else "")
            + "\n          </div>"
            "\n        </div>"
        )
    return html


def build_usps_html(usps):
    if not usps:
        return ""
    items = "".join(f'<span class="usp-chip">{escape(u)}</span>' for u in usps[:3])
    return f'<div class="usp-chips">{items}</div>'


def build_faq_html(faq):
    if not faq:
        return ""
    html = ""
    for item in faq[:4]:
        q = escape(item.get("q") or "")
        a = escape(item.get("a") or "")
        html += (
            f"\n      <div class=\"faq-item\">"
            f"\n        <p class=\"faq-q\">{q}</p>"
            f"\n        <p class=\"faq-a\">{a}</p>"
            f"\n      </div>"
        )
    return html


def build_payments_html(payments):
    if not payments:
        return ""
    items = "".join(f'<span class="pay-badge">{escape(p)}</span>' for p in payments[:6])
    return f'<div class="pay-badges">{items}</div>'


def build_social_html(social_media):
    if not social_media:
        return ""
    links = "".join(
        f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener" class="social-link">'
        f'{SOCIAL_LABELS.get(platform, platform.title())}</a>'
        for platform, url in social_media.items()
    )
    return f'<div class="social-links">{links}</div>' if links else ""


def extract_years(reviews):
    max_years = 1
    for r in reviews:
        posted = r.get("posted", "") or ""
        match = re.search(r"(\d+)\s+year", posted)
        if match:
            max_years = max(max_years, int(match.group(1)))
    return f"{max_years}+"


def build_reviews_html(reviews):
    seen_texts = set()
    unique = []
    for r in reviews:
        text = (r.get("text") or "").strip()
        if text and text not in seen_texts:
            seen_texts.add(text)
            unique.append(r)
        if len(unique) == 3:
            break

    html = ""
    for r in unique:
        text = (r.get("text") or "").strip()
        if len(text) > 220:
            text = text[:217].rstrip() + "..."
        posted = (r.get("posted") or "Recently").strip() or "Recently"
        author = (r.get("author") or "").strip() or "Customer"
        html += (
            "\n        <div class=\"review-card reveal\">"
            "\n          <div class=\"review-quote\">\"</div>"
            f"\n          <p class=\"review-text\">{escape(text)}</p>"
            "\n          <div class=\"review-stars\">★★★★★</div>"
            f"\n          <p class=\"review-meta\">{escape(author)} · Verified Google Review · {escape(posted)}</p>"
            "\n        </div>"
        )

    if not html:
        html = (
            "\n        <div class=\"review-card reveal\">"
            "\n          <div class=\"review-quote\">\"</div>"
            "\n          <p class=\"review-text\">Customers appreciate our quality, responsiveness, and professional service.</p>"
            "\n          <div class=\"review-stars\">★★★★★</div>"
            "\n          <p class=\"review-meta\">Verified Google Review · Recently</p>"
            "\n        </div>"
        )
    return html


def build_hours_html(hours_dict):
    if not hours_dict:
        return "<tr><td colspan='2' style='color:var(--muted)'>Hours not available</td></tr>"
    html = ""
    for day in DAY_ORDER:
        if day not in hours_dict:
            continue
        raw = str(hours_dict[day])
        cleaned = raw.split("\n")[0].strip()
        is_closed = cleaned.lower() == "closed"
        td_class = ' class="closed"' if is_closed else ""
        html += f"<tr><td>{day}</td><td{td_class}>{escape(cleaned)}</td></tr>\n"
    return html or "<tr><td colspan='2' style='color:var(--muted)'>Hours not available</td></tr>"


def build_photos_html(photos, business_name):
    html = ""
    for url in (photos or [])[:12]:
        html += (
            "\n        <div class=\"photo-cell\">"
            f"\n          <img src=\"{escape(url, quote=True)}\" alt=\"{escape(business_name)}\" onerror=\"this.parentElement.style.background='#2a2a28'\">"
            "\n        </div>"
        )
    if not html:
        html = (
            "\n        <div class=\"photo-cell\">"
            f"\n          <img src=\"\" alt=\"{escape(business_name)}\" onerror=\"this.parentElement.style.background='#2a2a28'\">"
            "\n        </div>"
        )
    return html


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_one(business, template_str):
    b = business

    name = b.get("name") or "Local Business"
    category = b.get("category") or "Business"
    full_address = b.get("full_address") or b.get("address") or ""
    phone_raw = b.get("phone") or ""
    phone_display = phone_raw
    rating = b.get("rating") or "5.0"
    total_reviews = b.get("total_reviews") or "0"
    photos = b.get("photos") or []
    cover_photo = b.get("cover_photo") or (photos[0] if photos else "")
    current_year = str(datetime.now().year)

    phone_digits = extract_phone_digits(phone_raw)

    # --- Groq single call ---
    ai = call_groq(b)

    # Address
    if ai:
        city = ai.get("city") or ""
        area = ai.get("area") or ""
    else:
        area, city = extract_location(full_address)

    # Hero title
    if ai and isinstance(ai.get("hero_title"), list) and len(ai["hero_title"]) == 3:
        hero_title_line1, hero_title_em, hero_title_line3 = ai["hero_title"]
    else:
        hero_title_line1, hero_title_em, hero_title_line3 = get_hero_title(category)

    # Hero subtitle
    hero_subtitle = (
        ai.get("hero_subtitle") if ai else None
    ) or (
        f"{name} offers professional {category.lower()} services "
        f"in {area}, {city} - serving the local community with expertise and care."
    )

    # About paragraphs
    about_paragraph_1 = (ai.get("about_para_1") if ai else None) or (
        f"{name} has been serving individuals and businesses in {city} "
        "with a commitment to quality, speed, and complete transparency. "
        "Whether you're a first-time customer or a long-standing client - we're here for you."
    )
    about_paragraph_2 = (ai.get("about_para_2") if ai else None) or (
        "Our team is known for being approachable, thorough, and always available to answer your questions "
        "in plain language - no jargon, just clarity."
    )

    # Services
    if ai and ai.get("services"):
        services_list_html = build_services_html_from_ai(ai["services"])
    else:
        scraped = (b.get("service_options") or []) + (b.get("offerings") or [])
        services_list_html = build_services_html(category, scraped_services=scraped or None)

    # USPs, FAQ, payments, social
    usps_html = build_usps_html(ai.get("usps") if ai else [])
    faq_html = build_faq_html(ai.get("faq") if ai else [])
    payments_html = build_payments_html(b.get("payments") or [])
    social_html = build_social_html(b.get("social_media") or {})

    wa_message = quote(f"Hi, I found {name} online and would like to know more about your services.")
    wa_booking_message = quote(f"Hi, I would like to book a free consultation with {name}.")

    years_stat = extract_years(b.get("reviews", []))
    reviews_html = build_reviews_html(b.get("reviews", []))
    hours_table_html = build_hours_html(b.get("hours", {}))
    photos_html = build_photos_html(photos, name)

    # Derived tokens
    phone_link = f"tel:+91{phone_digits}" if len(phone_digits) == 10 else f"tel:{phone_digits}"
    since_year = str(int(current_year) - int(years_stat.replace("+", "")) - 1)
    maps_query = quote(full_address or name)
    maps_link = f"https://maps.google.com/maps?q={maps_query}"
    maps_embed = f"https://maps.google.com/maps?q={maps_query}&output=embed"

    replacements = {
        "{{BUSINESS_NAME}}": escape(name),
        "{{CATEGORY}}": escape(category),
        "{{FULL_ADDRESS}}": escape(full_address),
        "{{PHONE_RAW}}": escape(phone_raw),
        "{{PHONE_DISPLAY}}": escape(phone_display),
        "{{RATING}}": escape(str(rating)),
        "{{TOTAL_REVIEWS}}": escape(str(total_reviews)),
        "{{COVER_PHOTO}}": escape(str(cover_photo), quote=True),
        "{{CURRENT_YEAR}}": current_year,
        "{{PHONE_DIGITS}}": escape(phone_digits),
        "{{CITY}}": escape(city),
        "{{AREA}}": escape(area),
        "{{WA_MESSAGE}}": wa_message,
        "{{WA_BOOKING_MESSAGE}}": wa_booking_message,
        "{{NAV_LOGO_HTML}}": logo_html(name),
        "{{FOOTER_LOGO_HTML}}": logo_html(name),
        "{{CATEGORY_SHORT}}": escape(category_short(category)),
        "{{HERO_TITLE_LINE1}}": escape(hero_title_line1),
        "{{HERO_TITLE_EM}}": escape(hero_title_em),
        "{{HERO_TITLE_LINE3}}": escape(hero_title_line3),
        "{{HERO_SUBTITLE}}": escape(hero_subtitle),
        "{{SERVICES_SECTION_TITLE}}": services_title(category),
        "{{SERVICES_LIST_HTML}}": services_list_html,
        "{{ABOUT_PARAGRAPH_1}}": escape(about_paragraph_1),
        "{{ABOUT_PARAGRAPH_2}}": escape(about_paragraph_2),
        "{{YEARS_STAT}}": escape(years_stat),
        "{{REVIEWS_HTML}}": reviews_html,
        "{{HOURS_TABLE_HTML}}": hours_table_html,
        "{{PHOTOS_HTML}}": photos_html,
        "{{USPS_HTML}}": usps_html,
        "{{FAQ_HTML}}": faq_html,
        "{{PAYMENTS_HTML}}": payments_html,
        "{{SOCIAL_HTML}}": social_html,
        # Aliases used by new templates
        "{{SERVICES_HTML}}": services_list_html,
        "{{HOURS_HTML}}": hours_table_html,
        "{{ABOUT_PARA_1}}": escape(about_paragraph_1),
        "{{ABOUT_PARA_2}}": escape(about_paragraph_2),
        "{{YEAR}}": current_year,
        "{{SINCE_YEAR}}": since_year,
        "{{PHONE_LINK}}": phone_link,
        "{{MAPS_LINK}}": maps_link,
        "{{MAPS_EMBED}}": maps_embed,
    }

    filled = template_str
    for token, value in replacements.items():
        filled = filled.replace(token, value)

    return filled


def generate_site(business, template):
    """Backward-compatible alias for older callers."""
    return generate_one(business, template)


def main():
    with open("template.html", "r", encoding="utf-8") as f:
        template = f.read()

    with open("business_website_data/businesses_progress.json", "r", encoding="utf-8") as f:
        businesses = json.load(f)

    os.makedirs("output", exist_ok=True)

    generated = 0
    skipped_website = 0
    skipped_no_name = 0

    for b in businesses:
        if b.get("has_website"):
            skipped_website += 1
            continue
        if not b.get("name"):
            skipped_no_name += 1
            continue

        html = generate_one(b, template)
        slug = make_slug(b["name"])
        out_path = os.path.join("output", f"{slug}.html")

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"✓ Generated: {slug}.html")
        generated += 1

    print(f"\nDone. {generated} sites generated. {skipped_website} skipped (already have website).")


if __name__ == "__main__":
    main()
