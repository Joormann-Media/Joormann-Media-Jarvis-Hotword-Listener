const trainerUrl = document.body.dataset.trainerUrl || "";

const hotwordSteps = document.getElementById("hotword-steps");
const intentSteps = document.getElementById("intent-steps");

const hotwordCreateForm = document.getElementById("hotword-create-form");
const hotwordExisting = document.getElementById("hotword-existing");
const hotwordPriority = document.getElementById("hotword-priority");
const hotwordDefault = document.getElementById("hotword-default");
const hotwordUseExistingBtn = document.getElementById("hotword-use-existing");
const hotwordSavePriorityBtn = document.getElementById("hotword-save-priority");
const hotwordSetDefaultBtn = document.getElementById("hotword-set-default");
const hotwordActiveId = document.getElementById("hotword-active-id");
const hotwordOrderBox = document.getElementById("hotword-order-box");
const hotwordUploadFile = document.getElementById("hotword-upload-file");
const hotwordUploadBtn = document.getElementById("hotword-upload-btn");
const hotwordRecordStart = document.getElementById("hotword-record-start");
const hotwordRecordStop = document.getElementById("hotword-record-stop");
const hotwordRecordSend = document.getElementById("hotword-record-send");
const hotwordRecordStatus = document.getElementById("hotword-record-status");
const hotwordRefreshSamples = document.getElementById("hotword-refresh-samples");
const hotwordNextToFinish = document.getElementById("hotword-next-to-finish");
const hotwordSamplesBox = document.getElementById("hotword-samples-box");
const copyHotwordToIntentBtn = document.getElementById("copy-hotword-to-intent");

const intentHotwordSelect = document.getElementById("intent-hotword-select");
const intentNext = document.getElementById("intent-next");
const intentActiveHotword = document.getElementById("intent-active-hotword");
const intentClientSelect = document.getElementById("intent-client-select");
const intentUserSelect = document.getElementById("intent-user-select");
const intentProfileSelect = document.getElementById("intent-profile-select");
const intentClientManual = document.getElementById("intent-client-manual");
const intentUserManual = document.getElementById("intent-user-manual");
const intentUploadFile = document.getElementById("intent-upload-file");
const intentRecordStart = document.getElementById("intent-record-start");
const intentRecordStop = document.getElementById("intent-record-stop");
const intentSendBtn = document.getElementById("intent-send-btn");
const intentRecordStatus = document.getElementById("intent-record-status");
const intentResultBox = document.getElementById("intent-result-box");

const intentKey = document.getElementById("intent-key");
const intentName = document.getElementById("intent-name");
const intentHandlerService = document.getElementById("intent-handler-service");
const intentHandlerAction = document.getElementById("intent-handler-action");
const intentSlotKey = document.getElementById("intent-slot-key");
const intentMemoryKey = document.getElementById("intent-memory-key");
const hotwordPhraseInput = document.getElementById("hotword-phrase");

const state = {
  activeHotwordId: "",
  hotwordBlob: null,
  intentBlob: null,
  hotwordRecorder: null,
  intentRecorder: null,
  hotwordChunks: [],
  intentChunks: [],
};

function initHelpPopovers() {
  const triggers = Array.from(document.querySelectorAll(".help-icon"));
  if (triggers.length === 0) {
    return;
  }

  const popover = document.createElement("div");
  popover.className = "help-popover";
  popover.setAttribute("role", "tooltip");
  document.body.appendChild(popover);

  let activeTrigger = null;
  let pinnedTrigger = null;

  function hidePopover() {
    popover.classList.remove("is-visible");
    activeTrigger = null;
    pinnedTrigger = null;
  }

  function placePopover(trigger) {
    const rect = trigger.getBoundingClientRect();
    const top = window.scrollY + rect.bottom + 10;
    let left = window.scrollX + rect.left + rect.width / 2;
    popover.style.top = `${top}px`;
    popover.style.left = `${left}px`;
  }

  function showPopover(trigger) {
    const text = trigger.dataset.helpText || trigger.getAttribute("title") || "";
    if (!text) {
      return;
    }
    activeTrigger = trigger;
    popover.textContent = text;
    popover.classList.add("is-visible");
    placePopover(trigger);
  }

  triggers.forEach((trigger) => {
    const helpText = trigger.getAttribute("title") || trigger.dataset.helpText || "";
    trigger.dataset.helpText = helpText;
    trigger.setAttribute("aria-label", helpText);

    trigger.addEventListener("mouseenter", () => {
      if (!pinnedTrigger) {
        showPopover(trigger);
      }
    });
    trigger.addEventListener("focus", () => showPopover(trigger));
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (pinnedTrigger === trigger && popover.classList.contains("is-visible")) {
        pinnedTrigger = null;
        popover.classList.remove("is-visible");
        } else {
        showPopover(trigger);
        pinnedTrigger = trigger;
      }
    });
    trigger.addEventListener("mouseleave", () => {
      if (!pinnedTrigger && activeTrigger === trigger) {
        popover.classList.remove("is-visible");
        activeTrigger = null;
      }
    });
    trigger.addEventListener("blur", () => {
      if (!pinnedTrigger && activeTrigger === trigger) {
        popover.classList.remove("is-visible");
        activeTrigger = null;
      }
    });
  });

  document.addEventListener("click", (event) => {
    if (popover.contains(event.target)) {
      return;
    }
    if (event.target.closest(".help-icon")) {
      return;
    }
    if (pinnedTrigger || activeTrigger) {
      hidePopover();
    }
  });

  window.addEventListener("scroll", () => {
    if (activeTrigger) {
      placePopover(activeTrigger);
    }
  }, { passive: true });

  window.addEventListener("resize", () => {
    if (activeTrigger) {
      placePopover(activeTrigger);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      hidePopover();
    }
  });
}

function setWizardStep(kind, step) {
  const panePrefix = `${kind}-`;
  const stepList = kind === "hotword" ? hotwordSteps : intentSteps;
  stepList.querySelectorAll("li").forEach((li) => {
    li.classList.toggle("is-active", Number(li.dataset.step) === step);
  });
  document.querySelectorAll(`[data-pane^="${panePrefix}"]`).forEach((pane) => {
    pane.classList.toggle("is-active", pane.dataset.pane === `${panePrefix}${step}`);
  });
}

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

async function parseJson(response) {
  const text = await response.text();
  return text ? JSON.parse(text) : {};
}

async function apiFetch(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await parseJson(response);
  if (!response.ok) {
    throw new Error(payload.detail || payload.error || `HTTP_${response.status}`);
  }
  return payload;
}

async function trainerFetch(path, options = {}) {
  const response = await fetch(`${trainerUrl}${path}`, options);
  const payload = await parseJson(response);
  if (!response.ok) {
    throw new Error(payload.detail || payload.error || `HTTP_${response.status}`);
  }
  return payload;
}

function fillHotwordSelects(hotwords) {
  [hotwordExisting, intentHotwordSelect].forEach((select) => {
    select.innerHTML = "";
    hotwords.forEach((item) => {
      const opt = document.createElement("option");
      opt.value = item.id;
      opt.textContent = `${item.label} (${item.id})`;
      select.appendChild(opt);
    });
  });
}

function renderHotwordOrder(hotwords) {
  hotwordOrderBox.textContent = JSON.stringify(
    (hotwords || []).map((item) => ({
      id: item.id,
      label: item.label,
      priority: item.priority ?? 100,
      is_default: !!item.is_default,
    })),
    null,
    2,
  );
}

async function refreshHotwords() {
  const data = await apiFetch("/hotwords");
  const hotwords = data.hotwords || [];
  fillHotwordSelects(hotwords);
  renderHotwordOrder(hotwords);
  if (!state.activeHotwordId && hotwords.length > 0) {
    state.activeHotwordId = hotwords[0].id;
    hotwordActiveId.textContent = state.activeHotwordId;
  }
  const selected = hotwords.find((item) => item.id === hotwordExisting.value) || hotwords[0];
  if (selected) {
    hotwordPriority.value = String(selected.priority ?? 100);
    hotwordDefault.checked = !!selected.is_default;
  }
}

async function refreshHotwordSamples() {
  if (!state.activeHotwordId) {
    hotwordSamplesBox.textContent = "Kein Hotword aktiv.";
    return;
  }
  const data = await apiFetch(`/hotwords/${encodeURIComponent(state.activeHotwordId)}`);
  hotwordSamplesBox.textContent = JSON.stringify(
    {
      hotword: data.hotword?.id,
      sample_count: (data.samples || []).length,
      samples: data.samples || [],
    },
    null,
    2,
  );
}

function setActiveHotword(id) {
  state.activeHotwordId = (id || "").trim();
  hotwordActiveId.textContent = state.activeHotwordId || "-";
  if (state.activeHotwordId) {
    hotwordExisting.value = state.activeHotwordId;
    intentHotwordSelect.value = state.activeHotwordId;
  }
}

async function uploadHotwordFile(file) {
  if (!state.activeHotwordId) {
    throw new Error("Kein aktives Hotword gesetzt.");
  }
  const formData = new FormData();
  formData.append("file", file, file.name || "sample.webm");
  await apiFetch(`/hotwords/${encodeURIComponent(state.activeHotwordId)}/samples/upload`, {
    method: "POST",
    body: formData,
  });
}

async function sendHotwordRecording(blob) {
  if (!state.activeHotwordId) {
    throw new Error("Kein aktives Hotword gesetzt.");
  }
  const formData = new FormData();
  formData.append("file", blob, "hotword-assistant-recording.webm");
  await apiFetch(`/hotwords/${encodeURIComponent(state.activeHotwordId)}/samples/browser-recording`, {
    method: "POST",
    body: formData,
  });
}

async function refreshBootstrap() {
  intentClientSelect.innerHTML = "";
  intentUserSelect.innerHTML = "";
  intentProfileSelect.innerHTML = '<option value="">Keins</option>';
  try {
    const data = await apiFetch("/trainer/bootstrap");
    (data.clients || []).forEach((client) => {
      const opt = document.createElement("option");
      opt.value = String(client.id);
      opt.textContent = `${client.name || "Client"} (#${client.id})`;
      intentClientSelect.appendChild(opt);
    });
    (data.users || []).forEach((user) => {
      const opt = document.createElement("option");
      opt.value = String(user.id);
      const label = user.name?.trim() ? user.name : user.email || `User ${user.id}`;
      opt.textContent = `${label} (#${user.id})`;
      intentUserSelect.appendChild(opt);
    });
    (data.profiles || []).forEach((profile) => {
      const opt = document.createElement("option");
      opt.value = String(profile.id);
      opt.textContent = `${profile.name || "Profil"} (#${profile.id})`;
      intentProfileSelect.appendChild(opt);
    });
  } catch (error) {
    intentRecordStatus.textContent = `Bootstrap Hinweis: ${error.message}`;
  }
}

function currentIntentHotword() {
  return (intentHotwordSelect.value || state.activeHotwordId || "").trim();
}

async function sendIntentIngest(fileOrBlob, filename) {
  const hotwordId = currentIntentHotword();
  if (!hotwordId) {
    throw new Error("Kein Hotword ausgewählt.");
  }

  const clientId = intentClientSelect.value || intentClientManual.value;
  const userId = intentUserSelect.value || intentUserManual.value;
  if (!clientId || !userId) {
    throw new Error("Client/User fehlen. Wähle im Bootstrap oder nutze Fallback IDs.");
  }

  const formData = new FormData();
  formData.append("file", fileOrBlob, filename);
  formData.append("hotword_id", hotwordId);
  formData.append("client_id", String(clientId));
  formData.append("user_id", String(userId));
  formData.append("jarvis_profile_id", intentProfileSelect.value || "");
  formData.append("intent_key", intentKey.value || "");
  formData.append("intent_name", intentName.value || "");
  formData.append("handler_service", intentHandlerService.value || "");
  formData.append("handler_action", intentHandlerAction.value || "");
  formData.append("slot_key", intentSlotKey.value || "");
  formData.append("memory_fact_key", intentMemoryKey.value || "");

  const result = await apiFetch("/trainer/ingest", { method: "POST", body: formData });
  intentResultBox.textContent = JSON.stringify(result, null, 2);
}

hotwordCreateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const phrases = parsePhrasesInput(hotwordPhraseInput.value);
  const payload = {
    id: document.getElementById("hotword-id").value.trim().toLowerCase(),
    label: document.getElementById("hotword-label").value.trim(),
    phrase: phrases[0] || hotwordPhraseInput.value.trim(),
    phrases,
    runtime_enabled: true,
    priority: Number(hotwordPriority.value || 100),
    is_default: !!hotwordDefault.checked,
  };
  await apiFetch("/hotwords", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  setActiveHotword(payload.id);
  await refreshHotwords();
  await refreshHotwordSamples();
  setWizardStep("hotword", 2);
});

hotwordUseExistingBtn.addEventListener("click", async () => {
  setActiveHotword(hotwordExisting.value);
  await refreshHotwordSamples();
  setWizardStep("hotword", 2);
});

hotwordSavePriorityBtn.addEventListener("click", async () => {
  const id = hotwordExisting.value || state.activeHotwordId;
  if (!id) {
    hotwordRecordStatus.textContent = "Kein Hotword ausgewählt.";
    return;
  }
  await apiFetch(`/hotwords/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      priority: Number(hotwordPriority.value || 100),
      is_default: !!hotwordDefault.checked,
    }),
  });
  hotwordRecordStatus.textContent = "Priorität/Default gespeichert.";
  await refreshHotwords();
});

hotwordSetDefaultBtn.addEventListener("click", async () => {
  const id = hotwordExisting.value || state.activeHotwordId;
  if (!id) {
    hotwordRecordStatus.textContent = "Kein Hotword ausgewählt.";
    return;
  }
  await apiFetch(`/hotwords/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_default: true }),
  });
  hotwordDefault.checked = true;
  hotwordRecordStatus.textContent = "Default-Hotword gesetzt.";
  await refreshHotwords();
});

hotwordUploadBtn.addEventListener("click", async () => {
  const file = hotwordUploadFile.files[0];
  if (!file) {
    hotwordRecordStatus.textContent = "Bitte eine Audio-Datei auswählen.";
    return;
  }
  await uploadHotwordFile(file);
  hotwordRecordStatus.textContent = "Upload gespeichert.";
  hotwordUploadFile.value = "";
  await refreshHotwordSamples();
});

hotwordRecordStart.addEventListener("click", async () => {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    hotwordRecordStatus.textContent = "Mikrofon nur via HTTPS oder localhost. Für LAN-URL bitte HTTPS nutzen.";
    return;
  }
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  state.hotwordChunks = [];
  state.hotwordBlob = null;
  state.hotwordRecorder = new MediaRecorder(stream);
  state.hotwordRecorder.ondataavailable = (evt) => {
    if (evt.data.size > 0) {
      state.hotwordChunks.push(evt.data);
    }
  };
  state.hotwordRecorder.onstop = () => {
    state.hotwordBlob = new Blob(state.hotwordChunks, { type: "audio/webm" });
    stream.getTracks().forEach((track) => track.stop());
    hotwordRecordSend.disabled = false;
    hotwordRecordStatus.textContent = "Aufnahme bereit. Du kannst senden oder erneut aufnehmen.";
  };
  state.hotwordRecorder.start();
  hotwordRecordStart.disabled = true;
  hotwordRecordStop.disabled = false;
  hotwordRecordStatus.textContent = "Aufnahme läuft...";
});

hotwordRecordStop.addEventListener("click", () => {
  if (!state.hotwordRecorder) {
    return;
  }
  state.hotwordRecorder.stop();
  hotwordRecordStart.disabled = false;
  hotwordRecordStop.disabled = true;
});

hotwordRecordSend.addEventListener("click", async () => {
  if (!state.hotwordBlob) {
    hotwordRecordStatus.textContent = "Keine Aufnahme vorhanden.";
    return;
  }
  await sendHotwordRecording(state.hotwordBlob);
  hotwordRecordStatus.textContent = "Aufnahme gespeichert. Nächste Aufnahme möglich.";
  state.hotwordBlob = null;
  hotwordRecordSend.disabled = true;
  await refreshHotwordSamples();
});

hotwordRefreshSamples.addEventListener("click", refreshHotwordSamples);
hotwordNextToFinish.addEventListener("click", async () => {
  if (!state.activeHotwordId) {
    hotwordRecordStatus.textContent = "Kein aktives Hotword gesetzt.";
    return;
  }

  hotwordNextToFinish.disabled = true;
  hotwordRecordStatus.textContent = "Finalisiere Hotword: Dataset bauen, trainieren, exportieren und Runtime aktivieren...";
  try {
    const result = await apiFetch(`/assistant/hotwords/${encodeURIComponent(state.activeHotwordId)}/finalize`, {
      method: "POST",
    });
    hotwordRecordStatus.textContent = "Hotword ist trainiert, exportiert und runtime-aktiv.";
    hotwordSamplesBox.textContent = JSON.stringify(result, null, 2);
    await refreshHotwords();
    await refreshHotwordSamples();
    setWizardStep("hotword", 3);
  } catch (error) {
    hotwordRecordStatus.textContent = `Finalisierung fehlgeschlagen: ${error.message}`;
  } finally {
    hotwordNextToFinish.disabled = false;
  }
});
copyHotwordToIntentBtn.addEventListener("click", () => {
  if (state.activeHotwordId) {
    intentHotwordSelect.value = state.activeHotwordId;
    intentActiveHotword.textContent = state.activeHotwordId;
  }
  setWizardStep("intent", 2);
});

hotwordExisting.addEventListener("change", async () => {
  setActiveHotword(hotwordExisting.value);
  await refreshHotwordSamples();
  await refreshHotwords();
});

intentNext.addEventListener("click", () => {
  intentActiveHotword.textContent = currentIntentHotword() || "-";
  setWizardStep("intent", 2);
});

intentRecordStart.addEventListener("click", async () => {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    intentRecordStatus.textContent = "Mikrofon nur via HTTPS oder localhost. Für LAN-URL bitte HTTPS nutzen.";
    return;
  }
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  state.intentChunks = [];
  state.intentBlob = null;
  state.intentRecorder = new MediaRecorder(stream);
  state.intentRecorder.ondataavailable = (evt) => {
    if (evt.data.size > 0) {
      state.intentChunks.push(evt.data);
    }
  };
  state.intentRecorder.onstop = () => {
    state.intentBlob = new Blob(state.intentChunks, { type: "audio/webm" });
    stream.getTracks().forEach((track) => track.stop());
    intentRecordStatus.textContent = "Intent-Aufnahme bereit.";
  };
  state.intentRecorder.start();
  intentRecordStart.disabled = true;
  intentRecordStop.disabled = false;
  intentRecordStatus.textContent = "Intent-Aufnahme läuft...";
});

intentRecordStop.addEventListener("click", () => {
  if (!state.intentRecorder) {
    return;
  }
  state.intentRecorder.stop();
  intentRecordStart.disabled = false;
  intentRecordStop.disabled = true;
});

intentSendBtn.addEventListener("click", async () => {
  const uploadFile = intentUploadFile.files[0];
  const source = uploadFile || state.intentBlob;
  if (!source) {
    intentRecordStatus.textContent = "Bitte Upload wählen oder aufnehmen.";
    return;
  }
  const filename = uploadFile ? uploadFile.name : "intent-assistant-recording.webm";
  await sendIntentIngest(source, filename);
  intentRecordStatus.textContent = "Intent-Datensatz gesendet.";
});

Promise.all([refreshHotwords(), refreshHotwordSamples(), refreshBootstrap()]).catch((error) => {
  hotwordSamplesBox.textContent = `Fehler beim Laden: ${error.message}`;
});

hotwordPhraseInput?.addEventListener("blur", (event) => {
  normalizePhrasesField(event.currentTarget);
});

if (window.lucide && typeof window.lucide.createIcons === "function") {
  window.lucide.createIcons();
}
initHelpPopovers();
