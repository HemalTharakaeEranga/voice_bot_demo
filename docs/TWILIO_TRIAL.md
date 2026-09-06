# Twilio trial path

The web demo is the recommended first version because it supports interruption behavior without paid telephony.

For a phone-based interview demo, create a Twilio trial account and use Twilio Programmable Voice with `<Say>` and `<Gather input="speech">` to build a turn-by-turn phone flow against the same FastAPI state machine.

Important trial limitation: Twilio's current trial documentation allows `<Say>` and speech `<Gather>`, but blocks `<Stream>`, `<VirtualAgent>`, `<Dial><Number>`, `<Dial><Sip>` and several other real-time/transfer features. Therefore, a full media-streaming realtime AI voice agent or real call transfer should not be promised on the free trial. Use the browser demo for barge-in and the Twilio trial for basic PSTN speech recognition/TTS proof-of-concept.

Keep Twilio credentials only in server environment variables. Never commit Account SID/Auth Token and never expose them in browser JavaScript.
