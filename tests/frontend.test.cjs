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
  element("languageSelect").value = options.locale || "en-US";
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
    results(chunks, {resultIndex = 0, end = false} = {}) {
      const results = chunks.map((chunk) => {
        const details = typeof chunk === "string" ? {text: chunk} : chunk;
        const result = [{transcript: details.text}];
        if (details.isFinal !== undefined) result.isFinal = details.isFinal;
        return result;
      });
      this.onresult?.({results, resultIndex});
      if (end) this.onend?.();
    }
    result(text, {isFinal, end = true, resultIndex} = {}) {
      const chunk = {text};
      if (isFinal !== undefined) chunk.isFinal = isFinal;
      const eventOptions = {end};
      if (resultIndex !== undefined) eventOptions.resultIndex = resultIndex;
      this.results([chunk], eventOptions);
    }
    error(error) { this.onerror?.({error}); }
    end() { this.onend?.(); }
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
    setTimeout(callback) {
      const id = Symbol("timer");
      timers.set(id, callback);
      return id;
    },
    clearTimeout(id) { timers.delete(id); },
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

test("markup defaults to English with one listening control and no automatic option", () => {
  assert.equal((markup.match(/id="listenButton"/g) || []).length, 1);
  assert.match(markup, /value="en-US" selected>English/);
  assert.doesNotMatch(markup, /value="auto"|Automatically detect|id="stopVoiceButton"|Stop voice|recordingTimer|Finish listening/);
  assert.doesNotMatch(source, /stopVoiceButton|AUTO_LOCALE|lockedLocale|recordingTimer|finishCapture|startServerRecording/);
  assert.doesNotMatch(source, /MediaRecorder|getUserMedia|\/api\/voice\/transcribe/);
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
  assert.equal(ui.element("languageSelect").value, "en-US");
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

test("one Start listening click recognizes and displays the exact final words", async () => {
  const transcript = "My exact captured words";
  const ui = await app({autoSpeak: false});

  assert.equal(ui.element("listenButtonLabel").textContent, "Start listening");
  assert.equal(ui.element("listenButton").attributes["aria-busy"], "false");
  assert.equal(ui.element("listenButton").attributes["aria-pressed"], undefined);
  await ui.element("listenButton").emit("click");
  assert.equal(ui.recognitions.length, 1);
  assert.equal(ui.recognitions[0].lang, "en-US");
  assert.equal(ui.recognitions[0].continuous, true);
  assert.equal(ui.recognitions[0].interimResults, true);
  assert.equal(ui.recorders.length, 0);
  assert.equal(ui.tracks.length, 0);
  assert.equal(ui.element("listenButtonLabel").textContent, "Listening\u2026");
  assert.equal(ui.element("listenButton").attributes["aria-busy"], "true");
  assert.equal(ui.element("listenButton").disabled, true);
  assert.equal(ui.element("voiceState").textContent, "Listening to you");

  ui.recognitions[0].result(transcript, {isFinal: true, end: false});
  await settle();
  assert.equal(ui.calls.filter((call) => call.url === "/api/messages").length, 0);
  assert.equal(ui.element("listenButtonLabel").textContent, "Listening\u2026");

  ui.recognitions[0].end();
  ui.recognitions[0].result("Duplicate stale result");
  await settle(8);

  assert.equal(ui.calls.some((call) => call.url === "/api/voice/transcribe"), false);
  const message = ui.calls.find((call) => call.url === "/api/messages");
  assert.equal(ui.calls.filter((call) => call.url === "/api/messages").length, 1);
  assert.equal(JSON.parse(message.options.body).text, transcript);
  assert.equal(JSON.parse(message.options.body).language_locale, "en-US");
  assert.deepEqual(ui.text(), ["Greeting en-US 1", transcript, "Reply en-US"]);
  assert.equal(ui.element("listenButtonLabel").textContent, "Start listening");
  assert.equal(ui.element("listenButton").attributes["aria-busy"], "false");
  assert.equal(ui.element("listenButton").disabled, false);
});

test("recognition buffers multiple final chunks and submits the complete utterance once", async () => {
  const ui = await app({autoSpeak: false});
  await ui.element("listenButton").emit("click");
  const recognition = ui.recognitions[0];

  recognition.results([
    {text: "September", isFinal: true},
    {text: "twenty", isFinal: false},
  ], {resultIndex: 0});
  await settle();
  assert.equal(ui.calls.filter((call) => call.url === "/api/messages").length, 0);

  recognition.results([
    {text: "September", isFinal: true},
    {text: "twenty third", isFinal: true},
    {text: "at nine", isFinal: false},
  ], {resultIndex: 1});
  await settle();
  assert.equal(ui.calls.filter((call) => call.url === "/api/messages").length, 0);

  recognition.results([
    {text: "September", isFinal: true},
    {text: "twenty third", isFinal: true},
    {text: "at nine thirty", isFinal: true},
    {text: ".", isFinal: true},
  ], {resultIndex: 2});
  recognition.end();
  await settle(8);

  const messages = ui.calls.filter((call) => call.url === "/api/messages");
  assert.equal(messages.length, 1);
  assert.equal(JSON.parse(messages[0].options.body).text, "September twenty third at nine thirty.");
  assert.deepEqual(ui.text(), [
    "Greeting en-US 1",
    "September twenty third at nine thirty.",
    "Reply en-US",
  ]);
});

test("interim speech is never submitted as a half answer", async () => {
  const ui = await app({autoSpeak: false});
  await ui.element("listenButton").emit("click");
  const recognition = ui.recognitions[0];

  recognition.result("twenty", {isFinal: false, end: false, resultIndex: 0});
  await settle();
  assert.equal(ui.calls.filter((call) => call.url === "/api/messages").length, 0);
  assert.equal(ui.timers.size, 2);

  recognition.result("twenty third of September", {isFinal: true, end: false, resultIndex: 0});
  await settle();
  assert.equal(ui.calls.filter((call) => call.url === "/api/messages").length, 0);
  assert.equal(ui.timers.size, 2);

  recognition.end();
  await settle(8);
  const messages = ui.calls.filter((call) => call.url === "/api/messages");
  assert.equal(messages.length, 1);
  assert.equal(JSON.parse(messages[0].options.body).text, "twenty third of September");
});

test("interim continuation refreshes the silence deadline until the phrase is final", async () => {
  const ui = await app({autoSpeak: false});
  await ui.element("listenButton").emit("click");
  const recognition = ui.recognitions[0];

  recognition.result("September", {isFinal: true, end: false, resultIndex: 0});
  await settle();
  assert.equal(ui.timers.size, 2);

  recognition.results([
    {text: "September", isFinal: true},
    {text: "twenty", isFinal: false},
  ], {resultIndex: 1});
  await settle();
  assert.equal(ui.timers.size, 2);
  assert.equal(ui.calls.filter((call) => call.url === "/api/messages").length, 0);

  recognition.results([
    {text: "September", isFinal: true},
    {text: "twenty third", isFinal: true},
  ], {resultIndex: 1});
  recognition.end();
  await settle(8);

  const messages = ui.calls.filter((call) => call.url === "/api/messages");
  assert.equal(messages.length, 1);
  assert.equal(JSON.parse(messages[0].options.body).text, "September twenty third");
});

test("stalled interim recognition stops without submitting an earlier fragment", async () => {
  const ui = await app({autoSpeak: false});
  await ui.element("listenButton").emit("click");
  const recognition = ui.recognitions[0];

  recognition.result("September", {isFinal: true, end: false, resultIndex: 0});
  recognition.results([
    {text: "September", isFinal: true},
    {text: "twenty", isFinal: false},
  ], {resultIndex: 1});
  const silenceTimeout = [...ui.timers.values()].at(-1);
  silenceTimeout();
  await settle(8);

  assert.equal(ui.calls.filter((call) => call.url === "/api/messages").length, 0);
  assert.equal(ui.run("capture"), null);
  assert.match(ui.element("statusLine").textContent, /did not finalize the complete phrase/);
});

test("Chinese recognition joins final chunks without inserting spaces", async () => {
  const ui = await app({autoSpeak: false});
  ui.element("languageSelect").value = "zh-CN";
  await ui.element("languageSelect").emit("change");
  await ui.element("listenButton").emit("click");
  const recognition = ui.recognitions[0];

  recognition.results([
    {text: "九月", isFinal: true},
    {text: "二十三日", isFinal: true},
  ]);
  recognition.end();
  await settle(8);

  const messages = ui.calls.filter((call) => call.url === "/api/messages");
  assert.equal(messages.length, 1);
  assert.equal(JSON.parse(messages[0].options.body).text, "九月二十三日");
});

test("Japanese recognition joins final chunks without inserting spaces", async () => {
  const ui = await app({autoSpeak: false});
  ui.element("languageSelect").value = "ja-JP";
  await ui.element("languageSelect").emit("change");
  await ui.element("listenButton").emit("click");
  const recognition = ui.recognitions[0];

  recognition.results([
    {text: "九月", isFinal: true},
    {text: "二十三日", isFinal: true},
  ]);
  recognition.end();
  await settle(8);

  const messages = ui.calls.filter((call) => call.url === "/api/messages");
  assert.equal(messages.length, 1);
  assert.equal(JSON.parse(messages[0].options.body).text, "九月二十三日");
});

test("a natural-silence grace period completes an utterance when the browser stays open", async () => {
  const ui = await app({autoSpeak: false});
  await ui.element("listenButton").emit("click");
  const recognition = ui.recognitions[0];
  recognition.result("September twenty third", {isFinal: true, end: false, resultIndex: 0});
  await settle();

  assert.equal(ui.calls.filter((call) => call.url === "/api/messages").length, 0);
  assert.equal(ui.timers.size, 2);
  const silenceTimeout = [...ui.timers.values()].at(-1);
  silenceTimeout();
  await settle(8);

  const messages = ui.calls.filter((call) => call.url === "/api/messages");
  assert.equal(messages.length, 1);
  assert.equal(JSON.parse(messages[0].options.body).text, "September twenty third");
  assert.equal(ui.run("capture"), null);
  assert.equal(ui.timers.size, 0);
});

test("Start listening interrupts active assistant playback before recognition", async () => {
  const ui = await app({autoSpeak: false});
  await ui.run('speak("Assistant reply", true, "en-US")');
  assert.equal(ui.audios[0].paused, undefined);

  await ui.element("listenButton").emit("click");
  assert.equal(ui.audios[0].paused, true);
  assert.equal(ui.recognitions.length, 1);
  assert.equal(ui.recorders.length, 0);
  ui.run("stopCapture()");
});

test("browser recognition and booking messages keep all ten selected locales", async () => {
  for (const locale of locales) {
    const ui = await app({locale, autoSpeak: false});
    await ui.element("listenButton").emit("click");
    assert.equal(ui.recognitions.length, 1, locale);
    assert.equal(ui.recognitions[0].lang, locale, locale);
    assert.equal(ui.recorders.length, 0, locale);
    ui.recognitions[0].result("Localized patient reply");
    await settle(8);

    const message = ui.calls.find((call) => call.url === "/api/messages");
    assert.equal(ui.run("effectiveLocale"), locale);
    assert.equal(JSON.parse(message.options.body).language_locale, locale);
    assert.deepEqual(ui.messageLocales(), [locale, locale, locale]);
    assert.equal(ui.calls.some((call) => call.url === "/api/voice/transcribe"), false, locale);
  }
});

test("the language indicator reports the selected language without a detection claim", async () => {
  const ui = await app({locale: "si-LK", autoSpeak: false});

  assert.equal(ui.run("effectiveLocale"), "si-LK");
  assert.equal(ui.element("languageSelect").value, "si-LK");
  assert.match(ui.element("detectedLanguage").textContent, /Using .*Sinhala/);
  assert.doesNotMatch(ui.element("detectedLanguage").textContent, /Detected/);
});

test("the selected language stays fixed across later recognition turns", async () => {
  const ui = await app({locale: "si-LK", autoSpeak: false});
  await ui.element("listenButton").emit("click");
  ui.recognitions[0].result("First patient reply");
  await settle(8);
  await ui.element("listenButton").emit("click");
  ui.recognitions[1].result("Second patient reply");
  await settle(8);
  assert.equal(ui.recognitions[0].lang, "si-LK");
  assert.equal(ui.recognitions[1].lang, "si-LK");
  assert.equal(ui.recorders.length, 0);
  assert.equal(ui.calls.some((call) => call.url === "/api/voice/transcribe"), false);
  assert.equal(ui.run("effectiveLocale"), "si-LK");
  const messages = ui.calls.filter((call) => call.url === "/api/messages");
  assert.equal(JSON.parse(messages[1].options.body).language_locale, "si-LK");
});

test("generated-voice quota does not change or disable browser listening", async () => {
  const ui = await app({
    locale: "fr-FR",
    voices: [{name: "English", lang: "en-US"}],
    fetch: (url) => url === "/api/voice/speak"
      ? response({detail: "OpenAI usage limit reached"}, 429) : undefined,
  });
  await ui.run('speak("Bonjour", true, "fr-FR")');
  await settle();

  assert.equal(ui.run("effectiveLocale"), "fr-FR");
  assert.equal(ui.run("speechProviderUnavailable"), true);
  assert.equal(ui.element("languageSelect").value, "fr-FR");
  assert.equal(ui.element("listenButton").disabled, false);

  await ui.element("listenButton").emit("click");
  assert.equal(ui.recognitions.length, 1);
  assert.equal(ui.recognitions[0].lang, "fr-FR");
  assert.equal(ui.recorders.length, 0);
  assert.equal(ui.calls.some((call) => call.url === "/api/voice/transcribe"), false);
  ui.run("stopCapture()");
  assert.equal(ui.calls.filter((call) => call.url === "/api/sessions").length, 1);
});

test("new booking preserves the selected language", async () => {
  const ui = await app({locale: "si-LK", autoSpeak: false});
  await ui.run("startSession(false)");
  assert.equal(ui.run("effectiveLocale"), "si-LK");
  assert.equal(ui.element("languageSelect").value, "si-LK");
  const sessions = ui.calls.filter((call) => call.url === "/api/sessions");
  assert.equal(JSON.parse(sessions.at(-1).options.body).language_locale, "si-LK");
});

test("without OpenAI the default English selection uses browser recognition", async () => {
  const ui = await app({configured: false});
  assert.equal(ui.element("languageSelect").value, "en-US");
  assert.equal(ui.element("listenButton").disabled, false);
  assert.equal(ui.element("practiceButton").disabled, false);
  assert.equal(ui.element("textInput").disabled, false);
  assert.match(ui.element("detectedLanguage").textContent, /Using English/);
  assert.match(ui.element("voiceAvailability").textContent, /browser's speech recognition/);
  assert.match(ui.element("voiceAvailability").textContent, /does not create or upload an audio recording/);
  await ui.element("listenButton").emit("click");
  assert.equal(ui.recognitions[0].lang, "en-US");
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
  const ui = await app({locale: "si-LK"});
  const session = ui.run("sessionId");
  const sample = ui.run("language().sample");
  await ui.element("practiceButton").emit("click");
  assert.equal(ui.recognitions.length, 1);
  assert.equal(ui.recognitions[0].lang, "si-LK");
  assert.equal(ui.recorders.length, 0);
  assert.equal(ui.element("practiceButtonLabel").textContent, "Listening to practice\u2026");
  assert.equal(ui.element("practiceButton").attributes["aria-busy"], "true");
  ui.recognitions[0].result(sample);
  await settle(8);
  assert.equal(ui.calls.filter((call) => call.url === "/api/messages").length, 0);
  assert.equal(ui.calls.some((call) => call.url === "/api/voice/transcribe"), false);
  assert.equal(ui.run("sessionId"), session);
  assert.deepEqual(ui.text(), ["Greeting si-LK 1"]);
  assert.match(ui.element("practiceResult").textContent, /100%/);
  assert.match(ui.element("practiceResult").textContent, /not pronunciation or fluency/);
  assert.equal(ui.element("practiceButtonLabel").textContent, "Practice speaking");
  assert.equal(ui.element("practiceButton").attributes["aria-busy"], "false");
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

test("new booking aborts active recognition and ignores its stale result", async () => {
  const ui = await app();
  await ui.element("listenButton").emit("click");
  const recognition = ui.recognitions[0];
  await ui.run("startSession(false)");
  assert.equal(recognition.aborted, true);
  assert.equal(ui.run("capture"), null);
  recognition.result("Stale recognized words");
  await settle(8);
  assert.deepEqual(ui.text(), ["Greeting en-US 2"]);
  assert.equal(ui.calls.filter((call) => call.url === "/api/messages").length, 0);
  assert.equal(ui.recorders.length, 0);
  assert.equal(ui.tracks.length, 0);
  assert.equal(ui.calls.some((call) => call.url === "/api/voice/transcribe"), false);
});

test("a recognition error restores the one-click listening control", async () => {
  const ui = await app({autoSpeak: false});
  await ui.element("listenButton").emit("click");
  ui.recognitions[0].error("no-speech");
  await settle();
  assert.equal(ui.run("capture"), null);
  assert.equal(ui.element("listenButtonLabel").textContent, "Start listening");
  assert.equal(ui.element("listenButton").attributes["aria-busy"], "false");
  assert.equal(ui.element("listenButton").disabled, false);
  assert.match(ui.element("statusLine").textContent, /No speech was detected/i);
  assert.equal(ui.calls.filter((call) => call.url === "/api/messages").length, 0);
  assert.equal(ui.calls.some((call) => call.url === "/api/voice/transcribe"), false);
});

test("a recognition safety timeout restores the one-click listening control", async () => {
  const ui = await app({autoSpeak: false});
  await ui.element("listenButton").emit("click");
  assert.equal(ui.timers.size, 1);

  const timeout = [...ui.timers.values()][0];
  timeout();

  assert.equal(ui.recognitions[0].aborted, true);
  assert.equal(ui.run("capture"), null);
  assert.equal(ui.timers.size, 0);
  assert.equal(ui.element("listenButtonLabel").textContent, "Start listening");
  assert.equal(ui.element("listenButton").attributes["aria-busy"], "false");
  assert.equal(ui.element("listenButton").disabled, false);
  assert.match(ui.element("statusLine").textContent, /no result was received/i);
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

test("recognition ending without a final result restores Start listening", async () => {
  const ui = await app({autoSpeak: false});
  await ui.element("listenButton").emit("click");
  ui.recognitions[0].end();
  assert.equal(ui.run("capture"), null);
  assert.equal(ui.element("listenButtonLabel").textContent, "Start listening");
  assert.equal(ui.element("listenButton").attributes["aria-busy"], "false");
  assert.equal(ui.element("listenButton").disabled, false);
  assert.match(ui.element("statusLine").textContent, /No speech received.*Start listening/i);
  assert.equal(ui.recorders.length, 0);
  assert.equal(ui.tracks.length, 0);
  assert.equal(ui.calls.some((call) => call.url === "/api/voice/transcribe"), false);
});
