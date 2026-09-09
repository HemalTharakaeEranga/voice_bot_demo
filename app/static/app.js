"use strict";

const $ = (id) => document.getElementById(id);
const languageSelect = $("languageSelect");
const textInput = $("textInput");
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const LOCAL_TTS_LOCALES = new Set(["si-LK", "ta-LK", "ar-SA"]);
const UNSPACED_TRANSCRIPT_LOCALES = new Set(["zh-CN", "ja-JP"]);
const DEFAULT_LOCALE = "en-US";
const FINAL_RESULT_SILENCE_MS = 1200;
const INTERIM_RESULT_SILENCE_MS = 1800;
const RECOGNITION_END_GRACE_MS = 1000;
const RECOGNITION_SAFETY_MS = 45000;
const bookingSteps = ["patient_name", "specialty", "appointment_date", "appointment_time", "confirm"];

let config = {
  openai_configured: false,
  clinic_today: "",
  clinic_utc_offset_minutes: 0,
  local_voice_locales: [],
  languages: [],
};
let sessionId = null;
let version = 0;
let ended = false;
let busy = false;
let pending = null;
let capture = null;
let effectiveLocale = DEFAULT_LOCALE;
// Reply playback and browser recognition are independent. A TTS provider
// failure must never disable the microphone for the rest of the page.
let speechProviderUnavailable = false;
let speechVersion = 0;
let speechRequest = null;
let audio = null;
let audioUrl = null;
let pendingPlayback = null;
let browserVoicesKnown = false;

function languageFor(locale) {
  return config.languages.find((item) => item.locale === locale) || null;
}
function language() {
  return languageFor(effectiveLocale);
}
function selectedLocale() {
  return languageFor(languageSelect.value)?.locale || null;
}
function defaultLocale() {
  return languageFor(DEFAULT_LOCALE)?.locale || config.languages[0]?.locale || DEFAULT_LOCALE;
}
function localeLabel(locale) {
  return languageFor(locale)?.label || locale;
}
function localVoiceAvailable(locale) {
  return Array.isArray(config.local_voice_locales)
    && config.local_voice_locales.includes(locale);
}
function usesLocalTts(locale) {
  return LOCAL_TTS_LOCALES.has(locale);
}
function resetLanguageContext() {
  effectiveLocale = selectedLocale() || defaultLocale();
}
function renderVoiceHint(state = document.body.dataset.state) {
  $("voiceHint").textContent = state === "listening"
    ? "Speak now in " + localeLabel(effectiveLocale)
      + ". Your final words will appear automatically."
    : state === "speaking"
      ? "Select Start listening to interrupt and reply."
      : state === "processing"
        ? "Please wait while Careline prepares the next step."
        : selectedLocale()
          ? "Speak naturally in " + localeLabel(effectiveLocale) + "."
          : "Select a conversation language to begin.";
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
  renderVoiceHint(state);
  document.querySelector(".voice-card")?.classList.toggle("is-listening", state === "listening");
  document.querySelector(".voice-card")?.classList.toggle("is-speaking", state === "speaking");
}
function browserRecognitionAvailable() {
  return Boolean(window.isSecureContext && selectedLocale() && Recognition);
}
function renderLanguageContext() {
  const indicator = $("detectedLanguage");
  indicator.classList.remove("needs-selection");
  if (selectedLocale()) {
    indicator.textContent = "Using " + localeLabel(effectiveLocale) + " for this booking.";
    return;
  }
  indicator.textContent = "Select a conversation language to begin.";
  indicator.classList.add("needs-selection");
}
function controls() {
  const canListen = browserRecognitionAvailable();
  textInput.disabled = busy || ended || Boolean(capture);
  $("textForm").querySelector("button").disabled = textInput.disabled;
  $("listenButton").disabled = busy || ended || !canListen || Boolean(capture);
  $("practiceButton").disabled = busy || !selectedLocale() || !language() || !canListen
    || Boolean(capture);
  $("testVoiceButton").disabled = busy || Boolean(capture) || !language();
  languageSelect.disabled = busy || Boolean(capture);
  $("listenButtonLabel").textContent = capture?.purpose === "booking"
    ? "Listening…" : "Start listening";
  $("practiceButtonLabel").textContent = capture?.purpose === "practice"
    ? "Listening to practice…" : "Practice speaking";
  $("listenButton").setAttribute("aria-busy", String(capture?.purpose === "booking"));
  $("practiceButton").setAttribute("aria-busy", String(capture?.purpose === "practice"));
  document.querySelectorAll("#quickReplies button, #quickReplies input").forEach((item) => {
    item.disabled = textInput.disabled;
  });
  document.querySelectorAll(".message-speak-button").forEach((item) => {
    item.disabled = busy || Boolean(capture);
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
  const header = document.createElement("div");
  header.className = "message-header";
  const label = document.createElement("strong");
  label.textContent = role === "assistant" ? "Careline assistant" : "You";
  header.append(label);
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  paragraph.lang = effectiveLocale;
  paragraph.dir = "auto";
  let replayButton = null;
  if (role === "assistant") {
    const replyLocale = effectiveLocale;
    replayButton = document.createElement("button");
    replayButton.type = "button";
    replayButton.className = "message-speak-button";
    replayButton.textContent = "Listen";
    replayButton.setAttribute("aria-label", "Play this assistant reply");
    replayButton.addEventListener("click", () => {
      if (!busy && !capture) void replayReply(text, replyLocale, replayButton);
    });
    header.append(replayButton);
  }
  item.append(header, paragraph);
  $("conversation").append(item);
  $("conversation").scrollTop = $("conversation").scrollHeight;
  return replayButton;
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
  return /quota|usage limit|billing|insufficient[_ ]quota|credit|spend limit/i.test(
    error.message || "",
  );
}
function isPersistentProviderError(error) {
  return isQuotaError(error) || [401, 402, 403].includes(error.status)
    || /api key|authentication|unauthorized|permissions/i.test(error.message || "");
}
function normalizedVoiceLocale(locale) {
  return String(locale || "").toLowerCase().replaceAll("_", "-");
}
function compatibleVoiceLocale(requestedLocale, voiceLocale) {
  const requested = normalizedVoiceLocale(requestedLocale);
  const candidate = normalizedVoiceLocale(voiceLocale);
  if (!requested || !candidate) return false;
  const requestedBase = requested.split("-")[0];
  const candidateParts = candidate.split("-");
  if (candidateParts[0] !== requestedBase) return false;
  if (requestedBase !== "zh") return true;

  // zh-CN content uses Mandarin and simplified characters. Do not select a
  // Cantonese or traditional-Chinese regional voice merely because it shares
  // the `zh` primary tag. Generic zh and zh-Hans variants remain compatible.
  return !candidateParts.some((part) => ["hant", "hk", "mo", "tw", "yue"].includes(part));
}
function matchingVoice(locale = effectiveLocale, availableVoices = null) {
  const voices = availableVoices || window.speechSynthesis?.getVoices() || [];
  if (voices.length) browserVoicesKnown = true;
  const normalized = normalizedVoiceLocale(locale);
  if (!normalized) return null;
  const base = normalized.split("-")[0];
  const exact = voices.find((voice) => normalizedVoiceLocale(voice.lang) === normalized);
  if (exact) return exact;
  const generic = voices.find((voice) => normalizedVoiceLocale(voice.lang) === base);
  if (generic) return generic;
  return voices.find((voice) => compatibleVoiceLocale(normalized, voice.lang)) || null;
}
function isMessageSpeakButton(button) {
  return String(button?.className || "").split(/\s+/).includes("message-speak-button");
}
function clearAudio(expectedAudio = null) {
  if (expectedAudio && audio !== expectedAudio) return;
  const currentAudio = audio;
  if (audio) {
    audio.pause();
    audio.removeAttribute("src");
    audio.load();
    audio = null;
  }
  if (audioUrl) URL.revokeObjectURL(audioUrl);
  audioUrl = null;
  if (pendingPlayback?.audio === currentAudio) {
    if (isMessageSpeakButton(pendingPlayback.actionButton)) {
      pendingPlayback.actionButton.textContent = "Listen";
      pendingPlayback.actionButton.classList.remove("audio-ready");
    }
    pendingPlayback = null;
  }
}
function stopSpeech() {
  speechVersion += 1;
  speechRequest?.abort();
  speechRequest = null;
  window.speechSynthesis?.cancel();
  clearAudio();
}
function browserVoiceUnavailableMessage(locale, prefix = "") {
  const help = localVoiceAvailable(locale)
    ? "Check the bundled local voice files, or install and enable this language’s system speech voice."
    : config.openai_configured
    ? "Check OpenAI API quota, or install and enable this language’s system speech voice."
    : "Install and enable this language’s system speech voice, or configure OpenAI voice.";
  return (prefix ? prefix + " " : "") + "Your browser could not provide "
    + localeLabel(locale) + " speech. " + help;
}
function speakWithBrowser(text, locale, token, unavailableMessage = "") {
  const synthesis = window.speechSynthesis;
  if (!synthesis || typeof SpeechSynthesisUtterance === "undefined") {
    status(unavailableMessage || browserVoiceUnavailableMessage(locale), "error");
    return false;
  }
  const voices = synthesis.getVoices() || [];
  if (voices.length) browserVoicesKnown = true;
  const voice = matchingVoice(locale, voices);
  if (browserVoicesKnown && !voice) {
    status(unavailableMessage || browserVoiceUnavailableMessage(locale), "error");
    return false;
  }
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = locale;
  // An empty getVoices() list can mean that voices are still loading. Until
  // the browser reports its list, leaving voice unset lets it resolve the
  // exact BCP 47 tag. Once the list is known, a compatible voice is required.
  if (voice) utterance.voice = voice;
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
    const errorName = event?.error || "";
    if (token === speechVersion && !["interrupted", "canceled"].includes(errorName)) {
      status(unavailableMessage || browserVoiceUnavailableMessage(locale), "error");
    }
  };
  try {
    synthesis.speak(utterance);
  } catch {
    status(unavailableMessage || browserVoiceUnavailableMessage(locale), "error");
    return false;
  }
  return true;
}
async function playPreparedAudio() {
  const prepared = pendingPlayback;
  if (!prepared || audio !== prepared.audio) return false;
  try {
    await prepared.audio.play();
    if (pendingPlayback === prepared) {
      pendingPlayback = null;
      if (isMessageSpeakButton(prepared.actionButton)) {
        prepared.actionButton.textContent = "Listen";
        prepared.actionButton.classList.remove("audio-ready");
      }
      status("Assistant speaking. Start listening to interrupt.", "speaking");
    }
    return true;
  } catch (error) {
    if (pendingPlayback !== prepared) return false;
    if (error.name === "NotAllowedError") {
      status("Audio is ready. Select Play audio again to allow sound.", "error");
      return false;
    }
    clearAudio(prepared.audio);
    if (usesLocalTts(prepared.locale)) {
      status("The local audio could not be played. Select Listen to generate it again.", "error");
      return false;
    }
    return speakWithBrowser(
      prepared.text,
      prepared.locale,
      prepared.token,
      browserVoiceUnavailableMessage(
        prepared.locale,
        "The generated audio could not be played.",
      ),
    );
  }
}
async function replayReply(text, locale, actionButton) {
  if (pendingPlayback?.text === text && pendingPlayback.locale === locale) {
    await playPreparedAudio();
    return;
  }
  // A deliberate replay is also an explicit retry after quota or permission
  // settings have been corrected; no page reload should be required.
  speechProviderUnavailable = false;
  capabilities();
  await speak(text, true, locale, actionButton);
}
async function speak(text, force = false, locale = effectiveLocale, actionButton = null) {
  if (!force && !$("autoSpeak").checked) return;
  stopSpeech();
  const token = speechVersion;
  const useLocalVoice = usesLocalTts(locale);
  if (!useLocalVoice && (!config.openai_configured || speechProviderUnavailable)) {
    speakWithBrowser(text, locale, token);
    return;
  }
  try {
    speechRequest = new AbortController();
    status(useLocalVoice ? "Preparing the offline voice…" : "Preparing the AI-generated voice…", "processing");
    const speechPath = useLocalVoice ? "/api/tts/local" : "/api/voice/speak";
    const response = await request(speechPath, json({
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
      if (useLocalVoice) {
        status("The local audio could not be played. Select Listen to try again.", "error");
        return;
      }
      speakWithBrowser(text, locale, token,
        browserVoiceUnavailableMessage(locale, "The generated audio could not be played."));
    };
    await currentAudio.play();
    if (token === speechVersion && audio === currentAudio) {
      status("Assistant speaking. Start listening to interrupt.", "speaking");
    }
  } catch (error) {
    if (token !== speechVersion || error.name === "AbortError") return;
    speechRequest = null;
    if (error.name === "NotAllowedError" && audio) {
      pendingPlayback = {audio, text, locale, token, actionButton};
      if (isMessageSpeakButton(actionButton)) {
        actionButton.textContent = "Play audio";
        actionButton.classList.add("audio-ready");
      }
      status(
        actionButton
          ? "Audio is ready. Select Play audio on this reply to allow sound."
          : "Audio is ready. Select Test voice again to allow sound.",
        "error",
      );
      return;
    }
    clearAudio();
    if (!useLocalVoice && isPersistentProviderError(error)) {
      speechProviderUnavailable = true;
      capabilities();
    }
    if (useLocalVoice) {
      status(error.message || "The local voice is unavailable. Please try again.", "error");
      return;
    }
    const fallbackMessage = isQuotaError(error)
      ? browserVoiceUnavailableMessage(locale, "The server voice quota has been reached.")
      : browserVoiceUnavailableMessage(locale, "The generated voice is unavailable.");
    speakWithBrowser(text, locale, token, fallbackMessage);
  }
}

function capabilities() {
  const selected = selectedLocale();
  const listeningLocale = selected;
  $("practicePhrase").textContent = selected
    ? languageFor(selected)?.sample || "No practice phrase is available for this language."
    : "Select a language above to load a matching practice phrase.";
  $("practicePhrase").lang = selected || effectiveLocale;
  $("practicePhrase").dir = "auto";
  renderVoiceHint();

  const notes = [];
  if (!window.isSecureContext) notes.push("Microphone access needs HTTPS or localhost.");
  if (!window.isSecureContext) {
    $("voiceAvailability").textContent = "Voice listening requires HTTPS or localhost. You can continue with text.";
  } else if (listeningLocale && Recognition) {
    $("voiceAvailability").textContent = "Listening uses your browser's speech recognition in the selected language. Careline does not create or upload an audio recording; your browser's speech service may process audio under its own terms.";
    notes.push("Browser recognition quality depends on your device, conversation language, and network.");
  } else {
    $("voiceAvailability").textContent = "Voice listening is unavailable in this browser. You can continue with text.";
    notes.push(Recognition
      ? "Choose a supported conversation language to use browser recognition."
      : "This browser has no speech recognition; text booking remains available.");
  }
  if (listeningLocale) {
    if (usesLocalTts(listeningLocale)) {
      notes.push(localVoiceAvailable(listeningLocale)
        ? "Replies use the bundled offline " + localeLabel(listeningLocale) + " voice."
        : "The local " + localeLabel(listeningLocale)
          + " voice is not ready on this server. Check the bundled model files.");
    } else if (!window.speechSynthesis || typeof SpeechSynthesisUtterance === "undefined") {
      notes.push("This browser has no speech playback service.");
    } else if ((!config.openai_configured || speechProviderUnavailable)
      && browserVoicesKnown && !matchingVoice(listeningLocale)) {
      notes.push("No compatible " + localeLabel(listeningLocale)
        + " playback voice is installed in this browser or operating system.");
    } else {
      notes.push(matchingVoice(listeningLocale)
        ? "A listed browser voice matches this language."
        : "The browser will try to resolve a " + localeLabel(listeningLocale)
          + " voice when playback starts.");
    }
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
function clinicDate() {
  const value = String(config.clinic_today || "");
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return new Date();
  const parsed = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return localDate(parsed) === value ? parsed : new Date();
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
      const now = clinicDate();
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
    appointment_date: "September 23, 9/23, 23/9, or 2026/9/23",
    appointment_time: "9 AM, 9:30, 9/30, 9-30, or 14:30",
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

async function startSession(shouldSpeak = true) {
  const token = ++version;
  pending?.abort();
  stopCapture();
  stopSpeech();
  sessionId = null;
  ended = false;
  resetLanguageContext();
  pending = new AbortController();
  $("conversation").replaceChildren();
  $("bookingSummary").hidden = true;
  $("practiceResult").textContent = selectedLocale()
    ? "Listen to the phrase, then select Practice speaking and say it."
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
    const replayButton = appendMessage("assistant", data.assistant_text);
    progress(data.step);
    status("Ready. Speak or type a demo patient name.");
    if (shouldSpeak) void speak(data.assistant_text, false, effectiveLocale, replayButton);
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
  if (!sessionId && !(await startSession(false))) {
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
    const replayButton = appendMessage("assistant", data.assistant_text);
    ended = data.status !== "active";
    progress(data.step, data.status);
    if (data.booking) showBooking(data.booking);
    status(ended
      ? "Conversation complete. Select New booking to start again."
      : "Ready for your reply.");
    void speak(data.assistant_text, false, effectiveLocale, replayButton);
  } catch (error) {
    if (token !== version || error.name === "AbortError") return;
    if (error.status === 404) {
      const restarted = await startSession(false);
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
  clearTimeout(active.safetyTimeout);
  clearTimeout(active.silenceTimeout);
  clearTimeout(active.endTimeout);
  if (capture === active) {
    capture = null;
    controls();
  }
}
function stopCapture() {
  if (!capture) return;
  const active = capture;
  active.cancelled = true;
  active.recognition?.abort();
  releaseCapture(active);
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
async function receiveTranscript(text, active) {
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
  textInput.value = value;
  await sendMessage(value);
}
function completeTranscript(active) {
  const chunks = [...active.finalResults.entries()]
    .sort(([left], [right]) => left - right)
    .map(([, text]) => text.trim())
    .filter(Boolean);
  const unspaced = UNSPACED_TRANSCRIPT_LOCALES.has(active.locale);
  return chunks.reduce((transcript, chunk) => {
    if (!transcript || unspaced || /^[,.;:!?%)\]}…，。！？、؛،]/u.test(chunk)) {
      return transcript + chunk;
    }
    return transcript + " " + chunk;
  }, "");
}
function submitRecognition(active) {
  if (active.cancelled || active.submitted || active.version !== version || capture !== active) return;
  if (active.hasPendingInterim) {
    active.cancelled = true;
    releaseCapture(active);
    status("The browser did not finalize the complete phrase. Select Start listening to try again.", "error");
    return;
  }
  active.submitted = true;
  const transcript = completeTranscript(active);
  releaseCapture(active);
  if (!transcript) {
    status("No speech received. Select Start listening to try again.");
    return;
  }
  void receiveTranscript(transcript, active);
}
function scheduleRecognitionSubmit(active) {
  clearTimeout(active.endTimeout);
  active.endTimeout = setTimeout(() => submitRecognition(active), RECOGNITION_END_GRACE_MS);
}
function scheduleRecognitionEnd(active, delay = FINAL_RESULT_SILENCE_MS) {
  clearTimeout(active.silenceTimeout);
  active.silenceTimeout = setTimeout(() => {
    if (active.cancelled || active.submitted || capture !== active) return;
    active.stopRequested = true;
    scheduleRecognitionSubmit(active);
    try {
      active.recognition.stop();
    } catch (_error) {
      submitRecognition(active);
    }
  }, delay);
}
function startBrowserRecognition(active) {
  const recognition = new Recognition();
  active.recognition = recognition;
  recognition.lang = active.locale;
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;
  recognition.onstart = () => {
    if (!active.cancelled) status("Listening. Speak now; pause when you’re finished.", "listening");
  };
  recognition.onresult = (event) => {
    if (active.cancelled || active.submitted || capture !== active) return;
    const results = Array.from(event.results || []);
    const hasResultIndex = Number.isInteger(event.resultIndex);
    const start = hasResultIndex ? Math.max(0, event.resultIndex) : 0;
    let syntheticIndex = active.syntheticResultIndex;
    let finalizedSpeech = false;
    let hasInterimSpeech = false;
    for (let index = start; index < results.length; index += 1) {
      const result = results[index];
      const transcript = String(result?.[0]?.transcript || "").trim();
      if (!transcript) continue;
      const exposesFinality = result && "isFinal" in Object(result);
      if (exposesFinality && !result.isFinal) {
        hasInterimSpeech = true;
        continue;
      }
      const resultIndex = hasResultIndex || results.length > 1 ? index : syntheticIndex++;
      active.finalResults.set(resultIndex, transcript);
      finalizedSpeech = true;
    }
    active.syntheticResultIndex = syntheticIndex;
    if (hasInterimSpeech) {
      active.hasPendingInterim = true;
      clearTimeout(active.endTimeout);
      active.endTimeout = null;
      if (active.purpose === "booking" && active.finalResults.size) {
        textInput.value = "";
      }
      if (active.stopRequested) scheduleRecognitionSubmit(active);
      else scheduleRecognitionEnd(active, INTERIM_RESULT_SILENCE_MS);
    } else if (finalizedSpeech) {
      active.hasPendingInterim = false;
      if (active.purpose === "booking") {
        textInput.value = completeTranscript(active);
      }
      if (active.stopRequested) scheduleRecognitionSubmit(active);
      else scheduleRecognitionEnd(active);
    }
  };
  recognition.onerror = (event) => {
    if (active.cancelled || active.submitted || capture !== active) return;
    if (event.error === "no-speech" && active.finalResults.size && !active.hasPendingInterim) {
      submitRecognition(active);
      return;
    }
    active.cancelled = true;
    const errors = {
      "not-allowed": "Microphone access was denied. Allow it in browser settings, or type your reply.",
      "service-not-allowed": "Browser speech recognition is disabled by browser or system policy. Enable it or type your reply.",
      "no-speech": "No speech was detected. Try again in a quiet space.",
      "audio-capture": "No microphone is available. Connect one or type your reply.",
      network: "Browser speech could not connect. Try again or type your reply.",
      "language-not-supported": "Browser recognition does not support the selected language. Choose another language or use text.",
    };
    status(errors[event.error] || "Speech recognition stopped. Try again or type your reply.", "error");
    releaseCapture(active);
  };
  recognition.onend = () => {
    if (active.cancelled || active.submitted || active.version !== version || capture !== active) return;
    submitRecognition(active);
  };
  active.safetyTimeout = setTimeout(() => {
    if (capture !== active || active.cancelled) return;
    active.cancelled = true;
    recognition.abort();
    releaseCapture(active);
    status("Listening stopped because no result was received. Select Start listening to try again.", "error");
  }, RECOGNITION_SAFETY_MS);
  recognition.start();
}
function startCapture(purpose) {
  if (capture) return;
  if (busy || !browserRecognitionAvailable() || (purpose === "booking" && ended)) return;
  if (purpose === "practice" && !selectedLocale()) {
    status("Select a language before starting speaking practice.", "error");
    return;
  }
  stopSpeech();
  const active = {
    purpose,
    version,
    locale: effectiveLocale,
    sample: language()?.sample || "",
    cancelled: false,
    submitted: false,
    stopRequested: false,
    hasPendingInterim: false,
    finalResults: new Map(),
    syntheticResultIndex: 0,
  };
  capture = active;
  controls();
  try {
    status("Starting listening. Allow microphone access if asked.", "processing");
    startBrowserRecognition(active);
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
  if (pendingPlayback?.actionButton === $("testVoiceButton")) {
    void playPreparedAudio();
    return;
  }
  if (language()) {
    speechProviderUnavailable = false;
    capabilities();
    void speak(language().sample, true, effectiveLocale, $("testVoiceButton"));
  }
});
$("autoSpeak").addEventListener("change", () => {
  if (!$("autoSpeak").checked) {
    stopSpeech();
    status("Automatic spoken replies paused.");
  }
});
$("textForm").addEventListener("submit", (event) => {
  event.preventDefault();
  void sendMessage(textInput.value);
});
window.speechSynthesis?.addEventListener?.("voiceschanged", () => {
  browserVoicesKnown = true;
  capabilities();
});
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
    languageSelect.replaceChildren(...config.languages.map((item) => {
      const option = document.createElement("option");
      option.value = item.locale;
      option.textContent = item.label;
      return option;
    }));
    languageSelect.value = languageFor(previous) ? previous : defaultLocale();
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
