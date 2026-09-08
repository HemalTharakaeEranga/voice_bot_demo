# Interview demo script

## 90-second primary demo

1. Open the demo in Chrome or Edge and leave **Conversation language** on automatic detection.
2. Select **Start listening** and say a complete phrase such as “My name is Demo Patient.”
3. Verify the transcript and the detected-language indicator. The language stays fixed for this
   booking.
4. Say or select a specialty.
5. Give a future date in `YYYY-MM-DD` format and a time between `08:00` and `17:00`.
6. Confirm using the localized yes phrase and show the demo confirmation code.
7. Start a new booking and repeat a short flow in Sinhala or another configured language.
8. Open **Speaking practice**, select a language, and show the transcript-match result. Explain that
   it checks recognized words and does not train a model or grade pronunciation.

Use fictional details only. The application does not contact a hospital or create a real booking.

## Voice behavior to explain

There is one microphone control. With a configured OpenAI key and available quota, it records a
short clip, detects one of the ten supported languages, and transcribes it. After detection, later
clips are pinned to that locale. Sinhala, Tamil, and Arabic replies use the dedicated local Piper
route. The other seven use OpenAI speech and can fall back to a compatible browser voice. A
different-language voice is never explicitly substituted.

If OpenAI quota is unavailable before detection, choose a specific language to use browser speech
recognition. If the language was already detected, browser recognition can continue in that fixed
language without restarting the booking. Typed input always remains available.

## Interruption and cleanup

Selecting **Start listening** while the assistant speaks stops playback before recording. Select
the same button again to finish a server recording; it also stops after 30 seconds. **Stop voice**
discards an active recording and stops playback. Audio is not stored by this application.

## Failure cases to demonstrate

- An invalid or past date is rejected.
- A time outside `08:00`–`17:00` is rejected.
- “Human” stops automation and requests receptionist assistance.
- An emergency phrase stops booking and directs the user to local emergency or clinical help.
- An unrelated medical question receives the appointment-only response.
- An expired session starts a fresh booking and keeps typed text available for explicit resubmission.

## Honest scope statement

You can describe the multilingual dialogue state machine, FastAPI API, parameterized SQLAlchemy
persistence, unified voice UI, validation, security middleware, automated tests, CI, and demo
documentation. Do not describe the transcript-match exercise as voice-model training, and do not
claim perfect recognition without testing each language, accent, microphone, and browser involved.
