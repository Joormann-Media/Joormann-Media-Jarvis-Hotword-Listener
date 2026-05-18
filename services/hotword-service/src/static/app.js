const pageBody = document.body;
const trainerUrl = pageBody.dataset.trainerUrl;

const resultBox = document.getElementById("result-box");
const detailBox = document.getElementById("hotword-detail-box");
const modelStatusBox = document.getElementById("model-status-box");
const trainerStatusBox = document.getElementById("trainer-status-box");
const runtimeStatusBox = document.getElementById("runtime-status-box");
const runtimeStatusBoxRuntime = document.getElementById("runtime-status-box-runtime");
const runtimeListenerRunning = document.getElementById("runtime-listener-running");
const runtimeEngine = document.getElementById("runtime-engine");
const runtimeActiveHotwordCount = document.getElementById("runtime-active-hotword-count");
const runtimeActiveHotwords = document.getElementById("runtime-active-hotwords");
const runtimeConfiguredEnabled = document.getElementById("runtime-configured-enabled");
const runtimeCooldown = document.getElementById("runtime-cooldown");
const runtimeDetectedHotword = document.getElementById("runtime-detected-hotword");
const runtimeRecordingFile = document.getElementById("runtime-recording-file");
const runtimeSpeaker = document.getElementById("runtime-speaker");
const runtimeTranscript = document.getElementById("runtime-transcript");
const runtimeResponseAudio = document.getElementById("runtime-response-audio");
const runtimeListenerRunningRuntime = document.getElementById("runtime-listener-running-runtime");
const runtimeEngineRuntime = document.getElementById("runtime-engine-runtime");
const runtimeActiveHotwordsRuntime = document.getElementById("runtime-active-hotwords-runtime");
const runtimeConfiguredEnabledRuntime = document.getElementById("runtime-configured-enabled-runtime");
const runtimeCooldownRuntime = document.getElementById("runtime-cooldown-runtime");
const runtimeDetectedHotwordRuntime = document.getElementById("runtime-detected-hotword-runtime");
const runtimeDispatchRuntime = document.getElementById("runtime-dispatch-runtime");
const runtimeAudioTuningStatus = document.getElementById("runtime-audio-tuning-status");
const runtimeInputGain = document.getElementById("runtime-input-gain");
const runtimeInputGainText = document.getElementById("runtime-input-gain-text");
const runtimeMinScore = document.getElementById("runtime-min-score");
const runtimeMinScoreText = document.getElementById("runtime-min-score-text");
const runtimeMinRmsFactor = document.getElementById("runtime-min-rms-factor");
const runtimeMinRmsFactorText = document.getElementById("runtime-min-rms-factor-text");
const runtimeRequiredHits = document.getElementById("runtime-required-hits");
const runtimeRequiredHitsText = document.getElementById("runtime-required-hits-text");
const runtimeInputDeviceSelect = document.getElementById("runtime-input-device-select");
const runtimeInputDeviceStatus = document.getElementById("runtime-input-device-status");
const runtimeAudioProbeStatus = document.getElementById("runtime-audio-probe-status");
const runtimeAudioProbePlayer = document.getElementById("runtime-audio-probe-player");
const micRmsBar = document.getElementById("mic-rms-bar");
const micPeakBar = document.getElementById("mic-peak-bar");
const micRmsText = document.getElementById("mic-rms-text");
const micPeakText = document.getElementById("mic-peak-text");
const micWaveCanvas = document.getElementById("mic-wave-canvas");
const micDeviceSelect = document.getElementById("mic-device-select");
const micDeviceLabel = document.getElementById("mic-device-label");
const micMeterStart = document.getElementById("mic-meter-start");
const micMeterStop = document.getElementById("mic-meter-stop");
const hotwordList = document.getElementById("hotword-list");
const uploadHotword = document.getElementById("upload-hotword");
const modelHotword = document.getElementById("model-hotword");
const recordHotword = document.getElementById("record-hotword");
const detectHotword = document.getElementById("detect-hotword");
const editHotword = document.getElementById("edit-hotword");
const trainerDatasetHotword = document.getElementById("trainer-dataset-hotword");
const trainerTrainHotword = document.getElementById("trainer-train-hotword");
const trainerExportHotword = document.getElementById("trainer-export-hotword");
const hotwordTrainerHotword = document.getElementById("hotword-trainer-hotword");
const intentTrainerHotword = document.getElementById("intent-trainer-hotword");
const createSpeakers = document.getElementById("create-speakers");
const editSpeakers = document.getElementById("edit-speakers");
const recordingStatus = document.getElementById("recording-status");
const intentTrainerClient = document.getElementById("intent-trainer-client");
const intentTrainerUser = document.getElementById("intent-trainer-user");
const intentTrainerProfile = document.getElementById("intent-trainer-profile");
const hotwordTrainerStatus = document.getElementById("hotword-trainer-status");
const intentTrainerStatus = document.getElementById("intent-trainer-status");
const hotwordTrainerBox = document.getElementById("hotword-trainer-box");
const intentTrainerBox = document.getElementById("intent-trainer-box");
const micCapabilityChip = document.getElementById("mic-capability-chip");
const hotwordTrainerMicHint = document.getElementById("hotword-trainer-mic-hint");
const intentTrainerMicHint = document.getElementById("intent-trainer-mic-hint");
const hotwordEditStatus = document.getElementById("hotword-edit-status");
const statusBox = document.getElementById("status-box");
const statusVersion = document.getElementById("status-version");
const statusPort = document.getElementById("status-port");
const statusUpdate = document.getElementById("status-update");
const statusLastError = document.getElementById("status-last-error");
const statusRuntimeFeedback = document.getElementById("status-runtime-feedback");
const statusUpdateFeedback = document.getElementById("status-update-feedback");
const statusLinkHotwordUi = document.getElementById("status-link-hotword-ui");
const statusLinkAssistant = document.getElementById("status-link-assistant");
const statusLinkSpeakerUi = document.getElementById("status-link-speaker-ui");

let mediaRecorder = null;
let recordedChunks = [];
let hotwordTrainerRecorder = null;
let hotwordTrainerRecordedChunks = [];
let hotwordTrainerRecordedBlob = null;
let intentTrainerRecorder = null;
let intentTrainerRecordedChunks = [];
let intentTrainerRecordedBlob = null;
const buildStatusByHotword = new Map();
let meterStream = null;
let meterAudioContext = null;
let meterAnalyser = null;
let meterSilenceFrames = 0;
let meterAnimationHandle = null;

function parsePhrasesInput(raw) {
  const text = String(raw || "").trim();
  if (!text) {
    return [];
  }
  const parts = text.split(/[\s,]+/).map((item) => item.trim()).filter(Boolean);
  return [...new Set(parts)];
}

function normalizePhrasesField(input) {
  if (!input) {
    return;
  }
  const phrases = parsePhrasesInput(input.value);
  if (phrases.length > 0) {
    input.value = phrases.join(", ");
  }
}

function showResult(payload) {
  resultBox.textContent = JSON.stringify(payload, null, 2);
}

async function parseJson(response) {
  const text = await response.text();
  return text ? JSON.parse(text) : {};
}

async function apiFetch(url, options = {}) {
  const response = await fetch(url, options);
  const data = await parseJson(response);
  showResult(data);
  if (!response.ok) {
    throw new Error(data.detail || data.error || "Request failed");
  }
  return data;
}

async function trainerFetch(path, options = {}) {
  const response = await fetch(`${trainerUrl}${path}`, options);
  const data = await parseJson(response);
  trainerStatusBox.textContent = JSON.stringify(data, null, 2);
  showResult(data);
  if (!response.ok) {
    throw new Error(data.detail || data.error || "Trainer request failed");
  }
  return data;
}

function selectedValues(select) {
  return Array.from(select.selectedOptions).map((option) => option.value);
}

function setHotwordEditStatus(message, level = "neutral") {
  if (!hotwordEditStatus) {
    return;
  }
  hotwordEditStatus.textContent = message;
  if (level === "error") {
    hotwordEditStatus.style.color = "#9f1d1d";
    return;
  }
  if (level === "warn") {
    hotwordEditStatus.style.color = "#8b5a00";
    return;
  }
  if (level === "ok") {
    hotwordEditStatus.style.color = "#166534";
    return;
  }
  hotwordEditStatus.style.color = "";
}

function setBuildStatus(hotwordId, message, level = "info") {
  if (!hotwordId) {
    return;
  }
  buildStatusByHotword.set(hotwordId, { message, level });
  const node = document.querySelector(`[data-build-status-for="${CSS.escape(hotwordId)}"]`);
  if (!node) {
    return;
  }
  node.textContent = message;
  node.classList.remove("is-ok", "is-error", "is-running");
  if (level === "ok") {
    node.classList.add("is-ok");
  } else if (level === "error") {
    node.classList.add("is-error");
  } else if (level === "running") {
    node.classList.add("is-running");
  }
}

function setSelectedValues(select, values) {
  Array.from(select.options).forEach((option) => {
    option.selected = values.includes(option.value);
  });
}

function populateSpeakerSelects(speakers) {
  [createSpeakers, editSpeakers].forEach((select) => {
    select.innerHTML = "";
    speakers.forEach((speaker) => {
      const option = document.createElement("option");
      option.value = speaker.id;
      option.textContent = `${speaker.label} (${speaker.id})`;
      select.appendChild(option);
    });
  });
}

function populateHotwordSelects(hotwords) {
  const selects = [
    uploadHotword,
    modelHotword,
    recordHotword,
    editHotword,
    trainerDatasetHotword,
    trainerTrainHotword,
    trainerExportHotword,
    hotwordTrainerHotword,
    intentTrainerHotword,
  ];

  selects.forEach((select) => {
    select.innerHTML = "";
    hotwords.forEach((hotword) => {
      const option = document.createElement("option");
      option.value = hotword.id;
      option.textContent = `${hotword.label} (${hotword.id})`;
      select.appendChild(option);
    });
  });

  detectHotword.innerHTML = '<option value="">Automatisch</option>';
  hotwords.forEach((hotword) => {
    const option = document.createElement("option");
    option.value = hotword.id;
    option.textContent = `${hotword.label} (${hotword.id})`;
    detectHotword.appendChild(option);
  });
}

function populateTrainerBootstrap(data) {
  if (!intentTrainerClient || !intentTrainerUser || !intentTrainerProfile) {
    return;
  }

  intentTrainerClient.innerHTML = "";
  intentTrainerUser.innerHTML = "";
  intentTrainerProfile.innerHTML = '<option value="">Keins</option>';

  (data.clients || []).forEach((client) => {
    const option = document.createElement("option");
    option.value = String(client.id);
    option.textContent = `${client.name || "Client"} (#${client.id})`;
    intentTrainerClient.appendChild(option);
  });

  (data.users || []).forEach((user) => {
    const option = document.createElement("option");
    option.value = String(user.id);
    const label = user.name && user.name.trim() !== "" ? user.name : user.email || `User ${user.id}`;
    option.textContent = `${label} (#${user.id})`;
    intentTrainerUser.appendChild(option);
  });

  (data.profiles || []).forEach((profile) => {
    const option = document.createElement("option");
    option.value = String(profile.id);
    option.textContent = `${profile.name || "Profil"} (#${profile.id})`;
    intentTrainerProfile.appendChild(option);
  });
}

function applyMicStatus(text, tone = "warn") {
  const hints = [hotwordTrainerMicHint, intentTrainerMicHint].filter(Boolean);
  hints.forEach((node) => {
    node.textContent = text;
  });

  if (!micCapabilityChip) {
    return;
  }
  micCapabilityChip.textContent = text;
  micCapabilityChip.classList.remove("status-chip-ok", "status-chip-warn", "status-chip-bad");
  micCapabilityChip.classList.add(
    tone === "ok" ? "status-chip-ok" : tone === "bad" ? "status-chip-bad" : "status-chip-warn",
  );
}

async function refreshMicCapabilityStatus() {
  if (!window.isSecureContext) {
    applyMicStatus("Mikrofon blockiert: Seite ist nicht HTTPS/localhost.", "bad");
    return;
  }
  if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== "function") {
    applyMicStatus("Mikrofon nicht verfuegbar: Browser/API blockiert.", "bad");
    return;
  }

  if (navigator.permissions && typeof navigator.permissions.query === "function") {
    try {
      const permission = await navigator.permissions.query({ name: "microphone" });
      if (permission.state === "granted") {
        applyMicStatus("Mikrofon bereit (Berechtigung erlaubt).", "ok");
        await refreshMicDevices();
      } else if (permission.state === "prompt") {
        applyMicStatus("Mikrofon bereit. Beim Start der Aufnahme kommt die Browser-Abfrage.", "warn");
      } else {
        applyMicStatus("Mikrofon blockiert (Browser-Berechtigung verweigert).", "bad");
      }
      return;
    } catch (_) {
      // Browser ohne Permission-Query-Unterstuetzung faellt auf Standardhinweis.
    }
  }

  applyMicStatus("Mikrofon bereit. Aufnahme sollte beim Klick starten.", "ok");
  await refreshMicDevices();
}

function fillEditForm(hotword) {
  editHotword.value = hotword.id;
  document.getElementById("edit-label").value = hotword.label || "";
  document.getElementById("edit-phrase").value = (hotword.phrases || [hotword.phrase || ""]).join(", ");
  document.getElementById("edit-notes").value = hotword.notes || "";
  document.getElementById("edit-sensitivity").value = hotword.sensitivity ?? "";
  document.getElementById("edit-detection-mode").value = hotword.detection_mode || "";
  document.getElementById("edit-training-backend").value = hotword.training_backend || "";
  document.getElementById("edit-engine-type").value = hotword.engine_type || "";
  document.getElementById("edit-model-format").value = hotword.model_format || "";
  document.getElementById("edit-model-path").value = hotword.model_path || "";
  document.getElementById("edit-active").checked = hotword.is_active;
  document.getElementById("edit-runtime-enabled").checked = hotword.runtime_enabled;
  setSelectedValues(editSpeakers, hotword.speaker_ids || []);
}

function syncTuningLabels() {
  if (runtimeInputGain && runtimeInputGainText) {
    runtimeInputGainText.textContent = `${Number(runtimeInputGain.value).toFixed(2)}x`;
  }
  if (runtimeMinScore && runtimeMinScoreText) {
    runtimeMinScoreText.textContent = Number(runtimeMinScore.value).toFixed(2);
  }
  if (runtimeMinRmsFactor && runtimeMinRmsFactorText) {
    runtimeMinRmsFactorText.textContent = Number(runtimeMinRmsFactor.value).toFixed(2);
  }
  if (runtimeRequiredHits && runtimeRequiredHitsText) {
    runtimeRequiredHitsText.textContent = String(runtimeRequiredHits.value);
  }
}

function updateMeterUi(rms, peak) {
  const rmsPercent = Math.max(0, Math.min(100, rms * 100));
  const peakPercent = Math.max(0, Math.min(100, peak * 100));
  if (micRmsBar) {
    micRmsBar.style.width = `${rmsPercent}%`;
  }
  if (micPeakBar) {
    micPeakBar.style.width = `${peakPercent}%`;
  }
  if (micRmsText) {
    micRmsText.textContent = `RMS ${(rms * 100).toFixed(1)}%`;
  }
  if (micPeakText) {
    micPeakText.textContent = `Peak ${(peak * 100).toFixed(1)}%`;
  }
}

function drawWave(buffer, gain = 1) {
  if (!micWaveCanvas) {
    return;
  }
  const context = micWaveCanvas.getContext("2d");
  if (!context) {
    return;
  }
  const width = micWaveCanvas.width;
  const height = micWaveCanvas.height;
  context.clearRect(0, 0, width, height);
  context.strokeStyle = "#4cd2a5";
  context.lineWidth = 2;
  context.beginPath();
  const step = Math.max(1, Math.floor(buffer.length / width));
  let x = 0;
  for (let i = 0; i < buffer.length; i += step) {
    const centered = (buffer[i] - 128) / 128;
    const amplified = Math.max(-1, Math.min(1, centered * gain));
    const y = (0.5 - amplified * 0.42) * height;
    if (x === 0) {
      context.moveTo(x, y);
    } else {
      context.lineTo(x, y);
    }
    x += 1;
    if (x >= width) {
      break;
    }
  }
  context.stroke();
}

async function refreshMicDevices() {
  if (!micDeviceSelect || !navigator.mediaDevices?.enumerateDevices) {
    return;
  }
  const devices = await navigator.mediaDevices.enumerateDevices();
  const inputs = devices.filter((item) => item.kind === "audioinput");
  const selected = micDeviceSelect.value;
  micDeviceSelect.innerHTML = "";
  const autoOption = document.createElement("option");
  autoOption.value = "";
  autoOption.textContent = "Automatisch (Browser-Default)";
  micDeviceSelect.appendChild(autoOption);
  inputs.forEach((device, index) => {
    const option = document.createElement("option");
    option.value = device.deviceId;
    option.textContent = device.label || `Mikrofon ${index + 1}`;
    micDeviceSelect.appendChild(option);
  });
  if (selected && inputs.some((item) => item.deviceId === selected)) {
    micDeviceSelect.value = selected;
  }
}

async function startMicMeter() {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    if (runtimeAudioTuningStatus) {
      runtimeAudioTuningStatus.textContent = "Live-Meter braucht HTTPS oder localhost mit Mikrofonfreigabe.";
    }
    return;
  }
  if (meterAnimationHandle) {
    return;
  }
  const selectedDeviceId = micDeviceSelect?.value || "";
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      deviceId: selectedDeviceId ? { exact: selectedDeviceId } : undefined,
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false,
    },
  });
  const context = new AudioContext();
  await refreshMicDevices();
  if (context.state === "suspended") {
    await context.resume();
  }
  const analyser = context.createAnalyser();
  analyser.fftSize = 2048;
  analyser.smoothingTimeConstant = 0.45;
  const source = context.createMediaStreamSource(stream);
  const muteGain = context.createGain();
  muteGain.gain.value = 0;
  source.connect(analyser);
  analyser.connect(muteGain);
  muteGain.connect(context.destination);

  meterStream = stream;
  meterAudioContext = context;
  meterAnalyser = analyser;
  meterSilenceFrames = 0;
  if (micMeterStart) {
    micMeterStart.disabled = true;
  }
  if (micMeterStop) {
    micMeterStop.disabled = false;
  }
  if (runtimeAudioTuningStatus) {
    runtimeAudioTuningStatus.textContent = "Live-Meter läuft.";
  }
  if (micDeviceLabel) {
    const trackLabel = stream.getAudioTracks()[0]?.label || "unbekannt";
    micDeviceLabel.textContent = `Aktive Quelle: ${trackLabel}`;
  }
  updateMeterUi(0, 0);

  const buffer = new Uint8Array(analyser.fftSize);
  const tick = () => {
    if (!meterAnalyser) {
      return;
    }
    meterAnalyser.getByteTimeDomainData(buffer);
    const previewGain = Math.max(0.1, Number(runtimeInputGain?.value || 1));
    let sumSquares = 0;
    let peak = 0;
    for (let i = 0; i < buffer.length; i += 1) {
      const centered = (buffer[i] - 128) / 128;
      const amplified = Math.max(-1, Math.min(1, centered * previewGain));
      const sample = Math.abs(amplified);
      sumSquares += sample * sample;
      if (sample > peak) {
        peak = sample;
      }
    }
    const rms = Math.sqrt(sumSquares / buffer.length);
    updateMeterUi(rms, peak);
    drawWave(buffer, previewGain);
    if (rms < 0.0015 && peak < 0.006) {
      meterSilenceFrames += 1;
      if (meterSilenceFrames === 80 && runtimeAudioTuningStatus) {
        runtimeAudioTuningStatus.textContent = "Live-Meter empfängt quasi kein Signal. Prüfe Browser-Mikrofonquelle oder OS-Input.";
      }
    } else {
      meterSilenceFrames = 0;
    }
    meterAnimationHandle = requestAnimationFrame(tick);
  };
  meterAnimationHandle = requestAnimationFrame(tick);
}

async function stopMicMeter() {
  if (meterAnimationHandle) {
    cancelAnimationFrame(meterAnimationHandle);
    meterAnimationHandle = null;
  }
  if (meterStream) {
    meterStream.getTracks().forEach((track) => track.stop());
    meterStream = null;
  }
  if (meterAudioContext) {
    await meterAudioContext.close();
    meterAudioContext = null;
  }
  meterAnalyser = null;
  meterSilenceFrames = 0;
  if (micMeterStart) {
    micMeterStart.disabled = false;
  }
  if (micMeterStop) {
    micMeterStop.disabled = true;
  }
  if (micDeviceLabel) {
    micDeviceLabel.textContent = "Noch keine Quelle aktiv.";
  }
  updateMeterUi(0, 0);
}

function renderHotwords(hotwords) {
  hotwordList.innerHTML = "";
  hotwords.forEach((hotword) => {
    const buildState = buildStatusByHotword.get(hotword.id);
    const buildText = buildState?.message || "Build-Status: noch nicht gestartet";
    const buildClass = buildState?.level === "ok"
      ? "is-ok"
      : buildState?.level === "error"
        ? "is-error"
        : buildState?.level === "running"
          ? "is-running"
          : "";
    const card = document.createElement("article");
    card.className = "hotword-card";
    card.innerHTML = `
      <h3>${hotword.label}</h3>
      <p><strong>ID:</strong> ${hotword.id}</p>
      <p><strong>Phrase:</strong> ${hotword.phrase}</p>
      <p><strong>Phrasen:</strong> ${(hotword.phrases || [hotword.phrase]).join(", ")}</p>
      <p><strong>Speaker:</strong> ${(hotword.speaker_ids || []).join(", ") || "Keine"}</p>
      <p><strong>Samples:</strong> ${hotword.sample_count}</p>
      <p><strong>Runtime:</strong> ${hotword.runtime_enabled ? "Ja" : "Nein"}</p>
      <p><strong>Detection:</strong> ${hotword.detection_mode || "personal"}</p>
      <p><strong>Engine:</strong> ${hotword.engine_type}</p>
      <p><strong>Backend:</strong> ${hotword.training_backend || "-"}</p>
      <p><strong>Format:</strong> ${hotword.model_format || "-"}</p>
      <p><strong>Model:</strong> ${hotword.model_ready ? "Bereit" : "Offen"}</p>
      <p><strong>Last Trained:</strong> ${hotword.last_trained_at || "-"}</p>
      <p><strong>Model Path:</strong> ${hotword.model_path || "noch kein Modell zugeordnet"}</p>
      <p><strong>Aktiv:</strong> ${hotword.is_active ? "Ja" : "Nein"}</p>
      <p>${hotword.notes || "Keine Notiz"}</p>
      <p class="build-status ${buildClass}" data-build-status-for="${hotword.id}">${buildText}</p>
      <div class="button-row">
        <button type="button" data-hotword="${hotword.id}" class="detail-button">Details / Samples</button>
        <button type="button" data-hotword="${hotword.id}" class="build-button">Training vorbereiten</button>
        <button type="button" data-hotword="${hotword.id}" class="delete-button">Hotword loeschen</button>
      </div>
    `;
    hotwordList.appendChild(card);
  });

  document.querySelectorAll(".detail-button").forEach((button) => {
    button.addEventListener("click", async () => {
      const data = await apiFetch(`/hotwords/${button.dataset.hotword}`);
      detailBox.textContent = JSON.stringify(data, null, 2);
      const statusData = await apiFetch(`/hotwords/${button.dataset.hotword}/model-status`);
      modelStatusBox.textContent = JSON.stringify(statusData, null, 2);
      fillEditForm(data.hotword);
    });
  });

  document.querySelectorAll(".build-button").forEach((button) => {
    button.addEventListener("click", async () => {
      const hotwordId = button.dataset.hotword;
      const originalText = button.textContent;
      button.disabled = true;
      button.textContent = "Training laeuft...";
      setBuildStatus(hotwordId, "Build laeuft ...", "running");
      try {
        const buildData = await apiFetch(`/hotwords/${hotwordId}/build-model`, { method: "POST" });
        const statusData = await apiFetch(`/hotwords/${hotwordId}/model-status`);
        modelStatusBox.textContent = JSON.stringify({ build: buildData, status: statusData }, null, 2);
        await refreshTrainerStatus();
        await refreshHotwords();
        if (statusData.model_ready) {
          setBuildStatus(hotwordId, "Build abgeschlossen: Modell ist bereit.", "ok");
        } else {
          setBuildStatus(hotwordId, "Build beendet, aber Modell noch nicht bereit.", "error");
        }
      } catch (error) {
        setBuildStatus(hotwordId, `Build fehlgeschlagen: ${error.message}`, "error");
      } finally {
        button.disabled = false;
        button.textContent = originalText;
      }
    });
  });

  document.querySelectorAll(".delete-button").forEach((button) => {
    button.addEventListener("click", async () => {
      const hotwordId = button.dataset.hotword;
      const confirmed = window.confirm(`Hotword '${hotwordId}' wirklich loeschen?`);
      if (!confirmed) {
        return;
      }
      await apiFetch(`/hotwords/${encodeURIComponent(hotwordId)}`, { method: "DELETE" });
      setHotwordEditStatus(`Hotword '${hotwordId}' geloescht.`, "ok");
      await refreshHotwords();
      await apiFetch("/runtime/reload-hotwords", { method: "POST" });
      await refreshRuntimeStatus();
      await refreshTrainerStatus();
    });
  });
}

function updateRuntimeCards(data) {
  const configuredText = data.configured_enabled ? "aktiv" : "deaktiviert";
  runtimeListenerRunning.textContent = data.listener_running ? "laeuft" : "gestoppt";
  runtimeEngine.textContent = data.engine || "-";
  runtimeActiveHotwordCount.textContent = data.active_hotword_count ?? 0;
  runtimeActiveHotwords.textContent = (data.active_hotwords || []).join(", ") || "-";
  runtimeConfiguredEnabled.textContent = configuredText;
  runtimeCooldown.textContent = data.cooldown_active ? "aktiv" : "inaktiv";
  runtimeDetectedHotword.textContent = data.last_detected_hotword || "-";
  runtimeRecordingFile.textContent = data.last_recording_file || "-";
  runtimeSpeaker.textContent = data.last_speaker_id || "-";
  runtimeTranscript.textContent = data.last_input_transcript || "-";
  runtimeResponseAudio.textContent = data.last_response_audio_file || "-";
  runtimeListenerRunningRuntime.textContent = runtimeListenerRunning.textContent;
  runtimeEngineRuntime.textContent = runtimeEngine.textContent;
  runtimeActiveHotwordsRuntime.textContent = runtimeActiveHotwords.textContent;
  runtimeConfiguredEnabledRuntime.textContent = configuredText;
  runtimeCooldownRuntime.textContent = runtimeCooldown.textContent;
  runtimeDetectedHotwordRuntime.textContent = runtimeDetectedHotword.textContent;
  runtimeDispatchRuntime.textContent = data.last_dispatch_status || "-";
  if (runtimeInputDeviceStatus) {
    const selectedLabel = runtimeInputDeviceSelect?.selectedOptions?.[0]?.textContent || data.device_name || "default";
    runtimeInputDeviceStatus.textContent = `Runtime-Mikro (Standard): ${selectedLabel}`;
  }
  const runtimeAutostartEnableButton = document.getElementById("runtime-autostart-enable");
  const runtimeAutostartDisableButton = document.getElementById("runtime-autostart-disable");
  if (runtimeAutostartEnableButton && runtimeAutostartDisableButton) {
    runtimeAutostartEnableButton.disabled = Boolean(data.configured_enabled);
    runtimeAutostartDisableButton.disabled = !data.configured_enabled;
  }
  runtimeStatusBox.textContent = JSON.stringify(data, null, 2);
  runtimeStatusBoxRuntime.textContent = JSON.stringify(data, null, 2);
}

async function refreshSpeakers() {
  const data = await apiFetch("/speakers");
  populateSpeakerSelects(data.speakers);
}

async function refreshHotwords() {
  const data = await apiFetch("/hotwords");
  populateHotwordSelects(data.hotwords);
  renderHotwords(data.hotwords);
}

async function refreshRuntimeStatus() {
  const data = await apiFetch("/runtime/status");
  updateRuntimeCards(data);
}

async function refreshRuntimeAudioTuning() {
  const data = await apiFetch("/runtime/audio-tuning");
  if (runtimeInputGain) {
    runtimeInputGain.value = String(data.input_gain ?? 1);
  }
  if (runtimeMinScore) {
    runtimeMinScore.value = String(data.min_score ?? 0.62);
  }
  if (runtimeMinRmsFactor) {
    runtimeMinRmsFactor.value = String(data.min_rms_factor ?? 0.35);
  }
  if (runtimeRequiredHits) {
    runtimeRequiredHits.value = String(data.required_hits ?? 2);
  }
  syncTuningLabels();
  if (runtimeAudioTuningStatus) {
    runtimeAudioTuningStatus.textContent = data.message || "Tuning geladen.";
  }
}

async function refreshRuntimeAudioDevices() {
  if (!runtimeInputDeviceSelect) {
    return;
  }
  const data = await apiFetch("/runtime/audio-devices");
  const current = data.configured_device_name || "";
  runtimeInputDeviceSelect.innerHTML = "";
  (data.devices || []).forEach((device) => {
    const option = document.createElement("option");
    option.value = device.value;
    option.textContent = device.label;
    runtimeInputDeviceSelect.appendChild(option);
  });
  runtimeInputDeviceSelect.value = current;
  if (runtimeInputDeviceStatus) {
    const selectedLabel = runtimeInputDeviceSelect.selectedOptions?.[0]?.textContent || current || "default";
    runtimeInputDeviceStatus.textContent = `Runtime-Mikro (Standard): ${selectedLabel}`;
  }
}

async function refreshTrainerStatus() {
  const [datasets, jobs, models] = await Promise.all([
    trainerFetch("/datasets"),
    trainerFetch("/train/status"),
    trainerFetch("/models"),
  ]);
  modelStatusBox.textContent = JSON.stringify({ datasets, jobs, models }, null, 2);
}

async function refreshTrainerBootstrap() {
  const data = await apiFetch("/trainer/bootstrap");
  populateTrainerBootstrap(data);
}

function setStatusLinks(link, href) {
  if (!link) {
    return;
  }
  if (!href) {
    link.removeAttribute("href");
    link.textContent = "Link nicht verfügbar";
    return;
  }
  link.href = href;
  link.textContent = href;
}

async function refreshServiceStatusHub() {
  if (!statusBox) {
    return;
  }
  const data = await apiFetch("/status");
  statusBox.textContent = JSON.stringify(data, null, 2);
  if (statusVersion) {
    statusVersion.textContent = data.version || "-";
  }
  if (statusPort) {
    statusPort.textContent = String(data?.ports?.hotword_service ?? "-");
  }
  if (statusUpdate) {
    statusUpdate.textContent = data?.update?.message || "-";
  }
  if (statusLastError) {
    statusLastError.textContent = data?.last_error?.detail || "-";
  }
  const localhostLinks = data?.links?.localhost || {};
  setStatusLinks(statusLinkHotwordUi, localhostLinks.hotword_ui || "");
  setStatusLinks(statusLinkAssistant, localhostLinks.assistant_ui || "");
  setStatusLinks(statusLinkSpeakerUi, localhostLinks.speaker_ui || "");
}

async function runStatusRuntimeAction(action) {
  const result = await apiFetch(`/status/actions/runtime/${action}`, { method: "POST" });
  if (statusRuntimeFeedback) {
    statusRuntimeFeedback.textContent = `Action '${action}': ${result?.feedback?.message || "OK"}`;
  }
  await refreshRuntimeStatus();
  await refreshServiceStatusHub();
}

async function runLabUpdate(mode) {
  const result = await apiFetch(`/status/actions/lab-update?mode=${encodeURIComponent(mode)}`, {
    method: "POST",
  });
  if (statusUpdateFeedback) {
    statusUpdateFeedback.textContent = result?.feedback?.message || `${mode} abgeschlossen.`;
  }
  await refreshServiceStatusHub();
}

document.querySelectorAll(".tab-button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab-button").forEach((item) => item.classList.remove("is-active"));
    document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.remove("is-active"));
    button.classList.add("is-active");
    document.querySelector(`[data-panel="${button.dataset.tab}"]`).classList.add("is-active");
  });
});

document.getElementById("hotword-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const phrases = parsePhrasesInput(formData.get("phrase"));
  await apiFetch("/hotwords", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      id: formData.get("id"),
      label: formData.get("label"),
      phrase: phrases[0] || String(formData.get("phrase") || "").trim(),
      phrases,
      speaker_ids: selectedValues(createSpeakers),
      notes: formData.get("notes"),
      sensitivity: formData.get("sensitivity") || null,
      detection_mode: formData.get("detection_mode") || null,
      engine_type: formData.get("engine_type") || null,
      model_path: formData.get("model_path") || null,
      runtime_enabled: formData.get("runtime_enabled") === "on",
      training_backend: formData.get("training_backend") || null,
      model_format: formData.get("model_format") || null,
    }),
  });
  event.currentTarget.reset();
  Array.from(createSpeakers.options).forEach((option) => { option.selected = false; });
  await refreshHotwords();
  await apiFetch("/runtime/reload-hotwords", { method: "POST" });
  await refreshRuntimeStatus();
});

document.getElementById("hotword-edit-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const hotwordId = editHotword.value;
  const phrases = parsePhrasesInput(document.getElementById("edit-phrase").value);
  try {
    const updateResult = await apiFetch(`/hotwords/${hotwordId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        label: document.getElementById("edit-label").value || null,
        phrase: phrases[0] || null,
        phrases,
        speaker_ids: selectedValues(editSpeakers),
        notes: document.getElementById("edit-notes").value || null,
        sensitivity: document.getElementById("edit-sensitivity").value || null,
        detection_mode: document.getElementById("edit-detection-mode").value || null,
        training_backend: document.getElementById("edit-training-backend").value || null,
        engine_type: document.getElementById("edit-engine-type").value || null,
        model_format: document.getElementById("edit-model-format").value || null,
        model_path: document.getElementById("edit-model-path").value || null,
        is_active: document.getElementById("edit-active").checked,
        runtime_enabled: document.getElementById("edit-runtime-enabled").checked,
      }),
    });
    await refreshHotwords();
    await apiFetch("/runtime/reload-hotwords", { method: "POST" });
    await refreshRuntimeStatus();
    if (updateResult?.hotword) {
      fillEditForm(updateResult.hotword);
      if (updateResult.hotword.runtime_enabled && !updateResult.hotword.model_ready) {
        setHotwordEditStatus(
          "Gespeichert, aber Runtime bleibt inaktiv: Modellpfad fehlt oder Datei existiert nicht.",
          "warn",
        );
      } else {
        setHotwordEditStatus("Hotword erfolgreich gespeichert.", "ok");
      }
    } else {
      setHotwordEditStatus("Hotword erfolgreich gespeichert.", "ok");
    }
  } catch (error) {
    setHotwordEditStatus(`Speichern fehlgeschlagen: ${error.message}`, "error");
  }
});

document.getElementById("delete-all-hotwords")?.addEventListener("click", async () => {
  const confirmed = window.confirm("Wirklich ALLE Hotwords inkl. Samples und Modelle loeschen?");
  if (!confirmed) {
    return;
  }
  const result = await apiFetch("/hotwords", { method: "DELETE" });
  setHotwordEditStatus(`Cleanup fertig: ${result.deleted_hotword_ids?.length || 0} Hotword(s) geloescht.`, "ok");
  await refreshHotwords();
  await apiFetch("/runtime/reload-hotwords", { method: "POST" });
  await refreshRuntimeStatus();
  await refreshTrainerStatus();
});

document.getElementById("hotword-phrase-create")?.addEventListener("blur", (event) => {
  normalizePhrasesField(event.currentTarget);
});
document.getElementById("edit-phrase")?.addEventListener("blur", (event) => {
  normalizePhrasesField(event.currentTarget);
});

document.getElementById("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = document.getElementById("upload-file").files[0];
  if (!file) {
    recordingStatus.textContent = "Bitte zuerst eine Audiodatei auswaehlen.";
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  await apiFetch(`/hotwords/${uploadHotword.value}/samples/upload`, { method: "POST", body: formData });
  event.currentTarget.reset();
  await refreshHotwords();
  await refreshTrainerStatus();
});

document.getElementById("model-upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = document.getElementById("model-file").files[0];
  if (!file) {
    recordingStatus.textContent = "Bitte zuerst eine .ppn Datei auswaehlen.";
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  await apiFetch(`/hotwords/${modelHotword.value}/model/upload`, { method: "POST", body: formData });
  event.currentTarget.reset();
  await refreshHotwords();
  await apiFetch("/runtime/reload-hotwords", { method: "POST" });
  await refreshRuntimeStatus();
});

document.getElementById("trainer-dataset-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  await trainerFetch("/datasets/build", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ hotword_id: trainerDatasetHotword.value }),
  });
  await refreshTrainerStatus();
});

document.getElementById("trainer-train-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  await trainerFetch("/train", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ hotword_id: trainerTrainHotword.value }),
  });
  await refreshTrainerStatus();
});

document.getElementById("trainer-export-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const exported = await trainerFetch("/models/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ hotword_id: trainerExportHotword.value }),
  });
  await apiFetch(`/hotwords/${trainerExportHotword.value}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model_path: exported.exported_model_path,
      model_format: exported.model_format,
      engine_type: "local",
      training_backend: "openwakeword-local",
      runtime_enabled: true,
    }),
  });
  await refreshHotwords();
  await apiFetch("/runtime/reload-hotwords", { method: "POST" });
  await refreshRuntimeStatus();
  await refreshTrainerStatus();
});

document.getElementById("detect-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = document.getElementById("detect-file").files[0];
  if (!file) {
    recordingStatus.textContent = "Bitte zuerst eine Testdatei auswaehlen.";
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  if (detectHotword.value) {
    formData.append("hotword_id", detectHotword.value);
  }
  await apiFetch("/detect/upload", { method: "POST", body: formData });
});

document.getElementById("start-recording").addEventListener("click", async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recordedChunks = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (evt) => {
      if (evt.data.size > 0) {
        recordedChunks.push(evt.data);
      }
    };
    mediaRecorder.onstop = async () => {
      const blob = new Blob(recordedChunks, { type: "audio/webm" });
      const formData = new FormData();
      formData.append("file", blob, "browser-recording.webm");
      await apiFetch(`/hotwords/${recordHotword.value}/samples/browser-recording`, {
        method: "POST",
        body: formData,
      });
      stream.getTracks().forEach((track) => track.stop());
      await refreshHotwords();
      await refreshTrainerStatus();
    };
    mediaRecorder.start();
    recordingStatus.textContent = "Aufnahme laeuft.";
    document.getElementById("start-recording").disabled = true;
    document.getElementById("stop-recording").disabled = false;
  } catch (error) {
    recordingStatus.textContent = `Mikrofonzugriff fehlgeschlagen: ${error.message}`;
  }
});

document.getElementById("stop-recording").addEventListener("click", () => {
  if (!mediaRecorder) {
    return;
  }
  mediaRecorder.stop();
  recordingStatus.textContent = "Aufnahme gespeichert.";
  document.getElementById("start-recording").disabled = false;
  document.getElementById("stop-recording").disabled = true;
});

document.getElementById("hotword-trainer-start-recording").addEventListener("click", async () => {
  if (!window.isSecureContext) {
    hotwordTrainerStatus.textContent = "Mikrofon ist nur mit HTTPS oder auf localhost verfügbar.";
    return;
  }
  if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== "function") {
    hotwordTrainerStatus.textContent = "Dieser Browser stellt kein getUserMedia bereit (HTTP/Browser-Blockade).";
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    hotwordTrainerRecordedChunks = [];
    hotwordTrainerRecordedBlob = null;
    hotwordTrainerRecorder = new MediaRecorder(stream);
    hotwordTrainerRecorder.ondataavailable = (evt) => {
      if (evt.data.size > 0) {
        hotwordTrainerRecordedChunks.push(evt.data);
      }
    };
    hotwordTrainerRecorder.onstop = () => {
      hotwordTrainerRecordedBlob = new Blob(hotwordTrainerRecordedChunks, { type: "audio/webm" });
      stream.getTracks().forEach((track) => track.stop());
      hotwordTrainerStatus.textContent = "Hotword-Aufnahme gespeichert und bereit zum Senden.";
    };
    hotwordTrainerRecorder.start();
    hotwordTrainerStatus.textContent = "Hotword-Aufnahme läuft.";
    document.getElementById("hotword-trainer-start-recording").disabled = true;
    document.getElementById("hotword-trainer-stop-recording").disabled = false;
  } catch (error) {
    hotwordTrainerStatus.textContent = `Mikrofonzugriff fehlgeschlagen: ${error.message}`;
  }
});

document.getElementById("hotword-trainer-stop-recording").addEventListener("click", () => {
  if (!hotwordTrainerRecorder) {
    return;
  }
  hotwordTrainerRecorder.stop();
  document.getElementById("hotword-trainer-start-recording").disabled = false;
  document.getElementById("hotword-trainer-stop-recording").disabled = true;
});

document.getElementById("hotword-trainer-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const fallbackFile = document.getElementById("hotword-trainer-audio-file").files[0];
  const fileToSend = fallbackFile || hotwordTrainerRecordedBlob;
  if (!fileToSend) {
    hotwordTrainerStatus.textContent = "Bitte Audio aufnehmen oder eine Datei auswählen.";
    return;
  }

  const formData = new FormData();
  formData.append("file", fileToSend, fallbackFile ? fallbackFile.name : "hotword-trainer-recording.webm");
  formData.append("hotword_id", hotwordTrainerHotword.value || "");
  const result = await apiFetch("/trainer/hotword-sample", { method: "POST", body: formData });
  hotwordTrainerBox.textContent = JSON.stringify(result, null, 2);
  hotwordTrainerStatus.textContent = "Hotword-Sample gesendet.";
  hotwordTrainerRecordedBlob = null;
  document.getElementById("hotword-trainer-audio-file").value = "";
  await refreshHotwords();
  await refreshTrainerStatus();
});

document.getElementById("intent-trainer-start-recording").addEventListener("click", async () => {
  if (!window.isSecureContext) {
    intentTrainerStatus.textContent = "Mikrofon ist nur mit HTTPS oder auf localhost verfügbar.";
    return;
  }
  if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== "function") {
    intentTrainerStatus.textContent = "Dieser Browser stellt kein getUserMedia bereit (HTTP/Browser-Blockade).";
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    intentTrainerRecordedChunks = [];
    intentTrainerRecordedBlob = null;
    intentTrainerRecorder = new MediaRecorder(stream);
    intentTrainerRecorder.ondataavailable = (evt) => {
      if (evt.data.size > 0) {
        intentTrainerRecordedChunks.push(evt.data);
      }
    };
    intentTrainerRecorder.onstop = () => {
      intentTrainerRecordedBlob = new Blob(intentTrainerRecordedChunks, { type: "audio/webm" });
      stream.getTracks().forEach((track) => track.stop());
      intentTrainerStatus.textContent = "Intent-Aufnahme gespeichert und bereit zum Senden.";
    };
    intentTrainerRecorder.start();
    intentTrainerStatus.textContent = "Intent-Aufnahme läuft.";
    document.getElementById("intent-trainer-start-recording").disabled = true;
    document.getElementById("intent-trainer-stop-recording").disabled = false;
  } catch (error) {
    intentTrainerStatus.textContent = `Mikrofonzugriff fehlgeschlagen: ${error.message}`;
  }
});

document.getElementById("intent-trainer-stop-recording").addEventListener("click", () => {
  if (!intentTrainerRecorder) {
    return;
  }
  intentTrainerRecorder.stop();
  document.getElementById("intent-trainer-start-recording").disabled = false;
  document.getElementById("intent-trainer-stop-recording").disabled = true;
});

document.getElementById("intent-trainer-form").addEventListener("submit", async (event) => {
  event.preventDefault();

  const fallbackFile = document.getElementById("intent-trainer-audio-file").files[0];
  const fileToSend = fallbackFile || intentTrainerRecordedBlob;
  if (!fileToSend) {
    intentTrainerStatus.textContent = "Bitte Audio aufnehmen oder eine Datei auswählen.";
    return;
  }

  const formData = new FormData();
  formData.append("file", fileToSend, fallbackFile ? fallbackFile.name : "intent-trainer-recording.webm");
  formData.append("hotword_id", intentTrainerHotword.value || recordHotword.value || "");
  formData.append("client_id", intentTrainerClient.value || "");
  formData.append("user_id", intentTrainerUser.value || "");
  formData.append("jarvis_profile_id", intentTrainerProfile.value || "");
  formData.append("intent_key", document.getElementById("intent-trainer-intent-key").value || "");
  formData.append("intent_name", document.getElementById("intent-trainer-intent-name").value || "");
  formData.append("handler_service", document.getElementById("intent-trainer-handler-service").value || "");
  formData.append("handler_action", document.getElementById("intent-trainer-handler-action").value || "");
  formData.append("slot_key", document.getElementById("intent-trainer-slot-key").value || "");
  formData.append("memory_fact_key", document.getElementById("intent-trainer-memory-key").value || "");

  const result = await apiFetch("/trainer/ingest", { method: "POST", body: formData });
  intentTrainerBox.textContent = JSON.stringify(result, null, 2);
  intentTrainerStatus.textContent = "Intent-Datensatz gesendet.";
  intentTrainerRecordedBlob = null;
  document.getElementById("intent-trainer-audio-file").value = "";
  await refreshHotwords();
});

document.getElementById("runtime-start").addEventListener("click", async () => {
  await apiFetch("/runtime/start", { method: "POST" });
  await refreshRuntimeStatus();
});

document.getElementById("runtime-stop").addEventListener("click", async () => {
  await apiFetch("/runtime/stop", { method: "POST" });
  await refreshRuntimeStatus();
});

document.getElementById("runtime-autostart-enable").addEventListener("click", async () => {
  await apiFetch("/runtime/configure-listener", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled: true }),
  });
  await refreshRuntimeStatus();
});

document.getElementById("runtime-autostart-disable").addEventListener("click", async () => {
  await apiFetch("/runtime/configure-listener", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled: false }),
  });
  await refreshRuntimeStatus();
});

document.getElementById("runtime-test-trigger").addEventListener("click", async () => {
  await apiFetch("/runtime/test-trigger", { method: "POST" });
  await refreshRuntimeStatus();
});

document.getElementById("runtime-reload-hotwords").addEventListener("click", async () => {
  await apiFetch("/runtime/reload-hotwords", { method: "POST" });
  await refreshRuntimeStatus();
  await refreshHotwords();
});

document.getElementById("runtime-refresh").addEventListener("click", refreshRuntimeStatus);
document.getElementById("runtime-audio-tuning-refresh").addEventListener("click", refreshRuntimeAudioTuning);
document.getElementById("status-refresh")?.addEventListener("click", refreshServiceStatusHub);
document.getElementById("status-runtime-start")?.addEventListener("click", () => runStatusRuntimeAction("start"));
document.getElementById("status-runtime-stop")?.addEventListener("click", () => runStatusRuntimeAction("stop"));
document.getElementById("status-runtime-reload")?.addEventListener("click", () => runStatusRuntimeAction("reload"));
document.getElementById("status-runtime-trigger")?.addEventListener("click", () => runStatusRuntimeAction("test-trigger"));
document.getElementById("status-update-check")?.addEventListener("click", () => runLabUpdate("status"));
document.getElementById("status-update-apply")?.addEventListener("click", () => runLabUpdate("apply"));
document.getElementById("refresh-hotwords").addEventListener("click", async () => {
  await refreshHotwords();
  await refreshRuntimeStatus();
  await refreshRuntimeAudioDevices();
  await refreshRuntimeAudioTuning();
  await refreshTrainerStatus();
  await refreshServiceStatusHub();
});

document.getElementById("runtime-input-device-apply")?.addEventListener("click", async () => {
  const value = runtimeInputDeviceSelect?.value || "";
  const result = await apiFetch("/runtime/audio-input", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_name: value }),
  });
  if (runtimeInputDeviceStatus) {
    const selectedLabel = runtimeInputDeviceSelect?.selectedOptions?.[0]?.textContent || value || "default";
    runtimeInputDeviceStatus.textContent = `${result.message || "Runtime-Mikro gespeichert."} Aktiver Standard: ${selectedLabel}`;
  }
  await refreshRuntimeStatus();
  await refreshRuntimeAudioDevices();
});

document.getElementById("runtime-audio-probe-run")?.addEventListener("click", async () => {
  if (runtimeAudioProbeStatus) {
    runtimeAudioProbeStatus.textContent = "Runtime-Mikrotest läuft ...";
  }
  try {
    const result = await apiFetch("/runtime/audio-probe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seconds: 3 }),
    });
    if (runtimeAudioProbeStatus) {
      runtimeAudioProbeStatus.textContent = `Probe: RMS ${(result.rms * 100).toFixed(2)}%, Peak ${(result.peak * 100).toFixed(2)}% · ${result.message}`;
    }
    if (runtimeAudioProbePlayer) {
      runtimeAudioProbePlayer.src = result.playback_url;
      runtimeAudioProbePlayer.load();
    }
    await refreshRuntimeStatus();
  } catch (error) {
    if (runtimeAudioProbeStatus) {
      runtimeAudioProbeStatus.textContent = `Runtime-Mikrotest fehlgeschlagen: ${error.message}`;
    }
  }
});

runtimeInputGain?.addEventListener("input", syncTuningLabels);
runtimeMinScore?.addEventListener("input", syncTuningLabels);
runtimeMinRmsFactor?.addEventListener("input", syncTuningLabels);
runtimeRequiredHits?.addEventListener("input", syncTuningLabels);

document.getElementById("runtime-audio-tuning-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    input_gain: Number(runtimeInputGain?.value || 1),
    min_score: Number(runtimeMinScore?.value || 0.62),
    min_rms_factor: Number(runtimeMinRmsFactor?.value || 0.35),
    required_hits: Number(runtimeRequiredHits?.value || 2),
  };
  const result = await apiFetch("/runtime/audio-tuning", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  syncTuningLabels();
  if (runtimeAudioTuningStatus) {
    runtimeAudioTuningStatus.textContent = result.message || "Empfindlichkeit gespeichert.";
  }
  await refreshRuntimeStatus();
});

micMeterStart?.addEventListener("click", async () => {
  try {
    await startMicMeter();
  } catch (error) {
    if (runtimeAudioTuningStatus) {
      runtimeAudioTuningStatus.textContent = `Live-Meter fehlgeschlagen: ${error.message}`;
    }
  }
});

micMeterStop?.addEventListener("click", async () => {
  await stopMicMeter();
  if (runtimeAudioTuningStatus) {
    runtimeAudioTuningStatus.textContent = "Live-Meter gestoppt.";
  }
});

Promise.all([refreshSpeakers(), refreshHotwords(), refreshRuntimeStatus(), refreshRuntimeAudioDevices(), refreshRuntimeAudioTuning(), refreshTrainerStatus(), refreshServiceStatusHub()]).catch((error) => {
  recordingStatus.textContent = error.message;
});

let runtimeAutoRefreshHandle = null;
function startRuntimeAutoRefresh() {
  if (runtimeAutoRefreshHandle !== null) {
    return;
  }
  runtimeAutoRefreshHandle = window.setInterval(() => {
    if (document.hidden) {
      return;
    }
    refreshRuntimeStatus().catch((error) => {
      runtimeDispatchRuntime.textContent = `status_error: ${error.message}`;
    });
  }, 2500);
}

startRuntimeAutoRefresh();

refreshTrainerBootstrap().catch((error) => {
  const message = `Trainer Bootstrap fehlgeschlagen: ${error.message}`;
  hotwordTrainerStatus.textContent = message;
  intentTrainerStatus.textContent = message;
});

refreshMicCapabilityStatus();
window.addEventListener("focus", refreshMicCapabilityStatus);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    refreshMicCapabilityStatus();
  } else if (meterAnimationHandle) {
    stopMicMeter().catch(() => {});
  }
});
