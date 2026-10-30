"""FastAPI adapter for the parallel CareCompass web interface.

The existing Streamlit app remains the primary implementation. This API reuses
its deterministic scoring, safety, recommendation, AI, and Supabase functions.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Annotated, Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_project_env() -> None:
    """Load the existing project .env without replacing explicitly set values."""
    try:
        lines = (PROJECT_ROOT / ".env").read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return
    for line in lines:
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry.startswith("export "):
            entry = entry[7:].lstrip()
        key, separator, value = entry.partition("=")
        key = key.strip()
        if not separator or not key or not (key[0].isalpha() or key[0] == "_"):
            continue
        if not all(char.isalnum() or char == "_" for char in key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


_load_project_env()

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import carecompass_core as cc
import carecompass_patterns as cpat


app = FastAPI(title="CareCompass API", version="0.1.0")
allowed_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CARECOMPASS_WEB_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=256)


class EmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class ConsentUpdate(BaseModel):
    consent_type: str
    granted: bool


class AssessmentSubmission(BaseModel):
    responses: list[int] = Field(min_length=21, max_length=21)
    context: dict[str, str]
    self_harm: bool = False


class CheckinSubmission(BaseModel):
    mood: int = Field(ge=1, le=5)
    stress: int = Field(ge=1, le=5)
    anxiety: int = Field(ge=1, le=5)
    energy: int = Field(ge=1, le=5)
    sleep: int = Field(ge=1, le=5)
    feelings: list[str] = Field(default_factory=list, max_length=12)
    note: str = Field(default="", max_length=500)


class ChatRequest(BaseModel):
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)


class PlanRequest(BaseModel):
    focus: str = "Overall wellbeing"


class ProfileUpdate(BaseModel):
    name: str = Field(default="", max_length=60)
    age: int | None = Field(default=None, ge=10, le=100)
    gender: str | None = None


def _http_error(message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail=message)


def _token_reply(response: Any) -> dict[str, Any]:
    session = getattr(response, "session", None)
    user = getattr(response, "user", None)
    if not session or not user:
        return {"confirmation_required": True, "message": "Check your email to confirm your account, then log in."}
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_at": session.expires_at,
        "user": {"id": user.id, "email": user.email},
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "carecompass-api"}


@app.post("/api/auth/signup")
def signup(body: Credentials) -> dict[str, Any]:
    if not cc.db.configured:
        raise _http_error("Supabase is not configured. Add its URL and publishable/anon key to the project .env.", 503)
    email = cc.clean_email(body.email)
    try:
        return _token_reply(cc.db._new().auth.sign_up({"email": email, "password": body.password}))
    except Exception as exc:
        raise _http_error(f"Could not create your account: {str(exc)[:180]}") from exc


@app.post("/api/auth/login")
def login(body: Credentials) -> dict[str, Any]:
    if not cc.db.configured:
        raise _http_error("Supabase is not configured. Add its URL and publishable/anon key to the project .env.", 503)
    email = cc.clean_email(body.email)
    try:
        response = cc.db._new().auth.sign_in_with_password({"email": email, "password": body.password})
        return _token_reply(response)
    except Exception as exc:
        raise _http_error(f"Could not sign in: {str(exc)[:180]}", 401) from exc


@app.post("/api/auth/reset")
def reset_password(body: EmailRequest) -> dict[str, str]:
    if not cc.db.configured:
        raise _http_error("Supabase is not configured.", 503)
    try:
        cc.db.reset(cc.clean_email(body.email))
    except Exception:
        pass
    return {"message": "If that address has an account, a reset link is on its way."}


@app.post("/api/auth/refresh")
def refresh_session(body: dict[str, str]) -> dict[str, Any]:
    refresh_token = (body.get("refresh_token") or "").strip()
    if not refresh_token:
        raise _http_error("Your session has expired. Please log in again.", 401)
    try:
        response = cc.db._new().auth.refresh_session(refresh_token)
        return _token_reply(response)
    except Exception as exc:
        raise _http_error("Your session has expired. Please log in again.", 401) from exc


def current_state(authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _http_error("Please log in to continue.", 401)
    token = authorization[7:].strip()
    if not token:
        raise _http_error("Please log in to continue.", 401)
    try:
        verified = cc.db._new().auth.get_user(token)
        user = verified.user
        state = cc.fresh()
        state.update(token=token, uid=user.id, email=user.email)
        cc.load_consents(state)
        cc.load_profile(state)
        return state
    except Exception as exc:
        raise _http_error("Your session has expired. Please log in again.", 401) from exc


CurrentState = Annotated[dict[str, Any], Depends(current_state)]


@app.get("/api/config")
def config() -> dict[str, Any]:
    context_questions = [
        ("sleep", "How has your sleep been lately?"),
        ("energy", "How has your energy been lately?"),
        ("pressure", "How much academic pressure do you feel?"),
        ("activity", "How often do you do physical activity or exercise?"),
        ("screen", "How much time do you spend on screens each day, outside of study?"),
        ("social", "How often do you spend time with friends or family?"),
        ("support", "What kind of support would you prefer?"),
    ]
    return {
        "assessment_questions": cc.ITEMS,
        "context_questions": [{"key": key, "question": question} for key, question in context_questions],
        "context_options": cc.CTX_OPTIONS,
        "answer_options": [{"value": value, "label": label.split(" - ", 1)[1]} for label, value in cc.CHOICES],
        "feelings": cc.FEELINGS,
        "plan_focus": cc.PLAN_FOCUS,
        "limits": cc.LIMITS,
        "support_lines": cc.SUPPORT_LINES,
        "gender_choices": cc.GENDER_CHOICES,
    }


@app.get("/api/me")
def me(state: CurrentState) -> dict[str, Any]:
    return {
        "user": {"id": state["uid"], "email": state["email"]},
        "profile": {"name": state.get("name"), "age": state.get("age"), "gender": state.get("gender")},
        "consent": state.get("consent", {}),
    }


@app.post("/api/consent")
def update_consent(body: ConsentUpdate, state: CurrentState) -> dict[str, Any]:
    if body.consent_type not in ("assessment", "followup"):
        raise _http_error("That consent choice is not supported.")
    try:
        cc.set_consent(state, body.consent_type, body.granted)
        return {"consent": state["consent"]}
    except Exception as exc:
        raise _http_error("We could not save that consent choice. Please try again.", 503) from exc


@app.post("/api/assessments")
def submit_assessment(body: AssessmentSubmission, state: CurrentState) -> dict[str, Any]:
    if not state.get("consent", {}).get("assessment"):
        raise _http_error("Assessment consent is needed before starting.", 403)
    problems = cc.validate_responses(body.responses)
    if problems:
        raise _http_error("Please answer every assessment question.", 422)
    invalid_context = [key for key, options in cc.CTX_OPTIONS.items()
                       if body.context.get(key) not in options]
    if invalid_context:
        raise _http_error("Please complete each context question.", 422)

    state.update(resp=body.responses, ctx=body.context, self_harm=body.self_harm,
                 catalog=cc.catalog_from_db(state))
    cc.build_result(state)
    result = state["result"]
    try:
        saved = cc.api(state, lambda client: client.rpc("save_assessment", {
            "p_bands": result["bands"], "p_summary": result["explanation"],
            "p_scoring_version": cc.SCORING_VERSION, "p_model_version": cc.init_models().version,
            "p_raw_scores": result["raw"], "p_responses": body.responses,
            "p_context": body.context, "p_model_estimates": result["ml"],
        }).execute()).data
    except Exception as exc:
        raise _http_error("Your result could not be saved. Please try again.", 503) from exc
    if not saved:
        raise _http_error("Your result could not be saved. Please try again.", 503)
    if result["safety"]["level"] != "none":
        cc.log(state, "safety_pathway_shown")
    if not result["groq"]:
        cc.log(state, "groq_fallback")
    cc.log(state, "assessment_saved")
    return {
        "id": saved,
        "bands": result["bands"],
        "safety": result["safety"],
        "explanation": result["explanation"],
        "recommendations": result["recs"],
        "lifestyle": cc.lifestyle_indicator(body.context),
        "groq_used": result["groq"],
        "limits": cc.LIMITS,
        "support_lines": cc.SUPPORT_LINES,
    }


@app.get("/api/history")
def history(state: CurrentState) -> dict[str, Any]:
    try:
        assessments = cc.api(state, lambda client: client.table("carecompass_assessments")
            .select("id,created_at,screening_mode,severity_bands")
            .order("created_at", desc=True).execute()).data
        checkins = cc.api(state, lambda client: client.table("carecompass_followups")
            .select("id,assessment_id,created_at,mood,stress,anxiety,energy,sleep,feelings,note")
            .order("created_at", desc=True).limit(60).execute()).data
        return {"assessments": assessments, "checkins": checkins}
    except Exception as exc:
        raise _http_error("Your history could not be loaded. Please try again.", 503) from exc


@app.post("/api/checkins")
def save_checkin(body: CheckinSubmission, state: CurrentState) -> dict[str, Any]:
    if not state.get("consent", {}).get("followup"):
        raise _http_error("Turn on check-in saving in settings before saving this check-in.", 403)
    if any(feeling not in cc.FEELINGS for feeling in body.feelings):
        raise _http_error("Please choose feelings from the list.", 422)
    try:
        latest = cc.api(state, lambda client: client.table("carecompass_assessments")
            .select("id").order("created_at", desc=True).limit(1).execute()).data
        saved = cc.api(state, lambda client: client.table("carecompass_followups").insert({
            "user_id": state["uid"], "assessment_id": latest[0]["id"] if latest else None,
            "mood": body.mood, "stress": body.stress, "anxiety": body.anxiety,
            "energy": body.energy, "sleep": body.sleep, "feelings": body.feelings or None,
            "note": body.note.strip() or None,
        }).execute()).data
    except Exception as exc:
        raise _http_error("Your check-in was not saved. Please try again.", 503) from exc
    reply = cc.checkin_reply(body.mood, body.feelings, body.note)
    cc.log(state, "followup_saved")
    if reply["show_support"]:
        cc.log(state, "safety_pathway_shown")
    return {"saved": bool(saved), "reply": reply, "support_lines": cc.SUPPORT_LINES}


@app.get("/api/wellbeing-summary")
def wellbeing_summary(state: CurrentState) -> dict[str, Any] | None:
    data = cc.fetch_wellbeing_summary(state)
    if not data:
        return None
    assessments = data.get("assessments") or []
    checkins = data.get("checkins") or []
    if not assessments and not checkins:
        return None
    patterns = cpat.mine_patterns(assessments, checkins)
    return {
        "voice": cpat.voice_preview(assessments, checkins, patterns, state.get("name")),
        "level": patterns["criticality"],
        "assessments": assessments[:3],
        "checkins": checkins[:3],
    }


@app.post("/api/wellbeing-summary/detail")
def wellbeing_summary_detail(state: CurrentState) -> dict[str, Any]:
    data = cc.fetch_wellbeing_summary(state) or {}
    assessments = (data.get("assessments") or [])[:3]
    checkins = (data.get("checkins") or [])[:3]
    patterns = cpat.mine_patterns(assessments, checkins)
    return {
        "summary": cpat.gentle_wellbeing_summary(assessments, checkins, patterns),
        "level": patterns["criticality"],
    }


@app.get("/api/plan")
def plan(state: CurrentState) -> dict[str, Any] | None:
    try:
        inputs = cc.fetch_latest_plan_inputs(state)
        if not inputs:
            return None
        urgent = bool(inputs.get("urgent"))
        result = cc.build_plan(inputs["bands"], inputs.get("context") or {}, urgent)
        return {
            "assessment_id": inputs["assessment_id"],
            "created_at": inputs["created_at"],
            "bands": inputs["bands"],
            "context": inputs.get("context") or {},
            "urgent": urgent,
            "plan": result,
        }
    except Exception as exc:
        raise _http_error("Your plan could not be loaded. Please try again.", 503) from exc


@app.post("/api/plan/ai")
def personalized_plan(body: PlanRequest, state: CurrentState) -> dict[str, str]:
    inputs = cc.fetch_latest_plan_inputs(state)
    if not inputs:
        raise _http_error("Complete an assessment before creating a plan.", 409)
    urgent = bool(inputs.get("urgent"))
    plan_data = cc.build_plan(inputs["bands"], inputs.get("context") or {}, urgent)
    text = cc.generate_ai_plan(inputs["bands"], inputs.get("context") or {},
                               body.focus, plan_data, urgent)
    if not text:
        return {"text": "", "fallback": "true"}
    cc.log(state, "plan_generated")
    return {"text": text, "fallback": "false"}


@app.post("/api/chat")
def chat(body: ChatRequest, state: CurrentState) -> dict[str, str]:
    history = []
    for message in body.history[-12:]:
        role = message.get("role")
        content = (message.get("content") or "")[:1500]
        if role in ("user", "assistant") and content:
            history.append({"role": role, "content": content})
    text, kind = cc.chat_reply(history)
    if kind == "crisis":
        cc.log(state, "chat_crisis_shown")
    return {"text": text, "kind": kind, "support_lines": cc.SUPPORT_LINES}


@app.put("/api/profile")
def update_profile(body: ProfileUpdate, state: CurrentState) -> dict[str, Any]:
    if body.gender is not None and body.gender not in cc.GENDER_CHOICES:
        raise _http_error("Choose one of the listed profile options.", 422)
    try:
        cc.save_profile(state, body.name, body.age, body.gender)
        cc.log(state, "profile_saved")
        return {"name": state.get("name"), "age": state.get("age"), "gender": state.get("gender")}
    except Exception as exc:
        raise _http_error("Your profile was not saved. Please try again.", 503) from exc


@app.delete("/api/assessments/{assessment_id}")
def delete_assessment(assessment_id: str, state: CurrentState) -> dict[str, Any]:
    try:
        deleted = cc.api(state, lambda client: client.rpc("delete_my_assessment", {"p_id": assessment_id}).execute()).data
        if deleted:
            cc.log(state, "assessment_deleted")
        return {"deleted": bool(deleted)}
    except Exception as exc:
        raise _http_error("This record could not be deleted. Please try again.", 503) from exc


@app.delete("/api/assessments")
def delete_all_assessments(state: CurrentState) -> dict[str, Any]:
    try:
        deleted = cc.api(state, lambda client: client.rpc("delete_all_my_assessments").execute()).data
        cc.log(state, "assessment_deleted")
        return {"deleted": deleted or 0}
    except Exception as exc:
        raise _http_error("Your saved assessments could not be deleted. Please try again.", 503) from exc


@app.post("/api/account-deletion")
def request_account_deletion(state: CurrentState) -> dict[str, str]:
    try:
        cc.api(state, lambda client: client.rpc("request_account_deletion").execute())
        cc.log(state, "deletion_requested")
        return {"message": "Your deletion request has been recorded."}
    except Exception as exc:
        raise _http_error("Your deletion request could not be recorded. Please try again.", 503) from exc
