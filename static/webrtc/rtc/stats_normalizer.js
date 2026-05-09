(function () {
  function numberOrNull(value) {
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  }

  function finalizeMetrics(metrics) {
    const next = Object.assign({}, metrics);
    const packetsExpected = (next.packets_received || 0) + (next.packets_lost || 0);
    if (packetsExpected > 0) {
      next.packet_loss_rate = (next.packets_lost / packetsExpected) * 100;
    } else if (next.packet_loss_rate === undefined) {
      next.packet_loss_rate = null;
    }
    return next;
  }

  window.RTCTrainingStatsNormalizer = {
    numberOrNull,
    finalizeMetrics
  };
})();
