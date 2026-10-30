# CareCompass web interface

This is a parallel Next.js interface. It does not replace or edit the existing Streamlit app. The FastAPI adapter in `../api` reuses the existing Python scoring, safety, recommendation, Groq, and Supabase code.

## Run locally

On Windows, double-click `Run CareCompass.bat` in the project root. It checks prerequisites, installs missing packages, opens the API and web app in separate windows, and opens the site in your browser.

To start the services manually:

1. Keep the existing project-root `.env` configured with `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and, optionally, `GROQ_API_KEY`.
2. Install the API dependencies once, from the project root:

   ```powershell
   python -m pip install -r api/requirements.txt
   ```

3. In one terminal, from the project root, start the API:

   ```powershell
   python -m uvicorn api.main:app --reload --port 8000
   ```

4. Copy `web/.env.example` to `web/.env.local`.
5. In another terminal:

   ```powershell
   cd web
   npm install
   npm run dev
   ```

6. Open `http://localhost:3000`. The original Streamlit app can continue running separately on its existing port.

Only the API reads the Supabase and Groq credentials. The browser receives an authenticated session token and communicates with the API; it never receives the Groq key.
