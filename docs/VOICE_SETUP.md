# Voice setup and automatic language detection

## How the unified voice flow works

The interface has one voice control and chooses its available path automatically. When an OpenAI
key is configured, the browser records a short clip and sends it to the same-origin FastAPI
endpoint. The server uses OpenAI for transcription, and the API key never enters JavaScript, HTML,
or a browser response. The demo does not store uploaded audio.

Reply playback uses the same `/api/voice/speak` endpoint for every supported language. Sinhala
(`si-LK`), Tamil (`ta-LK`), and Arabic (`ar-SA`) are synthesized locally with bundled Piper models
and returned as WAV audio. The other seven languages use OpenAI speech when the key is configured
and return MP3 audio. The browser receives audio bytes, never a provider choice or API credential.

The local Arabic route maps the application's Saudi Arabia locale (`ar-SA`) to the available
Jordanian `ar_JO-kareem-medium` model. Both use the Arabic language family, but accent and regional
pronunciation can differ. Test Arabic replies with the intended audience before a demonstration.

Without an OpenAI key, automatic detection is unavailable. After the user explicitly chooses one
of the ten languages, the same control can use browser speech recognition. Local Sinhala, Tamil,
and Arabic playback remains available without that key; the other seven languages use browser
speech synthesis as their fallback. For browser playback, the application always sets the exact
BCP 47 locale and uses a compatible listed voice when one exists. Once the browser reports its
installed voices, playback refuses an English or other mismatched fallback for Sinhala, Tamil,
Arabic, or another language. Every assistant reply has a **Listen** control; if autoplay blocks
generated audio, the prepared MP3 or WAV remains available for a direct user-initiated retry.
Browser and operating-system support varies, and the browser vendor may use an online service.
Typed booking remains available in every case.

The first unlocked recording sends `language_locale=auto` and a supported `fallback_locale`.
With the default `gpt-transcribe` model, the server sends the ten allowlisted language codes in the
plural `languages[]` hint. This limits recognition to the languages offered by the interface and
lets OpenAI return a detected `languages` array. After a language is selected or reliably detected,
later recordings send only that language as the plural hint. The server switches the booking
locale only when response metadata resolves to exactly one of these configured locales:

| Spoken language | Locale | Accepted canonical code |
| --- | --- | --- |
| English | `en-US` | `en` |
| Sinhala | `si-LK` | `si` |
| Tamil | `ta-LK` | `ta` |
| Hindi | `hi-IN` | `hi` |
| Spanish | `es-ES` | `es` |
| French | `fr-FR` | `fr` |
| German | `de-DE` | `de` |
| Arabic | `ar-SA` | `ar` |
| Chinese | `zh-CN` | `zh` |
| Japanese | `ja-JP` | `ja` |

Region variants, common ISO-639-3 codes, and common English language names are normalized into
that fixed allowlist. Empty metadata, unsupported-only metadata, malformed entries, or metadata
containing multiple different supported languages never triggers a locale switch. The response
then returns the declared fallback with `language_detected: false`. The application does not guess
a language from the transcript's alphabet and never presents a fallback as a detection.

After one reliable detection, later recordings send the supported locale explicitly. With
`gpt-transcribe`, this uses its plural language-hint field; compatible older transcription models
use the singular ISO-639-1 field. Localized assistant text is then sent to the unified server
speech endpoint. Sinhala, Tamil, and Arabic produce local WAV audio; the other seven locales
produce OpenAI MP3 audio when OpenAI is configured.

This is speech recognition and synthesis, not model training or pronunciation grading. Names,
accents, background noise, and short phrases can still be recognized incorrectly. Keep typed
input available to correct a transcript.

## Server configuration

Add these values to the existing `.env` without removing its database or host settings:

```dotenv
OPENAI_API_KEY=your_api_key_here
OPENAI_TRANSCRIPTION_MODEL=gpt-transcribe
OPENAI_SPEECH_MODEL=gpt-4o-mini-tts
OPENAI_SPEECH_VOICE=coral
OPENAI_TIMEOUT_SECONDS=45
VOICE_RATE_LIMIT_REQUESTS=30
CLINIC_UTC_OFFSET_MINUTES=330
```

Create the key in your [OpenAI API project](https://platform.openai.com/api-keys), then restart
Uvicorn because settings are cached for the running process. An empty key leaves typed booking,
explicitly selected browser recognition, and local Sinhala, Tamil, and Arabic playback available.
OpenAI transcription and server playback for the other seven languages return HTTP 503.

Install dependencies from `requirements.txt`, including the pinned `piper-tts==1.8.0` runtime.
The local models must exist at these fixed paths:

```text
models/arabic/ar_JO-kareem-medium.onnx
models/arabic/ar_JO-kareem-medium.onnx.json
models/sinhala/si_LK-ashoka-medium.onnx
models/sinhala/si_LK-ashoka-medium.onnx.json
models/tamil/ta_IN-rasa_female-medium.onnx
models/tamil/ta_IN-rasa_female-medium.onnx.json
```

The ONNX weights use Git LFS. Run `git lfs install` and `git lfs pull` after cloning. Startup does
not eagerly load the models; the relevant voice is verified and loaded on its first speech
request. Exact sources, pinned revisions, expected SHA-256 values, and licenses are recorded in
[`models/README.md`](../models/README.md) and
[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).

`gpt-transcribe` is the default because its JSON transcription response can include detected
languages. A different server-configured transcription model can still return text if it supports
the endpoint, but when it provides no detected-language metadata the application correctly returns
`language_detected: false`. The browser cannot select a model, API host, or API key.

The timeout accepts 5 to 120 seconds. Speech requests are not automatically retried because a
repeat can consume paid quota. Use project spend controls and keep public access restricted when a
paid key is configured.

## API contracts

| Endpoint | Request | Success |
| --- | --- | --- |
| `GET /api/config` | None | Configuration status, available local voice locales, clinic date/UTC offset, ten language records, and model names; never the key |
| `POST /api/voice/check` | No body | Model visibility status without generating or transcribing audio |
| `POST /api/voice/transcribe` | Multipart `audio`, `language_locale`, optional `fallback_locale` | Transcript and safe language-resolution metadata |
| `POST /api/voice/speak` | JSON `text` and a supported `language_locale` | Uncached `audio/wav` for `si-LK`/`ta-LK`/`ar-SA`; uncached `audio/mpeg` for the other seven locales |

Reliable automatic detection returns this shape:

```json
{
  "text": "recognized text",
  "language_locale": "ta-LK",
  "language_detected": true,
  "language_code": "ta"
}
```

When detection is absent or unreliable, `language_code` is omitted:

```json
{
  "text": "recognized text",
  "language_locale": "en-US",
  "language_detected": false
}
```

For backward compatibility, an explicit supported `language_locale` is still accepted and sent as
the transcription language hint. A later conflicting provider result never changes that explicit
locale; automatic mode is the only path that can switch an active conversation. Clients that use
automatic detection should send `auto` plus one of the ten supported fallback locales.

## Security controls

- Provider requests use the fixed HTTPS origin `https://api.openai.com/v1`; redirects and automatic
  retries are disabled so the bearer key is not forwarded to another host.
- Provider error bodies are never sent to the browser. Authentication, quota, timeout, invalid
  media, and upstream failures receive bounded application messages.
- Audio is limited to 10 MB. The endpoint allowlists browser recording MIME types, verifies basic
  container headers, rejects empty and malformed files, and replaces every client filename with a
  generated `recording.<type>` name.
- Locale values use the same fixed ten-language allowlist as the booking state machine. Client
  input cannot choose the OpenAI model or URL.
- Transcripts are limited to 4,096 characters and spoken text is normalized and limited before a
  provider request. Responses are marked `Cache-Control: no-store`.
- Local voice paths are fixed by the application. Model and configuration hashes are verified
  before loading, local synthesis text is bounded, and no user value selects a filesystem path.
- Piper runs in a worker thread with a lock per local voice, keeping CPU-bound synthesis off the
  asynchronous request loop and serializing access to each loaded model. A process admits at most
  two local synthesis jobs at once and returns HTTP 429 while both slots are occupied.

The voice endpoints do not construct or execute SQL. Appointment persistence remains behind the
application's validated booking flow and SQLAlchemy repository.

## Check all ten languages

1. Start a new booking and leave automatic language detection unlocked.
2. Speak a clear sentence in one configured language for at least a couple of seconds.
3. Verify that the displayed transcript and selected conversation language both match what was
   spoken. A fallback must not be labelled as detected.
4. Continue with a fake patient name, specialty, future date, and time. Verify that every assistant
   reply is displayed and spoken in the resolved language.
5. Complete or cancel the fake booking, start a new one to unlock detection, and repeat for each
   language on the actual microphone, browser, and operating system used for the demo.

Automated tests mock every OpenAI request and cover all ten mappings, local Sinhala, Tamil, and
Arabic routing, conflicting and unsupported metadata, upload validation, fixed-host requests,
safe failures, and secret non-disclosure. They do not spend API quota and cannot prove real
microphone, voice quality, or accent accuracy.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| OpenAI is not configured / HTTP 503 | Set `OPENAI_API_KEY` in the server `.env` and restart Uvicorn for automatic transcription and the seven OpenAI playback languages. Local Sinhala, Tamil, and Arabic playback does not require it. |
| API key or permissions rejected / HTTP 502 | Check the key's project, status, and model permissions. Never paste it into the browser. |
| Model unavailable / HTTP 502 | Confirm the configured model IDs are available to the API project. |
| OpenAI usage limit / HTTP 429 | Restore API billing or project quota, then select **Listen** on the reply to retry without reloading the page. Local Sinhala, Tamil, and Arabic playback remains available. |
| OpenAI timeout / HTTP 504 | Check server connectivity and retry one short recording. |
| Invalid or empty audio / HTTP 422 | Re-record an audible phrase using a supported browser recording format. |
| Unsupported recording / HTTP 415 | Use WebM, MP4/M4A, WAV, or MP3/MPEG audio. |
| Recording too large / HTTP 413 | Record a shorter phrase; the demo limit is 10 MB. |
| No reliable language result | Use `gpt-transcribe`, speak a longer clear phrase, and keep a valid fallback selected. |
| Microphone unavailable | Use localhost or HTTPS, grant microphone permission, and check the selected input device. |
| Generated audio was blocked by the browser | Select **Play audio** on that reply; the already generated audio is reused without another API request. |
| Local Sinhala, Tamil, or Arabic voice unavailable / HTTP 503 | Run `git lfs pull`, confirm the six model files are present, reinstall `requirements.txt`, and compare their SHA-256 values with `models/README.md`. A small text file beginning with `version https://git-lfs.github.com/spec/v1` is an unfetched LFS pointer. |
| Arabic playback has a different regional accent | The bundled Arabic model is Jordanian (`ar_JO`) while the application locale is Saudi Arabia (`ar-SA`). Use a reviewed Saudi model if exact regional pronunciation is required. |
| Browser cannot speak one of the other seven locales | Restore OpenAI API access or install/enable a matching language speech voice in the operating system, then restart the browser. |

## Local voice references

- [Piper project and Python runtime](https://github.com/OHF-Voice/piper1-gpl)
- [Rhasspy Jordanian Arabic Piper model, v1.0.0](https://huggingface.co/rhasspy/piper-voices/tree/v1.0.0/ar/ar_JO/kareem/medium)
- [Arabic Kareem training-data source](https://github.com/AliMokhammad/arabicttstrain/)
- [UNICEF Sinhala Piper model](https://huggingface.co/unicef/piper-si_LK-ashoka-medium)
- [TiniSoft Tamil Piper model](https://huggingface.co/tinisoft/piper-ta_IN-rasa_female-medium)
- [AI4Bharat Rasa dataset](https://huggingface.co/datasets/ai4bharat/Rasa)

## Official OpenAI references

- [Create transcription API reference](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create)
- [GPT-Transcribe model](https://developers.openai.com/api/docs/models/gpt-transcribe)
- [Text-to-speech guide](https://developers.openai.com/api/docs/guides/text-to-speech)
- [API key management](https://platform.openai.com/api-keys)
