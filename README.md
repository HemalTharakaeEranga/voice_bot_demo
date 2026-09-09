# Careline Clinic Voicebot Demo

Careline is a multilingual clinic appointment demonstration with one voice control, an explicit
language selector, localized replies, a guided booking flow, and a separate speaking-practice
area. English is selected by default, and the interface offers ten configured languages. A
deterministic FastAPI state machine handles the conversation and stores demo appointments in
SQLite.

> **Demo scope:** use fictional patient details only. This project is not connected to a clinic,
> does not provide medical advice, and is not a production or regulated healthcare system.

## Features

- Ten configured locales, with English selected by default: English (`en-US`), Sinhala (`si-LK`),
  Tamil (`ta-LK`), Hindi
  (`hi-IN`), Spanish (`es-ES`), French (`fr-FR`), German (`de-DE`), Arabic (`ar-SA`), Simplified
  Chinese (`zh-CN`), and Japanese (`ja-JP`).
- The user explicitly selects the conversation language. One **Start listening** click starts
  browser speech recognition in that locale; the browser ends after the utterance and the exact
  returned transcript is sent to the booking flow.
- Local Piper voices read Sinhala, Tamil, and Arabic replies without an OpenAI key or quota.
- OpenAI text-to-speech reads replies in the other seven languages when configured. A compatible
  browser/system voice is the fallback once a locale is known.
- Every assistant message has a **Listen** button. Prepared audio is preserved when browser
  autoplay is blocked.
- The booking parser accepts localized digits and month names, ISO dates, `September 23`,
  locale-ordered short dates such as `9/23`, and common 12-hour or 24-hour times.
- The speaking-practice result compares the recognized transcript with a sample. It does not
  train a model, fine-tune a voice, or grade pronunciation.
- Input validation, request limits, rate limits, same-origin checks, security headers, model hash
  verification, automated tests, Docker packaging, and GitHub Actions CI are included.

Speech recognition still depends on the speaker, microphone, background noise, browser, network,
and provider. Test all ten languages on the exact device used for a demonstration, and keep typed
input available for corrections.

## Voice routing

The page presents one voice experience; users do not choose a provider.

| Locale | Reply endpoint used by the browser | Engine | Result |
| --- | --- | --- | --- |
| `si-LK` | `POST /api/tts/local` | `si_LK-ashoka-medium` with Piper | WAV |
| `ta-LK` | `POST /api/tts/local` | `ta_IN-rasa_female-medium` with Piper | WAV |
| `ar-SA` | `POST /api/tts/local` | `ar_JO-kareem-medium` with Piper | WAV |
| `en-US`, `hi-IN`, `es-ES`, `fr-FR`, `de-DE`, `zh-CN`, `ja-JP` | `POST /api/voice/speak` | OpenAI speech | MP3 |

The shipped page listens through browser `SpeechRecognition` with the language selected on the
page. Careline does not create or upload an audio recording during this flow, although the browser
vendor may process microphone audio under its own terms. Assistant text, recognition requests,
reply playback, and booking messages keep the selected locale.

`POST /api/voice/speak` still accepts the three local locales for compatibility with older clients
and routes them to Piper before checking for an OpenAI key. Current browser code uses the explicit
`POST /api/tts/local` endpoint so local requests are easy to distinguish in developer tools and
cannot be confused with OpenAI quota failures.

The Tamil model is an Indian Tamil (`ta-IN`) voice used for the application’s Sri Lankan Tamil
locale (`ta-LK`). The Arabic model is Jordanian (`ar-JO`) and is used for the application’s Saudi
Arabic locale (`ar-SA`). Regional pronunciation can differ.

## Technology stack

| Area | Technology |
| --- | --- |
| Frontend | Semantic HTML, responsive CSS, vanilla JavaScript |
| Browser audio | Web Speech API, Blob/Object URL, and `Audio` |
| API server | Python 3.12, FastAPI, Uvicorn, Pydantic, Pydantic Settings |
| Cloud audio | OpenAI Audio APIs called from the server through HTTPX |
| Local speech | Piper TTS 1.8.0, ONNX Runtime, pinned ONNX voice models |
| Dialogue | Deterministic multilingual state machine and local date/time parsers |
| Persistence | SQLAlchemy 2 and SQLite |
| Model delivery | Git LFS and public Hugging Face model repositories |
| Quality | Pytest, Node.js test runner, Ruff, Bandit, pip-audit |
| Packaging and CI | Docker and GitHub Actions |

The application calls OpenAI’s HTTPS API directly with HTTPX. The API key is read only by the
server and is never placed in HTML or JavaScript.

## Project layout

```text
app/
├── dialogue/            # multilingual state machine, translations, date/time parsing
├── static/              # business UI: index.html, styles.css, app.js
├── api.py               # booking session and message routes
├── config.py            # validated environment settings
├── db.py                # SQLAlchemy engine/session setup
├── local_tts.py         # verified Piper models and WAV generation
├── main.py              # FastAPI application and middleware
├── models.py            # appointment database model
├── repository.py        # parameterized persistence operations
└── voice.py             # transcription, local TTS, and OpenAI speech routes
models/                  # Git LFS voice weights and matching JSON configuration
tests/                   # backend and browser-logic regression tests
docs/                    # architecture, security, voice, and demo notes
.github/workflows/ci.yml # test and security-check workflow
```

## Prerequisites

- Python 3.12
- Git
- [Git LFS](https://docs.github.com/en/repositories/working-with-files/managing-large-files/installing-git-large-file-storage)
- Chrome or Edge for microphone testing
- Node.js 24 only for frontend tests
- Docker Desktop or another Docker engine only for container use
- An OpenAI API project and quota only for the optional custom-client transcription endpoint and
  the seven cloud voices

No Hugging Face account, API key, or runtime connection is required. The three public voice models
and their JSON configuration files are downloaded once and then loaded locally.

## Clone and fetch the voice models

```bash
git clone https://github.com/HemalTharakaeEranga/voice_bot_demo.git clinic-voicebot-demo
cd clinic-voicebot-demo
git lfs install
git lfs pull
```

Git stores the large `.onnx` weights through LFS. A fresh clone can contain a small text pointer
instead of a model if LFS was not installed or the pull did not finish. The three model weights
total about 190 MB.

On PowerShell, confirm that the files are tens of megabytes:

```powershell
Get-Item models\sinhala\si_LK-ashoka-medium.onnx,
         models\tamil\ta_IN-rasa_female-medium.onnx,
         models\arabic\ar_JO-kareem-medium.onnx |
  Select-Object Name, Length
```

The expected weight sizes are 63,516,050 bytes for Sinhala, 63,511,037 bytes for Tamil, and
63,201,294 bytes for Arabic. The server also verifies pinned SHA-256 hashes before it loads a
model. All expected hashes and source revisions are in [models/README.md](models/README.md).

### Manual Hugging Face download

Use this only when `git lfs pull` is unavailable. These URLs pin the same revisions recorded in
the repository, so the downloaded bytes pass the application’s integrity checks. They are public
downloads and do not need a Hugging Face token.

```powershell
New-Item -ItemType Directory -Force -Path models\arabic,models\sinhala,models\tamil | Out-Null

Invoke-WebRequest `
  -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx?download=true' `
  -OutFile 'models\arabic\ar_JO-kareem-medium.onnx'
Invoke-WebRequest `
  -Uri 'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx.json?download=true' `
  -OutFile 'models\arabic\ar_JO-kareem-medium.onnx.json'

Invoke-WebRequest `
  -Uri 'https://huggingface.co/unicef/piper-si_LK-ashoka-medium/resolve/58c9ccaece6c9e54d275df1d922945d025fa2033/si_LK-ashoka-medium.onnx?download=true' `
  -OutFile 'models\sinhala\si_LK-ashoka-medium.onnx'
Invoke-WebRequest `
  -Uri 'https://huggingface.co/unicef/piper-si_LK-ashoka-medium/resolve/58c9ccaece6c9e54d275df1d922945d025fa2033/si_LK-ashoka-medium.onnx.json?download=true' `
  -OutFile 'models\sinhala\si_LK-ashoka-medium.onnx.json'

Invoke-WebRequest `
  -Uri 'https://huggingface.co/tinisoft/piper-ta_IN-rasa_female-medium/resolve/89e15edafc8b31e66ddf25f2adbe3bd3f20a9496/ta_IN-rasa_female-medium.onnx?download=true' `
  -OutFile 'models\tamil\ta_IN-rasa_female-medium.onnx'
Invoke-WebRequest `
  -Uri 'https://huggingface.co/tinisoft/piper-ta_IN-rasa_female-medium/resolve/89e15edafc8b31e66ddf25f2adbe3bd3f20a9496/ta_IN-rasa_female-medium.onnx.json?download=true' `
  -OutFile 'models\tamil\ta_IN-rasa_female-medium.onnx.json'
```

Then compare the downloads with the hashes in [models/README.md](models/README.md):

```powershell
Get-FileHash models\arabic\* -Algorithm SHA256
Get-FileHash models\sinhala\* -Algorithm SHA256
Get-FileHash models\tamil\* -Algorithm SHA256
```

On Linux or macOS, create the same directories and download each pinned URL with
`curl --fail --location URL --output PATH`. Use `sha256sum` on Linux or `shasum -a 256` on macOS.
Do not put an access token in a URL, script, commit, or screenshot.

## Install and run on Windows

From PowerShell in the cloned repository:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. Allow microphone access when prompted. Microphone capture requires
localhost or HTTPS. Development API documentation is available at <http://127.0.0.1:8000/docs>.

Check the running server from another PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/config
```

Install only runtime dependencies with `requirements.txt` when development tools are unnecessary.

## Install and run on Linux or macOS

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
test -f .env || cp .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. Use `curl http://127.0.0.1:8000/health` for a health check.

## Connect an OpenAI API key

The OpenAI API key enables generated reply speech for the seven cloud-routed languages and the
optional `/api/voice/transcribe` endpoint for custom clients. The shipped page listens with browser
speech recognition and does not send microphone recordings to that endpoint. Sinhala, Tamil, and
Arabic reply playback stays local and works with an empty key.

1. Create a standard project key on the [OpenAI API keys page](https://platform.openai.com/api-keys).
2. Confirm that the project has access and available quota for `gpt-transcribe` and
   `gpt-4o-mini-tts`.
3. Copy `.env.example` to `.env` if it does not exist.
4. Put the key only in the server’s local `.env` file:

   ```dotenv
   OPENAI_API_KEY=your_api_key_here
   OPENAI_TRANSCRIPTION_MODEL=gpt-transcribe
   OPENAI_SPEECH_MODEL=gpt-4o-mini-tts
   OPENAI_SPEECH_VOICE=coral
   OPENAI_TIMEOUT_SECONDS=45
   ```

5. Stop and restart Uvicorn. Settings are cached by the running process.
6. Open a new booking and select **Listen** on an assistant reply in one of the seven cloud-routed
   languages to verify generated playback. Page listening works through browser speech recognition
   whether or not the key is configured.

The server reads the secret with Pydantic `SecretStr`, calls the fixed
`https://api.openai.com/v1` origin with bearer authentication, and returns only configuration
status and model names to the browser. Redirects and automatic retries are disabled so the key is
not forwarded to another host or a billable audio request silently repeated.

Never place a real key in `app/static/app.js`, HTML, source code, command history shared with
others, screenshots, issue reports, Docker images, or commits. `.env` and `.env.*` files are
ignored while `.env.example` remains tracked with an empty placeholder. Use a deployment secret
manager in production. If a key is exposed, revoke it immediately and create a replacement.

Official references:

- [OpenAI API authentication and secret handling](https://developers.openai.com/api/reference/overview#authentication)
- [`gpt-transcribe` model](https://developers.openai.com/api/docs/models/gpt-transcribe)
- [`gpt-4o-mini-tts` model](https://developers.openai.com/api/docs/models/gpt-4o-mini-tts)
- [Speech-to-text guide](https://developers.openai.com/api/docs/guides/speech-to-text)
- [Text-to-speech guide](https://developers.openai.com/api/docs/guides/text-to-speech)
- [OpenAI API data controls](https://platform.openai.com/docs/models/default-usage-policies-by-endpoint)

The shipped page does not create or upload a microphone recording and does not call the
transcription endpoint. If a custom client calls `/api/voice/transcribe`, OpenAI processes that
audio; the application does not persist the uploaded recording or transcript. Review the current
provider data controls before using any sensitive data.

## Environment settings

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `development` | `production` disables `/docs` and `/openapi.json` and enables the HSTS response header |
| `DATABASE_URL` | `sqlite:///./voicebot_demo.db` | SQLAlchemy database URL for demo appointments |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated exact HTTP host allowlist |
| `RATE_LIMIT_REQUESTS` | `60` | General API requests allowed per client/window/process |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | In-memory rate-limit window in seconds |
| `VOICE_RATE_LIMIT_REQUESTS` | `30` | Voice and local TTS requests allowed per client/window/process |
| `CLINIC_UTC_OFFSET_MINUTES` | `330` | Fixed clinic clock offset; `330` is UTC+05:30 |
| `OPENAI_API_KEY` | empty | Optional server-only OpenAI project key |
| `OPENAI_TRANSCRIPTION_MODEL` | `gpt-transcribe` | Server-controlled transcription model |
| `OPENAI_SPEECH_MODEL` | `gpt-4o-mini-tts` | Server-controlled speech model |
| `OPENAI_SPEECH_VOICE` | `coral` | Server-controlled OpenAI voice |
| `OPENAI_TIMEOUT_SECONDS` | `45` | Provider request timeout, from 5 through 120 seconds |

`CLINIC_UTC_OFFSET_MINUTES` is a fixed offset and does not implement daylight-saving transitions.
Set it for the clinic before using yearless dates or same-day time validation.

## Use the booking demo

1. English is selected by default. Keep it selected or choose another one of the ten languages.
2. Select **Start listening** once and speak a complete phrase. The browser ends recognition after
   the utterance, and Careline sends the exact returned transcript as the next message.
3. Check the displayed transcript and selected language before continuing.
4. Provide a fictional patient name and a clinic/specialty.
5. Give a date within the next 365 days in `YYYY-MM-DD` format, or use a yearless date such as
   `September 23` or `9/23`.
6. Give a time between `08:00` and `17:00`, such as `09:30`, `9:30 AM`, or `5 PM`. Sinhala also
   accepts spoken forms such as `පෙරවරුව 11` and `පස්වරු හතර`.
7. Review the displayed values and answer with the localized yes/no phrase.

Yearless dates resolve to the next valid occurrence within 365 days using the configured clinic
clock. A same-day time must still be in the future. A database unique constraint prevents two
confirmed demo appointments from taking the same date and time slot.

Selecting **Start listening** while the assistant is speaking interrupts playback before browser
recognition begins. Typed messages remain available if voice recognition is missing or inaccurate.

## API endpoints

Interactive OpenAPI documentation is enabled at `/docs` only when `APP_ENV=development`.

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Lightweight process health response |
| `GET /api/config` | Safe public voice metadata, clinic date/offset, model names, and local availability; never the API key |
| `POST /api/sessions` | Start a localized booking session with a server-generated UUIDv4 |
| `POST /api/messages` | Advance the deterministic booking state machine |
| `POST /api/voice/check` | Check configured OpenAI model visibility without generating audio |
| `POST /api/voice/transcribe` | Validate and transcribe a WebM, MP4/M4A, WAV, or MP3 recording of at most 10 MB |
| `POST /api/tts/local` | Generate local WAV audio for `si-LK`, `ta-LK`, or `ar-SA`; maximum 1,000 characters |
| `POST /api/voice/speak` | Generate speech for a supported locale; current browser use is the seven OpenAI locales, with backward-compatible local routing |

Successful audio and all other `/api/` responses use `Cache-Control: no-store`. Local model names,
OpenAI models, provider host, and filesystem paths cannot be selected by a request.

The shipped browser does not call `POST /api/voice/transcribe`; it sends the exact final transcript
returned by browser speech recognition to the booking flow while keeping the selected locale. For
compatibility with custom API clients, the transcription endpoint accepts an explicit supported
locale or `language_locale=auto` together with a supported `fallback_locale`. This API-only
automatic mode is not an option in the page selector.

### Test local Sinhala speech directly

With the server running:

```powershell
$body = @{
  text = 'ආයුබෝවන්. ඔබගේ වෛද්‍ය හමුව වෙන් කර ගැනීමට මට උදව් කළ හැකිය.'
  language_locale = 'si-LK'
} | ConvertTo-Json

Invoke-WebRequest `
  -Uri 'http://127.0.0.1:8000/api/tts/local' `
  -Method Post `
  -ContentType 'application/json; charset=utf-8' `
  -Body $body `
  -OutFile 'sinhala_test.wav'
```

A successful response is HTTP 200 with `Content-Type: audio/wav`. Open `sinhala_test.wav` and
confirm the audio on the demonstration speakers.

## Quality and security checks

Activate the virtual environment, then run:

```bash
python -m pip check
python -m ruff check app tests
python -m bandit -r app -lll
python -m pip_audit -r requirements-dev.txt
python -m pytest
node --check app/static/app.js
node --test tests/frontend.test.cjs
```

No npm packages are required. Backend voice tests mock OpenAI requests and do not consume quota.
CI performs linting, a high-severity Bandit scan, dependency auditing, backend tests, JavaScript
syntax validation, and frontend tests on each push and pull request. Automated checks cannot prove
real microphone access, audible speaker output, provider quota, recognition quality, or accent
accuracy.

## Docker

Pull the real LFS model files before building. Docker can otherwise copy valid-looking pointer
files that fail only when local speech is requested.

```bash
git lfs pull
docker build -t clinic-voicebot-demo .
docker run --rm --name clinic-voicebot-demo --env-file .env -p 8000:8000 clinic-voicebot-demo
```

The container runs Uvicorn as a non-root user with one worker. The default SQLite file is inside
the container and disappears when the container is removed. This PowerShell example uses a named
volume for persistent demo data and enables production-mode application settings:

```powershell
docker run --rm --name clinic-voicebot-demo -p 8000:8000 --env-file .env `
  -e APP_ENV=production `
  -e ALLOWED_HOSTS=localhost `
  -e DATABASE_URL=sqlite:////data/voicebot_demo.db `
  -v clinic_voicebot_data:/data `
  clinic-voicebot-demo
```

Change `ALLOWED_HOSTS` to the exact external hostname when using a reverse proxy. Terminate TLS at
a correctly configured proxy or gateway; setting `APP_ENV=production` does not create HTTPS by
itself.

## Security controls

The demo includes these defenses:

- Pydantic validation for locale allowlists, field types, and bounded input lengths.
- A 64 KiB default request-body limit, an 11 MiB multipart limit on transcription, and a separate
  10 MiB decoded audio limit with allowlisted MIME types and basic container-header checks.
- SQLAlchemy expression queries and ORM inserts, which bind user values as parameters instead of
  concatenating them into SQL. SQL-injection-shaped values are tested as literal data.
- Same-origin checks for browser writes and trusted-host validation.
- CSP, frame denial, MIME-sniffing protection, referrer restrictions, a same-origin resource
  policy, and a microphone-only permissions policy.
- API `no-store`, root-page `no-store`, and static-asset revalidation headers.
- Server-generated UUIDv4 sessions, 30-minute inactivity expiry, and a 1,000-session process cap.
- Separate bounded in-memory API and voice request limiters with `Retry-After` responses. The
  application deliberately ignores spoofable `X-Forwarded-For` values.
- Fixed local model paths, pinned file sizes and SHA-256 hashes, one lock per voice, and a maximum
  of two active local synthesis jobs per process.
- A fixed OpenAI HTTPS origin, server-controlled model names, sanitized upstream errors, disabled
  redirects, and no automatic paid-request retries.
- A non-root Docker user and CI lint, test, static-analysis, and dependency-audit jobs.

The session UUID, Host header, Origin check, and source address are not authentication. Never make
a paid-key deployment public based only on these controls.

## Limits before production use

This repository does not include user authentication, staff roles, a real clinic integration,
application-level database encryption, migrations, audit trails, consent records, or a defined
retention/deletion workflow. SQLite, sessions, and rate-limit state are process-local. They reset
on restart and are not shared across workers. Run this demo with one Uvicorn worker; every extra
worker would also load its own copies of the local models.

Before any public or healthcare deployment:

1. Add authenticated access and endpoint-level authorization.
2. Put shared rate limiting and access control at a trusted API gateway.
3. Use TLS, exact hostnames, a secret manager, key rotation, OpenAI budget alerts, and a hard spend
   limit.
4. Replace SQLite with a managed encrypted database, backups, migrations, restricted credentials,
   and audit logging.
5. Use a shared session store and define data retention, deletion, incident response, and consent
   procedures.
6. Complete privacy, healthcare, accessibility, dependency, container, secret, SAST, DAST, and
   penetration-test reviews appropriate to the deployment.

See [docs/SECURITY.md](docs/SECURITY.md) for the full threat model. Automated tools reduce known
risk; they do not prove that software has no vulnerabilities.

## Troubleshooting

| Symptom | Meaning and action |
| --- | --- |
| `POST /api/voice/speak` returns `429` with `OpenAI usage limit reached` | This is a cloud quota/billing response for a non-local voice. Check the API project’s usage, model access, billing, and limits. Local Sinhala, Tamil, and Arabic playback is independent. |
| A voice route returns `429` with `Too many requests` | The demo’s per-process request limit was reached. Wait for the `Retry-After` interval. Do not disable the limiter on a public service. |
| `/api/tts/local` returns `503` with `Local speech is busy` | Two local synthesis jobs are already active. Wait briefly and select **Listen** again. |
| `/api/tts/local` returns `503` with `local ... voice is unavailable` | Run `git lfs pull`, verify all six model/config files and hashes, and run `python -m pip show piper-tts`. |
| Sinhala still calls `/api/voice/speak` | Restart Uvicorn and use `Ctrl+Shift+R`. Current JavaScript must call `/api/tts/local` for `si-LK`, `ta-LK`, and `ar-SA`. |
| The response text appears but local speech does not play | In browser developer tools, verify `/api/tts/local` returns 200 and `audio/wav`. Test the same endpoint with PowerShell, then check speaker volume and browser autoplay permissions. |
| OpenAI is not configured / `503` | Add the server-side key and restart for the optional custom-client transcription endpoint and seven cloud voices. The three local voices and shipped page's selected-language browser recognition still work without it. |
| API key or model rejected | Check the key’s project, model access, status, and permissions. Never paste the key into browser code or a support screenshot. |
| Microphone is unavailable | Use localhost or HTTPS, grant browser microphone permission, and check the selected input device. |
| Generated audio is ready but silent | Select **Play audio** on that reply to satisfy the browser’s user-interaction requirement. |
| A date or time is rejected | Use a future date in the configured clinic clock and a time from `08:00` through `17:00`. |
| Tamil or Arabic accent differs | The bundled mappings are `ta-IN` to `ta-LK` and `ar-JO` to `ar-SA`; review pronunciation with the intended audience. |

## Licenses and model attribution

- Application code: [MIT License](LICENSE).
- Piper runtime: GPL-3.0-or-later.
- Sinhala voice model: MIT.
- Tamil voice model and Rasa data attribution: CC BY 4.0.
- Arabic voice repository metadata: MIT. Its model card points to the training-data URL for
  licensing, and the linked repository does not state a license on its main page. Review the terms
  before redistributing that model.

The top-level MIT license does not replace the licenses of installed dependencies or bundled
models. Preserve [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) when redistributing the project.

## Additional documentation

- [Voice setup, API behavior, and language testing](docs/VOICE_SETUP.md)
- [Architecture and booking flow](docs/ARCHITECTURE.md)
- [Security threat model and production checklist](docs/SECURITY.md)
- [Interview demonstration script](docs/DEMO_SCRIPT.md)
- [Application email notes](docs/APPLICATION_EMAIL.md)
- [Twilio trial notes](docs/TWILIO_TRIAL.md)
