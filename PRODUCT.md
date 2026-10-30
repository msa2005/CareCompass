# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are individuals tracking their own wellbeing. This was confirmed for the current redesign.

## Product Purpose

CareCompass is a self-guided mental wellbeing app. Its current implementation lets people complete a DASS-21 screening, record voluntary check-ins, review their history, and find general wellbeing suggestions and support options. It is not a diagnostic service.

## Positioning

The implementation combines fixed-rule DASS-21 scoring with optional wellbeing context, check-ins, and AI-assisted wording. Its distinctive market position has not been confirmed; do not make comparative or clinical claims.

## Operating Context

CareCompass is a Streamlit web app for an individual user. The current flows include sign-in, consent, assessment, results, contextual questions, wellbeing plan, history, check-ins, chat, and profile and privacy settings. Supabase credentials are required for account and saved-record flows. The optional AI features use a Groq API key; the interface must remain clear when those services are unavailable.

## Capabilities and Constraints

- DASS-21 results are calculated by fixed rules; optional lifestyle context does not change the screening score.
- The app provides general suggestions and signposts support; it does not diagnose or provide medical advice.
- Assessment, follow-up, and deletion actions are consent-aware in the existing implementation. Preserve their behavior and explain destructive actions clearly.
- Assessment history and check-ins depend on the configured Supabase backend.
- AI wording, a personalised plan, and chat are optional and must retain their existing fallback and safety behavior.
- Existing model assets are present in `models/`; model estimates are currently marked experimental and hidden by configuration.
- UI language and interaction changes must not alter scoring, safety logic, consent rules, persistence, or data handling.

## Brand Commitments

- Keep the CareCompass name.
- Use a calm, light-only color theme appropriate to a mental wellbeing product.
- Do not use emoji. Use a consistent, accessible line-icon system where an icon helps recognition.
- Motion should feel gentle and purposeful, support state changes, and respect reduced-motion settings.

## Evidence on Hand

- Product behavior and safety copy: `carecompass_core.py` and `carecompass_streamlit.py`.
- Existing UI helpers and theme: `carecompass_ui.py` and `.streamlit/config.toml`.
- Existing wellbeing model files: `models/`.
- No project-specific photography, logo artwork, or image library was found in the workspace inventory.
- Supabase and Groq are external services configured through environment variables; credentials are not stored in this project.

## Product Principles

- Give people a calm, nonjudgmental way to check in with themselves.
- Make the difference between screening, personal context, general suggestions, and clinical care clear.
- Keep consent and privacy choices understandable and under the user's control.
- Preserve access to support guidance, especially when a safety check asks someone to reach out.

