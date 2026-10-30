"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_CARECOMPASS_API_URL || "http://localhost:8000";
const MOOD_WORDS = ["Very low", "Low", "Okay", "Good", "Very good"];
const BAND_ORDER = ["Normal", "Mild", "Moderate", "Severe", "Extremely Severe"];
const SUPPORT_LABELS = {
  low: "Steady",
  moderate: "Some strain",
  high: "A lot to carry",
  urgent: "Reach out for support today",
};

function Icon({ name, size = 19 }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.7, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true };
  const paths = {
    home: <><path d="m3.5 10 8.5-7 8.5 7"/><path d="M5.5 9v11h13V9M9.5 20v-6h5v6"/></>,
    check: <><path d="M12 21s8-3.8 8-10V5l-8-3-8 3v6c0 6.2 8 10 8 10Z"/><path d="m8.5 11.5 2.2 2.2 4.8-5"/></>,
    note: <><path d="M5 3.5h10l4 4V21H5z"/><path d="M14.5 3.5V8H19M8 12h8M8 16h8"/></>,
    history: <><path d="M3.5 12a8.5 8.5 0 1 0 2.3-5.8L3.5 8.5"/><path d="M3.5 4.5v4h4M12 7v5l3.2 2"/></>,
    heart: <path d="M20.4 8.4c0 5-8.4 11-8.4 11s-8.4-6-8.4-11a4.4 4.4 0 0 1 8.4-1.8 4.4 4.4 0 0 1 8.4 1.8Z"/>,
    chat: <><path d="M20 11.5a7.5 7.5 0 0 1-8 7.5 8.9 8.9 0 0 1-3.7-.8L4 20l1.3-3.5A7.1 7.1 0 0 1 4 12c0-4.4 3.6-8 8-8s8 3.1 8 7.5Z"/><path d="M8.5 12h.1m3.4 0h.1m3.4 0h.1"/></>,
    settings: <><circle cx="12" cy="12" r="3.2"/><path d="m19.4 13.5 1.1.9-1.4 2.5-1.4-.5a7.7 7.7 0 0 1-1.5.9l-.2 1.5h-2.9l-.3-1.5a7.7 7.7 0 0 1-1.6-.9l-1.3.5-1.5-2.5 1.2-.9a7 7 0 0 1 0-1.8l-1.2-.9 1.5-2.5 1.3.5a7.7 7.7 0 0 1 1.6-.9l.3-1.5H16l.2 1.5a7.7 7.7 0 0 1 1.5.9l1.4-.5 1.4 2.5-1.1.9a7 7 0 0 1 0 1.8Z" transform="translate(-1.3 -1.2)"/></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
    back: <><path d="M19 12H5m6 6-6-6 6-6"/></>,
    play: <><path d="m8 5 11 7-11 7z"/></>,
    stop: <><rect x="6" y="6" width="12" height="12" rx="2"/></>,
    logout: <><path d="M10 17l5-5-5-5M15 12H3"/><path d="M12 3h7a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-7"/></>,
    spark: <><path d="m12 3 1.3 5.7L19 10l-5.7 1.3L12 17l-1.3-5.7L5 10l5.7-1.3L12 3ZM19 16l.6 2.4L22 19l-2.4.6L19 22l-.6-2.4L16 19l2.4-.6L19 16Z"/></>,
    close: <><path d="m6 6 12 12M18 6 6 18"/></>,
    lock: <><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 1 1 8 0v3"/></>,
    calendar: <><rect x="3.5" y="5" width="17" height="16" rx="2"/><path d="M8 3v4M16 3v4M3.5 10h17"/></>,
  };
  return <svg {...common}>{paths[name] || paths.note}</svg>;
}

function Brand({ compact = false }) {
  return <div className={`brand ${compact ? "brand-compact" : ""}`}>
    <span className="brand-mark" aria-hidden="true"><Icon name="check" size={21} /></span>
    <span><strong>CareCompass</strong>{!compact && <small>your wellbeing, in your own words</small>}</span>
  </div>;
}

function Status({ level }) {
  const map = { none: ["Steady", "good"], elevated: ["Some strain", "warn"], urgent: ["Reach out for support today", "urgent"] };
  const [label, tone] = map[level] || [level || "Your result", "neutral"];
  return <span className={`status status-${tone}`}><i />{label}</span>;
}

function Band({ value }) {
  const index = BAND_ORDER.indexOf(value);
  return <span className={`band band-${index < 0 ? 0 : index}`}>{value}</span>;
}

function formatDate(value) {
  if (!value) return "Recently";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value).replace("T", " ").slice(0, 16) : date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function App() {
  const [screen, setScreen] = useState("auth");
  const [authMode, setAuthMode] = useState("login");
  const [session, setSession] = useState(null);
  const sessionRef = useRef(null);
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState({ name: "", age: "", gender: "" });
  const [consent, setConsent] = useState({});
  const [config, setConfig] = useState(null);
  const [notification, setNotification] = useState(null);
  const [noteVisible, setNoteVisible] = useState(false);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [auth, setAuth] = useState({ email: "", password: "" });
  const [forgot, setForgot] = useState(false);
  const [assessment, setAssessment] = useState([]);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [context, setContext] = useState({});
  const [selfHarm, setSelfHarm] = useState(false);
  const [result, setResult] = useState(null);
  const [checkin, setCheckin] = useState({ mood: 3, stress: 3, anxiety: 3, energy: 3, sleep: 3, feelings: [], note: "" });
  const [checkinReply, setCheckinReply] = useState(null);
  const [history, setHistory] = useState({ assessments: [], checkins: [] });
  const [plan, setPlan] = useState(null);
  const [planFocus, setPlanFocus] = useState("Overall wellbeing");
  const [aiPlan, setAiPlan] = useState("");
  const [chatOkay, setChatOkay] = useState(false);
  const [chat, setChat] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [settingsConfirm, setSettingsConfirm] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);

  const persistSession = useCallback((value) => {
    sessionRef.current = value;
    setSession(value);
    if (value) sessionStorage.setItem("carecompass-session", JSON.stringify(value));
    else sessionStorage.removeItem("carecompass-session");
  }, []);

  const request = useCallback(async (path, options = {}, allowRefresh = true) => {
    const current = sessionRef.current;
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (current?.access_token) headers.Authorization = `Bearer ${current.access_token}`;
    let response;
    try {
      response = await fetch(`${API}${path}`, { ...options, headers });
    } catch {
      throw new Error(`Cannot reach the CareCompass API at ${API}. Start the API service and try again.`);
    }
    if (response.status === 401 && allowRefresh && current?.refresh_token && path !== "/api/auth/refresh") {
      const refreshed = await fetch(`${API}/api/auth/refresh`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: current.refresh_token }),
      });
      if (refreshed.ok) {
        const nextSession = await refreshed.json();
        persistSession(nextSession);
        return request(path, options, false);
      }
      persistSession(null);
      setUser(null);
      setScreen("auth");
    }
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "Something went wrong. Please try again.");
    return payload;
  }, [persistSession]);

  const setRoute = useCallback((next) => {
    if (next !== "home") setNoteVisible(false);
    setScreen(next);
    setMobileNav(false);
    if (typeof window !== "undefined") window.history.replaceState(null, "", `#${next}`);
  }, []);

  const speak = useCallback((text) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window) || !text) {
      setNotice({ kind: "info", text: "Speech playback is not available in this browser. The note is still available to read." });
      return;
    }
    window.speechSynthesis.cancel();
    window.speechSynthesis.resume();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.96;
    utterance.pitch = 1;
    utterance.volume = 1;
    utterance.lang = "en-IN";
    window.speechSynthesis.speak(utterance);
  }, []);

  const loadSummary = useCallback(async (automatic = false) => {
    try {
      const data = await request("/api/wellbeing-summary");
      if (!data?.voice) return null;
      setNotification({ ...data, expanded: false, detail: "" });
      setNoteVisible(true);
      if (automatic) window.setTimeout(() => speak(data.voice), 450);
      return data;
    } catch {
      return null;
    }
  }, [request, speak]);

  const enterApp = useCallback(async (nextSession, initial = false) => {
    persistSession(nextSession);
    setError("");
    setBusy(true);
    try {
      const [me, appConfig] = await Promise.all([request("/api/me"), request("/api/config")]);
      setUser(me.user);
      setProfile({ name: me.profile?.name || "", age: me.profile?.age || "", gender: me.profile?.gender || "" });
      setConsent(me.consent || {});
      setConfig(appConfig);
      const destination = me.consent?.assessment ? "home" : "consent";
      setRoute(destination);
      if (destination === "home") await loadSummary(initial);
    } catch (err) {
      setError(err.message);
      persistSession(null);
    } finally {
      setBusy(false);
    }
  }, [loadSummary, persistSession, request, setRoute]);

  useEffect(() => {
    let mounted = true;
    const restore = async () => {
      const stored = sessionStorage.getItem("carecompass-session");
      if (!stored) return;
      try {
        const saved = JSON.parse(stored);
        if (!mounted || !saved?.access_token) return;
        sessionRef.current = saved;
        setSession(saved);
        const [me, appConfig] = await Promise.all([request("/api/me"), request("/api/config")]);
        if (!mounted) return;
        setUser(me.user);
        setProfile({ name: me.profile?.name || "", age: me.profile?.age || "", gender: me.profile?.gender || "" });
        setConsent(me.consent || {});
        setConfig(appConfig);
        const destination = me.consent?.assessment ? "home" : "consent";
        setScreen(destination);
        if (typeof window !== "undefined") window.history.replaceState(null, "", `#${destination}`);
        if (destination === "home") await loadSummary(true);
      } catch {
        sessionStorage.removeItem("carecompass-session");
        sessionRef.current = null;
      }
    };
    restore();
    return () => { mounted = false; };
  }, [loadSummary, request]);

  const authSubmit = async (event) => {
    event.preventDefault();
    // Unlock browser speech during the user's sign-in gesture. The summary text
    // arrives after the auth/API requests, so the later automatic attempt can
    // otherwise be rejected by browser autoplay rules.
    if (!forgot && "speechSynthesis" in window) window.speechSynthesis.resume();
    setBusy(true); setError(""); setNotice(null);
    try {
      if (forgot) {
        const data = await request("/api/auth/reset", { method: "POST", body: JSON.stringify({ email: auth.email }) }, false);
        setNotice({ kind: "success", text: data.message }); setForgot(false); return;
      }
      const path = authMode === "signup" ? "/api/auth/signup" : "/api/auth/login";
      const data = await request(path, { method: "POST", body: JSON.stringify(auth) }, false);
      if (data.confirmation_required) {
        setAuth({ email: auth.email, password: "" });
        setNotice({ kind: "success", text: data.message }); setAuthMode("login"); return;
      }
      setAuth({ email: "", password: "" });
      await enterApp(data, true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const signOut = () => {
    window.speechSynthesis?.cancel();
    persistSession(null); setUser(null); setNotification(null); setNoteVisible(false);
    setChat([]); setChatOkay(false); setResult(null); setScreen("auth");
    setAuth({ email: "", password: "" }); setAuthMode("login"); setForgot(false);
    setProfile({ name: "", age: "", gender: "" }); setConsent({}); setMobileNav(false);
    window.history.replaceState(null, "", "/");
  };

  const showSummaryAgain = async () => {
    let data = notification;
    if (!data) data = await loadSummary(false);
    if (!data?.voice) {
      setNotice({ kind: "info", text: "Complete an assessment or check-in first so there is something to summarize." });
      return;
    }
    const shortNote = { ...data, expanded: false, detail: "" };
    setNotification(shortNote);
    setNoteVisible(true);
    setRoute("home");
    speak(data.voice);
  };

  const openPage = async (destination) => {
    setError(""); setNotice(null); setRoute(destination);
    if (destination === "history" || destination === "followup") {
      try { setHistory(await request("/api/history")); } catch (err) { setError(err.message); }
    }
    if (destination === "plan") {
      try { setPlan(await request("/api/plan")); setAiPlan(""); } catch (err) { setError(err.message); }
    }
  };

  const grantConsent = async () => {
    setBusy(true); setError("");
    try {
      const assessmentConsent = await request("/api/consent", { method: "POST", body: JSON.stringify({ consent_type: "assessment", granted: true }) });
      const followupConsent = await request("/api/consent", { method: "POST", body: JSON.stringify({ consent_type: "followup", granted: consent.followup === true }) });
      setConsent({ ...assessmentConsent.consent, ...followupConsent.consent });
      setRoute("home");
      await loadSummary(false);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const startAssessment = () => {
    if (!consent.assessment) { setRoute("consent"); return; }
    setAssessment(Array(config?.assessment_questions?.length || 21).fill(null));
    setQuestionIndex(0); setContext({}); setSelfHarm(false); setResult(null); setRoute("assess");
  };

  const answerQuestion = (value) => setAssessment((old) => old.map((answer, index) => index === questionIndex ? value : answer));

  const advanceQuestion = () => {
    if (assessment[questionIndex] === null) { setError("Choose the answer that feels closest before continuing."); return; }
    setError("");
    if (questionIndex < assessment.length - 1) setQuestionIndex((index) => index + 1);
    else setRoute("context");
  };

  const submitAssessment = async () => {
    const missing = Object.entries(config?.context_options || {}).filter(([key, options]) => !options.includes(context[key]));
    if (missing.length) { setError("Please answer each context question before seeing your result."); return; }
    setBusy(true); setError("");
    try {
      const data = await request("/api/assessments", { method: "POST", body: JSON.stringify({ responses: assessment, context, self_harm: selfHarm }) });
      setResult(data); setRoute("results");
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const submitCheckin = async (event) => {
    event.preventDefault(); setBusy(true); setError(""); setCheckinReply(null);
    try {
      const data = await request("/api/checkins", { method: "POST", body: JSON.stringify(checkin) });
      setCheckinReply(data); setCheckin({ mood: 3, stress: 3, anxiety: 3, energy: 3, sleep: 3, feelings: [], note: "" });
      setHistory((old) => ({ ...old, checkins: [] }));
      setNotice({ kind: "success", text: "Your check-in was saved." });
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const sendChat = async (event) => {
    event.preventDefault();
    const prompt = chatInput.trim();
    if (!prompt) return;
    const nextChat = [...chat, { role: "user", content: prompt.slice(0, 1500) }];
    setChat(nextChat); setChatInput(""); setBusy(true); setError("");
    try {
      const data = await request("/api/chat", { method: "POST", body: JSON.stringify({ history: nextChat }) });
      setChat([...nextChat, { role: "assistant", content: data.text, kind: data.kind }]);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const expandSummary = async () => {
    if (!notification) return;
    setBusy(true); setError("");
    try {
      const data = await request("/api/wellbeing-summary/detail", { method: "POST", body: "{}" });
      const expanded = { ...notification, expanded: true, detail: data.summary, detailLevel: data.level };
      setNotification(expanded);
      setNoteVisible(true);
      speak(`${expanded.voice} Support signal: ${SUPPORT_LABELS[data.level] || "Steady"}. ${expanded.detail}`);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const saveProfile = async (event) => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const data = await request("/api/profile", { method: "PUT", body: JSON.stringify({ ...profile, age: profile.age === "" ? null : Number(profile.age) }) });
      setProfile({ ...data, name: data.name || "", age: data.age || "", gender: data.gender || "" });
      setNotice({ kind: "success", text: "Your profile has been saved." });
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const updateFollowupConsent = async (value) => {
    setBusy(true); setError("");
    try {
      const data = await request("/api/consent", { method: "POST", body: JSON.stringify({ consent_type: "followup", granted: value }) });
      setConsent(data.consent); setNotice({ kind: "success", text: "Your check-in preference has been updated." });
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const withdrawAssessmentConsent = async () => {
    if (!window.confirm("Withdraw assessment consent? New assessments and saved check-ins will stop until you consent again.")) return;
    setBusy(true); setError("");
    try {
      const first = await request("/api/consent", { method: "POST", body: JSON.stringify({ consent_type: "assessment", granted: false }) });
      const second = await request("/api/consent", { method: "POST", body: JSON.stringify({ consent_type: "followup", granted: false }) });
      setConsent({ ...first.consent, ...second.consent });
      setNotice({ kind: "success", text: "Assessment and check-in consent have been withdrawn." });
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const askDelete = async () => {
    if (!settingsConfirm) { setSettingsConfirm(true); return; }
    setBusy(true); setError("");
    try {
      const data = await request("/api/assessments", { method: "DELETE" });
      setNotice({ kind: "success", text: `Deleted ${data.deleted} saved assessment(s) and their linked check-ins.` });
      setSettingsConfirm(false); setHistory({ assessments: [], checkins: [] });
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  const navItems = useMemo(() => [
    { id: "home", label: "Home", icon: "home" },
    { id: "assess", label: "Weekly assessment", icon: "check" },
    { id: "plan", label: "My wellbeing plan", icon: "note" },
    { id: "followup", label: "Check in", icon: "heart" },
    { id: "chat", label: "Chat companion", icon: "chat" },
    { id: "history", label: "History", icon: "history" },
    { id: "settings", label: "Profile and settings", icon: "settings" },
  ], []);

  const renderNotification = () => notification && noteVisible && <section className="push-note" aria-label="Your wellbeing voice note">
    <div className="push-note-copy">
      <Status level={notification.level === "high" ? "elevated" : notification.level} />
      <p>{notification.voice}</p>
      <div className="note-controls">
        <button className="button button-voice" onClick={() => speak(notification.expanded ? `${notification.voice} Support signal: ${SUPPORT_LABELS[notification.detailLevel] || "Steady"}. ${notification.detail}` : notification.voice)}><Icon name="play" size={16} />{notification.expanded ? "Play full voice note" : "Play voice summary"}</button>
        <button className="button button-quiet" onClick={() => window.speechSynthesis?.cancel()}><Icon name="stop" size={16} />Stop</button>
      </div>
      <p className="privacy-inline">The greeting stays on this device. Groq receives category summaries, not your name or written check-in notes.</p>
    </div>
    {!notification.expanded ? <button className="button button-outline push-continue" onClick={expandSummary} disabled={busy}><span>{busy ? "Preparing your summary…" : "Continue to my detailed wellbeing summary"}</span><Icon name="arrow" size={17} /></button> : <div className="push-detail">
      <div className="detail-heading"><span className="section-label">A little more about your recent record</span><Status level={notification.detailLevel === "high" ? "elevated" : notification.detailLevel} /></div>
      <p>{notification.detail}</p>
      <small>This screening reflects recent answers. It is not a diagnosis.</small>
    </div>}
  </section>;

  const renderAuth = () => <main className="auth-stage">
    <div className="auth-side">
      <Brand />
      <div className="auth-message">
        <span className="section-label">A quieter way to notice</span>
        <h1>Make room for how you feel.</h1>
        <p>CareCompass is a private place to check in, reflect on recent patterns, and choose a gentle next step.</p>
        <div className="auth-note"><Icon name="lock" size={18} /><span>Your answers belong to you. This is a screening-support tool, not a diagnosis.</span></div>
      </div>
      <div className="auth-footer">Small observations can make a meaningful record.</div>
    </div>
    <section className="auth-form-wrap">
      <form className="auth-form" onSubmit={authSubmit}>
        <span className="section-label">{forgot ? "Account recovery" : authMode === "signup" ? "A place to begin" : "Welcome back"}</span>
        <h2>{forgot ? "Reset your password" : authMode === "signup" ? "Create your account" : "Sign in to your space"}</h2>
        <p className="muted">{forgot ? "We’ll send a reset link if an account matches this email." : "Your saved history and preferences are available after you sign in."}</p>
        {notice && <div className={`notice notice-${notice.kind}`}>{notice.text}</div>}
        {error && <div className="notice notice-error" role="alert">{error}</div>}
        <label>Email address<input type="email" autoComplete="email" required value={auth.email} onChange={(e) => setAuth({ ...auth, email: e.target.value })} /></label>
        {!forgot && <label>Password<input type="password" autoComplete={authMode === "signup" ? "new-password" : "current-password"} required minLength={8} value={auth.password} onChange={(e) => setAuth({ ...auth, password: e.target.value })} /></label>}
        <button className="button button-primary auth-submit" disabled={busy}>{busy ? "Please wait…" : forgot ? "Send reset link" : authMode === "signup" ? "Create account" : "Log in"}<Icon name="arrow" size={17} /></button>
        {!forgot && authMode === "login" && <button type="button" className="text-button forgot-link" onClick={() => { setForgot(true); setError(""); }}>Forgot password?</button>}
        <div className="auth-switch">{forgot ? <button type="button" className="text-button" onClick={() => setForgot(false)}>Back to sign in</button> : <>{authMode === "login" ? "New to CareCompass?" : "Already have an account?"} <button type="button" className="text-button" onClick={() => { setAuthMode(authMode === "login" ? "signup" : "login"); setError(""); }}>{authMode === "login" ? "Create an account" : "Log in"}</button></>}</div>
        <small className="auth-disclaimer">CareCompass supports reflection and screening. It does not replace care from a doctor or counsellor.</small>
      </form>
    </section>
  </main>;

  const renderConsent = () => <section className="onboard-wrap">
    <span className="section-label">Before you begin</span><h1>Choose how your information is used.</h1>
    <p className="lead">You can change these choices later in Profile and settings.</p>
    {error && <div className="notice notice-error">{error}</div>}
    <div className="consent-panel"><div className="consent-icon"><Icon name="check" size={20}/></div><div><strong>Assessment and saved results</strong><p>Your answers are processed using fixed scoring rules and saved privately to your account so you can revisit result categories.</p><label className="check-row"><input type="checkbox" checked={consent.assessmentDraft || false} onChange={(e) => setConsent({ ...consent, assessmentDraft: e.target.checked })}/><span>I agree to complete the questionnaire and have my results processed and saved.</span></label></div></div>
    <div className="consent-panel"><div className="consent-icon"><Icon name="history" size={20}/></div><div><strong>Optional follow-up check-ins</strong><p>Save brief check-ins to notice how your days have felt over time.</p><label className="check-row"><input type="checkbox" checked={consent.followupDraft || false} onChange={(e) => setConsent({ ...consent, followupDraft: e.target.checked })}/><span>I would like to save voluntary follow-up check-ins.</span></label></div></div>
    <p className="privacy-note">If AI wording is used, result categories, broad wellbeing patterns, relevant context, or approved suggestions may be sent to Groq. Your email, name, and raw questionnaire answers are not sent.</p>
    <div className="button-row"><button className="button button-primary" disabled={busy || !consent.assessmentDraft} onClick={grantConsent}>{busy ? "Saving choices…" : "Continue"}<Icon name="arrow" size={17}/></button><button className="button button-outline" onClick={signOut}>Leave without starting</button></div>
  </section>;

  const renderHome = () => <>
    <div className="home-heading"><div><span className="section-label">Your field notes</span><h1>{profile.name ? `Good to see you, ${profile.name.split(" ")[0]}.` : "A moment to check in."}</h1><p className="lead">A personal space to notice how the week has been, in your own words.</p></div><div className="date-mark"><Icon name="calendar" size={17}/><span>{new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}</span></div></div>
    {renderNotification()}
    {notice && <div className={`notice notice-${notice.kind}`}>{notice.text}</div>}{error && <div className="notice notice-error">{error}</div>}
    <section className="home-start">
      <div className="start-copy"><span className="section-label">A gentle starting point</span><h2>How has the past week felt?</h2><p>A 21-question check-in. Your result is based on fixed scoring rules and is not a diagnosis.</p><button className="button button-primary" onClick={startAssessment}>Start weekly assessment<Icon name="arrow" size={17}/></button></div>
      <div className="week-paper" aria-label="A calm illustrated week"><div className="paper-top"><span>NOTES ON THE WEEK</span><span>01 — 07</span></div><div className="paper-lines"><i/><i/><i/><i/><i/></div><div className="paper-stamp"><Icon name="heart" size={22}/><span>Start where<br/>you are</span></div></div>
    </section>
    <div className="section-title-row"><div><span className="section-label">Your space</span><h2>Choose a small next step</h2></div></div>
    <div className="home-grid">
      <button className="home-link" onClick={() => openPage("followup")}><span className="home-link-icon"><Icon name="heart"/></span><span><strong>Check in</strong><small>Record how today feels, right now.</small></span><Icon name="arrow" size={17}/></button>
      <button className="home-link" onClick={() => openPage("history")}><span className="home-link-icon"><Icon name="history"/></span><span><strong>Look back</strong><small>Revisit dated observations and results.</small></span><Icon name="arrow" size={17}/></button>
      <button className="home-link" onClick={() => openPage("plan")}><span className="home-link-icon"><Icon name="note"/></span><span><strong>Open your plan</strong><small>Explore general ideas that may fit.</small></span><Icon name="arrow" size={17}/></button>
      <button className="home-link" onClick={() => openPage("chat")}><span className="home-link-icon"><Icon name="chat"/></span><span><strong>Talk things through</strong><small>A supportive AI companion, with limits.</small></span><Icon name="arrow" size={17}/></button>
    </div>
    <p className="limits-line">{config?.limits?.replaceAll("**", "")}</p>
  </>;

  const renderAssessment = () => {
    if (!config) return <Loading />;
    const question = config.assessment_questions[questionIndex];
    const progress = ((questionIndex + 1) / config.assessment_questions.length) * 100;
    return <>
      <div className="page-heading"><span className="section-label">Weekly assessment</span><h1>Take this one question at a time.</h1><p className="lead">Think about how each statement applied to you over the past week.</p></div>
      <div className="assessment-progress"><div className="progress-meta"><span>Question {questionIndex + 1} of {config.assessment_questions.length}</span><span>{Math.round(progress)}%</span></div><div className="progress-track"><i style={{ width: `${progress}%` }}/></div></div>
      <section className="question-sheet"><div className="question-index">{String(questionIndex + 1).padStart(2, "0")}</div><h2>{question}</h2><p>Choose the response that feels closest to your experience.</p><div className="answer-list">{config.answer_options.map((option) => <button key={option.value} className={`answer-option ${assessment[questionIndex] === option.value ? "selected" : ""}`} onClick={() => answerQuestion(option.value)}><span className="answer-radio">{assessment[questionIndex] === option.value && <i/>}</span><span>{option.label}</span></button>)}</div>
        {error && <div className="notice notice-error">{error}</div>}<div className="button-row question-actions"><button className="button button-outline" onClick={() => questionIndex === 0 ? setRoute("home") : setQuestionIndex((index) => index - 1)}><Icon name="back" size={17}/>{questionIndex === 0 ? "Exit assessment" : "Back"}</button><button className="button button-primary" onClick={advanceQuestion}>{questionIndex === config.assessment_questions.length - 1 ? "Continue to context" : "Next question"}<Icon name="arrow" size={17}/></button></div>
      </section><p className="assessment-note">Your result is calculated with fixed DASS-21 scoring rules. CareCompass is not a diagnostic service.</p>
    </>;
  };

  const renderContext = () => <>
    <div className="page-heading"><span className="section-label">A little more context</span><h1>What has been shaping your week?</h1><p className="lead">These answers help tailor general suggestions. They do not change your assessment result.</p></div>
    <div className="context-form">{config?.context_questions?.map(({ key, question }, index) => <fieldset className="context-field" key={key}><legend><span>{String(index + 1).padStart(2, "0")}</span>{question}</legend><div className="context-options">{config.context_options[key].map((option) => <button type="button" key={option} className={`context-option ${context[key] === option ? "selected" : ""}`} onClick={() => setContext({ ...context, [key]: option })}>{option}</button>)}</div></fieldset>)}
      <label className="check-row safety-check"><input type="checkbox" checked={selfHarm} onChange={(e) => setSelfHarm(e.target.checked)}/><span>I have had thoughts of harming myself recently</span></label>
      {error && <div className="notice notice-error">{error}</div>}<div className="button-row"><button className="button button-outline" onClick={() => setRoute("assess")}><Icon name="back" size={17}/>Back to assessment</button><button className="button button-primary" disabled={busy} onClick={submitAssessment}>{busy ? "Preparing your result…" : "See my results"}<Icon name="arrow" size={17}/></button></div>
    </div>
  </>;

  const renderResults = () => result && <>
    <div className="page-heading"><span className="section-label">Your latest reflection</span><h1>Your results, held gently.</h1><p className="lead">Based on your answers for the past week. This screening result is not a diagnosis.</p></div>
    {result.safety?.text && <div className={`support-alert ${result.safety.level === "urgent" ? "urgent" : "elevated"}`}><Status level={result.safety.level}/><p>{result.safety.text.replaceAll("**", "").replaceAll("###", "")}</p><p>{config?.support_lines?.replaceAll("**", "")}</p></div>}
    <section className="result-paper"><div className="result-paper-head"><div><span className="section-label">Screening categories</span><h2>How the past week showed up</h2></div><Status level={result.safety?.level}/></div><div className="result-bands">{Object.entries(result.bands || {}).map(([area, band]) => <div className="result-band-row" key={area}><span>{area}</span><Band value={band}/></div>)}</div><p className="result-explanation">{result.explanation}</p><div className="non-diagnostic-note"><Icon name="note" size={17}/><span>These categories are a screening reflection, not a diagnosis or a prediction of what comes next.</span></div></section>
    <div className="section-title-row"><div><span className="section-label">Small next steps</span><h2>Suggestions for you</h2></div></div>
    <div className="recommendation-list">{(result.recommendations || []).slice(0, 3).map((item, index) => <article key={item.id || index} className="recommendation"><div className="recommendation-no">{String(index + 1).padStart(2, "0")}</div><div><h3>{item.title || "A small idea to consider"}</h3><p>{item.text}</p></div></article>)}</div>
    <div className="button-row result-actions"><button className="button button-primary" onClick={() => openPage("plan")}>Get my wellbeing plan<Icon name="arrow" size={17}/></button><button className="button button-outline" onClick={() => openPage("history")}>View history</button><button className="button button-outline" onClick={() => setRoute("home")}>Back to home</button></div>
  </>;

  const renderCheckin = () => <>
    <div className="page-heading"><span className="section-label">A dated observation</span><h1>How are you feeling right now?</h1><p className="lead">A private record of how today feels. It is not a diagnosis.</p></div>
    {!consent.followup && <section className="consent-panel"><div className="consent-icon"><Icon name="history"/></div><div><strong>Saving check-ins is turned off.</strong><p>Turn it on to keep a private record you can look back on.</p><button className="button button-outline" onClick={() => updateFollowupConsent(true)}>Turn on check-in saving<Icon name="arrow" size={16}/></button></div></section>}
    {checkinReply && <div className={`support-alert ${checkinReply.reply?.show_support ? "elevated" : "steady"}`}><p>{checkinReply.reply?.text}</p>{checkinReply.reply?.show_support && <p>{checkinReply.support_lines?.replaceAll("**", "")}</p>}</div>}
    <form className="checkin-sheet" onSubmit={submitCheckin}>
      <fieldset><legend>Overall, how are you feeling today?</legend><div className="mood-options">{MOOD_WORDS.map((word, index) => <button type="button" key={word} className={`mood-option ${checkin.mood === index + 1 ? "selected" : ""}`} onClick={() => setCheckin({ ...checkin, mood: index + 1 })}><span className="mood-dot">{checkin.mood === index + 1 && <i/>}</span>{word}</button>)}</div></fieldset>
      <fieldset><legend>Which words fit best? <small>Optional</small></legend><div className="feeling-options">{(config?.feelings || []).map((word) => <button type="button" key={word} className={`feeling-chip ${checkin.feelings.includes(word) ? "selected" : ""}`} onClick={() => setCheckin({ ...checkin, feelings: checkin.feelings.includes(word) ? checkin.feelings.filter((item) => item !== word) : [...checkin.feelings, word] })}>{word}</button>)}</div></fieldset>
      <div className="range-grid">{[["stress", "Stress right now", ["Calm", "Very stressed"]], ["anxiety", "Anxiety right now", ["Calm", "Very anxious"]], ["energy", "Energy right now", ["Very low", "High"]], ["sleep", "Sleep last night", ["Poor", "Great"]]].map(([key, label, bounds]) => <label className="range-field" key={key}><span>{label}</span><input type="range" min="1" max="5" value={checkin[key]} disabled={!consent.followup} onChange={(e) => setCheckin({ ...checkin, [key]: Number(e.target.value) })}/><span className="range-labels"><small>{bounds[0]}</small><small>{bounds[1]}</small></span></label>)}</div>
      <label className="field-label">Anything you would like to add? <span>Optional · up to 500 characters</span><textarea rows="3" maxLength="500" value={checkin.note} disabled={!consent.followup} onChange={(e) => setCheckin({ ...checkin, note: e.target.value })} placeholder="A few words for your own record"/></label>
      {error && <div className="notice notice-error">{error}</div>}<button className="button button-primary" disabled={busy || !consent.followup}>{busy ? "Saving…" : "Save my check-in"}<Icon name="arrow" size={17}/></button>
    </form>
    <section className="recent-record"><div className="section-title-row"><div><span className="section-label">Your history</span><h2>Recent check-ins</h2></div><button className="text-button" onClick={() => openPage("history")}>Open full history<Icon name="arrow" size={15}/></button></div>{history.checkins?.slice(0, 3).map((row) => <div className="observation-row" key={row.id || row.created_at}><time>{formatDate(row.created_at)}</time><span>Mood · {MOOD_WORDS[(row.mood || 3) - 1]}</span>{row.feelings?.length > 0 && <small>{row.feelings.slice(0, 3).join(" · ")}</small>}</div>)}</section>
  </>;

  const renderHistory = () => <>
    <div className="page-heading"><span className="section-label">Your field notes</span><h1>A record of your recent weeks.</h1><p className="lead">Screening categories and check-ins, kept in date order. A simple comparison, not a diagnosis or a measure of progress.</p></div>
    {error && <div className="notice notice-error">{error}</div>}
    {!history.assessments?.length && !history.checkins?.length ? <div className="empty-paper"><Icon name="history" size={23}/><h2>Your record will grow here.</h2><p>After your first assessment or check-in, you can return to these dated observations.</p></div> : <>
      {history.assessments?.length > 0 && <section className="history-section"><div className="section-title-row"><div><span className="section-label">Screening observations</span><h2>Recent result categories</h2></div></div><div className="history-table"><div className="history-table-head"><span>Date</span><span>Depression</span><span>Anxiety</span><span>Stress</span><span>Type</span><span/></div>{history.assessments.map((row) => <div className="history-table-row" key={row.id}><time>{formatDate(row.created_at)}</time><Band value={row.severity_bands?.Depression}/><Band value={row.severity_bands?.Anxiety}/><Band value={row.severity_bands?.Stress}/><span>{row.screening_mode || "Full assessment"}</span><button className="text-button danger-text" onClick={() => deleteRecord(row.id)}>Delete</button></div>)}</div></section>}
      {history.checkins?.length > 0 && <section className="history-section"><div className="section-title-row"><div><span className="section-label">Personal observations</span><h2>Recent check-ins</h2></div></div><div className="history-list">{history.checkins.map((row) => <article className="history-entry" key={row.id || row.created_at}><div className="history-entry-date"><time>{formatDate(row.created_at)}</time><span>Mood · {MOOD_WORDS[(row.mood || 3) - 1]}</span></div><div className="history-entry-metrics"><span>Stress <b>{row.stress ?? "—"}</b></span><span>Anxiety <b>{row.anxiety ?? "—"}</b></span><span>Energy <b>{row.energy ?? "—"}</b></span><span>Sleep <b>{row.sleep ?? "—"}</b></span></div>{row.feelings?.length > 0 && <p className="entry-feelings">{row.feelings.join(" · ")}</p>}{row.note && <p className="entry-note">{row.note}</p>}</article>)}</div></section>}
    </>}
  </>;

  async function deleteRecord(id) {
    if (!window.confirm("Delete this saved assessment and its linked check-ins? This cannot be undone.")) return;
    try { await request(`/api/assessments/${encodeURIComponent(id)}`, { method: "DELETE" }); setHistory((old) => ({ ...old, assessments: old.assessments.filter((row) => row.id !== id), checkins: old.checkins.filter((row) => row.assessment_id !== id) })); }
    catch (err) { setError(err.message); }
  }

  const renderPlan = () => <>
    <div className="page-heading"><span className="section-label">A plan that can flex</span><h1>Small ideas for a steadier week.</h1><p className="lead">General wellbeing guidance based on your most recent assessment. Try one or two ideas; you do not need to do everything.</p></div>
    {error && <div className="notice notice-error">{error}</div>}
    {!plan ? <div className="empty-paper"><Icon name="note" size={23}/><h2>Your plan will appear here.</h2><p>Complete an assessment first, then come back for a set of general ideas shaped around your answers.</p><button className="button button-outline" onClick={startAssessment}>Start an assessment<Icon name="arrow" size={17}/></button></div> : <>
      <section className="plan-intro"><div><span className="section-label">Based on {formatDate(plan.created_at)}</span><h2>{plan.plan.focus}</h2><p>{plan.plan.note}</p></div><div className="plan-result-levels">{Object.entries(plan.bands || {}).map(([key, value]) => <div key={key}><span>{key}</span><Band value={value}/></div>)}</div></section>
      {plan.urgent && <div className="support-alert urgent"><strong>Support deserves to come first.</strong><p>Please consider reaching out to someone today. You do not have to carry this alone.</p><p>{config?.support_lines?.replaceAll("**", "")}</p></div>}
      <div className="plan-sections">{plan.plan.sections?.map((section) => <details className="plan-section" key={section.key} open={section.start_here}><summary><span>{section.title}</span><span>{section.start_here ? "A place to begin" : "Explore"}</span></summary><div className="plan-items">{section.items.map((item) => <article key={item.title}><h3>{item.title}</h3><p>{item.text}</p></article>)}</div></details>)}</div>
      {plan.urgent ? <section className="personal-plan plan-ai-paused"><span className="section-label">AI personalization paused</span><h2>Your approved plan is ready.</h2><p>The plan above is already shaped by your latest assessment. Because your results call for support to come first, the AI-written version stays paused and the approved guidance remains unchanged.</p><p className="small-note">Please start with the support options above and consider reaching out to someone you trust today.</p></section> : <section className="personal-plan"><div className="section-title-row"><div><span className="section-label">A little more personal</span><h2>What would you like support with?</h2></div></div><div className="focus-row"><select value={planFocus} onChange={(e) => setPlanFocus(e.target.value)}>{(config?.plan_focus || []).map((focus) => <option key={focus}>{focus}</option>)}</select><button className="button button-primary" disabled={busy} onClick={generatePlan}>{busy ? "Writing…" : "Write a personalized plan"}<Icon name="arrow" size={17}/></button></div>{aiPlan && <div className="ai-plan">{aiPlan.split("\n").map((line, index) => line.startsWith("###") ? <h3 key={index}>{line.replace(/^#+\s*/, "")}</h3> : line.trim() ? <p key={index}>{line}</p> : null)}</div>}<p className="small-note">AI wording uses Groq and follows approved suggestions. Urgent support guidance stays fixed.</p></section>}
      <a className="download-link" href={`${API}/api/plan`} onClick={(e) => { e.preventDefault(); downloadPlan(); }}>Download my plan as text<Icon name="arrow" size={16}/></a>
    </>}
  </>;

  async function generatePlan() {
    setBusy(true); setError(""); setAiPlan("");
    try { const data = await request("/api/plan/ai", { method: "POST", body: JSON.stringify({ focus: planFocus }) }); if (data.text) setAiPlan(data.text); else setError("The personalized wording was unavailable just now. Use the approved ideas above instead."); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function downloadPlan() {
    if (!plan) return;
    const sections = (plan.plan.sections || []).map((section) => `${section.title}\n${section.items.map((item) => `- ${item.title}: ${item.text}`).join("\n")}`).join("\n\n");
    const content = `CareCompass — My wellbeing plan\nBased on ${formatDate(plan.created_at)}\n\n${plan.plan.focus}\n\n${sections}\n\n${plan.plan.note}\n\nCareCompass is not a diagnostic service.`;
    const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = "my-wellbeing-plan.txt"; link.click(); URL.revokeObjectURL(url);
  }

  const renderChat = () => <>
    <div className="page-heading"><span className="section-label">A listening space</span><h1>Talk it through, at your pace.</h1><p className="lead">A supportive AI companion can help you put feelings into words. It is not a therapist, doctor, or person.</p></div>
    <div className="chat-privacy"><Icon name="lock" size={17}/><span>Your messages are sent to Groq to write replies and are not saved in your account. If you may be in immediate danger, contact emergency support.</span></div>
    <label className="check-row chat-consent"><input type="checkbox" checked={chatOkay} onChange={(e) => setChatOkay(e.target.checked)}/><span>I understand how this conversation works.</span></label>
    {chatOkay && <section className="chat-window"><div className="chat-messages">{chat.length === 0 && <div className="chat-welcome"><span className="chat-mark"><Icon name="chat" size={21}/></span><h2>There is no rush.</h2><p>How are you feeling today? Share as much or as little as you like.</p></div>}{chat.map((message, index) => <article className={`chat-bubble ${message.role}`} key={`${index}-${message.content.slice(0, 12)}`}><small>{message.role === "assistant" ? "CareCompass companion" : "You"}</small><p>{message.content}</p>{message.kind === "crisis" && <p className="chat-support">{config?.support_lines?.replaceAll("**", "")}</p>}</article>)}{busy && <div className="chat-bubble assistant"><small>CareCompass companion</small><p className="typing">Taking a moment to respond…</p></div>}</div><form className="chat-compose" onSubmit={sendChat}><textarea rows="2" maxLength="1500" value={chatInput} onChange={(e) => setChatInput(e.target.value)} placeholder="Write what is on your mind…"/><button className="button button-primary" disabled={busy || !chatInput.trim()}>Send<Icon name="arrow" size={16}/></button></form><div className="chat-footer"><span>Responses may be imperfect. You deserve support from a real person too.</span><button className="text-button" onClick={() => setChat([])}>Clear conversation</button></div></section>}
  </>;

  const renderSettings = () => <>
    <div className="page-heading"><span className="section-label">Your choices</span><h1>Profile and privacy.</h1><p className="lead">Manage what is saved and how you use CareCompass.</p></div>
    {notice && <div className={`notice notice-${notice.kind}`}>{notice.text}</div>}{error && <div className="notice notice-error">{error}</div>}
    <section className="settings-section"><div className="settings-copy"><h2>Your profile</h2><p>Only you can see your saved profile details.</p></div><form className="settings-panel" onSubmit={saveProfile}><label className="field-label">Name <span>Optional</span><input maxLength="60" value={profile.name} onChange={(e) => setProfile({ ...profile, name: e.target.value })}/></label><div className="settings-row"><label className="field-label">Age<input type="number" min="10" max="100" value={profile.age} onChange={(e) => setProfile({ ...profile, age: e.target.value })}/></label><label className="field-label">Gender<select value={profile.gender} onChange={(e) => setProfile({ ...profile, gender: e.target.value })}><option value="">Choose an option</option>{(config?.gender_choices || []).map((choice) => <option key={choice}>{choice}</option>)}</select></label></div><button className="button button-primary" disabled={busy}>Save profile<Icon name="check" size={16}/></button></form></section>
    <section className="settings-section"><div className="settings-copy"><h2>Privacy and consent</h2><p>Your choices stay under your control.</p></div><div className="settings-panel"><div className="consent-status"><span>Assessment and saved results</span><Status level={consent.assessment ? "none" : "elevated"}/></div><div className="consent-status"><span>Voluntary check-ins</span><label className="switch-control"><input type="checkbox" checked={!!consent.followup} onChange={(e) => updateFollowupConsent(e.target.checked)}/><span className="switch-track"/><small>{consent.followup ? "On" : "Off"}</small></label></div><p className="small-note">AI wording may use result categories, broad wellbeing patterns, relevant context, and approved suggestions. Your email and name are not sent to Groq.</p><div className="account-address"><span>Signed in as</span><strong>{user?.email}</strong></div>{consent.assessment && <button className="text-button danger-text" onClick={withdrawAssessmentConsent} disabled={busy}>Withdraw assessment consent</button>}</div></section>
    <section className="settings-section danger-section"><div className="settings-copy"><h2>Delete saved assessments</h2><p>This action permanently removes your assessment history and linked check-ins.</p></div><div className="settings-panel"><p>Deleting saved history cannot be undone.</p><button className={`button ${settingsConfirm ? "button-danger" : "button-outline"}`} onClick={askDelete} disabled={busy}>{settingsConfirm ? "Confirm delete all my assessments" : "Delete all my assessments"}</button>{settingsConfirm && <button className="text-button" onClick={() => setSettingsConfirm(false)}>Cancel</button>}</div></section>
    <section className="settings-section danger-section"><div className="settings-copy"><h2>Request account removal</h2><p>Your request is recorded for an administrator to process.</p></div><div className="settings-panel"><button className="button button-outline" onClick={requestAccountDeletion}>Request account deletion</button></div></section>
    <div className="settings-bottom"><span>CareCompass is a screening-support tool, not a diagnostic service.</span><button className="button button-quiet" onClick={signOut}><Icon name="logout" size={17}/>Sign out</button></div>
  </>;

  async function requestAccountDeletion() {
    if (!window.confirm("Record a request to remove your CareCompass account? An administrator will process it.")) return;
    try { const data = await request("/api/account-deletion", { method: "POST", body: "{}" }); setNotice({ kind: "success", text: data.message }); }
    catch (err) { setError(err.message); }
  }

  if (!session || !user) return renderAuth();
  if (screen === "consent") return <div className="consent-shell"><header className="simple-top"><Brand compact/><button className="text-button" onClick={signOut}><Icon name="logout" size={16}/>Sign out</button></header>{renderConsent()}</div>;

  const content = {
    home: renderHome,
    assess: renderAssessment,
    context: renderContext,
    results: renderResults,
    plan: renderPlan,
    followup: renderCheckin,
    history: renderHistory,
    chat: renderChat,
    settings: renderSettings,
  }[screen] || renderHome;

  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
      <Brand />
      <div className="side-group-label">Your space</div>
      <nav className="side-nav" aria-label="Main navigation">{navItems.map((item) => <button key={item.id} className={`side-nav-item ${screen === item.id || (["context", "results"].includes(screen) && item.id === "assess") ? "active" : ""}`} onClick={() => item.id === "assess" ? startAssessment() : openPage(item.id)}><Icon name={item.icon}/><span>{item.label}</span></button>)}<button className="side-nav-item side-signout" onClick={signOut}><Icon name="logout"/><span>Sign out</span></button></nav>
      <div className="sidebar-spacer"/>
      <button className="side-nav-item voice-nav" onClick={showSummaryAgain}><Icon name="play"/><span>Hear my summary</span></button>
      <div className="side-user"><span className="user-mark">{(profile.name || user.email || "C").slice(0, 1).toUpperCase()}</span><span><strong>{profile.name || "Your account"}</strong><small>{user.email}</small></span></div>
    </aside>
    {mobileNav && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMobileNav(false)}/>}
    <main className="main-area"><header className="mobile-header"><button className="icon-button" onClick={() => setMobileNav(!mobileNav)} aria-label="Toggle navigation"><span className="menu-lines"/></button><Brand compact/><button className="icon-button" onClick={showSummaryAgain} aria-label="Hear my summary"><Icon name="play"/></button></header><div className="page-content"><div className="desktop-topline"><Brand compact/><button className="text-button" onClick={showSummaryAgain}><Icon name="play" size={16}/>Hear my summary</button></div>{content()}</div></main>
  </div>;
}

function Loading() { return <div className="loading-state"><span className="loading-dot"/><span>Opening your notes…</span></div>; }

export default function Page() { return <App/>; }
