(function () {
  const shared = window.RTCTrainingShared;

  function setNackMode(mode) {
    shared.state.nackMode = mode === "disabled" ? "disabled" : "enabled";
    renderNackMode();
    return shared.state.nackMode;
  }

  function renderNackMode() {
    const select = document.getElementById("nackModeSelect");
    const label = document.getElementById("nackModeState");
    if (select && select.value !== shared.state.nackMode) {
      select.value = shared.state.nackMode;
    }
    if (label) {
      label.textContent = shared.state.nackMode === "enabled"
        ? "nack_enabled"
        : "nack_disabled";
    }
  }

  function mungeSdp(sdp) {
    if (shared.state.nackMode !== "disabled" || !sdp) {
      return sdp;
    }
    let inVideoSection = false;
    return sdp.split(/\r?\n/).filter((line) => {
      if (line.startsWith("m=")) {
        inVideoSection = line.startsWith("m=video");
      }
      if (!inVideoSection) {
        return true;
      }
      return !/^a=rtcp-fb:\S+ nack(?:\s|$)/.test(line);
    }).join("\r\n");
  }

  function prepareLocalDescription(description) {
    if (!description || shared.state.nackMode !== "disabled") {
      return description;
    }
    return new RTCSessionDescription({
      type: description.type,
      sdp: mungeSdp(description.sdp)
    });
  }

  window.RTCTrainingNack = {
    setNackMode,
    renderNackMode,
    mungeSdp,
    prepareLocalDescription
  };
})();
