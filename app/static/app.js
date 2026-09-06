"use strict";

const $ = (id) => document.getElementById(id);
const languageSelect = $("languageSelect");
const textInput = $("textInput");
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const AUTO_LOCALE = "auto";
const DEFAULT_LOCALE = "en-US";
const bookingSteps = ["patient_name", "specialty", "appointment_date", "appointment_time", "confirm"];

let config = {openai_configured: false, languages: []};
let sessionId = null;
let version = 0;
let ended = false;
let busy = false;
let pending = null;
let capture = null;
let effectiveLocale = DEFAULT_LOCALE;
let lockedLocale = null;
let detectionUnconfirmed = false;
let providerUnavailable = false;
let recorderUnavailable = false;
let speechVersion = 0;
let speechRequest = null;
let audio = null;
let audioUrl = null;

function languageFor(locale) {
  return config.languages.find((item) => item.locale === locale) || null;
}
function language() {
  return languageFor(effectiveLocale);
}
function manualLocale() {
  return languageSelect.value !== AUTO_LOCALE && languageFor(languageSelect.value)
    ? languageSelect.value : null;
}
function defaultLocale() {
  return languageFor(DEFAULT_LOCALE)?.locale || config.languages[0]?.locale || DEFAULT_LOCALE;
}
function localeLabel(locale) {
  return languageFor(locale)?.label || locale;
}
function isAutomatic() {
  return languageSelect.value === AUTO_LOCALE;
}
function browserRecognitionLocale() {
  return manualLocale() || lockedLocale;
}
function resetLanguageContext() {
  lockedLocale = null;
  detectionUnconfirmed = false;
  effectiveLocale = manualLocale() || defaultLocale();
}
function status(message, state = "ready") {
  $("statusLine").textContent = message;
  $("voiceState").textContent = {
    ready: "Ready when you are",
    listening: "Listening to you",
    speaking: "Your assistant is speaking",
    processing: "One moment…",
    error: "Let’s try again",
  }[state] || "Ready when you are";
  document.body.dataset.state = state;
  document.querySelector(".voice-card")?.classList.toggle("is-listening", state === "listening");
  document.querySelector(".voice-card")?.classList.toggle("is-speaking", state === "speaking");
}
function serverRecordingAvailable() {
  return config.openai_configured && !providerUnavailable && !recorderUnavailable
    && Boolean(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);
}
function captureStrategy() {
  if (!window.isSecureContext) return null;
  if (serverRecordingAvailable()) return "server";
  if (browserRecognitionLocale() && Recognition) return "browser";
  return null;
}
function renderLanguageContext() {
  const indicator = $("detectedLanguage");
  indicator.classList.remove("detected", "needs-selection");
  if (manualLocale()) {
    indicator.textContent = "Using " + localeLabel(effectiveLocale) + " for this booking.";
    return;
  }
  if (lockedLocale) {
    indicator.textContent = "Detected " + localeLabel(lockedLocale) + " · fixed for this booking.";
    indicator.classList.add("detected");
    return;
  }
  if (!serverRecordingAvailable()) {
    indicator.textContent = "Automatic detection is unavailable. Select a language for browser listening.";
    indicator.classList.add("needs-selection");
    return;
  }
  if (detectionUnconfirmed) {
    indicator.textContent = "Language not confirmed. Continuing in " + localeLabel(effectiveLocale)
      + "; select a language if needed.";
    indicator.classList.add("needs-selection");
    return;
  }
  indicator.textContent = "Speak a complete phrase so detection is more reliable.";
}
function controls() {
  const strategy = captureStrategy();
  textInput.disabled = busy || ended || Boolean(capture);
  $("textForm").querySelector("button").disabled = textInput.disabled;
  $("listenButton").disabled = busy || ended || !strategy
    || Boolean(capture && capture.purpose !== "booking");
  $("practiceButton").disabled = busy || !manualLocale() || !language() || !strategy
    || Boolean(capture && capture.purpose !== "practice");
  $("testVoiceButton").disabled = busy || Boolean(capture) || !language();
  languageSelect.disabled = busy || Boolean(capture);
  $("listenButtonLabel").textContent = capture?.purpose === "booking"
    ? "Finish listening" : "Start listening";
  $("practiceButtonLabel").textContent = capture?.purpose === "practice"
    ? "Finish practice" : "Practice speaking";
  $("recordingTimer").hidden = !capture?.recorder || capture.recorder.state !== "recording";
  $("listenButton").setAttribute("aria-pressed", String(capture?.purpose === "booking"));
  $("practiceButton").setAttribute("aria-pressed", String(capture?.purpose === "practice"));
  document.querySelectorAll("#quickReplies button, #quickReplies input").forEach((item) => {
    item.disabled = textInput.disabled;
  });
}
function setBusy(value) {
  busy = value;
  $("conversation").setAttribute("aria-busy", String(value));
  controls();
}
function appendMessage(role, text) {
  const item = document.createElement("div");
  item.className = "message " + role;
  const label = document.createElement("strong");
  label.textContent = role === "assistant" ? "Careline assistant" : "You";
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  paragraph.lang = effectiveLocale;
  paragraph.dir = "auto";
  item.append(label, paragraph);
  $("conversation").append(item);
  $("conversation").scrollTop = $("conversation").scrollHeight;
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(path, options);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    const networkError = new Error("The server could not be reached. Check your connection and try again.");
    networkError.status = 0;
    throw networkError;
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const message = typeof data.detail === "string" ? data.detail
      : response.status === 422 ? "Please check your message and language."
      : "Request failed (" + response.status + "). Please try again.";
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return response;
}
function json(body, signal) {
  return {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
    signal,
  };
}
function isQuotaError(error) {
  return error.status === 429 || /quota|usage limit|billing/i.test(error.message || "");
}
function isProviderAvailabilityError(error) {
  return error.status === 0 || [401, 402, 403, 429, 500, 502, 503, 504].includes(error.status);
}
function recordingServiceMessage(error) {
  const browserReady = Boolean(browserRecognitionLocale() && Recognition);
  if (isQuotaError(error)) {
    return browserReady
      ? "The server voice quota has been reached. Click Start listening again to use browser recognition, or type your reply."
      : "The server voice quota has been reached. Select a specific language to use browser recognition, or type your reply.";
  }
  return browserReady
    ? "The server voice service is unavailable. Click Start listening again to use browser recognition, or type your reply."
    : "Automatic voice detection is unavailable. Select a specific language for browser recognition, or type your reply.";
}

function normalizedVoiceLocale(locale) {
  return String(locale || "").toLowerCase().replaceAll("_", "-");
}
function matchingVoice(locale = effectiveLocale) {
  const voices = window.speechSynthesis?.getVoices() || [];
  const normalized = normalizedVoiceLocale(locale);
  const base = normalized.split("-")[0];
  return voices.find((voice) => normalizedVoiceLocale(voice.lang) === normalized)
    || voices.find((voice) => normalizedVoiceLocale(voice.lang).split("-")[0] === base);
}
function clearAudio(expectedAudio = null) {
  if (expectedAudio && audio !== expectedAudio) return;
  if (audio) {
    audio.pause();
    audio.removeAttribute("src");
    audio.load();
    audio = null;
  }
  if (audioUrl) URL.revokeObjectURL(audioUrl);
  audioUrl = null;
}
function stopSpeech() {
  speechVersion += 1;
  speechRequest?.abort();
  speechRequest = null;
  window.speechSynthesis?.cancel();
  clearAudio();
}
function speakWithBrowser(text, locale, token, unavailableMessage = "") {
  const synthesis = window.speechSynthesis;
  const voice = matchingVoice(locale);
  if (!synthesis || typeof SpeechSynthesisUtterance === "undefined" || !voice) {
    status(unavailableMessage || "No playback voice is installed for " + localeLabel(locale)
      + ". You can read the reply in the conversation.", "error");
    return false;
  }
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = locale;
  utterance.voice = voice;
  utterance.rate = 0.95;
  utterance.onstart = () => {
    if (token === speechVersion) status("Assistant speaking. Start listening to interrupt.", "speaking");
  };
  utterance.onend = () => {
    if (token === speechVersion) {
      status(ended ? "Conversation complete. You can start a new booking." : "Ready for your reply.");
    }
  };
  utterance.onerror = (event) => {
    if (token === speechVersion && !["interrupted", "canceled"].includes(event.error)) {
      status("Playback failed. You can continue with text.", "error");
    }
  };
  synthesis.speak(utterance);
  return true;
}
async function speak(text, force = false) {
  if (!force && !$("autoSpeak").checked) return;
  stopSpeech();
  const token = speechVersion;
  const locale = effectiveLocale;
  if (!config.openai_configured || providerUnavailable) {
    speakWithBrowser(text, locale, token);
    return;
  }
  try {
    speechRequest = new AbortController();
    status("Preparing the AI-generated voice…", "processing");
    const response = await request("/api/voice/speak", json({
      text,
      language_locale: locale,
    }, speechRequest.signal));
    speechRequest = null;
    const blob = await response.blob();
    if (token !== speechVersion) return;
    audioUrl = URL.createObjectURL(blob);
    const currentAudio = new Audio(audioUrl);
    audio = currentAudio;
    currentAudio.onended = () => {
      if (token !== speechVersion || audio !== currentAudio) return;
      clearAudio(currentAudio);
      status(ended ? "Conversation complete. You can start a new booking." : "Ready for your reply.");
    };
    currentAudio.onerror = () => {
      if (token !== speechVersion || audio !== currentAudio) return;
      clearAudio(currentAudio);
      speakWithBrowser(text, locale, token,
        "The generated audio could not be played, and no matching browser voice is installed. You can read the reply.");
    };
    await currentAudio.play();
    if (token === speechVersion && audio === currentAudio) {
      status("Assistant speaking. Start listening to interrupt.", "speaking");
    }
  } catch (error) {
    if (token !== speechVersion || error.name === "AbortError") return;
    speechRequest = null;
    clearAudio();
    if (isProviderAvailabilityError(error)) {
      providerUnavailable = true;
      capabilities();
    }
    const fallbackMessage = isQuotaError(error)
      ? "The server voice quota has been reached, and no matching browser playback voice is installed. You can read the reply."
      : error.name === "NotAllowedError"
        ? "Audio playback was blocked. Use Test voice to allow sound, or read the reply."
        : "The generated voice is unavailable, and no matching browser playback voice is installed. You can read the reply.";
    speakWithBrowser(text, locale, token, fallbackMessage);
  }
}

function capabilities() {
  const selected = manualLocale();
  const listeningLocale = browserRecognitionLocale();
  $("practicePhrase").textContent = selected
    ? languageFor(selected)?.sample || "No practice phrase is available for this language."
    : "Select a language above to load a matching practice phrase.";
  $("practicePhrase").lang = selected || effectiveLocale;
  $("practicePhrase").dir = "auto";
  $("voiceHint").textContent = selected
    ? "Speak naturally in " + localeLabel(selected) + "."
    : lockedLocale
      ? "Continue naturally in " + localeLabel(lockedLocale) + "."
      : "Start with a complete phrase in your language.";

  const notes = [];
  if (!window.isSecureContext) notes.push("Microphone access needs HTTPS or localhost.");
  if (config.openai_configured && !providerUnavailable) {
    $("voiceAvailability").textContent = "OpenAI processes recordings only after you press Start listening. This demo does not store audio.";
    notes.push("Automatic detection is available for recorded speech; detection can be uncertain for short names or phrases.");
  } else if (listeningLocale && Recognition) {
    $("voiceAvailability").textContent = "Listening uses your browser vendor’s speech service. This demo does not store audio.";
    notes.push("Browser recognition quality depends on your device, conversation language, and network.");
  } else {
    $("voiceAvailability").textContent = "Automatic detection is unavailable. Select a language for browser listening, or continue with text.";
    notes.push(Recognition
      ? "Choose a specific language to use browser recognition."
      : "This browser has no speech recognition; text booking remains available.");
  }
  if (listeningLocale) {
    notes.push(matchingVoice(listeningLocale)
      ? "A matching browser playback voice is installed."
      : "No matching browser playback voice is installed for this language.");
  }
  $("browserNotice").textContent = notes.join(" ");
  renderLanguageContext();
  controls();
}

const specialties = {
  "en-US": ["General Medicine", "Cardiology", "Dental"],
  "si-LK": ["සාමාන්‍ය වෛද්‍ය", "හෘද රෝග", "දන්ත"],
  "ta-LK": ["பொது மருத்துவம்", "இதயவியல்", "பல் மருத்துவம்"],
  "hi-IN": ["सामान्य चिकित्सा", "हृदय रोग", "दंत चिकित्सा"],
  "es-ES": ["Medicina general", "Cardiología", "Odontología"],
  "fr-FR": ["Médecine générale", "Cardiologie", "Dentaire"],
  "de-DE": ["Allgemeinmedizin", "Kardiologie", "Zahnmedizin"],
  "ar-SA": ["الطب العام", "القلب", "الأسنان"],
  "zh-CN": ["全科", "心脏科", "牙科"],
  "ja-JP": ["一般内科", "循環器科", "歯科"],
};
function localDate(date) {
  return date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, "0")
    + "-" + String(date.getDate()).padStart(2, "0");
}
function progress(step, result = "active") {
  const index = bookingSteps.indexOf(step);
  document.querySelectorAll("#bookingProgress [data-step]").forEach((item) => {
    const position = bookingSteps.indexOf(item.dataset.step);
    item.classList.toggle("active", position === index && result === "active");
    item.classList.toggle("completed", result === "booked" || (index >= 0 && position < index));
    if (position === index && result === "active") item.setAttribute("aria-current", "step");
    else item.removeAttribute("aria-current");
  });
  const replies = $("quickReplies");
  replies.replaceChildren();
  if (result !== "active") return;
  function reply(label, value = label) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "quick-reply";
    button.textContent = label;
    button.addEventListener("click", () => sendMessage(value));
    replies.append(button);
  }
  if (step === "patient_name") reply("Use demo name", "Demo Patient");
  if (step === "specialty") (specialties[effectiveLocale] || specialties[DEFAULT_LOCALE])
    .forEach((name) => reply(name));
  if (step === "confirm" && language()) {
    reply(language().yes[0]);
    reply(language().no[0]);
  }
  if (["appointment_date", "appointment_time"].includes(step)) {
    const isDate = step === "appointment_date";
    const input = document.createElement("input");
    input.type = isDate ? "date" : "time";
    input.required = true;
    input.setAttribute("aria-label", isDate ? "Appointment date" : "Appointment time");
    if (isDate) {
      const now = new Date();
      input.min = localDate(now);
      const max = new Date(now);
      max.setDate(max.getDate() + 365);
      input.max = localDate(max);
      now.setDate(now.getDate() + 1);
      input.value = localDate(now);
    } else {
      input.min = "08:00";
      input.max = "17:00";
      input.value = "10:30";
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = "quick-reply";
    button.textContent = isDate ? "Use date" : "Use time";
    button.addEventListener("click", () => {
      if (input.reportValidity()) sendMessage(input.value);
    });
    replies.append(input, button);
  }
  textInput.placeholder = {
    patient_name: "Type a demo patient name…",
    specialty: "Choose or type a specialty…",
    appointment_date: "YYYY-MM-DD",
    appointment_time: "HH:MM · 08:00–17:00",
    confirm: "Confirm or choose another time…",
  }[step] || "Type your reply…";
  controls();
}
function showBooking(booking) {
  const summary = $("bookingSummary");
  summary.replaceChildren();
  summary.hidden = false;
  const title = document.createElement("strong");
  title.textContent = "Demo appointment confirmed";
  const details = document.createElement("p");
  details.dir = "auto";
  details.textContent = [booking.patient_name, booking.specialty,
    booking.appointment_date + " at " + booking.appointment_time].join(" · ");
  const code = document.createElement("p");
  code.textContent = "Reference: " + booking.public_id.slice(-8).toUpperCase()
    + " · Demo only; no real appointment has been made.";
  summary.append(title, details, code);
}

async function startSession(shouldSpeak = true, preserveLanguage = false) {
  const token = ++version;
  pending?.abort();
  stopCapture();
  stopSpeech();
  sessionId = null;
  ended = false;
  if (!preserveLanguage) resetLanguageContext();
  pending = new AbortController();
  $("conversation").replaceChildren();
  $("bookingSummary").hidden = true;
  $("practiceResult").textContent = manualLocale()
    ? "Listen to the phrase, then record yourself saying it."
    : "Choose a specific language to practice its phrase.";
  $("practiceResult").classList.remove("success", "error");
  textInput.value = "";
  capabilities();
  progress("patient_name");
  setBusy(true);
  status("Starting your booking…", "processing");
  try {
    const data = await (await request("/api/sessions", json({
      language_locale: effectiveLocale,
    }, pending.signal))).json();
    if (token !== version) return false;
    sessionId = data.session_id;
    appendMessage("assistant", data.assistant_text);
    progress(data.step);
    status(isAutomatic()
      ? "Ready. Speak a complete phrase with the patient’s name, or type a demo name."
      : "Ready. Speak or type a demo patient name.");
    if (shouldSpeak) void speak(data.assistant_text);
    return true;
  } catch (error) {
    if (token === version && error.name !== "AbortError") status(error.message, "error");
    return false;
  } finally {
    if (token === version) setBusy(false);
  }
}
async function sendMessage(text) {
  const value = String(text || "").trim();
  if (!value || busy || ended || capture) return;
  if (value.length > 500) {
    status("Please keep your reply under 500 characters.", "error");
    return;
  }
  if (!sessionId && !(await startSession(false, true))) {
    textInput.value = value;
    return;
  }
  const token = version;
  stopSpeech();
  setBusy(true);
  pending = new AbortController();
  appendMessage("user", value);
  status("Checking your reply…", "processing");
  try {
    const data = await (await request("/api/messages", json({
      session_id: sessionId,
      language_locale: effectiveLocale,
      text: value,
    }, pending.signal))).json();
    if (token !== version) return;
    textInput.value = "";
    appendMessage("assistant", data.assistant_text);
    ended = data.status !== "active";
    progress(data.step, data.status);
    if (data.booking) showBooking(data.booking);
    status(ended
      ? "Conversation complete. Select New booking to start again."
      : "Ready for your reply.");
    void speak(data.assistant_text);
  } catch (error) {
    if (token !== version || error.name === "AbortError") return;
    if (error.status === 404) {
      const restarted = await startSession(false, true);
      textInput.value = value;
      status(restarted
        ? "Your previous booking session expired. A fresh session is ready; your reply is kept below for you to submit again."
        : "Your booking session expired and could not restart. Your reply is kept below; try again.", "error");
      return;
    }
    textInput.value = value;
    status(error.message + " Your reply is kept in the text box.", "error");
  } finally {
    if (token === version) setBusy(false);
  }
}

function releaseCapture(active) {
  clearInterval(active.timer);
  active.stream?.getTracks().forEach((track) => track.stop());
  if (capture === active) {
    capture = null;
    $("recordingTimer").textContent = "00:00";
    controls();
  }
}
function stopCapture() {
  if (!capture) return;
  const active = capture;
  active.cancelled = true;
  active.recognition?.abort();
  if (active.recorder?.state === "recording") active.recorder.stop();
  releaseCapture(active);
}
function finishCapture() {
  if (capture?.recorder?.state === "recording") capture.recorder.stop();
  else capture?.recognition?.stop();
}
function normalizePractice(text) {
  return Array.from(String(text || "").normalize("NFKC").toLocaleLowerCase()
    .replace(/[\p{P}\p{Z}\p{S}\s]/gu, ""));
}
function comparePractice(expected, actual) {
  const left = normalizePractice(expected);
  const right = normalizePractice(actual);
  let previous = Array.from({length: right.length + 1}, (_, index) => index);
  left.forEach((character, index) => {
    const row = [index + 1];
    right.forEach((other, column) => row.push(Math.min(
      row[column] + 1,
      previous[column + 1] + 1,
      previous[column] + Number(character !== other),
    )));
    previous = row;
  });
  const length = Math.max(left.length, right.length);
  return length ? Math.round(100 * (1 - previous[right.length] / length)) : 0;
}
function applyDetectedLanguage(data) {
  if (!isAutomatic() || lockedLocale) return;
  if (data?.language_detected === true && languageFor(data.language_locale)) {
    lockedLocale = data.language_locale;
    effectiveLocale = lockedLocale;
    detectionUnconfirmed = false;
  } else {
    detectionUnconfirmed = true;
  }
  capabilities();
}
async function receiveTranscript(text, active, transcription = null) {
  if (active.cancelled || active.version !== version) return;
  const value = String(text || "").trim();
  if (!value) {
    status("No speech was detected. Try again in a quiet space.", "error");
    return;
  }
  if (active.purpose === "practice") {
    const score = comparePractice(active.sample, value);
    $("practiceResult").textContent = "Transcript match: " + score + "%. Heard: “" + value + "”. "
      + (score >= 85 ? "Good match. Try another language when you’re ready." : "Listen to the sample and try again.")
      + " This checks recognized text, not pronunciation or fluency.";
    $("practiceResult").classList.toggle("success", score >= 85);
    $("practiceResult").classList.toggle("error", score < 85);
    status("Practice complete. Your booking has not changed.");
    return;
  }
  applyDetectedLanguage(transcription);
  textInput.value = value;
  await sendMessage(value);
}
function startBrowserRecognition(active) {
  const recognition = new Recognition();
  active.recognition = recognition;
  recognition.lang = active.locale;
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  recognition.onstart = () => {
    if (!active.cancelled) status("Listening. Speak now; pause when you’re finished.", "listening");
  };
  recognition.onresult = (event) => {
    active.received = true;
    releaseCapture(active);
    void receiveTranscript(event.results[0][0].transcript, active);
  };
  recognition.onerror = (event) => {
    if (active.cancelled) return;
    active.cancelled = true;
    const errors = {
      "not-allowed": "Microphone access was denied. Allow it in browser settings, or type your reply.",
      "no-speech": "No speech was detected. Try again in a quiet space.",
      "audio-capture": "No microphone is available. Connect one or type your reply.",
      network: "Browser speech could not connect. Try again or type your reply.",
      "language-not-supported": "Browser recognition does not support the selected language. Choose another language or use text.",
    };
    status(errors[event.error] || "Speech recognition stopped. Try again or type your reply.", "error");
    releaseCapture(active);
  };
  recognition.onend = () => {
    if (capture === active) releaseCapture(active);
    if (!active.cancelled && !active.received && active.version === version) {
      status("No speech received. Select Start listening to try again.");
    }
  };
  recognition.start();
}
async function startServerRecording(active) {
  status("Waiting for microphone permission…", "processing");
  const stream = await navigator.mediaDevices.getUserMedia({audio: true});
  if (active.cancelled || active.version !== version) {
    stream.getTracks().forEach((track) => track.stop());
    return;
  }
  active.stream = stream;
  const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"]
    .find((type) => MediaRecorder.isTypeSupported(type));
  if (!mimeType) {
    recorderUnavailable = true;
    throw new Error("This browser cannot create a supported recording. Select a language to use browser recognition, or use text.");
  }
  const recorder = new MediaRecorder(stream, {mimeType});
  active.recorder = recorder;
  const chunks = [];
  recorder.ondataavailable = (event) => {
    if (event.data.size) chunks.push(event.data);
  };
  recorder.onerror = () => {
    if (active.cancelled) return;
    active.cancelled = true;
    recorderUnavailable = true;
    releaseCapture(active);
    capabilities();
    status("Recording failed. Select a language for browser recognition, or type your reply.", "error");
  };
  recorder.onstop = async () => {
    releaseCapture(active);
    if (active.cancelled || active.version !== version) return;
    const blob = new Blob(chunks, {type: recorder.mimeType});
    if (blob.size < 100) {
      status("The recording was empty. Please try again.", "error");
      return;
    }
    const form = new FormData();
    form.append("audio", blob, mimeType.includes("mp4") ? "recording.mp4" : "recording.webm");
    const autoUnlocked = isAutomatic() && !lockedLocale;
    form.append("language_locale", autoUnlocked ? AUTO_LOCALE : active.locale);
    form.append("fallback_locale", active.locale);
    pending = new AbortController();
    setBusy(true);
    status(autoUnlocked ? "Transcribing and identifying the language…" : "Transcribing your recording…", "processing");
    try {
      const response = await request("/api/voice/transcribe", {
        method: "POST",
        body: form,
        signal: pending.signal,
      });
      const data = await response.json();
      if (active.cancelled || active.version !== version) return;
      setBusy(false);
      await receiveTranscript(data.text, active, data);
    } catch (error) {
      if (active.version !== version || error.name === "AbortError") return;
      if (isProviderAvailabilityError(error)) {
        providerUnavailable = true;
        capabilities();
        status(recordingServiceMessage(error), "error");
      } else {
        status(error.message, "error");
      }
    } finally {
      if (active.version === version) setBusy(false);
    }
  };
  recorder.start();
  controls();
  let seconds = 0;
  active.timer = setInterval(() => {
    seconds += 1;
    $("recordingTimer").textContent = "00:" + String(seconds).padStart(2, "0");
    if (seconds >= 30 && recorder.state === "recording") recorder.stop();
  }, 1000);
  status("Recording. Speak now, then finish (30 seconds maximum).", "listening");
}
async function startCapture(purpose) {
  if (capture) {
    if (capture.purpose === purpose) finishCapture();
    return;
  }
  const strategy = captureStrategy();
  if (busy || !strategy || (purpose === "booking" && ended)) return;
  if (purpose === "practice" && !manualLocale()) {
    status("Select a language before starting speaking practice.", "error");
    return;
  }
  stopSpeech();
  const active = {
    purpose,
    version,
    locale: effectiveLocale,
    sample: language()?.sample || "",
    strategy,
    cancelled: false,
  };
  capture = active;
  controls();
  try {
    if (strategy === "server") await startServerRecording(active);
    else startBrowserRecognition(active);
  } catch (error) {
    if (active.cancelled || active.version !== version) return;
    active.cancelled = true;
    releaseCapture(active);
    capabilities();
    status(error.name === "NotAllowedError"
      ? "Microphone access was denied. Allow it in browser settings, or use text."
      : error.message, "error");
  }
}

$("newSessionButton").addEventListener("click", () => startSession());
languageSelect.addEventListener("change", () => startSession());
$("listenButton").addEventListener("click", () => startCapture("booking"));
$("practiceButton").addEventListener("click", () => startCapture("practice"));
$("testVoiceButton").addEventListener("click", () => {
  if (language()) void speak(language().sample, true);
});
$("autoSpeak").addEventListener("change", () => {
  if (!$("autoSpeak").checked) {
    stopSpeech();
    status("Automatic spoken replies paused.");
  }
});
$("stopVoiceButton").addEventListener("click", () => {
  stopSpeech();
  stopCapture();
  status(busy
    ? "Audio stopped. Waiting for the current request…"
    : "Voice stopped. You can continue with text.");
});
$("textForm").addEventListener("submit", (event) => {
  event.preventDefault();
  void sendMessage(textInput.value);
});
window.speechSynthesis?.addEventListener?.("voiceschanged", capabilities);
window.addEventListener("pagehide", () => {
  stopCapture();
  stopSpeech();
  pending?.abort();
});

async function initialize() {
  setBusy(true);
  try {
    config = await (await request("/api/config")).json();
    const previous = languageSelect.value;
    const automatic = document.createElement("option");
    automatic.value = AUTO_LOCALE;
    automatic.textContent = "Automatically detect · " + config.languages.length + " languages";
    languageSelect.replaceChildren(automatic, ...config.languages.map((item) => {
      const option = document.createElement("option");
      option.value = item.locale;
      option.textContent = item.label;
      return option;
    }));
    languageSelect.value = previous === AUTO_LOCALE || !languageFor(previous) ? AUTO_LOCALE : previous;
    resetLanguageContext();
    capabilities();
    await startSession(false);
  } catch (error) {
    capabilities();
    setBusy(false);
    status(error.message, "error");
  }
}
void initialize();
