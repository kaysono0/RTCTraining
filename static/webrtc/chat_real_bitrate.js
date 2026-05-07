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
    if (shared.state.bitrateMode === "manual") {
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
    label.textContent = "bitrate_auto";
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
    } else {
      shared.state.bitrateMode = "manual";
      shared.state.senderMaxBitrateBps = Math.round(numericValue * 1000);
    }
    renderBitrateMode();
    await applyCurrentBitrate();
    return shared.state.bitrateMode;
  }

  window.RTCTrainingBitrate = {
    setSenderBitrateKbps,
    applyCurrentBitrate,
    applyBitrateToPeerConnection,
    renderBitrateMode
  };
})();
