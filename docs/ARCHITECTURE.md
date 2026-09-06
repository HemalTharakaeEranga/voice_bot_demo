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
                 OpenAI speech, then same-locale browser voice fallback
```

The browser never receives the OpenAI API key. Automatic mode sends the first recording without a
language hint. The server accepts a detected language only when provider metadata resolves to one
unique member of the fixed ten-language allowlist. That locale is then fixed for the booking so a
short name, date, or time cannot change the conversation language. A new booking unlocks detection.

If server speech is unavailable after a language has been fixed, the same microphone control can
continue with browser recognition fixed to that locale. Before a language is known, the user must
select one for that fallback because browser speech recognition does not reliably identify an
arbitrary spoken language.

For reply playback, a listed same-language voice is preferred. If the browser's voice list is
empty or incomplete, the utterance keeps the exact locale and lets the browser resolve a suitable
default. The application never explicitly assigns a different-language voice.

## Booking flow

`/api/sessions` creates a server-generated UUIDv4 and an in-memory conversation record.
`/api/messages` validates that identifier, updates the deterministic booking state, and uses
SQLAlchemy expression queries and ORM inserts. The database unique constraint on date and time is
the final protection against concurrent slot conflicts. Completed confirmations are idempotent.

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
user strings. The OpenAI origin and models are server-controlled. See [Security](SECURITY.md) for
the threat model and the controls still required before any public or healthcare deployment.
