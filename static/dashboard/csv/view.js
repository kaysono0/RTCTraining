(function () {
  function bestBy(files, field, direction) {
    const valid = files.filter((file) => file.ok && file[field] !== null && file[field] !== undefined);
    if (!valid.length) {
      return null;
    }
    return valid.reduce((best, file) => {
      if (!best) {
        return file;
      }
      return direction === "max"
        ? (file[field] > best[field] ? file : best)
        : (file[field] < best[field] ? file : best);
    }, null);
  }

  function rangeCell(file, minField, avgField, maxField, suffix) {
    const minVal = file[minField];
    const avgVal = file[avgField];
    const maxVal = file[maxField];
    if (minVal === null || avgVal === null || maxVal === null) {
      return "-";
    }
    return `${minVal} / ${avgVal} / ${maxVal}${suffix}`;
  }

  window.RTCTrainingDashboardCsvView = {
    bestBy,
    rangeCell
  };
})();
