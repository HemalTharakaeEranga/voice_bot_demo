"use strict";

// Exercise the shipped browser script without adding a DOM package or making network calls.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../app/static/app.js"), "utf8");
const markup = fs.readFileSync(path.join(__dirname, "../app/static/index.html"), "utf8");
const locales = ["en-US", "si-LK", "ta-LK", "hi-IN", "es-ES", "fr-FR", "de-DE", "ar-SA", "zh-CN", "ja-JP"];
const labels = {
  "en-US": "English", "si-LK": "සිංහල · Sinhala", "ta-LK": "தமிழ் · Tamil",
  "hi-IN": "हिन्दी · Hindi", "es-ES": "Español · Spanish", "fr-FR": "Français · French",
  "de-DE": "Deutsch · German", "ar-SA": "العربية · Arabic", "zh-CN": "中文 · Chinese",
  "ja-JP": "日本語 · Japanese",
};
const localizedGreetings = {
  "si-LK": "ආයුබෝවන්. මට උපකාර කළ හැක්කේ වෛද්‍ය හමුවක් වෙන්කර ගැනීමට පමණි. රෝගියාගේ නම කුමක්ද?",
  "ta-LK": "வணக்கம். நான் மருத்துவ நேரம் பதிவு செய்வதற்கு மட்டுமே உதவ முடியும். நோயாளியின் பெயர் என்ன?",
  "ar-SA": "مرحبًا. يمكنني فقط مساعدتك في حجز موعد طبي. ما اسم المريض؟",
};

class Element {
  constructor(tagName = "div") {
    this.tagName = tagName;
    this.children = [];
    this.dataset = {};
    this.attributes = {};
    this.listeners = new Map();
    this.textContent = "";
    this.value = "";
    this.disabled = false;
    this.hidden = false;
    this.checked = false;
    const classes = new Set();
    this.classList = {
      add: (...items) => items.forEach((item) => classes.add(item)),
      remove: (...items) => items.forEach((item) => classes.delete(item)),
      contains: (item) => classes.has(item),
      toggle: (item, enabled) => {
        if (enabled ?? !classes.has(item)) classes.add(item);
        else classes.delete(item);
      },
    };
  }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = [...items]; }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; }
  querySelector(selector) { return this.children.find((item) => item.tagName === selector) || null; }
  addEventListener(name, callback) {
    if (!this.listeners.has(name)) this.listeners.set(name, []);
    this.listeners.get(name).push(callback);
  }
  async emit(name) {
    for (const callback of this.listeners.get(name) || []) await callback({preventDefault() {}});
  }
  reportValidity() { return Boolean(this.value); }
}

function response(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
    blob: async () => new Blob(["fake audio"]),
  };
}
function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return {promise, resolve};
}
const flush = () => new Promise((resolve) => setImmediate(resolve));
async function settle(rounds = 5) {
  for (let index = 0; index < rounds; index += 1) await flush();
}

async function app(options = {}) {
  const elements = new Map();
  for (const match of markup.matchAll(/<([a-z]+)\b[^>]*\bid="([^"]+)"[^>]*>/g)) {
    const element = new Element(match[1]);
    element.hidden = /\bhidden\b/.test(match[0]);
    elements.set(match[2], element);
  }
  const element = (id) => {
    assert.ok(elements.has(id), `The HTML must contain #${id}`);
    return elements.get(id);
  };
  element("languageSelect").value = options.locale || "auto";
  element("autoSpeak").checked = options.autoSpeak !== false;
  element("textForm").append(new Element("button"));

  const voiceCard = new Element();
  const steps = ["patient_name", "specialty", "appointment_date", "appointment_time", "confirm"]
    .map((step) => {
      const item = new Element("li");
      item.dataset.step = step;
      return item;
    });
  const document = {
    body: new Element("body"),
    getElementById: element,
    createElement: (tag) => new Element(tag),
    querySelector: (selector) => selector === ".voice-card" ? voiceCard : null,
    querySelectorAll: (selector) => selector.includes("bookingProgress") ? steps
      : selector.includes("quickReplies") ? element("quickReplies").children : [],
  };

  const calls = [];
  const recognitions = [];
  const recorders = [];
  const spoken = [];
  const audios = [];
  const tracks = [];
  const timers = new Map();
  const synthesisListeners = new Map();
  const playErrors = [...(options.playErrors || [])];
  class Recognition {
    constructor() { recognitions.push(this); }
    start() { this.onstart?.(); }
    stop() { this.onend?.(); }
    abort() { this.aborted = true; }
    result(text) { this.onresult?.({results: [[{transcript: text}]]}); }
  }
  class Recorder {
    static isTypeSupported() { return options.supportedRecording !== false; }
    constructor(stream, recorderOptions) {
      this.stream = stream;
      this.mimeType = recorderOptions.mimeType;
      this.state = "inactive";
      recorders.push(this);
    }
    start() { this.state = "recording"; }
    stop() {
      this.state = "inactive";
      queueMicrotask(() => {
        this.ondataavailable?.({data: new Blob([new Uint8Array(256)])});
        void this.onstop?.();
      });
    }
  }
  const synthesis = {
    getVoices: () => options.voices || [],
    cancel() {},
    speak(utterance) {
      spoken.push(utterance);
      if (options.synthesisThrow) throw new Error("Synthesis unavailable");
      if (options.synthesisError) utterance.onerror?.({error: options.synthesisError});
      else utterance.onstart?.();
    },
    addEventListener(name, callback) {
      if (!synthesisListeners.has(name)) synthesisListeners.set(name, []);
      synthesisListeners.get(name).push(callback);
    },
    async emit(name) {
      for (const callback of synthesisListeners.get(name) || []) await callback();
    },
  };
  class FakeAudio {
    constructor(url) {
      this.url = url;
      this.playCalls = 0;
      audios.push(this);
    }
    async play() {
      this.playCalls += 1;
      const playError = playErrors.length ? playErrors.shift() : options.playError;
      if (playError) throw Object.assign(new Error("Playback rejected"), {name: playError});
    }
    pause() { this.paused = true; }
    load() {}
    removeAttribute() {}
    fail() { this.onerror?.(); }
    finish() { this.onended?.(); }
  }
  const defaultGetUserMedia = async () => {
    const track = {stopped: false, stop() { this.stopped = true; }};
    tracks.push(track);
    return {getTracks: () => [track]};
  };
  const window = {
    isSecureContext: options.secure !== false,
    SpeechRecognition: options.recognition === false ? undefined : Recognition,
    MediaRecorder: options.mediaRecorder === false ? undefined : Recorder,
    speechSynthesis: options.synthesis === false ? undefined : synthesis,
    addEventListener() {},
  };
  let sessionNumber = 0;
  const transcriptions = [...(options.transcriptions || [])];
  const sandbox = {
    window,
    document,
    console,
    AbortController,
    Blob,
    FormData,
    navigator: options.mediaDevices === false ? {} : {
      mediaDevices: {getUserMedia: options.getUserMedia || defaultGetUserMedia},
    },
    MediaRecorder: Recorder,
    SpeechSynthesisUtterance: class {
      constructor(text) {
        this.text = text;
        this.voice = null;
      }
    },
    Audio: FakeAudio,
    URL: {createObjectURL: () => "blob:test", revokeObjectURL() {}},
    setInterval(callback) {
      const id = Symbol("timer");
      timers.set(id, callback);
      return id;
    },
    clearInterval(id) { timers.delete(id); },
    async fetch(url, requestOptions = {}) {
      calls.push({url, options: requestOptions});
      const custom = options.fetch?.(url, requestOptions, calls);
      if (custom !== undefined) return custom;
      if (url === "/api/config") {
        return response({
          openai_configured: options.configured !== false,
          clinic_today: options.clinicToday || "2026-09-08",
          clinic_utc_offset_minutes: 330,
          local_voice_locales: options.localVoices || [],
          languages: locales.map((locale) => ({
            locale,
            label: labels[locale],
            sample: locale === "si-LK" ? "මට වෛද්‍ය හමුවක් අවශ්‍යයි." : "I would like an appointment.",
            yes: ["yes"],
            no: ["no"],
          })),
        });
      }
      if (url === "/api/sessions") {
        const body = JSON.parse(requestOptions.body);
        return response({
          session_id: `session-${++sessionNumber}`,
          assistant_text: `Greeting ${body.language_locale} ${sessionNumber}`,
          step: "patient_name",
        });
      }
      if (url === "/api/messages") {
        const body = JSON.parse(requestOptions.body);
        return response({assistant_text: `Reply ${body.language_locale}`, step: "specialty", status: "active"});
      }
      if (url === "/api/voice/transcribe") {
        return response(transcriptions.shift() || {
          text: "Demo Patient",
          language_locale: "en-US",
          language_detected: false,
        });
      }
      if (["/api/voice/speak", "/api/tts/local"].includes(url)) return response({});
      throw new Error(`Unexpected request ${url}`);
    },
  };
  const context = vm.createContext(sandbox);
  vm.runInContext(source, context, {filename: "app/static/app.js"});
  await settle();
  return {
    element, calls, recognitions, recorders, spoken, audios, timers, tracks, document, synthesis,
    run: (code) => vm.runInContext(code, context),
    text: () => element("conversation").children.map((item) => item.children.at(-1).textContent),
    messageLocales: () => element("conversation").children.map((item) => item.children.at(-1).lang),
  };
}

test("markup exposes one unified microphone and no provider or connection selector", () => {
  assert.equal((markup.match(/id="listenButton"/g) || []).length, 1);
  assert.match(markup, /value="auto" selected>Automatically detect · 10 languages/);
  assert.doesNotMatch(markup + source, /voiceProvider|checkConnectionButton|providerStatus/);
  assert.doesNotMatch(source, /OPENAI_API_KEY|innerHTML/);
});

test("every JavaScript id exists in the shipped markup", () => {
  const ids = [...source.matchAll(/\$\("([A-Za-z][A-Za-z0-9_-]*)"\)/g)].map((match) => match[1]);
  for (const id of new Set(ids)) assert.match(markup, new RegExp(`id="${id}"`), `missing #${id}`);
});

test("initialization creates only a text session and makes no paid voice or check request", async () => {
  const ui = await app();
  assert.deepEqual(ui.calls.map((call) => call.url), ["/api/config", "/api/sessions"]);
  assert.equal(ui.element("languageSelect").value, "auto");
  assert.equal(JSON.parse(ui.calls[1].options.body).language_locale, "en-US");
  assert.equal(ui.audios.length, 0);
  assert.equal(ui.spoken.length, 0);
  assert.deepEqual(ui.text(), ["Greeting en-US 1"]);
});

test("selecting a bundled local voice displays and plays the exact localized greeting", async () => {
  for (const locale of ["si-LK", "ta-LK", "ar-SA"]) {
    const ui = await app({
      configured: false,
      localVoices: ["si-LK", "ta-LK", "ar-SA"],
      fetch: (url, requestOptions) => {
      if (url !== "/api/sessions") return undefined;
      const requestedLocale = JSON.parse(requestOptions.body).language_locale;
      return response({
        session_id: `session-${requestedLocale}`,
        assistant_text: localizedGreetings[requestedLocale] || "English greeting",
        step: "patient_name",
      });
      },
    });
    ui.element("languageSelect").value = locale;
    await ui.element("languageSelect").emit("change");
    await settle(8);

    assert.equal(ui.text().at(-1), localizedGreetings[locale]);
    assert.equal(ui.messageLocales().at(-1), locale);
    const speech = ui.calls.filter((call) => call.url === "/api/tts/local").at(-1);
    assert.deepEqual(JSON.parse(speech.options.body), {
      text: localizedGreetings[locale],
      language_locale: locale,
    });
    assert.equal(ui.audios.at(-1).playCalls, 1);
  }
});

test("date picker uses the server-provided clinic date", async () => {
  const ui = await app({clinicToday: "2026-09-08"});
  ui.run('progress("appointment_date")');
  const dateInput = ui.element("quickReplies").children.find((item) => item.tagName === "input");
  assert.equal(dateInput.min, "2026-09-08");
  assert.equal(dateInput.max, "2027-09-08");
  assert.equal(dateInput.value, "2026-09-09");
});

test("auto recording sends auto plus fallback, locks reliable detection, and replies in that locale", async () => {
  const ui = await app({transcriptions: [{
    text: "මගේ නම හේමල්",
    language_locale: "si-LK",
    language_detected: true,
    language_code: "si",
  }]});
  await ui.run('startCapture("booking")');
  ui.run("finishCapture()");
  await settle(8);

  const transcribe = ui.calls.find((call) => call.url === "/api/voice/transcribe");
  assert.equal(transcribe.options.body.get("language_locale"), "auto");
  assert.equal(transcribe.options.body.get("fallback_locale"), "en-US");
  const message = ui.calls.find((call) => call.url === "/api/messages");
  assert.equal(JSON.parse(message.options.body).language_locale, "si-LK");
  assert.equal(ui.run("effectiveLocale"), "si-LK");
  assert.equal(ui.run("lockedLocale"), "si-LK");
  assert.equal(ui.element("languageSelect").value, "auto");
  assert.match(ui.element("detectedLanguage").textContent, /Detected .*Sinhala/);
  const speech = ui.calls.find((call) => call.url === "/api/tts/local");
  assert.equal(JSON.parse(speech.options.body).language_locale, "si-LK");
  assert.deepEqual(ui.messageLocales(), ["en-US", "si-LK", "si-LK"]);
});

test("automatic detection accepts each of the ten supported locales without drift", async () => {
  for (const locale of locales) {
    const ui = await app({
      autoSpeak: false,
      transcriptions: [{
        text: "Localized patient reply",
        language_locale: locale,
        language_detected: true,
        language_code: locale.split("-")[0],
      }],
    });
    await ui.run('startCapture("booking")');
    ui.run("finishCapture()");
    await settle(8);

    const transcription = ui.calls.find((call) => call.url === "/api/voice/transcribe");
    const message = ui.calls.find((call) => call.url === "/api/messages");
    assert.equal(transcription.options.body.get("language_locale"), "auto", locale);
    assert.equal(ui.run("lockedLocale"), locale);
    assert.equal(ui.run("effectiveLocale"), locale);
    assert.equal(JSON.parse(message.options.body).language_locale, locale);
    assert.deepEqual(ui.messageLocales(), ["en-US", locale, locale]);
  }
});

test("uncertain or unsupported detection does not claim or lock a language", async () => {
  for (const transcription of [
    {text: "Hemal", language_locale: "fr-FR", language_detected: false},
    {text: "Hemal", language_locale: "xx-XX", language_detected: true, language_code: "xx"},
    {text: "Hemal"},
  ]) {
    const ui = await app({transcriptions: [transcription]});
    await ui.run('startCapture("booking")');
    ui.run("finishCapture()");
    await settle(8);
    assert.equal(ui.run("lockedLocale"), null);
    assert.equal(ui.run("effectiveLocale"), "en-US");
    assert.match(ui.element("detectedLanguage").textContent, /Language not confirmed/);
    const message = ui.calls.find((call) => call.url === "/api/messages");
    assert.equal(JSON.parse(message.options.body).language_locale, "en-US");
  }
});

test("locked auto language is used explicitly on later recordings and cannot drift", async () => {
  const ui = await app({transcriptions: [
    {text: "මගේ නම හේමල්", language_locale: "si-LK", language_detected: true},
    {text: "හෘද රෝග", language_locale: "fr-FR", language_detected: true},
  ]});
  await ui.run('startCapture("booking")');
  ui.run("finishCapture()");
  await settle(8);
  await ui.run('startCapture("booking")');
  ui.run("finishCapture()");
  await settle(8);
  const uploads = ui.calls.filter((call) => call.url === "/api/voice/transcribe");
  assert.equal(uploads[1].options.body.get("language_locale"), "si-LK");
  assert.equal(uploads[1].options.body.get("fallback_locale"), "si-LK");
  assert.equal(ui.run("effectiveLocale"), "si-LK");
  const messages = ui.calls.filter((call) => call.url === "/api/messages");
  assert.equal(JSON.parse(messages[1].options.body).language_locale, "si-LK");
});

test("voice quota failure keeps OpenAI listening and the detected booking language", async () => {
  const ui = await app({
    voices: [{name: "English", lang: "en-US"}],
    transcriptions: [{
      text: "Je m'appelle Hémal",
      language_locale: "fr-FR",
      language_detected: true,
      language_code: "fr",
    }],
    fetch: (url) => url === "/api/voice/speak"
      ? response({detail: "OpenAI usage limit reached"}, 429) : undefined,
  });
  await ui.run('startCapture("booking")');
  ui.run("finishCapture()");
  await settle(8);

  assert.equal(ui.run("lockedLocale"), "fr-FR");
  assert.equal(ui.run("speechProviderUnavailable"), true);
  assert.equal(ui.run("transcriptionProviderUnavailable"), false);
  assert.equal(ui.element("languageSelect").value, "auto");
  assert.equal(ui.element("listenButton").disabled, false);
  assert.match(ui.element("voiceAvailability").textContent, /OpenAI processes recordings/);
  assert.equal(ui.spoken.length, 0);
  assert.match(ui.element("statusLine").textContent, /server voice quota/i);

  await ui.run('startCapture("booking")');
  assert.equal(ui.recorders.length, 2);
  assert.equal(ui.recognitions.length, 0);
  ui.run("stopCapture()");
  assert.equal(ui.calls.filter((call) => call.url === "/api/sessions").length, 1);
});

test("new booking clears the automatic language lock", async () => {
  const ui = await app({transcriptions: [
    {text: "මගේ නම හේමල්", language_locale: "si-LK", language_detected: true},
  ]});
  await ui.run('startCapture("booking")');
  ui.run("finishCapture()");
  await settle(8);
  assert.equal(ui.run("lockedLocale"), "si-LK");
  await ui.run("startSession(false)");
  assert.equal(ui.run("lockedLocale"), null);
  assert.equal(ui.run("effectiveLocale"), "en-US");
  assert.match(ui.element("detectedLanguage").textContent, /complete phrase/);
});

test("without server voice auto mode asks for a language while text remains available", async () => {
  const ui = await app({configured: false});
  assert.equal(ui.element("listenButton").disabled, true);
  assert.equal(ui.element("practiceButton").disabled, true);
  assert.equal(ui.element("textInput").disabled, false);
  assert.match(ui.element("detectedLanguage").textContent, /Select a language/);
  assert.match(ui.element("voiceAvailability").textContent, /browser listening/);
});

test("without server voice a manual language uses browser recognition", async () => {
  const ui = await app({
    configured: false,
    locale: "fr-FR",
    voices: [{name: "Français", lang: "fr-FR"}],
  });
  await ui.run('startCapture("booking")');
  assert.equal(ui.recorders.length, 0);
  assert.equal(ui.recognitions.length, 1);
  assert.equal(ui.recognitions[0].lang, "fr-FR");
  ui.recognitions[0].result("Patient Démo");
  await settle();
  assert.equal(ui.calls.some((call) => call.url === "/api/voice/transcribe"), false);
  const message = ui.calls.find((call) => call.url === "/api/messages");
  assert.equal(JSON.parse(message.options.body).language_locale, "fr-FR");
  assert.equal(ui.spoken.at(-1).lang, "fr-FR");
});

test("browser listening, reading, and writing retain every configured locale", async () => {
  for (const locale of locales) {
    const ui = await app({configured: false, locale, autoSpeak: false});
    await ui.run('startCapture("booking")');
    assert.equal(ui.recognitions.length, 1, locale);
    assert.equal(ui.recognitions[0].lang, locale);
    ui.recognitions[0].result("Localized patient reply");
    await settle();

    const message = ui.calls.find((call) => call.url === "/api/messages");
    assert.equal(JSON.parse(message.options.body).language_locale, locale);
    assert.deepEqual(ui.messageLocales(), [locale, locale, locale]);
  }
});

test("transcription quota error gives an actionable manual browser fallback", async () => {
  let transcriptionCalls = 0;
  const ui = await app({
    locale: "fr-FR",
    voices: [{name: "Français", lang: "fr-FR"}],
    fetch: (url) => {
      if (url === "/api/voice/transcribe" && transcriptionCalls++ === 0) {
        return response({detail: "OpenAI usage limit reached"}, 429);
      }
    },
  });
  await ui.run('startCapture("booking")');
  ui.run("finishCapture()");
  await settle(8);
  assert.match(ui.element("statusLine").textContent, /quota.*Start listening again.*browser recognition/i);
  await ui.run('startCapture("booking")');
  assert.equal(ui.recognitions.length, 1);
  assert.equal(ui.recognitions[0].lang, "fr-FR");
  assert.equal(ui.recorders.length, 1);
});

test("a transient transcription failure retries server listening on the next recording", async () => {
  let transcriptionCalls = 0;
  const ui = await app({
    locale: "fr-FR",
    autoSpeak: false,
    fetch: (url) => url === "/api/voice/transcribe" && transcriptionCalls++ === 0
      ? response({detail: "Temporary transcription failure"}, 503) : undefined,
  });
  await ui.run('startCapture("booking")');
  ui.run("finishCapture()");
  await settle(8);

  assert.equal(ui.run("transcriptionProviderUnavailable"), false);
  assert.match(ui.element("statusLine").textContent, /temporarily unavailable.*retry/i);
  assert.match(ui.element("voiceAvailability").textContent, /OpenAI processes recordings/);

  await ui.run('startCapture("booking")');
  ui.run("finishCapture()");
  await settle(8);
  assert.equal(ui.recorders.length, 2);
  assert.equal(ui.recognitions.length, 0);
  assert.equal(ui.calls.filter((call) => call.url === "/api/voice/transcribe").length, 2);
  assert.equal(ui.calls.filter((call) => call.url === "/api/messages").length, 1);
});

test("quota failure in auto mode requires a manual language and never guesses", async () => {
  const ui = await app({fetch: (url) => url === "/api/voice/transcribe"
    ? response({detail: "insufficient_quota"}, 429) : undefined});
  await ui.run('startCapture("booking")');
  ui.run("finishCapture()");
  await settle(8);
  assert.equal(ui.element("listenButton").disabled, true);
  assert.match(ui.element("statusLine").textContent, /Select a specific language/);
  assert.equal(ui.run("lockedLocale"), null);
});

test("generated speech failure falls back once to a matching browser voice", async () => {
  const ui = await app({
    locale: "fr-FR",
    voices: [{name: "Français", lang: "fr-FR"}],
    fetch: (url) => url === "/api/voice/speak"
      ? response({detail: "Voice quota reached"}, 429) : undefined,
  });
  await ui.run('speak("Bonjour", true)');
  await settle();
  assert.equal(ui.calls.filter((call) => call.url === "/api/voice/speak").length, 1);
  assert.equal(ui.spoken.length, 1);
  assert.equal(ui.spoken[0].voice.name, "Français");
  assert.equal(ui.run("speechProviderUnavailable"), true);
  assert.equal(ui.run("transcriptionProviderUnavailable"), false);
});

test("an OpenAI voice quota flag does not block a bundled local voice", async () => {
  let speechCalls = 0;
  const ui = await app({
    locale: "en-US",
    localVoices: ["si-LK", "ta-LK", "ar-SA"],
    voices: [{name: "English", lang: "en-US"}],
    fetch: (url) => {
      if (url === "/api/voice/speak" && speechCalls++ === 0) {
        return response({detail: "Voice quota reached"}, 429);
      }
      return undefined;
    },
  });

  await ui.run('speak("Hello", true, "en-US")');
  assert.equal(ui.run("speechProviderUnavailable"), true);
  await ui.run(`speak(${JSON.stringify(localizedGreetings["si-LK"])}, true, "si-LK")`);
  await settle();

  const cloudCalls = ui.calls.filter((call) => call.url === "/api/voice/speak");
  const localCalls = ui.calls.filter((call) => call.url === "/api/tts/local");
  assert.equal(cloudCalls.length, 1);
  assert.equal(localCalls.length, 1);
  assert.equal(JSON.parse(localCalls[0].options.body).language_locale, "si-LK");
  assert.equal(ui.audios.length, 1);
  assert.equal(ui.audios[0].playCalls, 1);
});

test("a busy local voice does not disable OpenAI speech", async () => {
  let speechCalls = 0;
  const ui = await app({
    locale: "si-LK",
    localVoices: ["si-LK", "ta-LK", "ar-SA"],
    voices: [{name: "Sinhala", lang: "si-LK"}],
    fetch: (url) => {
      if (url === "/api/tts/local" && speechCalls++ === 0) {
        return response({detail: "Local speech is busy. Please try again shortly."}, 503);
      }
      return undefined;
    },
  });

  await ui.run(`speak(${JSON.stringify(localizedGreetings["si-LK"])}, true, "si-LK")`);
  assert.equal(ui.run("speechProviderUnavailable"), false);
  await ui.run('speak("Hello", true, "en-US")');
  await settle();

  const localCalls = ui.calls.filter((call) => call.url === "/api/tts/local");
  const cloudCalls = ui.calls.filter((call) => call.url === "/api/voice/speak");
  assert.equal(localCalls.length, 1);
  assert.equal(cloudCalls.length, 1);
  assert.equal(JSON.parse(cloudCalls[0].options.body).language_locale, "en-US");
  assert.equal(ui.audios.length, 1);
});

test("local-language replies use Piper even when availability metadata is stale", async () => {
  const cases = [
    {locale: "si-LK"},
    {locale: "ta-LK"},
    {locale: "ar-SA"},
  ];
  for (const {locale} of cases) {
    const reply = localizedGreetings[locale];
    const ui = await app({
      configured: false,
      locale,
      fetch: (url) => url === "/api/messages"
        ? response({assistant_text: reply, step: "specialty", status: "active"})
        : undefined,
    });
    assert.match(ui.element("browserNotice").textContent, /local .* voice is not ready/i);
    await ui.run('sendMessage("Demo Patient")');
    await settle();

    assert.equal(ui.text().at(-1), reply);
    assert.equal(ui.messageLocales().at(-1), locale);
    const localCall = ui.calls.find((call) => call.url === "/api/tts/local");
    assert.deepEqual(JSON.parse(localCall.options.body), {text: reply, language_locale: locale});
    assert.equal(ui.audios.length, 1);
    assert.equal(ui.spoken.length, 0);
  }
});

test("reply replay retries OpenAI after voice quota is restored", async () => {
  let speechCalls = 0;
  const reply = "Bonjour. Quel service souhaitez-vous ?";
  const ui = await app({
    locale: "fr-FR",
    voices: [{name: "English", lang: "en-US"}],
    fetch: (url) => {
      if (url === "/api/messages") {
        return response({assistant_text: reply, step: "specialty", status: "active"});
      }
      if (url === "/api/voice/speak" && speechCalls++ === 0) {
        return response({detail: "Voice quota reached"}, 429);
      }
      return undefined;
    },
  });
  await ui.run('sendMessage("Demo Patient")');
  await settle();
  assert.equal(ui.run("speechProviderUnavailable"), true);
  assert.equal(ui.spoken.length, 0);

  const replayButton = ui.element("conversation").children.at(-1).children[0].children.at(-1);
  await replayButton.emit("click");
  await settle();
  assert.equal(ui.calls.filter((call) => call.url === "/api/voice/speak").length, 2);
  assert.equal(ui.audios.length, 1);
  assert.equal(ui.audios[0].playCalls, 1);
  assert.equal(JSON.parse(ui.calls.filter((call) => call.url === "/api/voice/speak").at(-1).options.body).text, reply);
});

test("an autoplay block preserves generated audio for a direct reply-button replay", async () => {
  const ui = await app({
    locale: "si-LK",
    localVoices: ["si-LK", "ta-LK", "ar-SA"],
    playErrors: ["NotAllowedError", null],
  });
  const reply = localizedGreetings["si-LK"];
  ui.run(`appendMessage("assistant", ${JSON.stringify(reply)})`);
  const replayButton = ui.element("conversation").children.at(-1).children[0].children.at(-1);
  await ui.run(`speak(${JSON.stringify(reply)}, true, "si-LK", document.getElementById("conversation").children.at(-1).children[0].children.at(-1))`);
  await settle();

  assert.equal(ui.audios.length, 1);
  assert.equal(ui.audios[0].playCalls, 1);
  assert.equal(ui.run("Boolean(pendingPlayback)"), true);
  assert.equal(replayButton.textContent, "Play audio");
  const speechCalls = ui.calls.filter((call) => call.url === "/api/tts/local").length;

  await replayButton.emit("click");
  await settle();
  assert.equal(ui.audios[0].playCalls, 2);
  assert.equal(ui.run("pendingPlayback"), null);
  assert.equal(replayButton.textContent, "Listen");
  assert.equal(ui.calls.filter((call) => call.url === "/api/tts/local").length, speechCalls);
});

test("Test voice reuses prepared audio after an autoplay block", async () => {
  const ui = await app({
    locale: "ta-LK",
    localVoices: ["si-LK", "ta-LK", "ar-SA"],
    playErrors: ["NotAllowedError", null],
  });
  await ui.element("testVoiceButton").emit("click");
  await settle();
  assert.equal(ui.run("Boolean(pendingPlayback)"), true);
  assert.equal(ui.audios[0].playCalls, 1);

  await ui.element("testVoiceButton").emit("click");
  await settle();
  assert.equal(ui.audios[0].playCalls, 2);
  assert.equal(ui.run("pendingPlayback"), null);
  assert.equal(ui.calls.filter((call) => call.url === "/api/tts/local").length, 1);
});

test("generated speech requests the selected locale for all ten languages", async () => {
  for (const locale of locales) {
    const ui = await app({locale});
    await ui.run('speak("Localized assistant reply", true)');
    const expectedPath = ["si-LK", "ta-LK", "ar-SA"].includes(locale)
      ? "/api/tts/local" : "/api/voice/speak";
    const calls = ui.calls.filter((call) => call.url === expectedPath);
    assert.equal(calls.length, 1, locale);
    assert.equal(JSON.parse(calls[0].options.body).language_locale, locale);
    assert.equal(ui.audios.length, 1, locale);
    assert.equal(ui.spoken.length, 0, locale);
  }
});

test("a transient generated speech error is retried on the next reply", async () => {
  let speechCalls = 0;
  const ui = await app({
    locale: "de-DE",
    voices: [{name: "Deutsch", lang: "de-DE"}],
    fetch: (url) => url === "/api/voice/speak" && speechCalls++ === 0
      ? response({detail: "Temporary voice failure"}, 503) : undefined,
  });
  await ui.run('speak("Guten Tag", true)');
  assert.equal(ui.spoken.length, 1);
  assert.equal(ui.run("speechProviderUnavailable"), false);

  await ui.run('speak("Willkommen", true)');
  assert.equal(ui.calls.filter((call) => call.url === "/api/voice/speak").length, 2);
  assert.equal(ui.audios.length, 1);
});

test("the application rate limit is temporary and is not saved as an OpenAI quota failure", async () => {
  let speechCalls = 0;
  const ui = await app({
    locale: "de-DE",
    voices: [{name: "Deutsch", lang: "de-DE"}],
    fetch: (url) => url === "/api/voice/speak" && speechCalls++ === 0
      ? response({detail: "Too many requests. Please try again shortly."}, 429) : undefined,
  });
  await ui.run('speak("Guten Tag", true)');
  assert.equal(ui.run("speechProviderUnavailable"), false);
  assert.equal(ui.spoken.length, 1);

  await ui.run('speak("Willkommen", true)');
  assert.equal(ui.calls.filter((call) => call.url === "/api/voice/speak").length, 2);
  assert.equal(ui.audios.length, 1);
});

test("audio playback error cannot create a replay loop", async () => {
  const ui = await app({locale: "en-US", voices: [{name: "English", lang: "en-US"}]});
  await ui.run('speak("Hello", true)');
  assert.equal(ui.audios.length, 1);
  ui.audios[0].fail();
  ui.audios[0].fail();
  assert.equal(ui.spoken.length, 1);
});

test("a local audio playback error never falls through to a missing system voice", async () => {
  const ui = await app({
    configured: false,
    locale: "si-LK",
    voices: [{name: "English", lang: "en-US"}],
  });
  await ui.run('speak("ආයුබෝවන්", true)');
  ui.audios[0].fail();
  assert.equal(ui.spoken.length, 0);
  assert.match(ui.element("statusLine").textContent, /local audio could not be played/i);
});

test("browser playback chooses an exact voice and never assigns a different language", async () => {
  const exact = await app({
    configured: false,
    locale: "en-US",
    voices: [{name: "British", lang: "en-GB"}, {name: "American", lang: "en_US"}],
  });
  await exact.run('speak("Hello", true)');
  assert.equal(exact.spoken[0].voice.name, "American");

  const absent = await app({
    configured: false,
    locale: "si-LK",
    voices: [{name: "English", lang: "en-US"}],
  });
  absent.run('speakWithBrowser("ආයුබෝවන්", "si-LK", speechVersion)');
  assert.equal(absent.spoken.length, 0);
  assert.match(absent.element("statusLine").textContent, /could not provide .*Sinhala speech/i);
});

test("browser fallback requests every cloud locale tag when its voice list is empty", async () => {
  for (const locale of locales.filter((item) => !["si-LK", "ta-LK", "ar-SA"].includes(item))) {
    const ui = await app({configured: false, locale, voices: []});
    await ui.run('speak("Localized assistant reply", true)');
    assert.equal(ui.spoken.length, 1, locale);
    assert.equal(ui.spoken[0].lang, locale);
    assert.equal(ui.spoken[0].voice, null);
  }
});

test("Chinese playback does not substitute Cantonese or traditional regional voices", async () => {
  const ui = await app({
    configured: false,
    locale: "zh-CN",
    voices: [
      {name: "Cantonese regional", lang: "zh-HK"},
      {name: "Cantonese language", lang: "zh-yue"},
    ],
  });
  await ui.run('speak("您好", true)');
  assert.equal(ui.spoken.length, 0);
  assert.match(ui.element("statusLine").textContent, /could not provide .*Chinese speech/i);
});

test("Chinese playback accepts a compatible simplified Mandarin voice", async () => {
  const ui = await app({
    configured: false,
    locale: "zh-CN",
    voices: [
      {name: "English", lang: "en-US"},
      {name: "Mandarin simplified", lang: "zh-Hans-CN"},
    ],
  });
  await ui.run('speak("您好", true)');
  assert.equal(ui.spoken[0].lang, "zh-CN");
  assert.equal(ui.spoken[0].voice.name, "Mandarin simplified");
});

test("an actual browser language error gives actionable voice setup guidance", async () => {
  const ui = await app({
    configured: false,
    locale: "hi-IN",
    voices: [],
    synthesisError: "language-unavailable",
  });
  await ui.run('speak("नमस्ते", true)');
  assert.match(ui.element("statusLine").textContent, /could not provide .*Hindi speech/i);
  assert.match(ui.element("statusLine").textContent, /install and enable/i);
});

test("a synchronous browser synthesis failure is handled without losing text", async () => {
  const ui = await app({
    configured: false,
    locale: "hi-IN",
    synthesisThrow: true,
  });
  await ui.run('speak("नमस्ते", true)');
  assert.equal(ui.spoken.length, 1);
  assert.match(ui.element("statusLine").textContent, /could not provide .*Hindi speech/i);
});

test("speaking practice remains isolated from the booking session", async () => {
  const ui = await app({
    locale: "si-LK",
    transcriptions: [{
      text: "මට වෛද්‍ය හමුවක් අවශ්‍යයි",
      language_locale: "si-LK",
      language_detected: true,
    }],
  });
  const session = ui.run("sessionId");
  await ui.run('startCapture("practice")');
  ui.run("finishCapture()");
  await settle(8);
  assert.equal(ui.calls.filter((call) => call.url === "/api/messages").length, 0);
  assert.equal(ui.run("sessionId"), session);
  assert.deepEqual(ui.text(), ["Greeting si-LK 1"]);
  assert.match(ui.element("practiceResult").textContent, /100%/);
  assert.match(ui.element("practiceResult").textContent, /not pronunciation or fluency/);
});

test("practice handles Unicode punctuation and normalization", async () => {
  const ui = await app({locale: "es-ES"});
  assert.equal(ui.run('comparePractice("Sí, por favor!", "Si\\u0301 por favor")'), 100);
  assert.equal(ui.run('comparePractice("はい、お願いします。", "はい お願いします")'), 100);
  assert.equal(ui.run('comparePractice("ＡＢＣ！", "abc")'), 100);
  assert.equal(ui.run('comparePractice("", "")'), 0);
});

test("reset ignores stale message responses even when fetch ignores AbortSignal", async () => {
  const old = deferred();
  const ui = await app({fetch: (url) => url === "/api/messages" ? old.promise : undefined});
  const sending = ui.run('sendMessage("Old patient")');
  await flush();
  const previousCall = ui.calls.at(-1);
  await ui.run("startSession(false)");
  assert.equal(previousCall.options.signal.aborted, true);
  old.resolve(response({assistant_text: "Old answer", step: "done", status: "cancelled"}));
  await sending;
  assert.deepEqual(ui.text(), ["Greeting en-US 2"]);
  assert.equal(ui.run("sessionId"), "session-2");
});

test("overlapping new sessions keep only the most recent greeting", async () => {
  const slow = deferred();
  let count = 0;
  const ui = await app({fetch: (url) => {
    if (url === "/api/sessions" && ++count === 2) return slow.promise;
  }});
  const first = ui.run("startSession(false)");
  const second = ui.run("startSession(false)");
  await second;
  slow.resolve(response({session_id: "stale", assistant_text: "Stale greeting", step: "patient_name"}));
  assert.equal(await first, false);
  assert.deepEqual(ui.text(), ["Greeting en-US 2"]);
  assert.equal(ui.run("sessionId"), "session-2");
});

test("late microphone permission after cancellation immediately releases its stream", async () => {
  const permission = deferred();
  const track = {stopped: false, stop() { this.stopped = true; }};
  const ui = await app({getUserMedia: () => permission.promise});
  const starting = ui.run('startCapture("booking")');
  ui.run("stopCapture()");
  permission.resolve({getTracks: () => [track]});
  await starting;
  assert.equal(track.stopped, true);
  assert.equal(ui.recorders.length, 0);
  assert.equal(ui.run("capture"), null);
});

test("cancelled recording releases tracks and never uploads audio", async () => {
  const ui = await app();
  await ui.run('startCapture("booking")');
  assert.equal(ui.recorders[0].state, "recording");
  ui.run("stopCapture()");
  await settle();
  assert.equal(ui.tracks[0].stopped, true);
  assert.equal(ui.timers.size, 0);
  assert.equal(ui.calls.some((call) => call.url === "/api/voice/transcribe"), false);
});

test("late transcription after reset cannot enter the next conversation", async () => {
  const transcription = deferred();
  const ui = await app({fetch: (url) => url === "/api/voice/transcribe"
    ? transcription.promise : undefined});
  await ui.run('startCapture("booking")');
  ui.run("finishCapture()");
  await flush();
  await ui.run("startSession(false)");
  transcription.resolve(response({text: "Old recording", language_locale: "fr-FR", language_detected: true}));
  await settle();
  assert.deepEqual(ui.text(), ["Greeting en-US 2"]);
  assert.equal(ui.calls.filter((call) => call.url === "/api/messages").length, 0);
  assert.equal(ui.run("lockedLocale"), null);
});

test("expired session starts fresh in the effective locale and keeps reply for explicit resubmission", async () => {
  let messages = 0;
  const ui = await app({
    locale: "fr-FR",
    fetch: (url) => url === "/api/messages" && messages++ === 0
      ? response({detail: "Session expired"}, 404) : undefined,
  });
  await ui.run('sendMessage("Patient Démo")');
  await settle();
  assert.equal(ui.calls.filter((call) => call.url === "/api/messages").length, 1);
  assert.equal(ui.calls.filter((call) => call.url === "/api/sessions").length, 2);
  assert.equal(JSON.parse(ui.calls.filter((call) => call.url === "/api/sessions")[1].options.body).language_locale, "fr-FR");
  assert.deepEqual(ui.text(), ["Greeting fr-FR 2"]);
  assert.equal(ui.element("textInput").value, "Patient Démo");
  assert.match(ui.element("statusLine").textContent, /submit again/);
});

test("terminal booking disables booking input while preserving manual practice", async () => {
  const ui = await app({locale: "en-US", fetch: (url) => url === "/api/messages"
    ? response({assistant_text: "Cancelled", step: "cancelled", status: "cancelled"}) : undefined});
  await ui.run('sendMessage("cancel")');
  assert.equal(ui.element("textInput").disabled, true);
  assert.equal(ui.element("listenButton").disabled, true);
  assert.equal(ui.element("practiceButton").disabled, false);
  await ui.run('sendMessage("yes")');
  assert.equal(ui.calls.filter((call) => call.url === "/api/messages").length, 1);
});

test("failed message preserves editable text for retry", async () => {
  const ui = await app({fetch: (url) => url === "/api/messages"
    ? response({detail: "Please try again"}, 503) : undefined});
  await ui.run('sendMessage("Demo Patient")');
  assert.equal(ui.element("textInput").value, "Demo Patient");
  assert.equal(ui.element("textInput").disabled, false);
  assert.match(ui.element("statusLine").textContent, /kept in the text box/);
});

test("recording timer is visible only during server recording", async () => {
  const ui = await app();
  assert.equal(ui.element("recordingTimer").hidden, true);
  await ui.run('startCapture("booking")');
  assert.equal(ui.element("recordingTimer").hidden, false);
  ui.run("stopCapture()");
  await settle();
  assert.equal(ui.element("recordingTimer").hidden, true);
  assert.equal(ui.timers.size, 0);
});
