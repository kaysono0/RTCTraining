(function () {
  const shared = window.RTCTrainingShared;
  const PRESETS = {
    manual: { nackMode: "enabled", bitrateKbps: 0, abrMode: "off" },
    nack_on: { nackMode: "enabled", bitrateKbps: 0, abrMode: "off" },
    nack_off: { nackMode: "disabled", bitrateKbps: 0, abrMode: "off" },
    bitrate_300: { nackMode: "enabled", bitrateKbps: 300, abrMode: "off" },
    bitrate_800: { nackMode: "enabled", bitrateKbps: 800, abrMode: "off" },
    nack_on_abr_off: { nackMode: "enabled", bitrateKbps: 0, abrMode: "off" },
    nack_off_abr_off: { nackMode: "disabled", bitrateKbps: 0, abrMode: "off" },
    abr_simple: { nackMode: "enabled", bitrateKbps: null, abrMode: "on" },
    nack_on_abr_on: { nackMode: "enabled", bitrateKbps: null, abrMode: "on" },
    nack_off_abr_on: { nackMode: "disabled", bitrateKbps: null, abrMode: "on" }
  };

  function weakNetworkLabel(session) {
    const weak = session && session.weak_network ? session.weak_network : {};
    return weak.profile || "-";
  }

  function durationLabel(session) {
    if (!session) {
      return "-";
    }
    if (session.duration_seconds !== null && session.duration_seconds !== undefined) {
      return `${session.duration_seconds}s`;
    }
    if (!session.started_at) {
      return "-";
    }
    const end = session.finished_at || Date.now() / 1000;
    return `${Math.max(0, Math.round(end - session.started_at))}s`;
  }

  function plannedDurationLabel(session) {
    return session && session.planned_duration_seconds
      ? `${session.planned_duration_seconds}s`
      : "-";
  }

  function renderPresetSummary(presetName) {
    const summary = document.getElementById("testSessionPresetSummary");
    if (!summary) {
      return;
    }
    const preset = PRESETS[presetName] || PRESETS.manual;
    summary.textContent = [
      `preset: ${presetName}`,
      `nack: ${preset.nackMode}`,
      `bitrate: ${preset.bitrateKbps === null ? "abr" : preset.bitrateKbps || "auto"}`,
      `abr: ${preset.abrMode}`
    ].join(" | ");
  }

  function renderTestSession() {
    const label = document.getElementById("testSessionState");
    if (label) {
      label.textContent = `test_session_${shared.state.testSessionStatus}`;
    }
    const session = shared.state.testSession;
    renderPresetSummary(session && session.preset ? session.preset : "manual");
    const details = document.getElementById("testSessionDetails");
    if (details) {
      details.textContent = session
        ? [
          `id: ${session.test_session_id}`,
          `preset: ${session.preset}`,
          `weak: ${weakNetworkLabel(session)}`,
          `planned: ${plannedDurationLabel(session)}`,
          `samples: ${session.sample_count || 0}`,
          `duration: ${durationLabel(session)}`
        ].join(" | ")
        : "";
    }
    const downloads = document.getElementById("testSessionDownloads");
    if (!downloads) {
      return;
    }
    downloads.replaceChildren();
    const files = shared.state.testSession && shared.state.testSession.csv_files
      ? shared.state.testSession.csv_files
      : [];
    files.forEach((file) => {
      const link = document.createElement("a");
      link.href = file.download_url;
      link.textContent = file.display_name || file.filename || `${file.room_id}/${file.test_session_id}/${file.peer_id}/${file.remote_peer_id}.csv`;
      link.setAttribute("download", "");
      downloads.appendChild(link);
    });
  }

  async function applyTestPreset(presetName) {
    const name = PRESETS[presetName] ? presetName : "manual";
    const preset = PRESETS[name];
    if (window.RTCTrainingNack && window.RTCTrainingNack.setNackMode) {
      window.RTCTrainingNack.setNackMode(preset.nackMode);
    }
    if (window.RTCTrainingBitrate && window.RTCTrainingBitrate.setAbrMode) {
      if (preset.abrMode === "on") {
        await window.RTCTrainingBitrate.setAbrMode("on");
      } else if (preset.bitrateKbps !== null) {
        await window.RTCTrainingBitrate.setSenderBitrateKbps(preset.bitrateKbps);
      } else {
        await window.RTCTrainingBitrate.setAbrMode("off");
      }
    }
    const select = document.getElementById("testPresetSelect");
    if (select && select.value !== name) {
      select.value = name;
    }
    renderPresetSummary(name);
    return {
      preset: name,
      nack_mode: shared.state.nackMode,
      bitrate_mode: shared.state.bitrateMode,
      sender_max_bitrate_bps: shared.state.senderMaxBitrateBps,
      abr_mode: shared.state.abrMode
    };
  }

  function readUiOptions(overrides) {
    const presetSelect = document.getElementById("testPresetSelect");
    const weakNetworkInput = document.getElementById("testWeakNetworkInput");
    const durationInput = document.getElementById("testSessionDurationInput");
    const noteInput = document.getElementById("testSessionNoteInput");
    const options = overrides || {};
    const durationValue = options.planned_duration_seconds !== undefined
      ? options.planned_duration_seconds
      : (durationInput ? durationInput.value : "");
    return {
      preset: options.preset || (presetSelect ? presetSelect.value : "manual"),
      planned_duration_seconds: normalizeDuration(durationValue),
      metadata: options.metadata || {
        note: noteInput ? noteInput.value : ""
      },
      weak_network: options.weak_network || {
        profile: weakNetworkInput ? weakNetworkInput.value : ""
      }
    };
  }

  function normalizeDuration(value) {
    if (value === null || value === undefined || value === "") {
      return null;
    }
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }

  async function postJson(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const payload = await response.json();
    if (!payload.ok) {
      throw new Error(payload.error.message);
    }
    return payload.data.session;
  }

  async function startTestSession(options) {
    if (shared.state.testSessionId && shared.state.testSessionStatus === "running") {
      throw new Error(
        "A test session is already running (" + shared.state.testSessionId +
        "). Finish or cancel it before starting a new one."
      );
    }
    const uiOptions = readUiOptions(options);
    await applyTestPreset(uiOptions.preset);
    const session = await postJson("/stats/test/start", {
      room_id: shared.state.roomId,
      peer_id: shared.state.clientId,
      display_name: shared.state.localDisplayName || "",
      preset: uiOptions.preset,
      planned_duration_seconds: uiOptions.planned_duration_seconds,
      metadata: uiOptions.metadata,
      weak_network: uiOptions.weak_network
    });
    shared.state.testSessionId = session.test_session_id;
    shared.state.testSessionStatus = session.status;
    shared.state.testSession = session;
    renderTestSession();
    shared.addTimelineEvent("test_session_started", {
      category: "test",
      summary: session.test_session_id
    });
    return session;
  }

  async function finishTestSession() {
    if (!shared.state.testSessionId) {
      return null;
    }
    const session = await postJson("/stats/test/finish", {
      test_session_id: shared.state.testSessionId
    });
    shared.state.testSessionId = null;
    shared.state.testSessionStatus = session.status;
    shared.state.testSession = session;
    renderTestSession();
    shared.addTimelineEvent("test_session_finished", {
      category: "test",
      summary: `${session.test_session_id} samples=${session.sample_count}`
    });
    return session;
  }

  async function cancelTestSession() {
    if (!shared.state.testSessionId) {
      return null;
    }
    const session = await postJson("/stats/test/cancel", {
      test_session_id: shared.state.testSessionId
    });
    shared.state.testSessionId = null;
    shared.state.testSessionStatus = session.status;
    shared.state.testSession = session;
    renderTestSession();
    shared.addTimelineEvent("test_session_canceled", {
      category: "test",
      summary: session.test_session_id
    });
    return session;
  }

  window.RTCTrainingTestSession = {
    applyTestPreset,
    renderTestSession,
    startTestSession,
    finishTestSession,
    cancelTestSession
  };
})();
