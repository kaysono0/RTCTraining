(function () {
  function formatNumber(value, digits) {
    if (typeof value !== "number" || !Number.isFinite(value)) {
      return "--";
    }
    return value.toFixed(digits);
  }

  function renderRemoteStats(container, metrics) {
    container.innerHTML = "";
    const resolution = metrics.frame_width && metrics.frame_height
      ? `${metrics.frame_width}x${metrics.frame_height}`
      : "--";
    const rows = [
      ["Bitrate", `${formatNumber(metrics.bitrate_kbps, 1)} kbps`],
      ["Resolution", resolution],
      ["FPS", formatNumber(metrics.fps, 1)],
      ["Lost", metrics.packets_lost ?? "--"],
      ["Loss%", formatNumber(metrics.packet_loss_rate, 2)],
      ["Jitter", `${formatNumber(metrics.jitter_ms, 1)} ms`],
      ["RTT", `${formatNumber(metrics.rtt_ms, 1)} ms`],
      ["ICE", metrics.ice_connection_state || "--"],
      ["Codec", metrics.codec || "--"],
      ["Candidate", `${metrics.local_candidate_type || "?"}/${metrics.remote_candidate_type || "?"}`],
      ["NACK/PLI", `${metrics.nack_count ?? "--"}/${metrics.pli_count ?? "--"}`]
    ];
    for (const [label, value] of rows) {
      const item = document.createElement("span");
      item.textContent = `${label}: ${value}`;
      container.appendChild(item);
    }
  }

  window.RTCTrainingRemoteStatsView = {
    formatNumber,
    renderRemoteStats
  };
})();
