# Architecture

## Goal

Careline is a task-limited clinic appointment voicebot demo. It presents one microphone control,
supports ten configured conversation languages, and keeps appointment decisions in a deterministic
state machine rather than an LLM.

## Unified voice flow

```text
One microphone button
        |
        +-- OpenAI configured --> short MediaRecorder clip
        |                           |
        |                           v
        |                    /api/voice/transcribe
        |                           |
        |                 reliable supported language?
        |                      /              \
        |                    yes              no
        |                    lock       keep safe fallback
        |                      \              /
        +-- manual fallback --> browser SpeechRecognition
                                   |
                                   v
                            /api/messages
                                   |
                       deterministic dialogue manager
                          | validation / safety rules
                                   |
                          SQLite demo appointment store
                                   |
                         localized assistant response
                                   |
                    locale-based speech routing
                         /                    \
      /api/tts/local                    /api/voice/speak
      Sinhala / Tamil / Arabic          other seven locales
              local Piper WAV             OpenAI speech MP3
                         \                    /
                      same-locale browser voice fallback
```

The browser never receives the OpenAI API key. With `gpt-transcribe`, automatic mode sends the ten
supported codes as language hints. The server accepts a detected language only when provider
metadata resolves to one unique member of that fixed allowlist. That locale is then fixed for the
booking so a short name, date, or time cannot change the conversation language. A new booking
unlocks detection.

If server speech is unavailable after a language has been fixed, the same microphone control can
continue with browser recognition fixed to that locale. Before a language is known, the user must
select one for that fallback because browser speech recognition does not reliably identify an
arbitrary spoken language.

For reply playback, the server routes `si-LK`, `ta-LK`, and `ar-SA` to pinned local Piper models.
Those paths do not need an OpenAI key or quota and return WAV audio. The Arabic application locale
maps to the Jordanian `ar_JO-kareem-medium` voice, so regional pronunciation can differ. The
remaining seven locales use the server-controlled OpenAI speech model and return MP3 audio. The
browser uses separate same-origin endpoints behind the same client control. `/api/voice/speak`
keeps local routing for backward compatibility with older clients.

Each assistant message has a direct replay control and a listed same-language browser voice is the
fallback. If generated audio is ready but browser autoplay blocks it, that control keeps the audio
available for a user-initiated retry. Once the browser reports its installed voices, the
application refuses a different-language default rather than mispronouncing localized text.

## Booking flow

`/api/sessions` creates a server-generated UUIDv4 and an in-memory conversation record.
`/api/messages` validates that identifier, updates the deterministic booking state, and uses
SQLAlchemy expression queries and ORM inserts. The database unique constraint on date and time is
the final protection against concurrent slot conflicts. Completed confirmations are idempotent.

Date and time parsing is local and allowlisted; no input is interpreted as code or passed to SQL.
It accepts localized digits, configured month names, locale-ordered short dates, common clock
markers, and a bounded set of spoken English clock phrases. Yearless dates resolve to their next
valid occurrence within 365 days. The API uses `CLINIC_UTC_OFFSET_MINUTES` (330 by default) as the
authoritative clinic clock and rejects same-day slots that have passed, including a final recheck
at confirmation.

Sessions expire after 30 minutes, the process keeps at most 1,000 least-recently-used sessions, and
unknown or evicted identifiers receive a fixed 404. Session state is process-local, so run this
demo with one Uvicorn worker.

## Supported demo languages

English, Sinhala, Tamil, Hindi, Spanish, French, German, Arabic, Simplified Chinese, and Japanese.
These are configured application languages, not a promise of perfect recognition for every accent,
name, microphone, or browser. Test all ten on the exact demonstration device.

## Security boundary

The application validates locale and payload lengths, limits request bodies and rates, checks
browser write origins and hosts, returns restrictive response headers, and never builds SQL from
user strings. The OpenAI origin and models are server-controlled. Local model paths are fixed,
model and configuration hashes are verified before loading, and synthesis runs outside the async
request loop with per-voice locking. A nonblocking admission limit allows at most two local
synthesis jobs per process, preventing an unbounded worker-thread queue. See [Security](SECURITY.md)
for the threat model and the controls still required before any public or healthcare deployment.
