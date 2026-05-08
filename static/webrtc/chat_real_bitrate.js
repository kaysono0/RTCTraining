(function () {
  const shared = window.RTCTrainingShared;

  function videoSenders(peerConnection) {
    if (!peerConnection || !peerConnection.getSenders) {
      return [];
    }
    return peerConnection.getSenders().filter((sender) => {
      return sender.track && sender.track.kind === "video";
    });
  }

  async function applyBitrateToSender(sender) {
    if (!sender || !sender.getParameters || !sender.setParameters) {
      return;
    }
    const parameters = sender.getParameters();
    parameters.encodings = parameters.encodings && parameters.encodings.length
      ? parameters.encodings
      : [{}];
    if (["manual", "abr"].includes(shared.state.bitrateMode)) {
      parameters.encodings[0].maxBitrate = shared.state.senderMaxBitrateBps;
    } else {
      delete parameters.encodings[0].maxBitrate;
    }
    await sender.setParameters(parameters);
  }

  async function applyBitrateToPeerConnection(peerConnection) {
    for (const sender of videoSenders(peerConnection)) {
      await applyBitrateToSender(sender);
    }
  }

  async function applyCurrentBitrate() {
    const entries = Object.values(shared.state.peerConnections || {});
    for (const peerConnection of entries) {
      await applyBitrateToPeerConnection(peerConnection);
    }
  }

  function numberFromInput(id, fallback) {
    const element = document.getElementById(id);
    const value = element ? Number(element.value) : fallback;
    return Number.isFinite(value) && value > 0 ? value : fallback;
  }

  function readAbrConfig() {
    shared.state.abrConfig = {
      minBitrateKbps: numberFromInput("abrMinBitrateInput", shared.state.abrConfig.minBitrateKbps),
      maxBitrateKbps: numberFromInput("abrMaxBitrateInput", shared.state.abrConfig.maxBitrateKbps),
      stepKbps: numberFromInput("abrStepKbpsInput", shared.state.abrConfig.stepKbps),
      intervalMs: shared.state.abrConfig.intervalMs,
      lossThresholdPercent: numberFromInput("abrLossThresholdInput", shared.state.abrConfig.lossThresholdPercent),
      rttThresholdMs: numberFromInput("abrRttThresholdInput", shared.state.abrConfig.rttThresholdMs)
    };
    if (shared.state.abrConfig.maxBitrateKbps < shared.state.abrConfig.minBitrateKbps) {
      shared.state.abrConfig.maxBitrateKbps = shared.state.abrConfig.minBitrateKbps;
    }
    return shared.state.abrConfig;
  }

  function renderBitrateMode() {
    const input = document.getElementById("senderBitrateInput");
    const label = document.getElementById("bitrateModeState");
    if (input && shared.state.bitrateMode === "manual") {
      input.value = String(shared.state.senderMaxBitrateBps / 1000);
    }
    if (!label) {
      return;
    }
    if (shared.state.bitrateMode === "manual") {
      label.textContent = `bitrate_manual_${shared.state.senderMaxBitrateBps / 1000}kbps`;
      return;
    }
    if (shared.state.bitrateMode === "abr") {
      label.textContent = `bitrate_abr_${shared.state.senderMaxBitrateBps / 1000}kbps`;
      return;
    }
    label.textContent = "bitrate_auto";
  }

  function renderAbrMode() {
    const select = document.getElementById("abrModeSelect");
    const label = document.getElementById("abrModeState");
    if (select && select.value !== shared.state.abrMode) {
      select.value = shared.state.abrMode;
    }
    if (label) {
      label.textContent = shared.state.abrMode === "on"
        ? `abr_on_${shared.state.abrLastDecision}`
        : "abr_off";
    }
  }

  async function setSenderBitrateKbps(value) {
    const text = value === null || value === undefined ? "" : String(value).trim();
    const numericValue = text === "" ? 0 : Number(text);
    if (!Number.isFinite(numericValue) || numericValue < 0) {
      const label = document.getElementById("bitrateModeState");
      if (label) {
        label.textContent = "bitrate_invalid";
      }
      return shared.state.bitrateMode;
    }
    if (numericValue === 0) {
      shared.state.bitrateMode = "auto";
      shared.state.senderMaxBitrateBps = null;
      shared.state.abrMode = "off";
      shared.state.abrTargetBitrateBps = null;
      shared.state.abrLastDecision = "off";
    } else {
      shared.state.bitrateMode = "manual";
      shared.state.senderMaxBitrateBps = Math.round(numericValue * 1000);
      shared.state.abrMode = "off";
      shared.state.abrTargetBitrateBps = null;
      shared.state.abrLastDecision = "off";
    }
    renderBitrateMode();
    renderAbrMode();
    await applyCurrentBitrate();
    return shared.state.bitrateMode;
  }

  function boundedTarget(targetKbps, config) {
    return Math.round(Math.min(config.maxBitrateKbps, Math.max(config.minBitrateKbps, targetKbps)) * 1000);
  }

  async function runAbrDecision(metrics) {
    if (shared.state.abrMode !== "on") {
      return {
        decision: "off",
        target_bitrate_bps: null
      };
    }
    const config = readAbrConfig();
    const currentKbps = (shared.state.abrTargetBitrateBps || shared.state.senderMaxBitrateBps || config.maxBitrateKbps * 1000) / 1000;
    if (!metrics) {
      shared.state.abrLastDecision = "waiting";
      renderAbrMode();
      return {
        decision: "waiting",
        target_bitrate_bps: shared.state.abrTargetBitrateBps
      };
    }

    const loss = Number(metrics.packet_loss_rate || 0);
    const rtt = Number(metrics.rtt_ms || 0);
    const fps = Number(metrics.fps || 0);
    let decision = "hold";
    let targetBps = boundedTarget(currentKbps, config);

    if (loss >= config.lossThresholdPercent || rtt >= config.rttThresholdMs) {
      decision = "decrease";
      targetBps = boundedTarget(currentKbps - config.stepKbps, config);
    } else if (
      loss < config.lossThresholdPercent / 2 &&
      rtt < config.rttThresholdMs / 2 &&
      fps >= 20
    ) {
      decision = "increase";
      targetBps = boundedTarget(currentKbps + config.stepKbps, config);
    }

    shared.state.abrLastDecision = decision;
    shared.state.abrTargetBitrateBps = targetBps;
    shared.state.senderMaxBitrateBps = targetBps;
    shared.state.bitrateMode = "abr";
    renderBitrateMode();
    renderAbrMode();
    await applyCurrentBitrate();
    return {
      decision,
      target_bitrate_bps: targetBps
    };
  }

  async function setAbrMode(mode) {
    shared.state.abrMode = mode === "on" ? "on" : "off";
    if (shared.state.abrMode === "on") {
      const config = readAbrConfig();
      const currentKbps = shared.state.senderMaxBitrateBps
        ? shared.state.senderMaxBitrateBps / 1000
        : config.maxBitrateKbps;
      shared.state.abrTargetBitrateBps = boundedTarget(currentKbps, config);
      shared.state.senderMaxBitrateBps = shared.state.abrTargetBitrateBps;
      shared.state.bitrateMode = "abr";
      shared.state.abrLastDecision = "hold";
    } else {
      shared.state.abrTargetBitrateBps = null;
      shared.state.abrLastDecision = "off";
      shared.state.bitrateMode = "auto";
      shared.state.senderMaxBitrateBps = null;
    }
    renderBitrateMode();
    renderAbrMode();
    await applyCurrentBitrate();
    return shared.state.abrMode;
  }

  window.RTCTrainingBitrate = {
    setSenderBitrateKbps,
    setAbrMode,
    runAbrDecision,
    applyCurrentBitrate,
    applyBitrateToPeerConnection,
    renderBitrateMode,
    renderAbrMode
  };
})();
