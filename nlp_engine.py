"""
NLP and Automated Root-Cause Attribution Engine.
Analyzes sentiment polarity, extracts diagnostic n-grams, and calculates
automated root-cause attribution linking structured logistics latency and SKU return rates
with unstructured customer sentiment, isolating catalog measurement errors.
"""

import re
from typing import Dict, List, Any, Tuple
import numpy as np

# Domain-specific sentiment and diagnostic lexicons
NEGATIVE_SIGNALS = {
    "terrible": -0.9, "awful": -0.9, "horrible": -0.9, "broken": -0.85, "defective": -0.85,
    "wrong": -0.7, "inaccurate": -0.8, "misleading": -0.85, "delayed": -0.75, "late": -0.65,
    "damage": -0.8, "damaged": -0.85, "crushed": -0.8, "missing": -0.7, "tight": -0.6,
    "small": -0.5, "short": -0.5, "poor": -0.7, "fail": -0.8, "failed": -0.85,
    "disaster": -0.95, "unacceptable": -0.9, "refund": -0.6, "waste": -0.8
}

POSITIVE_SIGNALS = {
    "great": 0.8, "excellent": 0.9, "perfect": 0.95, "good": 0.6, "love": 0.85,
    "fast": 0.7, "prompt": 0.75, "accurate": 0.8, "quality": 0.7, "comfortable": 0.75,
    "smooth": 0.65, "impressed": 0.8, "sharp": 0.7, "durable": 0.75
}

# Anchors for Root Cause Categories
ROOT_CAUSE_CATEGORIES = {
    "CATALOG_MEASUREMENT_ERROR": {
        "display_name": "Catalog Measurement / Sizing Chart Discrepancy",
        "description": "Garment dimensions, size charts, or catalog measurements misleading customers.",
        "owner": "Catalog Operations & Merchandising",
        "keywords": ["size chart", "sizing", "chest", "measurement", "measurements", "waist", "sleeve", "armhole", "dimensions", "tight", "fits like", "too small", "mislabeled", "specs"]
    },
    "TRANSIT_DELAY_LOGISTICS": {
        "display_name": "Carrier Transit Latency & Shipping Damage",
        "description": "Delivery transit latency SLA breaches, stalled courier scans, or package damage in transit.",
        "owner": "Logistics & Carrier Network Management",
        "keywords": ["transit", "delayed", "late delivery", "carrier", "apexlogistics", "courier", "stalled", "tracking", "crushed", "battered", "days late", "shipping delay"]
    },
    "PRODUCT_QUALITY_DEFECT": {
        "display_name": "Manufacturing & Hardware Quality Defect",
        "description": "Component failure, defective battery/materials, factory assembly faults.",
        "owner": "Quality Assurance & Supplier Engineering",
        "keywords": ["battery", "earbud", "charge", "crackling", "broke", "defective", "hardware", "quality defect", "stitching", "zipper", "frayed", "manufacturing"]
    },
    "CATALOG_SPEC_MISMATCH": {
        "display_name": "Product Listing / Specification Omission",
        "description": "Accessories, cables, or package contents advertised on page but omitted in packaging.",
        "owner": "Product Content & Packaging Compliance",
        "keywords": ["missing cable", "advertised", "listing", "specs", "cable included", "description error", "omitted", "false advertising"]
    },
    "BUYER_PREFERENCE_REMORSE": {
        "display_name": "Customer Preference / Remorse",
        "description": "Customer changed mind, ordered multiple colorways, or standard non-defect return.",
        "owner": "Customer Experience & Retention",
        "keywords": ["changed mind", "no longer needed", "color", "bought two", "style preference"]
    }
}


def analyze_sentiment(text: str) -> Dict[str, Any]:
    """
    Computes sentiment polarity (-1.0 to +1.0) and label for a text snippet.
    """
    if not text:
        return {"polarity": 0.0, "label": "NEUTRAL", "confidence": 0.0}

    tokens = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    if not tokens:
        return {"polarity": 0.0, "label": "NEUTRAL", "confidence": 0.0}

    score = 0.0
    matches = 0

    for token in tokens:
        if token in NEGATIVE_SIGNALS:
            score += NEGATIVE_SIGNALS[token]
            matches += 1
        elif token in POSITIVE_SIGNALS:
            score += POSITIVE_SIGNALS[token]
            matches += 1

    if matches > 0:
        normalized_polarity = max(-1.0, min(1.0, score / max(1, matches)))
    else:
        normalized_polarity = 0.0

    if normalized_polarity <= -0.15:
        label = "NEGATIVE"
    elif normalized_polarity >= 0.15:
        label = "POSITIVE"
    else:
        label = "NEUTRAL"

    confidence = round(min(1.0, 0.4 + (matches * 0.15)), 2)
    return {
        "polarity": round(normalized_polarity, 3),
        "label": label,
        "confidence": confidence,
        "signal_matches": matches
    }


def extract_key_diagnostic_phrases(texts: List[str], top_n: int = 5) -> List[Tuple[str, int]]:
    """
    Extracts high-frequency problem n-grams and diagnostic phrases from customer logs.
    """
    phrase_counts: Dict[str, int] = {}
    stop_words = {"the", "a", "an", "and", "or", "in", "on", "at", "for", "with", "is", "was", "to", "of", "my", "i", "it", "this", "that", "but"}

    for text in texts:
        clean = re.sub(r'[^\w\s]', ' ', text.lower())
        words = [w for w in clean.split() if len(w) > 2 and w not in stop_words]
        # Bigrams
        for i in range(len(words) - 1):
            bg = f"{words[i]} {words[i+1]}"
            phrase_counts[bg] = phrase_counts.get(bg, 0) + 1
        # Trigrams
        for i in range(len(words) - 2):
            tg = f"{words[i]} {words[i+1]} {words[i+2]}"
            phrase_counts[tg] = phrase_counts.get(tg, 0) + 1

    sorted_phrases = sorted(phrase_counts.items(), key=lambda x: x[1], reverse=True)
    return sorted_phrases[:top_n]


def calculate_root_cause_attribution(
    sku_row: Dict[str, Any],
    customer_texts: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Automated Root-Cause Attribution:
    Reconciles structured operational metrics (return_rate_pct, baseline, avg_transit_latency_days)
    with unstructured customer text sentiment and keyword semantic resonance.
    
    Isolates:
    - CATALOG_MEASUREMENT_ERROR: High returns + Normal latency + Heavy sizing/chart complaints
    - TRANSIT_DELAY_LOGISTICS: High latency + Carrier delays + Delivery/damaged box complaints
    - PRODUCT_QUALITY_DEFECT: High returns + Normal latency + Battery/hardware breakdown complaints
    """
    return_rate = float(sku_row.get("return_rate_pct", 0.0))
    baseline = float(sku_row.get("baseline_return_threshold", 0.08)) * 100
    latency = float(sku_row.get("avg_transit_latency_days", 0.0))
    lost_gmv = float(sku_row.get("lost_return_gmv", 0.0))

    # Base raw scores for each category
    category_scores = {cat: 0.1 for cat in ROOT_CAUSE_CATEGORIES.keys()}

    # 1. Unstructured Customer Text Signals (Tickets & Reviews)
    for item in customer_texts:
        text = (item.get("raw_text") or item.get("review_text") or "").lower()
        sentiment = analyze_sentiment(text)
        weight = 1.0 + abs(sentiment["polarity"]) if sentiment["label"] == "NEGATIVE" else 0.5

        for cat, config in ROOT_CAUSE_CATEGORIES.items():
            matches = sum(1 for kw in config["keywords"] if kw in text)
            if matches > 0:
                category_scores[cat] += matches * weight * 1.5

    # 2. Structured Metric Reconciliation (Anomalies)
    # Return rate anomaly multiplier
    return_rate_ratio = return_rate / max(1.0, baseline)

    # A. CATALOG MEASUREMENT ERROR:
    # Characterized by: Abnormally high return rate (>2x baseline) AND normal/low transit latency (<1.0 day)
    if return_rate_ratio >= 2.0 and latency < 1.0:
        category_scores["CATALOG_MEASUREMENT_ERROR"] *= (1.5 + return_rate_ratio)

    # B. TRANSIT DELAY LOGISTICS:
    # Characterized by: Elevated transit latency (>1.5 days delay) and carrier SLA breaches
    if latency >= 1.5:
        category_scores["TRANSIT_DELAY_LOGISTICS"] *= (2.0 + latency)
    elif latency < 0.5:
        category_scores["TRANSIT_DELAY_LOGISTICS"] *= 0.3  # De-emphasize if transit was on time

    # C. PRODUCT QUALITY DEFECT:
    # High return rate with normal latency, but specifically mentions component issues
    if return_rate_ratio >= 2.0 and latency < 1.0:
        # Balanced with text signal
        category_scores["PRODUCT_QUALITY_DEFECT"] *= (1.0 + (return_rate_ratio * 0.7))

    # D. HEALTHY / BUYERS REMORSE:
    if return_rate_ratio <= 1.0 and latency < 1.0:
        category_scores["BUYER_PREFERENCE_REMORSE"] *= 3.0

    # Normalize to Attribution Percentages
    total_score = sum(category_scores.values())
    attribution_pcts = {
        cat: round((score / total_score) * 100, 1)
        for cat, score in category_scores.items()
    }

    # Sort categories by attribution share
    sorted_attribution = sorted(attribution_pcts.items(), key=lambda x: x[1], reverse=True)
    primary_category, primary_confidence = sorted_attribution[0]
    category_meta = ROOT_CAUSE_CATEGORIES[primary_category]

    # Generate Evidence Synthesis
    evidence = []
    if latency > 1.5:
        evidence.append(f"Structured logistics latency anomaly: {latency} days avg transit latency (SLA target breach).")
    else:
        evidence.append(f"Transit logistics nominal ({latency} days latency) - logistics transit eliminated as root cause.")

    if return_rate > baseline * 1.5:
        evidence.append(f"Elevated return rate anomaly: {return_rate}% vs baseline threshold of {baseline}%.")
    
    if lost_gmv > 1000:
        evidence.append(f"Severe financial impact: ${lost_gmv:,.2f} in refunded return GMV.")

    return {
        "primary_root_cause": primary_category,
        "primary_root_cause_name": category_meta["display_name"],
        "attribution_confidence_pct": primary_confidence,
        "attribution_breakdown": attribution_pcts,
        "recommended_owner": category_meta["owner"],
        "root_cause_description": category_meta["description"],
        "evidence_summary": evidence,
        "structured_reconciliation": {
            "return_rate_pct": return_rate,
            "baseline_threshold_pct": baseline,
            "avg_transit_latency_days": latency,
            "lost_return_gmv": lost_gmv
        }
    }
