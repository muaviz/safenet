"""
SafeNet AI Content Classification & Threat Detection Module.
Provides rule-based heuristics, domain categorization, and optional LLM classification.
"""

import os
import re
from urllib.parse import urlparse

# Predefined domain category dictionaries
CATEGORY_PRESETS = {
    "adult": [
        "pornhub.com", "xvideos.com", "xnxx.com", "chaturbate.com", "onlyfans.com",
        "redtube.com", "youporn.com", "stripchat.com", "cam4.com"
    ],
    "gambling": [
        "bet365.com", "pokerstars.com", "draftkings.com", "fanduel.com", "stake.com",
        "bovada.lv", "roobet.com", "betonline.ag", "888casino.com"
    ],
    "gaming": [
        "roblox.com", "fortnite.com", "epicgames.com", "steampowered.com", "twitch.tv",
        "discord.com", "minecraft.net", "ea.com", "riotgames.com"
    ],
    "social": [
        "tiktok.com", "instagram.com", "facebook.com", "twitter.com", "x.com",
        "reddit.com", "snapchat.com", "pinterest.com", "tumblr.com"
    ],
    "video_streaming": [
        "youtube.com", "netflix.com", "disneyplus.com", "hulu.com", "primevideo.com"
    ],
    "educational": [
        "wikipedia.org", "khanacademy.org", "coursera.org", "edx.org", "duolingo.com",
        "nationalgeographic.com", "nasa.gov", "codecademy.com", "scratch.mit.edu", "pbskids.org"
    ]
}

# Suspicious / malicious keywords for real-time text analysis
INAPPROPRIATE_KEYWORDS = [
    r"\bporn(ography)?\b", r"\bxxx\b", r"\bnsfw\b", r"\berotic\b", r"\bhentai\b",
    r"\bgambl(e|ing)\b", r"\bcasino\b", r"\bbetting\b", r"\bslots\b",
    r"\bgore\b", r"\bweapon(s)?\b", r"\bexplosive(s)?\b"
]

PHISHING_KEYWORDS = [
    r"confirm your password", r"verify your bank account", r"crypto payout",
    r"urgent account suspended", r"free gift card giveaway", r"metamask wallet phrase"
]

def normalize_domain(url: str) -> str:
    """Normalize a URL to its root domain (lowercase, no www, no protocol, no path)."""
    if not url:
        return ""
    url = url.strip().lower()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url
    try:
        parsed = urlparse(url)
        domain = parsed.hostname or parsed.netloc or ""
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url.split('/')[0].replace("www.", "")

def classify_domain_quick(domain: str) -> str:
    """Quick lookup of known domain categories."""
    clean_domain = normalize_domain(domain)
    for category, domains in CATEGORY_PRESETS.items():
        for d in domains:
            if clean_domain == d or clean_domain.endswith("." + d):
                return category
    return "general"

def classify_page_content(url: str, title: str = "", snippet: str = "", safety_tier: str = "moderate") -> dict:
    """
    Classify page safety based on URL, title, and body snippets.
    Returns: {"blocked": bool, "category": str, "reason": str, "confidence": float}
    """
    domain = normalize_domain(url)
    category = classify_domain_quick(domain)

    # Educational is always safe
    if category == "educational":
        return {"blocked": False, "category": category, "reason": "Approved Educational Content", "confidence": 0.99}

    # Strict Tier: Only educational or pre-approved allowed
    if safety_tier == "strict":
        if category in ["adult", "gambling", "social", "gaming", "video_streaming"]:
            return {
                "blocked": True,
                "category": category,
                "reason": f"Category '{category.replace('_', ' ').title()}' is restricted in Strict Safe Mode.",
                "confidence": 0.95
            }

    # Known bad categories across all tiers
    if category in ["adult", "gambling"]:
        return {
            "blocked": True,
            "category": category,
            "reason": f"Restricted category: {category.title()}",
            "confidence": 0.98
        }

    # Text / Metadata Heuristics
    combined_text = f"{title} {snippet}".lower()

    for pattern in INAPPROPRIATE_KEYWORDS:
        if re.search(pattern, combined_text, re.IGNORECASE):
            return {
                "blocked": True,
                "category": "inappropriate",
                "reason": "AI detected inappropriate or adult themes on this webpage.",
                "confidence": 0.88
            }

    for pattern in PHISHING_KEYWORDS:
        if re.search(pattern, combined_text, re.IGNORECASE):
            return {
                "blocked": True,
                "category": "scam_phishing",
                "reason": "AI Security Shield: Potential phishing or scam threat detected.",
                "confidence": 0.92
            }

    return {
        "blocked": False,
        "category": category,
        "reason": "Content verified safe",
        "confidence": 0.85
    }
