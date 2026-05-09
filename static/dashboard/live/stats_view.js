(function () {
  function formatMetric(value, suffix) {
    if (value === undefined || value === null || value === "") {
      return "-";
    }
    if (typeof value === "number") {
      return `${Number(value.toFixed(2))}${suffix}`;
    }
    return `${value}${suffix}`;
  }

  function newestSample(samples) {
    if (window.RTCTrainingDashboardLivePresenter) {
      return window.RTCTrainingDashboardLivePresenter.newestSample(samples);
    }
    return (samples || []).reduce((newest, sample) => {
      if (!newest) {
        return sample;
      }
      const newestOrder = newest.sample_index || newest.timestamp || 0;
      const sampleOrder = sample.sample_index || sample.timestamp || 0;
      return sampleOrder > newestOrder ? sample : newest;
    }, null);
  }

  window.RTCTrainingDashboardStatsView = {
    formatMetric,
    newestSample
  };
})();
