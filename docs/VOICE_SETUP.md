# Voice setup and automatic language detection

## How the unified voice flow works

The interface has one voice control and chooses its available path automatically. When an OpenAI
key is configured, the browser records a short clip and sends it to the same-origin FastAPI
endpoint. The server uses OpenAI for transcription, and the API key never enters JavaScript, HTML,
or a browser response. The demo does not store uploaded audio.

Without an OpenAI key, automatic detection is unavailable. After the user explicitly chooses one
of the ten languages, the same control can use browser speech recognition and speech synthesis.
For playback, the application always sets the exact BCP 47 locale. It uses a compatible listed
voice when one exists; otherwise it leaves the voice unset so the browser can choose its most
suitable default for that locale. It never deliberately substitutes an English voice for Sinhala
or another language. Browser and operating-system support varies, and the browser vendor may use
an online service. Typed booking remains available in every case.

The first unlocked recording sends `language_locale=auto` and a supported `fallback_locale`.
Automatic mode deliberately omits both the singular `language` hint and the plural `languages`
hint. With the default `gpt-transcribe` model, OpenAI may return a `languages` array. The server
switches the booking locale only when that metadata resolves to exactly one of these configured
locales:

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

After one reliable detection, later recordings send the supported locale explicitly. This gives
OpenAI an ISO-639-1 language hint for better accuracy and latency. Localized assistant text is
then sent to the server speech endpoint for generated MP3 playback.

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
```

Create the key in your [OpenAI API project](https://platform.openai.com/api-keys), then restart
Uvicorn because settings are cached for the running process. An empty key leaves typed booking and
the explicitly selected browser-voice fallback available while server voice endpoints return HTTP
503.

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
| `GET /api/config` | None | Configuration status, ten language records, and model names; never the key |
| `POST /api/voice/check` | No body | Model visibility status without generating or transcribing audio |
| `POST /api/voice/transcribe` | Multipart `audio`, `language_locale`, optional `fallback_locale` | Transcript and safe language-resolution metadata |
| `POST /api/voice/speak` | JSON `text` and a supported `language_locale` | Uncached `audio/mpeg` bytes |

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

Automated tests mock every OpenAI request and cover all ten mappings, conflicting and unsupported
metadata, upload validation, fixed-host requests, safe failures, and secret non-disclosure. They do
not spend API quota and cannot prove real microphone or accent accuracy.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| OpenAI is not configured / HTTP 503 | Set `OPENAI_API_KEY` in the server `.env` and restart Uvicorn. |
| API key or permissions rejected / HTTP 502 | Check the key's project, status, and model permissions. Never paste it into the browser. |
| Model unavailable / HTTP 502 | Confirm the configured model IDs are available to the API project. |
| OpenAI usage limit / HTTP 429 | Check API billing, project limits, and provider rate limits. |
| OpenAI timeout / HTTP 504 | Check server connectivity and retry one short recording. |
| Invalid or empty audio / HTTP 422 | Re-record an audible phrase using a supported browser recording format. |
| Unsupported recording / HTTP 415 | Use WebM, MP4/M4A, WAV, or MP3/MPEG audio. |
| Recording too large / HTTP 413 | Record a shorter phrase; the demo limit is 10 MB. |
| No reliable language result | Use `gpt-transcribe`, speak a longer clear phrase, and keep a valid fallback selected. |
| Microphone unavailable | Use localhost or HTTPS, grant microphone permission, and check the selected input device. |
| Browser cannot speak Sinhala or another locale | Use **Test voice** after the browser's voices finish loading. If playback still fails, restore OpenAI API quota or install/enable that language's speech voice in the operating system, then restart the browser. |

## Official OpenAI references

- [Create transcription API reference](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create)
- [GPT-Transcribe model](https://developers.openai.com/api/docs/models/gpt-transcribe)
- [Text-to-speech guide](https://developers.openai.com/api/docs/guides/text-to-speech)
- [API key management](https://platform.openai.com/api-keys)
