"""CareCompass pattern mining + voice summary (v1, additive).

Reads the user's last 3 assessments + up to 14 recent check-ins, mines frequent
itemsets and association rules over that user's own data, scores criticality with
transparent rules, and produces a warm, short spoken-text summary.

This module does NOT change scoring, safety, recommendations or chat.
It depends only on BANDS from carecompass_core.
"""
from itertools import combinations
import json

import carecompass_core as cc

BANDS = cc.BANDS

# ------------------------------------------------------------- helpers
_MOOD_BUCKETS  = {1: "Very_low", 2: "Low", 3: "Okay", 4: "Good", 5: "Very_good"}
_LOW_FEELINGS  = {"Anxious", "Overwhelmed", "Hopeless", "Lonely", "Numb", "Sad"}
_HIGH_BANDS    = {"Severe", "Extremely Severe"}

def _bands(a): return a.get("bands") or {}
def _ctx(a):   return a.get("context") or {}

def _assessment_items(a):
    """One transaction per assessment: bands + lifestyle strains + urgent flag."""
    items = set()
    for sub, band in _bands(a).items():
        items.add(f"{sub}_{band.replace(' ', '_')}")
    c = _ctx(a)
    if c.get("sleep")    in ("Poor", "Very poor"):              items.add("Sleep_Poor")
    if c.get("energy")   in ("Low", "Very low"):                items.add("Energy_Low")
    if c.get("pressure") in ("High", "Very high"):              items.add("Pressure_High")
    if c.get("activity") in ("Rarely", "Almost never"):         items.add("Activity_Low")
    if c.get("screen")   in ("5-8 hours", "More than 8 hours"): items.add("Screen_High")
    if c.get("social")   in ("Rarely", "Almost never"):         items.add("Social_Low")
    if a.get("urgent"):                                         items.add("Urgent_Flag")
    return items

def _checkin_items(c):
    """One transaction per check-in: mood bucket + high stress/anxiety + low energy/sleep + low feelings."""
    items = set()
    m = c.get("mood")
    if m is not None: items.add(f"Mood_{_MOOD_BUCKETS.get(m, 'Okay')}")
    if (c.get("stress")  or 0) >= 4: items.add("Stress_Checkin_High")
    if (c.get("anxiety") or 0) >= 4: items.add("Anxiety_Checkin_High")
    if (c.get("energy")  or 5) <= 2: items.add("Energy_Checkin_Low")
    if (c.get("sleep")   or 5) <= 2: items.add("Sleep_Checkin_Poor")
    for f in (c.get("feelings") or []):
        if f in _LOW_FEELINGS: items.add(f"Feeling_{f}")
    return items

def _trend_items(assessments):
    """One transaction with trend flags across the last (up to) 3 assessments.
    `assessments` is newest-first, so seq[0] is now and seq[-1] is oldest:
      seq[0] < seq[-1] -> newer scores are lower -> Improving
      seq[0] > seq[-1] -> newer scores are higher -> Worsening
      flat at Severe / Extremely Severe -> Persistent_High
    """
    items = set()
    for sub in ("Depression", "Anxiety", "Stress"):
        seq = [BANDS.index(_bands(a).get(sub, "Normal")) for a in assessments if _bands(a).get(sub)]
        if len(seq) < 2:
            continue
        if all(seq[i] <= seq[i + 1] for i in range(len(seq) - 1)) and seq[0] < seq[-1]:
            items.add(f"Trend_{sub}_Improving")
        elif all(seq[i] >= seq[i + 1] for i in range(len(seq) - 1)) and seq[0] > seq[-1]:
            items.add(f"Trend_{sub}_Worsening")
        elif all(x == seq[0] for x in seq) and seq[0] >= 2:
            items.add(f"Trend_{sub}_Persistent_High")
    return items

# ------------------------------------------------------------- Apriori + rules
def _frequent_itemsets(transactions, min_support=0.35, max_size=3):
    """Return {frozenset(items): support}. Simple, small-data-friendly Apriori."""
    n = len(transactions)
    if n == 0:
        return {}
    freq = {}
    for it in {i for t in transactions for i in t}:
        sup = sum(1 for t in transactions if it in t) / n
        if sup >= min_support:
            freq[frozenset([it])] = sup
    cur = list(freq.keys())
    for size in range(2, max_size + 1):
        cands = set()
        for i, a in enumerate(cur):
            for b in cur[i + 1:]:
                u = a | b
                if len(u) == size:
                    cands.add(u)
        new = {}
        for c in cands:
            sup = sum(1 for t in transactions if c <= t) / n
            if sup >= min_support:
                new[c] = sup
        freq.update(new)
        cur = list(new.keys())
        if not cur:
            break
    return freq

def _association_rules(freq, min_conf=0.6):
    """Return [{ant, con, support, confidence}] from the frequent-itemset map."""
    rules = []
    for itemset, sup in freq.items():
        if len(itemset) < 2:
            continue
        for size in range(1, len(itemset)):
            for ant in combinations(sorted(itemset), size):
                ant = frozenset(ant)
                con = itemset - ant
                s_ant = freq.get(ant)
                if s_ant and sup / s_ant >= min_conf:
                    rules.append({"ant": ant, "con": con,
                                  "support": round(sup, 2),
                                  "confidence": round(sup / s_ant, 2)})
    seen, out = set(), []
    for r in rules:
        k = (r["ant"], r["con"])
        if k not in seen:
            seen.add(k); out.append(r)
    return out

# ------------------------------------------------------------- criticality
def _criticality(assessments, checkins, rules, urgent_flag):
    """Transparent rule-based hint (NOT a new safety decision — safety still comes from cc.safety_check)."""
    reasons, score = [], 0
    bands = _bands(assessments[0]) if assessments else {}

    # Current state
    for sub, band in bands.items():
        score += BANDS.index(band)
        if band in _HIGH_BANDS:
            reasons.append(f"{sub} is {band.lower()} in your most recent assessment")

    # Trends across the last (up to 3) assessments — newest-first
    for sub in ("Depression", "Anxiety", "Stress"):
        seq = [BANDS.index(_bands(a).get(sub, "Normal")) for a in assessments]
        if len(seq) >= 2:
            if seq[0] > seq[-1]:
                reasons.append(f"{sub} has been rising across your last {len(seq)} assessments")
                score += 2
            elif seq[0] == seq[1] and seq[0] >= 3:
                reasons.append(f"{sub} has stayed high across your last {len(seq)} assessments")
                score += 3

    # Check-ins
    recent = (checkins or [])[:5]
    if recent:
        low   = sum(1 for c in recent if (c.get("mood")    or 3) <= 2)
        hi_st = sum(1 for c in recent if (c.get("stress")  or 0) >= 4)
        hi_an = sum(1 for c in recent if (c.get("anxiety") or 0) >= 4)
        if low >= 3:
            reasons.append(f"low mood in {low} of your last {len(recent)} check-ins"); score += 2
        if hi_st >= 3 or hi_an >= 3:
            reasons.append("high stress or anxiety in most recent check-ins"); score += 2

    # A single strong rule gives one extra bump (prevents runaway scoring)
    for r in rules:
        if "Urgent_Flag" in r["con"] or any(
                b in x for x in r["con"] for b in ("Extremely_Severe", "Severe")):
            score += 1
            break

    extreme = any(b == "Extremely Severe" for b in bands.values())
    severe  = any(b == "Severe"          for b in bands.values())
    if urgent_flag or extreme:
        level = "urgent"
    elif severe or score >= 10:
        level = "high"
    elif score >= 4:
        level = "moderate"
    else:
        level = "low"
    return level, score, reasons

# ------------------------------------------------------------- public API
def mine_patterns(assessments, checkins, min_support=0.35, max_size=3, min_conf=0.6):
    """Return {transactions, frequent, rules, criticality, score, reasons, trend}."""
    transactions = []
    for a in (assessments or []):
        t = _assessment_items(a)
        if t:
            transactions.append(t)
    for c in (checkins or []):
        t = _checkin_items(c)
        if t:
            transactions.append(t)
    trends = _trend_items(assessments or [])
    if trends:
        transactions.append(trends)

    freq  = _frequent_itemsets(transactions, min_support=min_support, max_size=max_size)
    rules = _association_rules(freq, min_conf=min_conf)

    urgent_flag = bool(assessments and assessments[0].get("urgent"))
    level, score, reasons = _criticality(assessments or [], checkins or [], rules, urgent_flag)

    return {"transactions": transactions, "frequent": freq, "rules": rules,
            "criticality": level, "score": score, "reasons": reasons,
            "trend": sorted(trends)}

_LEVEL_OPENERS = {
    "urgent":   "I want to gently check in. What you have been carrying sounds very heavy right now, and I really want you to reach out to someone today.",
    "high":     "Your recent results and check-ins suggest things have been quite heavy. You do not have to manage this alone.",
    "moderate": "Things look a bit strained over the last week or two, but there is room to gently turn things around.",
    "low":      "Your recent results and check-ins look steady. That is really good to see.",
}

def voice_summary(assessments, checkins, patterns, name=None):
    """Short, warm, plain-English text suitable for text-to-speech. Deterministic — no AI, no safety decisions here."""
    who = (name or "").strip()
    greeting = f"Hi {who}." if who else "Hi."
    if not assessments and not checkins:
        return (f"{greeting} Welcome back to CareCompass. "
                "When you are ready, complete an assessment and I will check in with you.")
    parts = [greeting, _LEVEL_OPENERS[patterns["criticality"]]]
    if assessments:
        bands = _bands(assessments[0])
        if bands:
            worst = max(bands, key=lambda k: BANDS.index(bands[k]))
            if BANDS.index(bands[worst]) >= 1:
                parts.append(f"The area asking for the most care is {worst.lower()}, at {bands[worst].lower()}.")
    if patterns["reasons"]:
        parts.append("I have noticed " + "; ".join(patterns["reasons"][:2]) + ".")
    if patterns["criticality"] in ("moderate", "high", "urgent"):
        parts.append("Please open your plan for gentle ideas that fit you, and reach out to someone you trust.")
    else:
        parts.append("Keep doing what is helping. Even small, steady habits make a difference.")
    return " ".join(parts)


def _voice_greeting(name=None):
    """Keep personal identifiers local; the greeting is never sent to Groq."""
    who = " ".join(str(name or "").split())[:40]
    return f"Hi {who}." if who else "Hi."


def _checkin_categories(checkins):
    """Reduce a check-in to human-readable categories; never include notes or raw ratings."""
    mood_labels = {1: "very low", 2: "low", 3: "okay", 4: "good", 5: "very good"}
    level_labels = {1: "very low", 2: "low", 3: "moderate", 4: "high", 5: "very high"}
    out = []
    for checkin in (checkins or [])[:3]:
        item = {}
        for key, labels in (("mood", mood_labels), ("stress", level_labels),
                            ("anxiety", level_labels), ("energy", level_labels),
                            ("sleep", level_labels)):
            try:
                value = int(checkin.get(key))
            except (TypeError, ValueError):
                continue
            if value in labels:
                item[key] = labels[value]
        if item:
            out.append(item)
    return out


def _assessment_payload(assessments, patterns, checkins=None):
    """Only send coarse result categories, check-in categories, and support category."""
    latest = [
        {area: band for area, band in (_bands(item) or {}).items()
         if area in ("Depression", "Anxiety", "Stress") and band in BANDS}
        for item in (assessments or [])[:3]
    ]
    return {"recent_assessment_categories": latest,
            "recent_checkin_categories": _checkin_categories(checkins),
            "support_category": patterns.get("criticality", "low")}


def voice_preview(assessments, checkins, patterns, name=None):
    """Return a local greeting and one gentle AI-written line, with a safe fallback."""
    greeting = _voice_greeting(name)
    if not assessments:
        return greeting + " " + _LEVEL_OPENERS.get(patterns.get("criticality"), _LEVEL_OPENERS["low"])

    text = cc.groq_complete([
        {"role": "system", "content":
         "Write exactly one warm, gentle sentence for a personal wellbeing voice note. "
         "Reflect only the supplied broad assessment categories and support category. "
         "Do not diagnose, use clinical labels for the person, add advice, mention scores or numbers, "
         "or suggest a safety level. Do not include a greeting; it is added locally. Keep it under 24 words."},
        {"role": "user", "content": json.dumps(_assessment_payload(assessments, patterns))}],
        temperature=0.25, max_tokens=100)
    if (not text or len(text) > 220 or len(text.split()) > 30
            or cc.BAD_OUTPUT.search(text) or cc.CHAT_BAD.search(text) or cc.crisis_text(text)):
        bands = {area: band for area, band in _bands(assessments[0]).items()
                 if area in ("Depression", "Anxiety", "Stress") and band in BANDS}
        if bands:
            worst = max(bands, key=lambda area: BANDS.index(bands[area]))
            line = f"Your recent check-in shows {worst.lower()} may need a little extra care."
        else:
            line = _LEVEL_OPENERS.get(patterns.get("criticality"), _LEVEL_OPENERS["low"])
        return greeting + " " + line
    return greeting + " " + text.strip().strip('"')


def gentle_wellbeing_summary(assessments, checkins, patterns):
    """Write a roughly 50-word reflection from the latest three assessments and check-ins."""
    assessments = (assessments or [])[:3]
    checkins = (checkins or [])[:3]
    if not assessments and not checkins:
        return "There is not enough saved history to make a summary yet. When you feel ready, add a check-in or complete an assessment and return here."

    latest = ({area: band for area, band in _bands(assessments[0]).items()
               if area in ("Depression", "Anxiety", "Stress") and band in BANDS}
              if assessments else {})
    checkin_categories = _checkin_categories(checkins)
    fallback_parts = [f"{area.lower()} is {band.lower()}" for area, band in latest.items()]
    recent_mood = [item["mood"] for item in checkin_categories if "mood" in item]
    recent_strain = [f"{key} {item[key]}" for item in checkin_categories for key in ("stress", "anxiety") if key in item]
    recent_care = [f"{key} {item[key]}" for item in checkin_categories for key in ("energy", "sleep") if key in item]
    fallback_parts_for_text = []
    if fallback_parts:
        fallback_parts_for_text.append("Your latest screening categories are " + ", ".join(fallback_parts) + ".")
    if recent_mood:
        mood_text = ", ".join(dict.fromkeys(recent_mood))
        fallback_parts_for_text.append("Across the recent check-ins, mood was recorded as " + mood_text + ".")
    if recent_strain:
        fallback_parts_for_text.append("Recent check-ins recorded " + ", ".join(dict.fromkeys(recent_strain)) + ".")
    if recent_care:
        fallback_parts_for_text.append("Energy and sleep notes included " + ", ".join(dict.fromkeys(recent_care)) + ".")
    fallback = " ".join(fallback_parts_for_text)
    fallback += " Together, these entries are a small snapshot of recent experiences, not a diagnosis or the whole of who you are."
    if patterns.get("criticality") == "urgent" or any(item.get("urgent") for item in assessments):
        fallback += " Please reach out to someone you trust or a support professional today; you do not have to handle this alone."
    if not latest and not checkin_categories:
        return "I could not read the saved wellbeing categories just now. You can revisit your history or add a check-in when ready."
    if patterns.get("criticality") == "urgent" or any(item.get("urgent") for item in assessments):
        return fallback

    text = cc.groq_complete([
        {"role": "system", "content":
         "Write a gentle, plain-language reflection of about 50 words using only the supplied recent assessment "
         "and check-in categories. Mention the overall support signal in calm, non-alarming language and describe "
         "the pattern without claiming a cause. Keep assessment category names and levels accurate. Screening is not "
         "a diagnosis. Do not diagnose, infer treatment, add recommendations, or mention scores or numbers. "
         "Use 40 to 60 words, without a greeting."},
        {"role": "user", "content": json.dumps(_assessment_payload(assessments, patterns, checkins))}],
        temperature=0.25, max_tokens=150)
    if (not text or len(text) > 420 or not 35 <= len(text.split()) <= 70
            or cc.BAD_OUTPUT.search(text) or cc.CHAT_BAD.search(text) or cc.crisis_text(text)):
        return fallback
    return text.strip().strip('"')

# ------------------------------------------------------------- self-test
def selftest():
    # Empty state
    assert mine_patterns([], [])["criticality"] == "low"

    # Single assessment, all Normal -> low
    norm = [{"bands": {"Depression": "Normal", "Anxiety": "Normal", "Stress": "Normal"},
             "context": {}, "urgent": False}]
    assert mine_patterns(norm, [])["criticality"] == "low"

    # Any Severe -> high
    sev = [{"bands": {"Depression": "Severe", "Anxiety": "Mild", "Stress": "Moderate"},
            "context": {}, "urgent": False}]
    assert mine_patterns(sev, [])["criticality"] == "high"

    # Any Extremely Severe -> urgent
    ext = [{"bands": {"Depression": "Extremely Severe", "Anxiety": "Normal", "Stress": "Normal"},
            "context": {}, "urgent": False}]
    assert mine_patterns(ext, [])["criticality"] == "urgent"

    # Urgent flag from item 21 -> urgent
    flg = [{"bands": {"Depression": "Normal", "Anxiety": "Normal", "Stress": "Normal"},
            "context": {}, "urgent": True}]
    assert mine_patterns(flg, [])["criticality"] == "urgent"

    # Voice summary always returns a reasonably long sentence
    for a, c in [([], []), (norm, []), (sev, []), (ext, []), (flg, [])]:
        t = voice_summary(a, c, mine_patterns(a, c), "Sam")
        assert isinstance(t, str) and len(t) > 20

    # Apriori sanity
    freq = _frequent_itemsets([{"A", "B"}, {"A", "B"}, {"A"}], min_support=0.5)
    assert frozenset(["A", "B"]) in freq

    # Trend labels: newest-first ordering must produce Improving for descending scores,
    # Worsening for ascending scores, and Persistent_High only for a flat high plateau.
    two_improving = [
        {"bands": {"Depression": "Normal", "Anxiety": "Normal", "Stress": "Normal"}, "context": {}},
        {"bands": {"Depression": "Severe", "Anxiety": "Normal", "Stress": "Normal"}, "context": {}},
    ]
    two_worsening = [
        {"bands": {"Depression": "Severe", "Anxiety": "Normal", "Stress": "Normal"}, "context": {}},
        {"bands": {"Depression": "Normal", "Anxiety": "Normal", "Stress": "Normal"}, "context": {}},
    ]
    three_flat_high = [
        {"bands": {"Depression": "Severe", "Anxiety": "Normal", "Stress": "Normal"}, "context": {}},
        {"bands": {"Depression": "Severe", "Anxiety": "Normal", "Stress": "Normal"}, "context": {}},
        {"bands": {"Depression": "Severe", "Anxiety": "Normal", "Stress": "Normal"}, "context": {}},
    ]
    assert "Trend_Depression_Improving"      in _trend_items(two_improving),  _trend_items(two_improving)
    assert "Trend_Depression_Worsening"      in _trend_items(two_worsening),  _trend_items(two_worsening)
    assert "Trend_Depression_Persistent_High" in _trend_items(three_flat_high), _trend_items(three_flat_high)

    print("carecompass_patterns selftest passed")
