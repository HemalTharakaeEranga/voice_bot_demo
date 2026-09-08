# Clinic Voicebot Demo

A multilingual clinic appointment demo with a responsive business interface, automatic spoken-language detection, speech input, spoken replies, and a separate voice practice area. The booking flow uses a deterministic FastAPI state machine and SQLite. Local Piper models speak Sinhala, Tamil, and Arabic without OpenAI quota; OpenAI provides automatic detection for all ten languages and server speech for the other seven. Explicitly selected browser speech and typed messages remain available without an API key.

## What it supports

- Ten configured locales: English (`en-US`), Sinhala (`si-LK`), Tamil (`ta-LK`), Hindi (`hi-IN`), Spanish (`es-ES`), French (`fr-FR`), German (`de-DE`), Arabic (`ar-SA`), Chinese (`zh-CN`), Japanese (`ja-JP`).
- One voice control that automatically uses local Piper speech for Sinhala, Tamil, and Arabic, server-side OpenAI speech for the other seven languages when configured, or browser speech after the user explicitly selects a language. The API key stays on the server.
- Every assistant reply has a **Listen** control and playback always requests that reply's exact locale. Once the browser reports its installed voices, the application requires a compatible same-language voice and never substitutes English for Sinhala, Tamil, or another language.
- Automatic OpenAI detection supplies the same ten-language allowlist to `gpt-transcribe` and accepts only one reliable match. Missing, unsupported, or conflicting metadata uses the selected fallback without claiming it was detected.
- Voice practice: play a localized sample, read it aloud, and compare the recognized transcript. This is a transcript match check, not pronunciation grading, model training, or fine-tuning.
- Guided booking accepts ISO dates, localized month names such as `September 23`, unambiguous
  short dates such as `9/23`, and common spoken times such as `9:30 AM` or `5 PM`.
- Security headers, separate API and voice rate limits, input validation, tests, Docker, and CI.

Ten configured interface languages do not mean guaranteed speech recognition for every accent, name, microphone, or browser. Replies in Sinhala, Tamil, and Arabic use the bundled local models, while recognition still depends on OpenAI or the browser. The Arabic interface locale is `ar-SA`, but its bundled `ar_JO-kareem-medium` voice is Jordanian Arabic, so regional pronunciation may differ. Use typed input whenever recognition is unavailable or inaccurate. AI-generated voices are disclosed in the interface.

The three ONNX model weights are stored with Git LFS. After cloning, install Git LFS and fetch the
actual model files before starting the application:

```bash
git lfs install
git lfs pull
```

The application verifies their pinned SHA-256 hashes before loading them. See
[`models/README.md`](models/README.md) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for
model sources, exact revisions, licenses, and attribution.

## Run on Windows

```powershell
cd clinic-voicebot-demo
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` in Chrome or Edge. Allow microphone access when you choose to record. Microphone recording requires localhost or HTTPS. Browser speech services may also require internet access.

## Run on Linux/macOS

```bash
cd clinic-voicebot-demo
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
test -f .env || cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Connect OpenAI

1. Create an API key in your [OpenAI API project](https://platform.openai.com/api-keys) and ensure the project has speech model access and available API quota.
2. Add these settings to your existing local `.env`. Keep your database and other settings intact:

   ```dotenv
   OPENAI_API_KEY=your_api_key_here
   OPENAI_TRANSCRIPTION_MODEL=gpt-transcribe
   OPENAI_SPEECH_MODEL=gpt-4o-mini-tts
   OPENAI_SPEECH_VOICE=coral
   OPENAI_TIMEOUT_SECONDS=45
   VOICE_RATE_LIMIT_REQUESTS=30
   CLINIC_UTC_OFFSET_MINUTES=330
   ```

3. Restart Uvicorn and start a new booking. The unified voice control uses OpenAI for recognition,
   local Piper playback for Sinhala, Tamil, and Arabic, and OpenAI playback for the other seven
   languages.
4. Record a clear phrase and verify that the transcript and conversation language match, then test reply playback.

The page makes no paid voice request when it loads. OpenAI transcription and playback for the
seven non-local languages use your API project's paid quota. Sinhala, Tamil, and Arabic Piper
synthesis runs locally and does not use the OpenAI key or quota. The browser cannot choose the
provider model, API host, or key. Never put the key in JavaScript, HTML, a screenshot, or a
committed file. `.env` is ignored by Git.

`CLINIC_UTC_OFFSET_MINUTES` defines the clinic's booking clock and defaults to `330`
(UTC+05:30, Sri Lanka). Set the signed UTC offset for the clinic before deployment so yearless
dates and same-day time validation do not depend on the server machine's clock zone.

See [Voice setup and troubleshooting](docs/VOICE_SETUP.md) for provider behavior, per-language testing, and endpoint details. The integration follows the [official OpenAI transcription documentation](https://developers.openai.com/api/docs/guides/speech-to-text) and [speech synthesis documentation](https://developers.openai.com/api/docs/guides/text-to-speech).

## Test the demo

Use fake patient details only. With OpenAI configured, start by speaking and verify the detected conversation language; without it, select a language first. Enter a fake name, specialty, a future date such as `2026-09-23`, `September 23`, or `9/23`, and a time such as `10:30` or `9:30 AM`. Confirm only after checking the displayed details. This demo does not connect to a real hospital, contact a receptionist, or provide medical advice.

Use voice practice separately to test the microphone, recognition, and sample playback for each locale. A matching transcript is evidence that a particular sample was recognized; it is not a guarantee that all names, accents, dates, or conversations will be recognized correctly.

## Quality checks

```bash
python -m ruff check app tests
python -m bandit -r app -lll
python -m pip_audit -r requirements.txt
python -m pytest
node --check app/static/app.js
node --test tests/frontend.test.cjs
```

The frontend regression checks use Node.js 24's built-in test runner; no npm packages are required.

The voice API tests use a mock HTTP transport. They never contact OpenAI or spend API quota.
Automated checks verify the local routing and WAV contract but do not validate real speech quality.
Live microphone and speaker checks must be performed on the intended device with the available
voice path.

## Share a temporary demo

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

Quick Tunnels are for temporary development demos. Add only the exact generated hostname to
`ALLOWED_HOSTS`, then restart the server. If OpenAI is configured, visitors can invoke the speech
endpoints and consume the server project's quota. Keep the demo local, or add access control,
gateway rate limits, and provider spend limits before sharing a paid endpoint. Do not use real
patient information.

See [Architecture](docs/ARCHITECTURE.md), [Security](docs/SECURITY.md), and [Twilio trial notes](docs/TWILIO_TRIAL.md) for the existing booking architecture and additional demo options.
