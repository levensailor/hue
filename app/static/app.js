const state = {
  settings: null,
  areas: [],
};

function $(id) {
  return document.getElementById(id);
}

async function readJson(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail || response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
}

async function api(path, options) {
  return readJson(await fetch(path, options));
}

function setNote(id, text) {
  $(id).textContent = text;
}

function setRunning(running, message) {
  $("run-pill").dataset.state = running ? "running" : "idle";
  $("run-pill").textContent = running ? "Live" : "Idle";
  if (message) {
    setNote("show-note", message);
  }
}

function option(value, label, selected) {
  const node = document.createElement("option");
  node.value = value;
  node.textContent = label;
  node.selected = Boolean(selected);
  return node;
}

function fillSelect(select, items, selectedValue) {
  select.innerHTML = "";
  items.forEach((item) => select.appendChild(option(item.value, item.label, item.value === selectedValue)));
}

function parseChannels(raw) {
  return raw
    .split(",")
    .map((part) => Number.parseInt(part.trim(), 10))
    .filter((value) => Number.isInteger(value) && value >= 0);
}

function collectRequest() {
  const hostField = $("bridge-host").value.trim();
  return {
    audio_device_index: Number.parseInt($("device-select").value, 10),
    channel_map: parseChannels($("channel-map").value || "0,1"),
    area_id: $("area-select").value,
    mode: $("mode-select").value,
    sensitivity: Number.parseFloat($("sensitivity").value),
    brightness: Number.parseFloat($("brightness").value),
    saturation: Number.parseFloat($("saturation").value),
    hue_host: hostField || $("bridge-select").value,
  };
}

async function saveSettings() {
  const payload = collectRequest();
  if (Number.isNaN(payload.audio_device_index)) {
    payload.audio_device_index = null;
  }
  state.settings = await api("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

async function loadHealth() {
  const health = await api("/api/health");
  $("app-name").textContent = health.app_name;
  $("app-author").textContent = `${health.author} · Logic Pro + Hue Play`;
  document.title = health.app_name;
}

async function loadDevices() {
  const payload = await api("/api/audio/devices");
  const selected = String(state.settings?.audio_device_index ?? payload.default_index ?? "");
  fillSelect(
    $("device-select"),
    payload.devices.map((device) => ({
      value: String(device.index),
      label: `${device.is_ssl ? "SSL · " : ""}${device.name} (${device.max_input_channels} in)`,
    })),
    selected,
  );
}

async function loadBridges() {
  const payload = await api("/api/hue/bridges");
  const selected = state.settings?.hue_host || "";
  fillSelect(
    $("bridge-select"),
    [
      { value: "", label: payload.bridges.length ? "Select a discovered bridge" : "No bridge found — enter an IP" },
      ...payload.bridges.map((bridge) => ({
        value: bridge.host,
        label: `${bridge.name || "Hue Bridge"} · ${bridge.host}`,
      })),
    ],
    selected,
  );
  if (selected && !$("bridge-host").value) {
    $("bridge-host").value = selected;
  }
}

async function loadAreas() {
  const payload = await api("/api/hue/areas");
  state.areas = payload.areas;
  setNote(
    "pair-note",
    payload.paired
      ? `Paired with ${payload.host}. ${payload.areas.length} entertainment area(s).`
      : "Not paired yet. Press the bridge button, then pair.",
  );
  fillSelect(
    $("area-select"),
    payload.areas.length
      ? payload.areas.map((area) => ({
          value: area.id,
          label: `${area.name} · ${area.channels.length} channel(s)`,
        }))
      : [{ value: "", label: "No entertainment area found" }],
    state.settings?.area_id || "",
  );
}

async function loadSettings() {
  state.settings = await api("/api/settings");
  $("channel-map").value = (state.settings.channel_map || [0, 1]).join(",");
  $("mode-select").value = state.settings.mode || "spectrum";
  $("sensitivity").value = state.settings.sensitivity;
  $("brightness").value = state.settings.brightness;
  $("saturation").value = state.settings.saturation;
  if (state.settings.hue_host) {
    $("bridge-host").value = state.settings.hue_host;
  }
}

async function pairBridge() {
  const host = $("bridge-host").value.trim() || $("bridge-select").value;
  if (!host) {
    setNote("pair-note", "Choose a discovered bridge or enter its IP address.");
    return;
  }
  setNote("pair-note", "Waiting for the bridge link button...");
  try {
    const result = await api("/api/hue/pair", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ host }),
    });
    setNote("pair-note", result.message);
    await loadAreas();
  } catch (error) {
    setNote("pair-note", error.message);
  }
}

async function startShow() {
  const request = collectRequest();
  if (Number.isNaN(request.audio_device_index)) {
    setRunning(false, "Select an SSL or other input device first.");
    return;
  }
  if (!request.area_id) {
    setRunning(false, "Select a Hue Entertainment area that includes your Play lights.");
    return;
  }
  try {
    await saveSettings();
    const result = await api("/api/show/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
    });
    setRunning(result.running, result.message);
  } catch (error) {
    setRunning(false, error.message);
  }
}

async function stopShow() {
  const result = await api("/api/show/stop", { method: "POST" });
  setRunning(result.running, result.message);
}

function renderSpectrum(bands) {
  const root = $("spectrum");
  if (!root.childElementCount) {
    for (let index = 0; index < 16; index += 1) {
      root.appendChild(document.createElement("b"));
    }
  }
  Array.from(root.children).forEach((bar, index) => {
    const value = bands[index] || 0;
    bar.style.height = `${Math.max(8, value * 100)}%`;
  });
}

function renderLevels(frame) {
  $("level-bass").style.width = `${frame.bass * 100}%`;
  $("level-mid").style.width = `${frame.mid * 100}%`;
  $("level-high").style.width = `${frame.high * 100}%`;
  $("level-rms").style.width = `${frame.rms * 100}%`;
}

function renderLights(lights) {
  const root = $("lights");
  if (root.childElementCount !== lights.length) {
    root.innerHTML = "";
    lights.forEach(() => {
      const orb = document.createElement("div");
      orb.className = "orb";
      root.appendChild(orb);
    });
  }
  Array.from(root.children).forEach((orb, index) => {
    const light = lights[index];
    if (!light) {
      return;
    }
    const red = Math.round(light.r * 255);
    const green = Math.round(light.g * 255);
    const blue = Math.round(light.b * 255);
    orb.style.background = `rgb(${red}, ${green}, ${blue})`;
    orb.style.boxShadow = `0 0 24px rgba(${red}, ${green}, ${blue}, 0.45)`;
  });
}

function connectMeters() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${window.location.host}/ws/meters`);
  socket.addEventListener("message", (event) => {
    const frame = JSON.parse(event.data);
    renderSpectrum(frame.bands || []);
    renderLevels(frame);
    renderLights(frame.lights || []);
    if (frame.beat) {
      $("run-pill").textContent = "Beat";
    }
  });
  socket.addEventListener("close", () => {
    window.setTimeout(connectMeters, 1500);
  });
}

async function boot() {
  await loadHealth();
  await loadSettings();
  await Promise.all([loadDevices(), loadBridges(), loadAreas()]);
  const status = await api("/api/show/status");
  setRunning(status.running, status.message);
  connectMeters();
}

$("discover-btn").addEventListener("click", () => loadBridges().catch((error) => setNote("pair-note", error.message)));
$("pair-btn").addEventListener("click", pairBridge);
$("start-btn").addEventListener("click", startShow);
$("stop-btn").addEventListener("click", stopShow);
$("bridge-select").addEventListener("change", (event) => {
  if (event.target.value) {
    $("bridge-host").value = event.target.value;
  }
});

boot().catch((error) => setNote("show-note", error.message));
