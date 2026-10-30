"""CareCompass core logic (UI-independent): scoring, safety, recommendations, Groq adapter, ML service, Supabase layer.
Used by streamlit_app.py. Supabase (auth, Postgres with RLS) + saved sklearn models + Groq (wording only).
Module order follows the master plan: auth -> consent -> questionnaire -> scoring -> ML -> safety
-> context -> recommendations -> Groq adapter -> persistence -> follow-up -> pattern mining (v4) -> audit.
Scoring and safety are deterministic; neither the ML model nor Groq can override them.
"""
import os, re, glob, json, hashlib, functools

# ============================ CONFIG ============================
NOTICE_VERSION = "2026-10-v1"
SCORING_VERSION = "dass21-standard-v1"
ENABLE_ADAPTIVE = False          # adaptive pathway stays disabled until verified (no UI is built for it)
SHOW_RESEARCH_MODEL_VIEW = False # show ML estimate on results screen (research only)
# llama-3.3-70b-versatile and llama-3.1-8b-instant were shut down by Groq on 16 Aug 2026. Models are tried in order;
# set GROQ_MODEL to put your own choice first. Check console.groq.com/docs/models for the current list.
GROQ_MODELS = list(dict.fromkeys(m for m in [os.environ.get("GROQ_MODEL"), "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b"] if m))
MODEL_DIR = os.environ.get("MODEL_DIR", "models")
ITEM_OFFSET = 0                  # set to 1 if your training data coded items 1-4 instead of 0-3
GENDER_CHOICES = ["Female", "Male", "Other / prefer not to say"]
# --- ML mapping assumptions: models predict ONLY after you confirm all of these are true for your training data ---
#  1. Feature A1..A7 / D1..D7 / S1..S7 are the subscale's items in ascending DASS-21 item-number order
#     (e.g. A1=item 2, A2=item 4, A3=item 7, A4=item 9, A5=item 15, A6=item 19, A7=item 20).
#  2. Class labels 0,1,2,3,4 mean Normal, Mild, Moderate, Severe, Extremely Severe (in that order).
#  3. Item answers were coded 0-3 (else set ITEM_OFFSET=1) and Age is in years.
#  4. GENDER_MAP below matches how Gender was coded when you trained.
ML_MAPPINGS_CONFIRMED = False
GENDER_MAP = None                # e.g. {"Female": 0, ...} if your pipeline expects numeric gender; None = pass the string

# Edit to match your institution. Verify every number before real use.
SUPPORT_LINES = (
    "**If you need to talk to someone now**\n"
    "- Emergency: **112**\n"
    "- Tele-MANAS (India, free, 24x7): **14416** or 1-800-891-4416\n"
    "- Your college counselling cell / a trusted friend, family member or doctor\n"
)

# ============================ DASS-21 DATA ============================
ITEMS = [
    "I found it hard to wind down",
    "I was aware of dryness of my mouth",
    "I couldn't seem to experience any positive feeling at all",
    "I experienced breathing difficulty (e.g. excessively rapid breathing, breathlessness in the absence of physical exertion)",
    "I found it difficult to work up the initiative to do things",
    "I tended to over-react to situations",
    "I experienced trembling (e.g. in the hands)",
    "I felt that I was using a lot of nervous energy",
    "I was worried about situations in which I might panic and make a fool of myself",
    "I felt that I had nothing to look forward to",
    "I found myself getting agitated",
    "I found it difficult to relax",
    "I felt down-hearted and blue",
    "I was intolerant of anything that kept me from getting on with what I was doing",
    "I felt I was close to panic",
    "I was unable to become enthusiastic about anything",
    "I felt I wasn't worth much as a person",
    "I felt that I was rather touchy",
    "I was aware of the action of my heart in the absence of physical exertion (e.g. sense of heart rate increase, heart missing a beat)",
    "I felt scared without any good reason",
    "I felt that life was meaningless",
]  # VERIFY against your approved wording
CHOICES = [("0 - Did not apply to me at all", 0), ("1 - Applied to me to some degree, or some of the time", 1),
           ("2 - Applied to me to a considerable degree, or a good part of the time", 2),
           ("3 - Applied to me very much, or most of the time", 3)]
SUBSCALES = {"Depression": [3, 5, 10, 13, 16, 17, 21], "Anxiety": [2, 4, 7, 9, 15, 19, 20],
             "Stress": [1, 6, 8, 11, 12, 14, 18]}
CUTS = {"Depression": [9, 13, 20, 27], "Anxiety": [7, 9, 14, 19], "Stress": [14, 18, 25, 33]}  # on x2 scores
BANDS = ["Normal", "Mild", "Moderate", "Severe", "Extremely Severe"]

# ============================ SCORING ENGINE ============================
def validate_responses(resp):
    """Return list of problems (empty = valid)."""
    if not isinstance(resp, list) or len(resp) != 21:
        return ["Expected 21 answers."]
    return [f"Item {i+1} is unanswered or invalid." for i, v in enumerate(resp)
            if not (isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 3)]

def score(resp):
    raw = {s: 2 * sum(resp[i - 1] for i in idx) for s, idx in SUBSCALES.items()}
    bands = {s: BANDS[sum(raw[s] > c for c in CUTS[s])] for s in raw}
    return raw, bands

# ============================ SAFETY ENGINE ============================
URGENT_TEXT = ("### Please reach out for support today\n"
               "Some of your answers suggest you may be going through something really heavy. "
               "You don't have to handle it alone, and talking to a real person can help.\n\n" + SUPPORT_LINES)

def safety_check(resp, bands, self_harm_flag=False):
    """Deterministic. Always runs; never depends on a model or API."""
    if self_harm_flag or resp[20] >= 2:  # item 21 'life was meaningless' >= 2, or explicit disclosure
        return {"level": "urgent", "text": URGENT_TEXT}
    if any(b in ("Severe", "Extremely Severe") for b in bands.values()):
        return {"level": "elevated",
                "text": ("### Talking to someone could help\n"
                         "Your answers point to a lot of strain right now. Consider speaking with a counsellor "
                         "or doctor.\n\n" + SUPPORT_LINES)}
    return {"level": "none", "text": ""}

# ============================ RECOMMENDATIONS ============================
# Built-in approved set (used when the Supabase recommendation_catalog has no approved rows). Have a counsellor review before real use.
def _r(i, title, text, **kw): return dict(id=i, title=title, text=text, **kw)
CATALOG = [
    # --- stress
    _r("R_BREATH", "Slow your body down first",
       "Sit comfortably and breathe in through your nose for 4 counts, hold gently for 2, then breathe out slowly for 6. Repeat for 2-3 minutes. A long out-breath tells your body it is safe to ease off. You can do this before an exam, in a queue, or in bed.", sub="Stress", min=1),
    _r("R_BREAKS", "Build real breaks into your study day",
       "Study in blocks of 25-40 minutes, then take 5-10 minutes away from screens: stretch, drink water, look out of a window. Protect one fully free hour a day with no studying and no scrolling. Rest is part of doing well, not a reward you have to earn.", sub="Stress", min=1),
    _r("R_MUSCLE", "Release the tension you are carrying",
       "Starting from your toes, tighten each muscle group for 5 seconds and then let go for 10, working up to your shoulders and jaw. Most people are surprised how much they were holding. It takes about 8 minutes and works well before sleep.", sub="Stress", min=2),
    _r("R_LIST", "Get it out of your head and onto paper",
       "Spend 5 minutes writing everything on your mind. Circle the three things that really need action this week, and cross out what is outside your control. A short list is far easier to face than a swirl of worries.", sub="Stress", min=1),
    # --- anxiety
    _r("R_GROUND", "Ground yourself in the present moment",
       "When your mind is racing, name 5 things you can see, 4 you can feel, 3 you can hear, 2 you can smell and 1 you can taste. This gently pulls your attention out of 'what if' and back into the room.", sub="Anxiety", min=1),
    _r("R_WORRY", "Give your worries a time slot",
       "Pick a 15-minute 'worry window' each day. When a worry pops up at other times, jot it down and tell yourself 'later'. In your window, ask of each one: can I do something about this? If yes, choose one small step; if no, practise letting it sit.", sub="Anxiety", min=1),
    _r("R_FACE", "Take one small step toward what you have been avoiding",
       "Avoiding things feels like relief but lets fear grow. Pick one thing you have been putting off and shrink it to a tiny first step, like opening the document or sending a short message. Do only that step, then notice that you coped.", sub="Anxiety", min=2),
    # --- depression / low mood
    _r("R_ACTIVITY", "Do one small thing you used to enjoy",
       "When mood is low, waiting to 'feel like it' rarely works. Action often comes first and the feeling follows. Pick something tiny and kind: a favourite song, a hot drink in the sun, ten minutes of a hobby. Any amount counts.", sub="Depression", min=1),
    _r("R_WALK", "Get daylight and gentle movement",
       "A 10-20 minute walk outdoors, ideally in the morning, helps mood, energy and sleep for many people. No special clothes or goals needed. Slow is fine.", sub="Depression", min=1),
    _r("R_KIND", "Speak to yourself the way you would to a friend",
       "If harsh thoughts like 'I am useless' show up, pause and ask what you would say to a friend who felt this way. Write that kinder sentence down and read it back to yourself. It feels awkward at first and gets easier with practice.", sub="Depression", min=1),
    _r("R_WINS", "Notice your small wins",
       "At the end of each day, write down three things that went okay, even 'I got out of bed' or 'I ate lunch'. When we are low, the mind filters out the good. This gently trains it to notice again.", sub="Depression", min=1),
    # --- reaching out
    _r("R_TALK", "Tell someone you trust how you have been feeling",
       "Choose one person (a friend, sibling, parent or mentor) and say, 'I have been finding things hard lately and wanted you to know.' You do not need perfect words or a solution. Being heard really does lighten the load.", sub=None, min=2),
    _r("R_COUNSEL", "Consider talking to a professional",
       "A counsellor or doctor can help you make sense of what you are going through and teach tools that work. Most colleges have a counselling cell. Booking a first session is an ordinary, brave step, and many students find that even one conversation helps.", sub=None, min=3),
    # --- for everyone: things that lift mood
    _r("R_CONNECT", "Connect with someone, even briefly",
       "Send a message to a friend, sit with classmates at lunch, or call home. Short moments of connection protect your mood more than we expect.", sub=None, min=0, uplift=True),
    _r("R_LOOKFWD", "Put something to look forward to in tomorrow",
       "Schedule one small enjoyable thing: a favourite meal, a game, a walk with a friend, an episode you have been saving. Having something ahead gives the day a gentle pull.", sub=None, min=0, uplift=True),
    _r("R_PATIENT", "Be patient with yourself",
       "You are handling a lot: studies, expectations and a life that keeps changing. Finding things hard does not mean you are failing. Aim for 'good enough' today and let that be enough.", sub=None, min=0, uplift=True),
    # --- context-driven
    _r("R_SLEEP", "Protect your sleep",
       "Keep a steady bedtime and wake time, even on weekends, and keep screens away for the last 30 minutes. Limit caffeine to the morning. If your mind is busy at night, write tomorrow's to-do list before bed. If you are awake for more than 20 minutes, get up, do something calm in dim light, and return when sleepy.", ctx=("sleep", ["Poor", "Very poor"])),
    _r("R_ENERGY", "Work with your energy, not against it",
       "Notice when in the day you feel sharpest and put your hardest task there. Use low-energy periods for easy jobs or rest. Eat regularly, drink water and get a few minutes of daylight, because low fuel makes everything feel heavier.", ctx=("energy", ["Low", "Very low"])),
    _r("R_PLAN", "Make the academic pressure smaller",
       "Break each big task into pieces you can finish in 30-60 minutes and put them on a weekly plan. Choose your top three priorities and let the rest be 'good enough' or wait. If the workload feels truly impossible, talk to a faculty mentor early. Most are more understanding than students expect.", ctx=("pressure", ["High", "Very high"])),
    _r("R_MOVE", "Move your body a little, most days",
       "You do not need a gym. Aim for 20-30 minutes of something you can stand: a brisk walk, cycling, dancing in your room, a short stretch routine. Movement releases tension, improves sleep and lifts mood. Start with 10 minutes and add a little each week.", ctx=("activity", ["Rarely", "Almost never"])),
    _r("R_SCREEN", "Give your mind a break from screens",
       "Try keeping the last hour before bed screen-free, muting non-essential notifications, and setting one or two phone-free blocks in the day, such as meals. Scrolling can feel restful but often leaves the mind more wired and comparing. Replace some of it with music, a walk or a chat.", ctx=("screen", ["5-8 hours", "More than 8 hours"])),
    _r("R_SOCIAL", "Reconnect with people who feel safe",
       "Reach out to one person you feel comfortable with: a message, a call, or a tea together. Keep it small and easy. Isolation tends to make low and anxious feelings louder, and even short, regular contact helps.", ctx=("social", ["Rarely", "Almost never"])),
    _r("R_PEER", "Study and unwind with other people",
       "Arrange a study session or a walk with a friend this week. Being around others makes tasks feel lighter, and you can share the load without having to explain everything.", ctx=("support", ["Talking to friends or peers"])),
    _r("R_SELF", "Try a daily 10-minute reset",
       "Choose guided relaxation, journaling or gentle stretching and do it at the same time each day, for example after dinner. Doing it regularly matters more than doing it for long.", ctx=("support", ["Self-help tools"])),
    _r("R_PRO", "Book a first appointment",
       "Ask your college counselling cell or a doctor for a first appointment. You can say simply, 'I would like to talk to someone about how I have been feeling.' You do not need to be in crisis to deserve support.", ctx=("support", ["Professional support"])),
    # --- urgent state only
    _r("R_STAY", "Please do not stay alone with this",
       "Go to someone you trust, or to a warm public place, and tell them how heavy it has felt. If you feel you might act on thoughts of harming yourself, call 112 or Tele-MANAS 14416 right now.", urgent=True),
]
URGENT_IDS = ("R_STAY", "R_TALK", "R_COUNSEL")

def recommend(bands, ctx, safety, catalog=None, limit=12):
    catalog = catalog or CATALOG
    if safety["level"] == "urgent":  # safety state restricts to support-oriented items
        out = [r for r in CATALOG if r["id"] in URGENT_IDS]
        return sorted(out, key=lambda r: URGENT_IDS.index(r["id"]))
    maxband = max(BANDS.index(b) for b in bands.values())
    by_sub, ctx_hits, general, uplift = {}, [], [], []
    for r in catalog:
        if r.get("urgent"): continue
        if "ctx" in r:
            key, vals = r["ctx"]
            if ctx.get(key) in vals: ctx_hits.append(r)
        elif r.get("uplift"):
            uplift.append(r)
        elif r.get("sub"):
            if BANDS.index(bands[r["sub"]]) >= r.get("min", 1):
                by_sub.setdefault(r["sub"], []).append(r)
        elif maxband >= r.get("min", 1):
            general.append(r)
    out = []
    for sub in sorted(by_sub, key=lambda x: -BANDS.index(bands[x])):  # most affected area first
        out += by_sub[sub][:2]
    out += ctx_hits[:6] + general + uplift[:3]
    if len(out) < 4:
        out += [r for r in catalog if r["id"] in ("R_WALK", "R_BREATH") and r not in out]
    seen, final = set(), []
    for r in out:
        if r["id"] not in seen: seen.add(r["id"]); final.append(r)
    return final[:limit]

# ============================ LIFESTYLE PATTERN INDICATOR ============================
# NOT a classifier and NOT a diagnosis. Transparent rules showing which area daily habits may be straining.
# Weights are heuristic (reasonable, not clinically validated): have your supervisor review them. Never affects DASS bands or safety.
CTX_OPTIONS = dict(
    sleep=["Good", "Okay", "Poor", "Very poor"], energy=["High", "Normal", "Low", "Very low"],
    pressure=["Low", "Moderate", "High", "Very high"],
    activity=["Most days", "A few times a week", "Rarely", "Almost never"],
    screen=["Under 3 hours", "3-5 hours", "5-8 hours", "More than 8 hours"],
    social=["Often", "Sometimes", "Rarely", "Almost never"],
    support=["Self-help tools", "Talking to friends or peers", "Professional support", "Not sure"])
AREAS = {"Stress": "stress", "Anxiety": "anxiety", "Low mood": "low"}
#            (question, answer): (points {area: pts}, plain-language driver)
LIFESTYLE_RULES = {
    ("pressure", "High"): ({"stress": 2, "anxiety": 1}, "high academic pressure"),
    ("pressure", "Very high"): ({"stress": 3, "anxiety": 2}, "very high academic pressure"),
    ("sleep", "Poor"): ({"stress": 1, "anxiety": 1, "low": 1}, "poor sleep"),
    ("sleep", "Very poor"): ({"stress": 2, "anxiety": 2, "low": 1}, "very poor sleep"),
    ("energy", "Low"): ({"low": 1}, "low energy"),
    ("energy", "Very low"): ({"low": 2}, "very low energy"),
    ("activity", "Rarely"): ({"low": 1, "anxiety": 1}, "little physical activity"),
    ("activity", "Almost never"): ({"low": 2, "anxiety": 1, "stress": 1}, "almost no physical activity"),
    ("screen", "5-8 hours"): ({"anxiety": 1}, "long daily screen time"),
    ("screen", "More than 8 hours"): ({"anxiety": 2, "stress": 1, "low": 1}, "very long daily screen time"),
    ("social", "Rarely"): ({"low": 1}, "little social contact"),
    ("social", "Almost never"): ({"low": 2, "anxiety": 1}, "almost no social contact"),
}
_MAX = {a: sum(max((pts.get(a, 0) for (q2, _), (pts, _d) in LIFESTYLE_RULES.items() if q2 == q), default=0)
               for q in {q for q, _ in LIFESTYLE_RULES}) for a in AREAS.values()}

def lifestyle_indicator(ctx):
    """-> {area: {'level': 'Lower'|'Moderate'|'Higher', 'drivers': [str]}} from the lifestyle answers only."""
    out = {}
    for area, key in AREAS.items():
        pts, drivers = 0, []
        for q, ans in ctx.items():
            rule = LIFESTYLE_RULES.get((q, ans))
            if rule and rule[0].get(key):
                pts += rule[0][key]; drivers.append(rule[1])
        ratio = pts / _MAX[key] if _MAX[key] else 0
        out[area] = {"level": "Higher" if ratio >= 0.6 else ("Moderate" if ratio >= 0.3 else "Lower"), "drivers": drivers}
    return out

# ============================ GROQ CLIENT HELPER ============================
LAST_GROQ_ERROR = ""
_THINK = re.compile(r"<think>.*?</think>", re.S)

def groq_complete(messages, temperature, max_tokens=700):
    """Try each configured model in turn. Returns text or None; the reason for failure is kept in LAST_GROQ_ERROR."""
    global LAST_GROQ_ERROR
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        LAST_GROQ_ERROR = "GROQ_API_KEY is not set in the environment the app is running in."; return None
    try:
        from groq import Groq
        client = Groq(api_key=key)
    except Exception as e:
        LAST_GROQ_ERROR = f"groq library problem: {str(e)[:150]}"; return None
    errs = []
    for model in GROQ_MODELS:
        try:
            extra = {"extra_body": {"reasoning_effort": "low"}} if model.startswith("openai/gpt-oss") else {}
            r = client.chat.completions.create(model=model, messages=messages, temperature=temperature,
                                               max_tokens=max_tokens, **extra)
            text = _THINK.sub("", r.choices[0].message.content or "").strip()
            if text:
                LAST_GROQ_ERROR = ""; return text
            errs.append(f"{model}: empty reply")
        except Exception as e:
            errs.append(f"{model}: {str(e)[:110]}")
    LAST_GROQ_ERROR = " | ".join(errs)[:450]
    return None

# ============================ GROQ ADAPTER ============================
BAD_OUTPUT = re.compile(r"\b(disorder|diagnos\w*|prescri\w*|medicat\w*|you have (depression|anxiety)|\d)", re.I)

def fallback_explanation(bands, recs):
    parts = ", ".join(f"{s.lower()}: {b.lower()}" for s, b in bands.items())
    return (f"This screening suggests the following levels over the past week ({parts}). This is not a diagnosis. "
            "Here are some suggestions that may help.")

def explain(bands, recs, ctx, safety):
    """Returns (text, used_groq). Groq only rephrases approved content; any problem -> deterministic fallback."""
    fb = fallback_explanation(bands, recs)
    if safety["level"] == "urgent":  # urgent state: fixed safe wording only
        return fb, False
    payload = {"levels": bands, "context": ctx, "approved_suggestions": [r.get("title", r["text"]) for r in recs]}
    text = groq_complete([
        {"role": "system", "content":
         "You are a kind wellbeing assistant for college students. Write a short, warm, encouraging note (max 130 words) "
         "that acknowledges how the person may be feeling, mentions the given levels gently, and invites them to try "
         "the suggested ideas one small step at a time. Rules: do not diagnose; do not use clinical labels for the person; "
         "do not add any advice, medication, or numbers that are not provided; do not change the levels; "
         "say this is a screening, not a diagnosis."},
        {"role": "user", "content": json.dumps(payload)}], temperature=0.3, max_tokens=700)
    if not text or len(text) > 1200 or BAD_OUTPUT.search(text):
        return fb, False
    return text, True

# ============================ ML INFERENCE SERVICE ============================
class ModelService:
    """Loads joblib pipelines, validates schema/labels, refuses to guess. Disabled per-subscale on any doubt."""
    def __init__(self, model_dir=MODEL_DIR):
        self.models, self.status, self.version = {}, {}, "none"
        vers = []
        try:
            import joblib
        except Exception:
            self.status = {s: "disabled: joblib missing" for s in SUBSCALES}
            return
        for sub in SUBSCALES:
            key = sub.lower()[:6]  # stress / anxiet / depres
            files = [f for f in glob.glob(os.path.join(model_dir, "*.joblib")) if key in os.path.basename(f).lower()]
            if len(files) != 1:
                self.status[sub] = f"disabled: {len(files)} artifact(s) matched"
                continue
            try:
                m = joblib.load(files[0])
                cols = list(m.feature_names_in_)
                plan, items = [], set()
                for c in cols:
                    lc = c.lower()
                    pos = re.fullmatch(r"([ads])([1-7])", lc.strip())
                    if "age" in lc: plan.append(("age", None))
                    elif "gender" in lc or "sex" in lc: plan.append(("gender", None))
                    elif pos:
                        if pos.group(1) != sub[0].lower(): raise ValueError(f"feature '{c}' does not belong to {sub}")
                        n = SUBSCALES[sub][int(pos.group(2)) - 1]  # k-th item of the subscale, ascending item number
                        plan.append(("item", n)); items.add(n)
                    else:
                        n = re.findall(r"\d+", c)
                        if len(n) != 1: raise ValueError(f"cannot map feature '{c}'")
                        plan.append(("item", int(n[0]))); items.add(int(n[0]))
                if items != set(SUBSCALES[sub]): raise ValueError("item set does not match subscale")
                classes = [self._band_of(c) for c in getattr(m, "classes_", getattr(m[-1], "classes_", []))]
                if not classes or None in classes: raise ValueError("class labels are neither 0-4 nor the 5 band names")
                if not hasattr(m, "predict_proba"): raise ValueError("no predict_proba")
                self.models[sub] = (m, cols, plan)
                self.status[sub] = "ok" if ML_MAPPINGS_CONFIRMED else "loaded, but predictions stay OFF until ML_MAPPINGS_CONFIRMED=True"
                vers.append(f"{key}:{hashlib.sha256(open(files[0],'rb').read()).hexdigest()[:8]}")
            except Exception as e:
                self.status[sub] = f"disabled: {e}"
        if vers: self.version = "|".join(vers)

    @staticmethod
    def _band_of(c):
        """Class label -> band name. Accepts 0-4 (ordinal) or the band names themselves; anything else -> None."""
        try:
            i = int(c)
            if str(c).strip().lstrip("-").isdigit() or isinstance(c, (int,)) or type(c).__name__.startswith(("int", "float")):
                return BANDS[i] if 0 <= i <= 4 else None
        except (TypeError, ValueError):
            pass
        return str(c) if str(c) in BANDS else None

    def predict(self, resp, age, gender):
        """Returns {sub: {band, confidence}} for validated models only; never raises."""
        import pandas as pd
        out = {}
        if not ML_MAPPINGS_CONFIRMED: return out  # never show estimates built on unconfirmed assumptions
        for sub, (m, cols, plan) in self.models.items():
            try:
                row = {}
                for c, (kind, n) in zip(cols, plan):
                    if kind == "item": row[c] = resp[n - 1] + ITEM_OFFSET
                    elif kind == "age":
                        if age is None: raise ValueError("age missing")
                        row[c] = age
                    else:
                        if not gender: raise ValueError("gender missing")
                        row[c] = GENDER_MAP[gender] if GENDER_MAP else gender
                p = m.predict_proba(pd.DataFrame([row], columns=cols))[0]
                cls = [self._band_of(c) for c in getattr(m, "classes_", getattr(m[-1], "classes_", []))]
                i = int(p.argmax())
                out[sub] = {"band": cls[i], "confidence": round(float(p[i]), 3)}
            except Exception:
                continue  # leave this subscale without an estimate; never substitute
        return out

# ============================ SUPABASE LAYER ============================
class Expired(Exception):
    pass

class DB:
    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL", "")
        self.key = os.environ.get("SUPABASE_ANON_KEY", "")  # anon/publishable key ONLY. Never the service-role key.
    @property
    def configured(self): return bool(self.url and self.key)
    def _new(self):
        from supabase import create_client
        return create_client(self.url, self.key)  # fresh client per call: no shared session between users
    def authed(self, token):
        c = self._new(); c.postgrest.auth(token); return c
    def sign_up(self, email, pw):
        r = self._new().auth.sign_up({"email": email, "password": pw})
        return r.session is not None
    def sign_in(self, email, pw):
        r = self._new().auth.sign_in_with_password({"email": email, "password": pw})
        return r.session.access_token, r.user.id, r.user.email
    def reset(self, email):
        a = self._new().auth
        (getattr(a, "reset_password_for_email", None) or a.reset_password_email)(email)

db, models = DB(), None

def fresh():
    return {"uid": None, "email": None, "token": None, "consent": {}, "resp": [None] * 21, "idx": 0,
            "name": None, "age": None, "gender": None, "ctx": {}, "self_harm": False, "result": None, "aid": None}

def api(S, fn):
    if not S.get("token"): raise Expired()
    try:
        return fn(db.authed(S["token"]))
    except Exception as e:
        m = str(e).lower()
        if "jwt" in m or "pgrst301" in m or "expired" in m or "401" in m:
            S.clear(); S.update(fresh()); raise Expired()
        raise

def log(S, ev):
    try: api(S, lambda c: c.rpc("log_event", {"p_type": ev, "p_model_version": models.version if models else None}).execute())
    except Exception: pass

def load_consents(S):
    rows = api(S, lambda c: c.table("consent_records").select("consent_type,granted,recorded_at")
               .order("recorded_at", desc=True).execute()).data
    S["consent"] = {}
    for r in rows:
        S["consent"].setdefault(r["consent_type"], r["granted"])  # newest first

def set_consent(S, ctype, granted):
    api(S, lambda c: c.table("consent_records").insert(
        {"user_id": S["uid"], "consent_type": ctype, "notice_version": NOTICE_VERSION, "granted": granted}).execute())
    S["consent"][ctype] = granted

def catalog_from_db(S):
    try:
        rows = api(S, lambda c: c.table("recommendation_catalog").select("*").execute()).data
        out = []
        for r in rows:
            cond = r["applicable_conditions"] or {}
            d = {"id": r["recommendation_id"], "text": r["approved_text"]}
            if "ctx" in cond: d["ctx"] = tuple(cond["ctx"])
            else: d.update(sub=cond.get("sub"), min=cond.get("min", 1))
            out.append(d)
        return out or None
    except Expired: raise
    except Exception: return None

# ============================ PROFILE ============================
def load_profile(S):
    rows = api(S, lambda c: c.table("profiles").select("display_name,age,gender").eq("user_id", S["uid"]).execute()).data
    if rows:
        S["name"], S["age"], S["gender"] = rows[0]["display_name"], rows[0]["age"], rows[0]["gender"]

def save_profile(S, name, age, gender):
    name = (name or "").strip()[:60] or None
    age = int(age) if age else None
    api(S, lambda c: c.table("profiles").upsert(
        {"user_id": S["uid"], "display_name": name, "age": age, "gender": gender or None}).execute())
    S["name"], S["age"], S["gender"] = name, age, gender or None

# ============================ CRISIS TEXT CHECK + CHATBOT ============================
CHAT_TEMPERATURE = 0.2
CRISIS_RE = re.compile(r"(suicid|kill myself|end my life|want to die|wanna die|don'?t want to (live|be here|exist)|"
                       r"self[- ]?harm|hurt myself|harm myself|cut myself|better off dead|no reason to live|end it all|take my own life)", re.I)

def crisis_text(t):
    return bool(CRISIS_RE.search(t or ""))

CRISIS_REPLY = ("I'm really glad you told me, and I'm sorry it has been this painful. What you are feeling matters, and you "
                "deserve support from a real person right now. Please reach out to someone today, and if you are in "
                "immediate danger, call emergency services.\n\n" + SUPPORT_LINES +
                "\nIf you like, I can stay and talk with you while you reach out. Is there someone nearby you can be with?")

CHAT_SYSTEM = (
    "You are CareCompass Companion, a warm, gentle supportive chat companion for college students in India. "
    "You are not a therapist, doctor or human, and you never claim to be. "
    "How to reply: first reflect and validate what the person said in your own words; then, only if it fits, offer ONE small, "
    "practical idea (such as slow breathing, a short walk, writing thoughts down, talking to someone trusted); you may end with at most "
    "ONE gentle open question. Keep replies to 50-110 words, plain simple language, no lists, no headings. "
    "Never diagnose or label the person with a condition. Never suggest medication, supplements or doses. Never promise outcomes. "
    "If things sound heavy or ongoing, kindly encourage talking to a trusted person or the college counselling cell. "
    "If the person mentions harming themselves or not wanting to live, urge them to contact emergency services (112) or Tele-MANAS (14416) right now. "
    "Stay on wellbeing and emotional support; politely decline unrelated tasks."
)
CHAT_BAD = re.compile(r"(you have (depression|anxiety|a disorder|ptsd|bipolar)|you are (depressed|bipolar)|diagnos(e|ed) you|"
                      r"prescri\w*|dosage|\bmg\b|antidepressant|\bpills?\b)", re.I)
CHAT_FALLBACK = ("Thank you for sharing that with me. It sounds like a lot to carry, and your feelings make sense. "
                 "I'm having trouble replying properly right now, so here is something small you can try: breathe in slowly for 4 counts "
                 "and out for 6, a few times. If it keeps feeling heavy, please talk to someone you trust or your college counselling cell.")

GREETING_RE = re.compile(r"^\s*(hi+|hello+|hey+|good (morning|afternoon|evening)|namaste|hola|yo|how are you\??)[\s!.,]*$", re.I)
GREETING_REPLY = ("Hi, I'm glad you're here. How are you feeling today? You can tell me as much or as little as you like, "
                  "and there is no rush.")

def chat_reply(history):
    """history: list of {'role': 'user'|'assistant', 'content': str}. Returns (text, kind) with kind in crisis|ai|fallback.
    The crisis check is deterministic and runs first; the model never decides whether to show safety information."""
    last = history[-1]["content"] if history else ""
    if crisis_text(last):
        return CRISIS_REPLY, "crisis"
    msgs = [{"role": "system", "content": CHAT_SYSTEM}] + [
        {"role": m["role"], "content": m["content"][:1500]} for m in history[-12:]]
    text = groq_complete(msgs, temperature=CHAT_TEMPERATURE, max_tokens=700)
    if text and len(text) <= 1500 and not CHAT_BAD.search(text) and not crisis_text(text):
        return text, "ai"
    if text:  # reply was produced but failed the safety filter
        globals()["LAST_GROQ_ERROR"] = "AI reply was blocked by the safety filter."
    return (GREETING_REPLY if GREETING_RE.match(last) else CHAT_FALLBACK), "fallback"

# ============================ "HOW ARE YOU FEELING NOW" CHECK-INS ============================
MOOD_LABELS = {1: "Very low", 2: "Low", 3: "Okay", 4: "Good", 5: "Very good"}
FEELINGS = ["Calm", "Hopeful", "Happy", "Okay", "Tired", "Overwhelmed", "Anxious", "Sad", "Irritable", "Lonely", "Numb", "Hopeless"]

def checkin_reply(mood, feelings, note):
    """Deterministic, kind response to a check-in. show_support is set by rules, never by a model."""
    feelings = feelings or []
    support = mood == 1 or "Hopeless" in feelings or crisis_text(note)
    if support:
        text = ("Thank you for being honest about how you are feeling. That sounds really hard, and you do not have to carry it alone. "
                "Please consider reaching out to someone today, using the support options below. For right now, try putting both feet on "
                "the floor and breathing out slowly for 6 counts, a few times.")
    elif mood == 2:
        text = ("Thank you for checking in. Low days are tough, and they do shift. Be gentle with yourself today: drink some water, "
                "get a little daylight, and do one small thing that feels kind. Talking to someone you trust could help too.")
    elif mood == 3:
        text = ("Thanks for checking in. 'Okay' is a perfectly good place to be. If you can, do one small thing today that "
                "your future self will thank you for, like a walk, a proper meal or an early night.")
    else:
        text = ("It is lovely to hear you are doing well. Take a moment to notice what has been helping, so you can come back to it on harder days.")
    return {"text": text, "show_support": support}

def mood_trend(rows):
    """rows newest-first -> short text comparing the two most recent check-ins."""
    if len(rows) < 2 or rows[0].get("mood") is None or rows[1].get("mood") is None: return ""
    d = rows[0]["mood"] - rows[1]["mood"]
    return "Your mood is a little higher than your last check-in." if d > 0 else (
        "Your mood is a little lower than your last check-in. That is okay, and it is good that you are tracking it." if d < 0
        else "Your mood is about the same as your last check-in.")

# ============================ WELLNESS PLAN (lifestyle, sleep, diet, study) ============================
# General wellbeing ideas, deterministic and written for students. Not medical advice, not a diet plan: no calorie or weight targets.
def _p(title, text, when=None): return dict(title=title, text=text, when=when)
# when: None = always | ("band", Subscale, min_band_index) | ("ctx", key, [values]) | ("any", [specs...])
PLAN = {
 "routine": ("Daily routine & lifestyle", [
    _p("Anchor your day with a steady rhythm", "Get up at about the same time every day, get 10 minutes of daylight soon after waking, and end the day with a short wind-down. A predictable rhythm steadies mood, energy and sleep, and takes pressure off decision-making."),
    _p("Move your body a little every day", "Aim for something you enjoy, even small: a 15-20 minute walk, stretching, cycling, a game with friends, dancing in your room. Starting small matters more than starting big. Moving, especially outdoors, is one of the most reliable natural mood and stress lifters."),
    _p("Schedule small good things like classes", "Each day, write down three small activities in your timetable: one for pleasure (music, a hobby, a show), one for achievement (a small task completed) and one for connection (a message, a call, a shared meal). Do them even if you do not feel like it. Mood often follows action.", ("band", "Depression", 1)),
    _p("Add two short reset breaks to your day", "Pick two fixed times, for example after lunch and in the evening, for 3-5 minutes of slow breathing, stretching or stepping outside. Planned breaks stop tension building up all day and make racing thoughts easier to settle.", ("any", [("band", "Anxiety", 1), ("band", "Stress", 1)])),
    _p("Tame the scroll", "Keep your phone out of reach while you sleep, silence non-essential notifications, and choose set times for social media instead of grabbing it whenever you feel low or bored. Comparing yourself with other people's highlights can quietly lower mood."),
    _p("Keep something just for joy", "Protect one activity every day that has no purpose except enjoyment, and do not feel guilty about it. Rest and fun are what make hard work sustainable."),
 ]),
 "sleep": ("Sleep", [
    _p("Set a steady sleep window", "Choose a bedtime and wake time you can keep, including weekends (within about an hour). Regular timing helps your body clock more than extra hours on random days."),
    _p("Wind down for the last 30 minutes", "Dim the lights, put screens away, and do something calm: a warm shower, light stretching, reading, or writing tomorrow's to-do list so your mind is not holding it overnight."),
    _p("If you cannot fall asleep", "If you are still awake after about 20 minutes, get up, do something quiet in dim light, and go back when sleepy. Avoid checking the time or the phone. Lying in bed worrying teaches the brain that bed means stress.", ("ctx", "sleep", ["Poor", "Very poor"])),
    _p("Daytime habits that protect night sleep", "Have caffeine only in the morning or early afternoon, get daylight and some movement during the day, avoid heavy meals late at night, and keep daytime naps short (20-30 minutes, early afternoon)."),
 ]),
 "food": ("Food & drink", [
    _p("Eat regularly and do not skip meals", "Try to have breakfast, lunch and dinner at fairly regular times. Long gaps without food can bring on irritability, shakiness, poor concentration and anxious feelings. If appetite is low, small frequent snacks are fine."),
    _p("Build meals that give steady energy", "Combine slow-release carbohydrates (oats, ragi, millets, brown rice, whole-wheat roti) with protein (dal, pulses, sprouts, curd, paneer, eggs, nuts) and vegetables or a fruit. This gives steadier energy and concentration than snacks that are mostly sugar or refined flour."),
    _p("Drink water through the day", "Keep a bottle with you and sip regularly. Mild dehydration can cause tiredness, headaches and low concentration that are easily mistaken for stress or low mood."),
    _p("Go easy on caffeine and sugary drinks", "Strong tea or coffee, energy drinks and fizzy drinks can raise heart rate, restlessness and anxious feelings, and disturb sleep, especially in the afternoon and evening. Try swapping some for water, buttermilk, coconut water or herbal tea, and cut back gradually.", ("any", [("band", "Anxiety", 1), ("band", "Stress", 1), ("ctx", "sleep", ["Poor", "Very poor"])])),
    _p("Foods that support mood", "No single food fixes mood, but overall eating patterns matter. Include fruits and vegetables, nuts and seeds (walnuts, flaxseed, chia), curd or other fermented foods, pulses and whole grains, and fish if you eat it. Think 'more of the good' rather than 'ban the rest'."),
    _p("On low-energy days", "Eat something within an hour or so of waking, keep easy snacks handy (banana, roasted chana, nuts, curd), and drink water. If tiredness lasts for weeks, it is worth a routine check-up with a doctor, because common and treatable causes such as low iron, vitamin D or B12, or thyroid problems can feel like low mood.", ("ctx", "energy", ["Low", "Very low"])),
    _p("Alcohol, tobacco and energy shots", "These can feel like relief in the moment but usually worsen anxiety, mood and sleep over time. If you find yourself using them to cope, speak with a counsellor or doctor. That is a common and fixable situation."),
 ]),
 "study": ("Academic stress & study habits", [
    _p("Choose three priorities a day", "Each morning pick the three things that matter most, break each into 30-60 minute tasks, and do those first. Everything else is a bonus. A short list you finish builds confidence; a long one you never finish builds dread.", ("any", [("ctx", "pressure", ["High", "Very high"]), ("band", "Stress", 1)])),
    _p("Study in short, focused blocks", "Work for 25-40 minutes with your phone away, then rest for 5-10 minutes. After four blocks take a longer break. Short blocks are easier to start and keep your focus fresher."),
    _p("Prepare for exams without all-nighters", "Start early with a rough plan by topic and marks weightage, practise past papers under timed conditions, and protect your sleep, especially the night before. Sleep helps memory, so an all-nighter usually costs more than it gives.", ("any", [("ctx", "pressure", ["High", "Very high"]), ("band", "Stress", 2)])),
    _p("Ask for help early", "If a subject or deadline feels impossible, tell a faculty mentor, class advisor or a senior sooner rather than later. Most are more understanding than students expect, and extensions or guidance are often possible.", ("any", [("ctx", "pressure", ["High", "Very high"]), ("band", "Stress", 2)])),
    _p("Adopt a 'good enough' rule", "Not every task needs your best effort. Decide in advance which ones deserve 100% and which only need to be done. Perfectionism is a major source of academic stress."),
 ]),
 "connect": ("Connection & support", [
    _p("Have one real conversation a week", "Pick a friend or family member and talk about something real, not just assignments. Feeling understood is one of the strongest protections for mental health."),
    _p("Join something small", "A study group, sports session, club or music jam gives you regular, low-pressure company. You do not need to be outgoing. Showing up is enough."),
    _p("Consider professional support", "A counsellor can teach practical tools for stress, worry and low mood, and most colleges offer this free. You do not need to be in crisis to go, and one conversation can already help.", ("any", [("band", "Depression", 2), ("band", "Anxiety", 2), ("band", "Stress", 2), ("ctx", "support", ["Professional support"])])),
 ]),
}
PLAN_ORDER = ["routine", "sleep", "food", "study", "connect"]
PLAN_NOTE = ("These are general wellbeing ideas for students, not medical advice or a diet plan. If you have a medical condition, allergies, "
             "or worries about eating, please talk to a doctor or dietitian. Try one or two ideas this week rather than everything at once.")

EXAMPLE_ACADEMIC = {
    "title": "Worked example: bringing academic stress down in one week",
    "steps": [
        ("Empty your head (10 minutes, Sunday evening)", "Write down everything pending: assignments, lab records, internals, project reviews, exam topics. Seeing it all on paper is already calming, because the list is usually smaller than the feeling."),
        ("Sort it into four boxes", "Do this week · Schedule for later · Ask for help or an extension · Drop or shrink. Move at least two things out of 'Do this week'. That is allowed."),
        ("Pick three priorities per day", "Break each into tasks of 30-60 minutes. Write them in your timetable like classes."),
        ("Sample day (adjust to your timetable)", "7:00 wake, water, 10 minutes of daylight or a short walk\n8:00 proper breakfast with protein\n9:00-10:30 hardest subject: two 40-minute blocks with a 10-minute break\n11:00-1:00 classes or labs\n1:00 lunch away from your desk, 15 minutes of rest\n2:00-3:30 assignment or record work in two blocks\n4:30 walk, sport or time with friends\n6:00-7:30 lighter revision, one subject\n8:00 dinner, no studying\n9:00 free time, then write tomorrow's top three\n10:30 phone away, wind down, asleep by about 11:00"),
        ("Exam countdown (3 weeks to go)", "Week 1: cover the syllabus by marks weightage. Week 2: revise and do timed past papers. Week 3: strengthen weak topics, keep sleep steady, stop new material 1-2 days before. Night before: light revision, pack your bag, sleep."),
        ("When panic hits", "Pause and breathe in for 4, out for 6, a few times. Then write down just the next 20-minute step and do only that. If you are stuck, message a friend or mentor. Asking is part of studying well."),
        ("Review on Friday (10 minutes)", "What worked? What will you change next week? Reward yourself for effort, not only for results."),
    ],
}

def _cond(when, bands, ctx):
    if when is None: return True
    k = when[0]
    if k == "band": return BANDS.index(bands[when[1]]) >= when[2]
    if k == "ctx": return ctx.get(when[1]) in when[2]
    if k == "any": return any(_cond(w, bands, ctx) for w in when[1])
    return False

def build_plan(bands, ctx, urgent=False):
    """Deterministic lifestyle / sleep / diet / study plan from the latest bands + personalisation answers."""
    ctx = ctx or {}
    top = max(bands, key=lambda k: BANDS.index(bands[k]))
    if BANDS.index(bands[top]) == 0:
        focus = "Your answers show you are coping well right now. This plan is about keeping it that way and building small habits that protect your wellbeing."
    else:
        word = {"Stress": "stress", "Anxiety": "worry and anxiety", "Depression": "low mood"}[top]
        focus = (f"Your answers suggest {word} is asking for the most care right now. The ideas below start with what is most likely to help. "
                 "You do not need to do everything. Try one or two this week and build from there.")
    sections = []
    for key in PLAN_ORDER:
        title, items = PLAN[key]
        chosen = [{"title": i["title"], "text": i["text"]} for i in items if _cond(i["when"], bands, ctx)]
        if chosen: sections.append({"key": key, "title": title, "items": chosen})
    # which section to start with
    if ctx.get("pressure") in ("High", "Very high") or BANDS.index(bands["Stress"]) >= 2: start = "study"
    elif ctx.get("sleep") in ("Poor", "Very poor"): start = "sleep"
    elif BANDS.index(bands["Depression"]) >= 1: start = "routine"
    else: start = None
    for sec in sections: sec["start_here"] = sec["key"] == start
    return {"focus": focus, "sections": sections, "example": EXAMPLE_ACADEMIC,
            "example_relevant": start == "study", "note": PLAN_NOTE, "urgent": urgent}

def plan_to_text(plan, bands=None, created=None):
    out = ["CareCompass - My wellness plan", ""]
    if created: out.append(f"Based on my assessment from {created}")
    if bands: out.append("Levels: " + ", ".join(f"{k}: {v}" for k, v in bands.items()))
    out += ["", plan["focus"], ""]
    for sec in plan["sections"]:
        out.append(sec["title"].upper())
        for i in sec["items"]: out += [f"- {i['title']}: {i['text']}", ""]
    ex = plan["example"]; out.append(ex["title"].upper())
    for n, (t, d) in enumerate(ex["steps"], 1): out += [f"{n}. {t}", d, ""]
    out += [plan["note"], "", "CareCompass is not a diagnostic service. If you need to talk to someone now: Emergency 112, Tele-MANAS 14416."]
    return "\n".join(out)

PLAN_FOCUS = ["Overall wellbeing", "Academic stress", "Sleep", "Low mood and motivation", "Worry and anxiety", "Energy and food"]
PLAN_BAD = re.compile(r"(diagnos\w*|disorder|prescri\w*|medicat\w*|antidepress\w*|supplement\w*|vitamin|\bmg\b|calori\w*|kcal|"
                      r"weight[- ]?loss|lose weight|fasting|detox|cleanse|you have (depression|anxiety|a disorder))", re.I)
PLAN_HEADINGS = ["### Your daily routine", "### Movement and lifestyle", "### Food and drink", "### Easing academic stress", "### Your three small steps this week"]

def generate_ai_plan(bands, ctx, focus, plan, urgent=False):
    """Groq writes a personalised plan, using ONLY the approved ideas in `plan`. Returns markdown or None (reason in LAST_GROQ_ERROR).
    Never called in the urgent safety state. Output is checked; on any doubt the caller shows the approved plan instead."""
    if urgent:
        return None
    ideas = {sec["title"]: [f"{i['title']}: {i['text'][:170]}" for i in sec["items"]] for sec in plan["sections"]}
    payload = {"levels": bands, "daily_habits": ctx or {}, "focus": focus if focus in PLAN_FOCUS else PLAN_FOCUS[0], "approved_ideas": ideas}
    system = ("You are a kind wellbeing coach for college students in India. Using ONLY the approved ideas provided, write a personalised "
              "plan in markdown with exactly these headings, in this order: " + "; ".join(PLAN_HEADINGS) + ". "
              "Be warm, practical and encouraging, in simple language, 350-500 words in total. Give concrete examples (for instance sample meal "
              "ideas using dal, curd, fruit, millets, sprouts, nuts, or a sample study block), and prioritise the given focus. "
              "Rules: do not diagnose or name any condition; do not mention scores; never mention medication, supplements, vitamins, "
              "calories, weight loss, fasting or detox; do not add medical claims; do not change the given levels. Add one short line saying this is "
              "general wellbeing guidance, and that anyone with a health condition or allergy should check with a doctor or dietitian.")
    text = groq_complete([{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload)}],
                         temperature=0.3, max_tokens=2500)
    if not text:
        return None
    if len(text) > 6000 or PLAN_BAD.search(text) or crisis_text(text):
        globals()["LAST_GROQ_ERROR"] = "The AI plan was blocked by the safety filter, so the approved plan is shown instead."; return None
    if sum(h in text for h in PLAN_HEADINGS) < 3:
        globals()["LAST_GROQ_ERROR"] = "The AI plan came back incomplete, so the approved plan is shown instead."; return None
    return text

def fetch_latest_plan_inputs(S):
    """Latest assessment's bands + personalisation answers via a reviewed DB function (private table stays unreadable)."""
    d = api(S, lambda c: c.rpc("get_my_latest_plan_inputs").execute()).data
    return d if isinstance(d, dict) and d.get("bands") else None  # {assessment_id, created_at, bands, context, urgent}

# ============================ v4: WELLBEING SUMMARY FOR PATTERN MINING + VOICE ============================
def fetch_wellbeing_summary(S):
    """v4: last 3 assessments + up to 14 recent check-ins, via get_my_wellbeing_summary() (read-only, RLS-scoped).
    Returns {'assessments': [...], 'checkins': [...]} or None on any non-auth failure.
    No raw responses or raw scores ever leave the database — only bands, context, and an urgent boolean."""
    try:
        d = api(S, lambda c: c.rpc("get_my_wellbeing_summary").execute()).data
        return d if isinstance(d, dict) else None
    except Expired:
        raise                       # keep Expired semantics intact so guarded() can redirect to login
    except Exception:
        return None                 # soft-fail: pattern mining is a UX nicety, never blocks the app

# ============================ SHARED TEXT + HELPERS ============================
LIMITS = ("**CareCompass is not a diagnostic service.** It is a screening-support tool based on the DASS-21 "
          "questionnaire. It cannot replace a doctor or counsellor.")
PRIVACY = ("**Privacy notice (" + NOTICE_VERSION + ")**\n\n- You sign in with your email; we never store your password.\n"
           "- Your answers are saved only if you consent, and only you can read them.\n"
           "- Your history page shows result levels only, not raw answers or scores.\n"
           "- If AI wording is used, your result levels, broad wellbeing patterns, relevant context, and approved suggestions may be sent to Groq; "
           "your email and name are not sent, and raw questionnaire answers are not sent.\n"
           "- The chat companion sends your chat messages to the same AI service; chat messages are not saved.\n"
           "- Your profile (name, age, gender) is optional and visible only to you.\n- You can delete assessments, withdraw consent, or request account deletion at any time.")

def clean_email(e):
    """Strip markdown-link junk from pasted addresses: [a@b.com](mailto:a@b.com) -> a@b.com"""
    e = (e or "").strip()
    m = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", e)
    return m.group(0).lower() if m else e

def date_str(iso): return (iso or "")[:16].replace("T", " ")
def bands_str(b): return " · ".join(f"{k[0]}: {v}" for k, v in b.items())

def init_models():
    global models
    if models is None: models = ModelService()
    return models

def build_result(S):
    """Steps 4-9: score, ML, safety, recommend, explain. Pure function of S (no DB)."""
    raw, bands = score(S["resp"])
    safety = safety_check(S["resp"], bands, S["self_harm"])
    ml = init_models().predict(S["resp"], S["age"], S["gender"]) if init_models().models else {}
    recs = recommend(bands, S["ctx"], safety, S.get("catalog"))
    text, used = explain(bands, recs, S["ctx"], safety)
    S["result"] = {"raw": raw, "bands": bands, "safety": safety, "ml": ml, "recs": recs, "explanation": text, "groq": used}

def selftest():
    assert validate_responses([0] * 21) == [] and validate_responses([0] * 20 + [4])
    raw, b = score([0] * 21); assert b == {"Depression": "Normal", "Anxiety": "Normal", "Stress": "Normal"}
    raw, b = score([3] * 21); assert raw == {"Depression": 42, "Anxiety": 42, "Stress": 42} and set(b.values()) == {"Extremely Severe"}
    r = [0] * 21; r[20] = 2; assert safety_check(r, score(r)[1])["level"] == "urgent"
    assert safety_check([0] * 21, score([0] * 21)[1], True)["level"] == "urgent"
    assert score([1] * 21)[0]["Stress"] == 14 and score([1] * 21)[1]["Stress"] == "Normal"
    s = {"level": "none", "text": ""}; assert all(isinstance(x, dict) for x in recommend(score([2] * 21)[1], {"sleep": "Poor"}, s))
    assert BAD_OUTPUT.search("You have depression") and not BAD_OUTPUT.search("Take a gentle walk.")
    assert clean_email("[a@b.com](mailto:a@b.com)") == "a@b.com"
    assert crisis_text("I want to die") and crisis_text("thinking of ending my life? no: end my life") and not crisis_text("I failed my exam, feeling low")
    assert chat_reply([{"role": "user", "content": "I want to kill myself"}])[1] == "crisis"
    os.environ.pop("GROQ_API_KEY", None); assert chat_reply([{"role": "user", "content": "I feel stressed"}])[1] == "fallback"
    assert CHAT_BAD.search("You have depression") and not CHAT_BAD.search("That sounds hard. Try a slow breath.")
    assert checkin_reply(1, [], "")["show_support"] and not checkin_reply(4, ["Calm"], "")["show_support"] and checkin_reply(3, [], "feel like I want to die")["show_support"]
    n = recommend(score([2] * 21)[1], {"sleep": "Poor", "pressure": "High", "support": "Self-help tools"}, {"level": "none", "text": ""})
    assert 6 <= len(n) <= 12 and all("title" in r for r in n), len(n)
    assert [r["id"] for r in recommend(score([0] * 21)[1], {}, {"level": "none", "text": ""})][:1] != []
    assert [r["id"] for r in recommend(score([3] * 21)[1], {}, {"level": "urgent", "text": ""})] == list(URGENT_IDS)
    hi = lifestyle_indicator({"pressure": "Very high", "sleep": "Very poor", "activity": "Almost never", "screen": "More than 8 hours", "social": "Almost never", "energy": "Very low"})
    lo = lifestyle_indicator({"pressure": "Low", "sleep": "Good", "activity": "Most days", "screen": "Under 3 hours", "social": "Often", "energy": "High"})
    assert all(v["level"] == "Higher" for v in hi.values()), hi
    assert all(v["level"] == "Lower" and not v["drivers"] for v in lo.values()), lo
    assert lifestyle_indicator({})["Stress"]["level"] == "Lower"
    bz = {"Depression": "Moderate", "Anxiety": "Mild", "Stress": "Severe"}
    pl = build_plan(bz, {"sleep": "Poor", "energy": "Low", "pressure": "High", "support": "Not sure"})
    keys = [x["key"] for x in pl["sections"]]; assert keys == PLAN_ORDER and any(x["start_here"] for x in pl["sections"] if x["key"] == "study")
    assert all(len(x["items"]) >= 3 for x in pl["sections"]) and "Download" not in plan_to_text(pl) and len(plan_to_text(pl, bz)) > 3000
    ok = build_plan(score([0] * 21)[1], {}); assert "coping well" in ok["focus"] and len(ok["sections"]) >= 4
    import types, sys as _s
    calls = []
    class _FakeGroq:
        def __init__(self, api_key): self.chat = types.SimpleNamespace(completions=self)
        def create(self, model, **kw):
            calls.append(model)
            if model == "openai/gpt-oss-120b": raise RuntimeError("model_decommissioned")
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="<think>x</think>Hello, how are you feeling today?"))])
    _s.modules["groq"] = types.SimpleNamespace(Groq=_FakeGroq); os.environ["GROQ_API_KEY"] = "k"
    assert chat_reply([{"role": "user", "content": "hi"}]) == ("Hello, how are you feeling today?", "ai") and calls[:2] == ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    del _s.modules["groq"]; os.environ.pop("GROQ_API_KEY", None)
    assert chat_reply([{"role": "user", "content": "hello!"}])[0] == GREETING_REPLY and "GROQ_API_KEY" in LAST_GROQ_ERROR
    # AI plan writer: accepted when complete + clean, rejected when it drifts, never run in the urgent state
    g = globals(); old = g["groq_complete"]
    good = "\n".join(h + "\nTry a steady routine." for h in PLAN_HEADINGS) + "\nThis is general wellbeing guidance; check with a doctor or dietitian for health conditions."
    plan_ = build_plan(bz, {"sleep": "Poor"})
    try:
        g["groq_complete"] = lambda *a, **k: good
        assert generate_ai_plan(bz, {}, "Sleep", plan_) == good and generate_ai_plan(bz, {}, "Sleep", plan_, urgent=True) is None
        g["groq_complete"] = lambda *a, **k: good + " Aim for 1500 calories."
        assert generate_ai_plan(bz, {}, "Sleep", plan_) is None
        g["groq_complete"] = lambda *a, **k: "### Your daily routine\nJust one section."
        assert generate_ai_plan(bz, {}, "Sleep", plan_) is None
    finally:
        g["groq_complete"] = old
    # v4: the new helper must be importable and callable safely without a DB
    assert callable(fetch_wellbeing_summary)
    print("selftest passed")
