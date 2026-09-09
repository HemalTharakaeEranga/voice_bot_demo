# Interview demo script

## 90-second primary demo

1. Open the demo in Chrome or Edge. English is selected by default; keep it or explicitly choose
   another conversation language.
2. Select **Start listening** once and say a complete phrase such as “My name is Demo Patient.” The
   browser ends recognition after the utterance and Careline sends the exact returned transcript.
3. Verify the displayed transcript and selected-language indicator. The selected locale stays fixed
   for this booking.
4. Say or select a specialty.
5. Give a future date such as `September 23`, `9/23`, `23/09`, or `2026/09/23`, then a time
   between `08:00` and `17:00` such as `9 AM`, `9:30`, `9/30`, or a localized spoken time.
6. Confirm using the localized yes phrase and show the demo confirmation code.
7. Select Sinhala or another configured language. The change starts a fresh booking; repeat a
   short flow.
8. Open **Speaking practice**, select a language, and show the transcript-match result. Explain that
   it checks recognized words and does not train a model or grade pronunciation.

Use fictional details only. The application does not contact a hospital or create a real booking.

## Voice behavior to explain

There is one microphone control and an explicit ten-language selector. The shipped page uses
browser `SpeechRecognition` in the selected language, independent of the OpenAI key. Sinhala,
Tamil, and Arabic replies use the dedicated local Piper route. The other seven use OpenAI speech
when configured and can fall back to a compatible browser voice. A different-language voice is
never explicitly substituted.

The OpenAI key enables those seven cloud reply voices and the optional transcription endpoint for
custom clients; shipped page listening does not call that endpoint. The backend retains
`language_locale=auto` with a supported `fallback_locale` for custom API clients, but that
compatibility mode is not shown in the page selector. Typed input always remains available.

## Interruption and cleanup

Selecting **Start listening** while the assistant speaks stops playback and begins browser
recognition. The browser ends after the utterance; there is no timer or second click. Careline does
not create or upload a recording, although the browser vendor may process microphone audio under
its own terms.

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
