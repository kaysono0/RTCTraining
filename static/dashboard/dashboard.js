(function () {
  if (window.__RTCTrainingDashboardInlineBootstrap) {
    return;
  }

  let liveStatsRefreshPromise = null;
  const liveStatsState = {
    requestSeq: 0,
    clearing: false,
    snapshot: null,
    snapshotAvailable: true,
    selectedPeerPair: "all",
    metric: "rtt_ms"
  };
  const LIVE_TREND_WINDOW_SECONDS = 60;
  const csvAnalysisState = {
    result: null,
    metric: "rtt_ms",
    sessions: []
  };
  const REQUIRED_CSV_FIELDS = [
    "sample_index",
    "timestamp",
    "room_id",
    "test_session_id",
    "peer_id",
    "remote_peer_id",
    "rtt_ms",
    "packet_loss_rate",
    "jitter_ms",
    "bitrate_kbps",
    "fps",
    "nack_mode",
    "abr_mode"
  ];
  const CSV_METRICS = {
    rtt_ms: { label: "RTT", avgField: "avg_rtt_ms", suffix: " ms", direction: "min" },
    packet_loss_rate: { label: "Loss", avgField: "avg_packet_loss_rate", suffix: "%", direction: "min" },
    jitter_ms: { label: "Jitter", avgField: "avg_jitter_ms", suffix: " ms", direction: "min" },
    bitrate_kbps: { label: "Bitrate", avgField: "avg_bitrate_kbps", suffix: " kbps", direction: "max" },
    fps: { label: "FPS", avgField: "avg_fps", suffix: "", direction: "max" }
  };
  const LIVE_METRICS = {
    rtt_ms: { label: "RTT", suffix: " ms" },
    packet_loss_rate: { label: "Loss Rate", suffix: "%" },
    jitter_ms: { label: "Jitter", suffix: " ms" },
    bitrate_kbps: { label: "Bitrate", suffix: " kbps" },
    fps: { label: "FPS", suffix: "" }
  };
  const dom = window.RTCTrainingDashboardDom;
  const statsView = window.RTCTrainingDashboardStatsView;
  const csvAnalysis = window.RTCTrainingDashboardCsvAnalysis;
  const csvView = window.RTCTrainingDashboardCsvView;
  const livePresenter = window.RTCTrainingDashboardLivePresenter;

  function queryParam(name) {
    return new URLSearchParams(window.location.search).get(name);
  }

  function setText(id, text) {
    if (dom && dom.setText) {
      dom.setText(id, text);
      return;
    }
    const element = document.getElementById(id);
    if (element) {
      element.textContent = text;
    }
  }

  function addClickListener(id, callback) {
    if (dom && dom.addClickListener) {
      dom.addClickListener(id, callback);
      return;
    }
    const element = document.getElementById(id);
    if (element) {
      element.addEventListener("click", callback);
    }
  }

  function getText(id) {
    if (dom && dom.getText) {
      return dom.getText(id);
    }
    const element = document.getElementById(id);
    return element ? element.textContent : "";
  }

  function roomCountLabel(rooms) {
    const count = Object.keys(rooms || {}).length;
    return `${count} ${count === 1 ? "room" : "rooms"}`;
  }

  function formatMetric(value, suffix) {
    if (statsView && statsView.formatMetric) {
      return statsView.formatMetric(value, suffix);
    }
    if (value === undefined || value === null || value === "") {
      return "-";
    }
    if (typeof value === "number") {
      return `${Number(value.toFixed(2))}${suffix}`;
    }
    return `${value}${suffix}`;
  }

  function formatLocalTime(date) {
    return date.toLocaleTimeString("zh-CN", { hour12: false });
  }

  function formatEpochSeconds(epochSeconds) {
    if (!epochSeconds) {
      return null;
    }
    return new Date(epochSeconds * 1000).toLocaleString("zh-CN", { hour12: false });
  }

  function lastSampleLabel(peer) {
    const sampleTime = formatEpochSeconds(peer.last_sample_timestamp);
    if (sampleTime) {
      return `last_sample: ${sampleTime}`;
    }
    if (peer.last_sample_index) {
      return `last_sample: unknown_time; sample #${peer.last_sample_index}`;
    }
    return "last_sample: unknown_time";
  }

  function sampleTimeLabel(sample) {
    const sampleTime = formatEpochSeconds(sample.timestamp);
    if (sampleTime) {
      return sampleTime;
    }
    if (sample.sample_index) {
      return `unknown_time; sample #${sample.sample_index}`;
    }
    return "unknown_time";
  }

  function metric(sample, name) {
    return (sample.metrics || {})[name];
  }

  function newestSample(samples) {
    if (statsView && statsView.newestSample) {
      return statsView.newestSample(samples);
    }
    if (livePresenter && livePresenter.newestSample) {
      return livePresenter.newestSample(samples);
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

  function shortPeerId(peerId) {
    if (livePresenter && livePresenter.shortPeerId) {
      return livePresenter.shortPeerId(peerId);
    }
    if (!peerId) {
      return "";
    }
    return peerId.length > 12 ? `${peerId.slice(0, 12)}...` : peerId;
  }

  function peerLabel(peerId, labels) {
    if (livePresenter && livePresenter.peerLabel) {
      return livePresenter.peerLabel(peerId, labels);
    }
    if (!peerId) {
      return "-";
    }
    const displayName = labels && labels[peerId];
    return displayName ? `${displayName} (${shortPeerId(peerId)})` : shortPeerId(peerId);
  }

  function peerPairLabel(peerId, remotePeerId, labels) {
    if (livePresenter && livePresenter.peerPairLabel) {
      return livePresenter.peerPairLabel(peerId, remotePeerId, labels);
    }
    return `${peerLabel(peerId, labels)} -> ${peerLabel(remotePeerId, labels)}`;
  }

  function peerPairKey(peerId, remotePeerId) {
    return `${peerId}->${remotePeerId}`;
  }

  function samplePairKey(sample) {
    return peerPairKey(sample.peer_id, sample.remote_peer_id);
  }

  function selectedPairMatches(peerId, remotePeerId) {
    return liveStatsState.selectedPeerPair === "all" ||
      liveStatsState.selectedPeerPair === peerPairKey(peerId, remotePeerId);
  }

  function buildPeerLabelsFromMembers(members) {
    if (livePresenter && livePresenter.buildPeerLabelsFromMembers) {
      return livePresenter.buildPeerLabelsFromMembers(members);
    }
    return (members || []).reduce((labels, member) => {
      labels[member.peer_id] = member.display_name;
      return labels;
    }, {});
  }

  function missingFields(sample) {
    const required = [
      "connection_state",
      "ice_connection_state",
      "rtt_ms",
      "packets_sent",
      "packets_received",
      "packets_lost",
      "jitter_ms",
      "bitrate_kbps",
      "fps",
      "frame_width",
      "frame_height",
      "bytes_received",
      "frames_decoded",
      "frames_dropped",
      "codec",
      "nack_enabled",
      "nack_mode",
      "nack_count",
      "local_candidate_type",
      "remote_candidate_type",
      "candidate_pair_protocol",
      "available_outgoing_bitrate_kbps"
    ];
    const metrics = sample.metrics || {};
    return required.filter((name) => {
      const value = metrics[name];
      return value === undefined || value === null || value === "";
    });
  }

  function numberFromRow(row, field) {
    if (csvAnalysis && csvAnalysis.numberFromRow) {
      return csvAnalysis.numberFromRow(row, field);
    }
    const value = Number(row[field]);
    return Number.isFinite(value) ? value : null;
  }

  function summarizeCsvFile(entry) {
    if (csvAnalysis && csvAnalysis.summarizeCsvFile) {
      return csvAnalysis.summarizeCsvFile(entry);
    }
    return {
      name: entry.name,
      ok: false,
      missing: REQUIRED_CSV_FIELDS,
      sample_count: 0,
      rows: []
    };
  }

  function bestBy(files, field, direction) {
    if (csvView && csvView.bestBy) {
      return csvView.bestBy(files, field, direction);
    }
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
    if (csvView && csvView.rangeCell) {
      return csvView.rangeCell(file, minField, avgField, maxField, suffix);
    }
    const minVal = file[minField];
    const avgVal = file[avgField];
    const maxVal = file[maxField];
    if (minVal === null || avgVal === null || maxVal === null) {
      return "-";
    }
    return `${minVal} / ${avgVal} / ${maxVal}${suffix}`;
  }

  function renderCsvAnalysis(result) {
    const validation = document.getElementById("csvValidationPanel");
    const tableBody = document.querySelector("#csvComparisonTable tbody");
    const trend = document.getElementById("csvTrendComparison");
    if (validation) {
      validation.innerHTML = "";
      for (const file of result.files) {
        const item = document.createElement("div");
        item.textContent = file.ok
          ? `${file.name}: ok`
          : `${file.name}: missing ${file.missing.join(", ")}`;
        validation.appendChild(item);
      }
    }
    if (tableBody) {
      tableBody.innerHTML = "";
      for (const file of result.files.filter((item) => item.ok)) {
        const row = document.createElement("tr");
        [
          file.name,
          file.sample_count,
          file.room_id,
          file.test_session_id,
          file.peer_id,
          file.remote_peer_id,
          rangeCell(file, "min_rtt_ms", "avg_rtt_ms", "max_rtt_ms", " ms"),
          rangeCell(file, "min_packet_loss_rate", "avg_packet_loss_rate", "max_packet_loss_rate", "%"),
          rangeCell(file, "min_jitter_ms", "avg_jitter_ms", "max_jitter_ms", " ms"),
          rangeCell(file, "min_bitrate_kbps", "avg_bitrate_kbps", "max_bitrate_kbps", " kbps"),
          rangeCell(file, "min_fps", "avg_fps", "max_fps", "")
        ].forEach((value) => {
          const cell = document.createElement("td");
          cell.textContent = String(value);
          row.appendChild(cell);
        });
        tableBody.appendChild(row);
      }
    }
    if (trend) {
      renderCsvTrend(result);
    }
    renderExperimentComparison(result);
    renderCsvTrendChart(result);
  }

  function rowsByField(files, field) {
    const groups = {};
    for (const file of files || []) {
      if (!file.ok) {
        continue;
      }
      for (const row of file.rows || []) {
        const value = row[field];
        if (!value) {
          continue;
        }
        groups[value] = groups[value] || [];
        groups[value].push(row);
      }
    }
    return groups;
  }

  function averageRows(rows, field) {
    const values = (rows || [])
      .map((row) => numberFromRow(row, field))
      .filter((value) => value !== null);
    if (!values.length) {
      return null;
    }
    return Number((values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(2));
  }

  function renderExperimentComparison(result) {
    const panel = document.getElementById("experimentComparisonPanel");
    if (!panel) {
      return;
    }
    panel.innerHTML = "";
    const files = result.files || [];
    const lines = [];
    const nackGroups = rowsByField(files, "nack_mode");
    if (nackGroups.enabled && nackGroups.disabled) {
      const enabledLoss = averageRows(nackGroups.enabled, "packet_loss_rate");
      const disabledLoss = averageRows(nackGroups.disabled, "packet_loss_rate");
      if (enabledLoss !== null && disabledLoss !== null) {
        lines.push(
          enabledLoss <= disabledLoss
            ? `NACK: enabled lower loss than disabled (${enabledLoss}% vs ${disabledLoss}%)`
            : `NACK: disabled lower loss than enabled (${disabledLoss}% vs ${enabledLoss}%)`
        );
      }
    }

    const abrGroups = rowsByField(files, "abr_mode");
    if (abrGroups.on && abrGroups.off) {
      const onBitrate = averageRows(abrGroups.on, "bitrate_kbps");
      const offBitrate = averageRows(abrGroups.off, "bitrate_kbps");
      if (onBitrate !== null && offBitrate !== null) {
        lines.push(
          onBitrate >= offBitrate
            ? `ABR: on higher bitrate than off (${onBitrate} kbps vs ${offBitrate} kbps)`
            : `ABR: off higher bitrate than on (${offBitrate} kbps vs ${onBitrate} kbps)`
        );
      }
    }

    const bitrateRows = files
      .filter((file) => file.ok)
      .flatMap((file) => file.rows || [])
      .map((row) => numberFromRow(row, "sender_max_bitrate_bps"))
      .filter((value) => value !== null && value > 0);
    if (bitrateRows.length) {
      const maxKbps = Math.round(Math.max(...bitrateRows) / 1000);
      lines.push(`Bitrate config: ${maxKbps} kbps highest configured target`);
    }

    if (!lines.length) {
      panel.textContent = "experiment_comparison_waiting";
      return;
    }
    for (const line of lines) {
      const item = document.createElement("div");
      item.textContent = line;
      panel.appendChild(item);
    }
  }

  function renderCsvTrend(result) {
    const trend = document.getElementById("csvTrendComparison");
    if (!trend) {
      return;
    }
    trend.innerHTML = "";
    const metricConfig = CSV_METRICS[csvAnalysisState.metric] || CSV_METRICS.rtt_ms;
    const best = bestBy(result.files, metricConfig.avgField, metricConfig.direction);
    const item = document.createElement("div");
    item.textContent = best
      ? `${metricConfig.label} best: ${best.name} (${formatMetric(best[metricConfig.avgField], metricConfig.suffix)})`
      : `${metricConfig.label} best: -`;
    trend.appendChild(item);
  }

  function csvSeries(file, metricName) {
    const rows = file.rows || [];
    const sampleIndexes = rows
      .map((row) => numberFromRow(row, "sample_index"))
      .filter((value) => value !== null);
    const minSampleIndex = sampleIndexes.length ? Math.min(...sampleIndexes) : null;
    return rows
      .map((row, index) => {
        const sampleIndex = numberFromRow(row, "sample_index");
        return {
          x: sampleIndex !== null && minSampleIndex !== null ? sampleIndex - minSampleIndex : index,
          y: numberFromRow(row, metricName)
        };
      })
      .filter((point) => point.y !== null);
  }

  function renderCsvTrendChart(result) {
    const chart = document.getElementById("csvTrendChart");
    if (!chart) {
      return;
    }
    chart.innerHTML = "";
    const metricName = csvAnalysisState.metric;
    const metricConfig = CSV_METRICS[metricName] || CSV_METRICS.rtt_ms;
    const files = (result.files || []).filter((file) => file.ok);
    const series = files.map((file) => ({ file, points: csvSeries(file, metricName) }))
      .filter((item) => item.points.length > 0);
    if (!series.length) {
      chart.textContent = "trend_waiting";
      return;
    }

    const width = 780;
    const height = 280;
    const padLeft = 62;
    const padRight = 28;
    const padTop = 36;
    const padBottom = 40;
    const plotWidth = width - padLeft - padRight;
    const plotHeight = height - padTop - padBottom;

    const allPoints = series.flatMap((item) => item.points);
    const minX = Math.min(...allPoints.map((point) => point.x));
    const maxX = Math.max(...allPoints.map((point) => point.x));
    const minY = Math.min(...allPoints.map((point) => point.y));
    const maxY = Math.max(...allPoints.map((point) => point.y));
    const xRange = maxX - minX || 1;
    const yRange = maxY - minY || 1;
    const colors = ["#23576b", "#b45309", "#15803d", "#7c3aed", "#be123c"];

    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", metricConfig.label + " trend over normalized sample index");

    // Chart title
    var title = document.createElementNS("http://www.w3.org/2000/svg", "text");
    title.setAttribute("x", String(width / 2));
    title.setAttribute("y", String(padTop / 2 + 4));
    title.setAttribute("text-anchor", "middle");
    title.setAttribute("fill", "#15202b");
    title.setAttribute("font-size", "13");
    title.setAttribute("font-weight", "bold");
    title.textContent = metricConfig.label + " Trend (per sample)";
    svg.appendChild(title);

    // Grid lines (horizontal)
    var gridLines = 5;
    for (var g = 0; g <= gridLines; g++) {
      var gy = padTop + (plotHeight * g / gridLines);
      var gridLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
      gridLine.setAttribute("x1", String(padLeft));
      gridLine.setAttribute("y1", String(Number(gy.toFixed(1))));
      gridLine.setAttribute("x2", String(padLeft + plotWidth));
      gridLine.setAttribute("y2", String(Number(gy.toFixed(1))));
      gridLine.setAttribute("stroke", "#e5eaed");
      gridLine.setAttribute("stroke-width", "1");
      svg.appendChild(gridLine);

      // Y-axis tick labels
      var yVal = minY + yRange * (1 - g / gridLines);
      var yLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
      yLabel.setAttribute("x", String(padLeft - 6));
      yLabel.setAttribute("y", String(Number((gy + 3).toFixed(1))));
      yLabel.setAttribute("text-anchor", "end");
      yLabel.setAttribute("fill", "#53636b");
      yLabel.setAttribute("font-size", "10");
      yLabel.textContent = String(Number(yVal.toFixed(1)));
      svg.appendChild(yLabel);
    }

    // Y-axis label
    var yAxisLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
    yAxisLabel.setAttribute("x", String(-(padTop + plotHeight / 2)));
    yAxisLabel.setAttribute("y", "14");
    yAxisLabel.setAttribute("transform", "rotate(-90)");
    yAxisLabel.setAttribute("text-anchor", "middle");
    yAxisLabel.setAttribute("fill", "#53636b");
    yAxisLabel.setAttribute("font-size", "11");
    yAxisLabel.textContent = metricConfig.label + " (" + metricConfig.suffix.trim() + ")";
    svg.appendChild(yAxisLabel);

    // X-axis label
    var xAxisLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
    xAxisLabel.setAttribute("x", String(padLeft + plotWidth / 2));
    xAxisLabel.setAttribute("y", String(height - 8));
    xAxisLabel.setAttribute("text-anchor", "middle");
    xAxisLabel.setAttribute("fill", "#53636b");
    xAxisLabel.setAttribute("font-size", "11");
    xAxisLabel.textContent = "Normalized Sample Index";
    svg.appendChild(xAxisLabel);

    // X-axis tick labels
    var xTicks = 6;
    for (var h = 0; h <= xTicks; h++) {
      var xVal = minX + xRange * h / xTicks;
      var gx = padLeft + plotWidth * h / xTicks;
      var xTickLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
      xTickLabel.setAttribute("x", String(Number(gx.toFixed(1))));
      xTickLabel.setAttribute("y", String(height - padBottom + 16));
      xTickLabel.setAttribute("text-anchor", "middle");
      xTickLabel.setAttribute("fill", "#53636b");
      xTickLabel.setAttribute("font-size", "10");
      xTickLabel.textContent = String(Math.round(xVal));
      svg.appendChild(xTickLabel);
    }

    // Axis lines (L-shape)
    var axis = document.createElementNS("http://www.w3.org/2000/svg", "path");
    axis.setAttribute("d", [
      "M", padLeft, padTop,
      "L", padLeft, padTop + plotHeight,
      "L", padLeft + plotWidth, padTop + plotHeight
    ].join(" "));
    axis.setAttribute("fill", "none");
    axis.setAttribute("stroke", "#9aa8af");
    axis.setAttribute("stroke-width", "1.5");
    svg.appendChild(axis);

    // Data polylines
    series.forEach(function (item, index) {
      var pts = item.points.map(function (point) {
        var x = padLeft + ((point.x - minX) / xRange) * plotWidth;
        var y = padTop + plotHeight - ((point.y - minY) / yRange) * plotHeight;
        return Number(x.toFixed(1)) + "," + Number(y.toFixed(1));
      }).join(" ");
      var line = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
      line.setAttribute("points", pts);
      line.setAttribute("fill", "none");
      line.setAttribute("stroke", colors[index % colors.length]);
      line.setAttribute("stroke-width", "2.5");
      line.setAttribute("data-file", item.file.name);
      svg.appendChild(line);
    });

    // Legend
    var legend = document.createElement("div");
    legend.className = "csv-trend-legend";
    series.forEach(function (item, index) {
      var label = document.createElement("span");
      label.style.setProperty("--series-color", colors[index % colors.length]);
      label.textContent = item.file.name;
      legend.appendChild(label);
    });

    chart.append(svg, legend);
  }

  function analyzeCsvTexts(entries) {
    const files = (entries || []).map(summarizeCsvFile);
    const result = {
      ok: files.length > 0 && files.every((file) => file.ok),
      files
    };
    csvAnalysisState.result = result;
    renderCsvAnalysis(result);
    setText("csvState", result.ok ? "csv_ready" : "csv_invalid");
    return result;
  }

  function setCsvMetric(metricName) {
    csvAnalysisState.metric = CSV_METRICS[metricName] ? metricName : "rtt_ms";
    const select = document.getElementById("csvMetricSelect");
    if (select && select.value !== csvAnalysisState.metric) {
      select.value = csvAnalysisState.metric;
    }
    if (csvAnalysisState.result) {
      renderCsvTrend(csvAnalysisState.result);
      renderCsvTrendChart(csvAnalysisState.result);
    }
    return csvAnalysisState.metric;
  }

  function sessionCsvOptionValue(session, file) {
    return JSON.stringify({
      test_session_id: session.test_session_id,
      remote_peer_id: file.remote_peer_id,
      download_url: file.download_url,
      filename: file.filename,
      display_name: file.display_name
    });
  }

  function renderTestSessionCsvList(sessions) {
    const select = document.getElementById("testSessionCsvSelect");
    const panel = document.getElementById("testSessionCsvPanel");
    if (select) {
      select.innerHTML = "";
      for (const session of sessions || []) {
        for (const file of session.csv_files || []) {
          const option = document.createElement("option");
          option.value = sessionCsvOptionValue(session, file);
          option.textContent = file.display_name || [
            session.test_session_id,
            session.preset,
            file.remote_peer_id,
            session.duration_seconds ? `${session.duration_seconds}s` : "",
            `samples=${session.sample_count}`
          ].filter(Boolean).join(" | ");
          select.appendChild(option);
        }
      }
    }
    if (panel) {
      panel.textContent = sessions && sessions.length
        ? `sessions_loaded: ${sessions.length}`
        : "sessions_empty";
    }
  }

  async function loadTestSessionCsvList() {
    const origin = document.getElementById("webrtcOriginInput").value.trim();
    const roomId = document.getElementById("statsRoomInput").value.trim() || "room1";
    const response = await fetch(`/api/webrtc/stats/test/sessions?origin=${encodeURIComponent(origin)}&room_id=${encodeURIComponent(roomId)}`);
    const payload = await readJsonResponse(response);
    if (!payload.ok) {
      setText("testSessionCsvPanel", payload.error.code);
      return payload;
    }
    csvAnalysisState.sessions = payload.data.sessions || [];
    renderTestSessionCsvList(csvAnalysisState.sessions);
    return { sessions: csvAnalysisState.sessions };
  }

  function dashboardCsvDownloadUrl(downloadUrl, origin) {
    const path = new URL(downloadUrl, origin).pathname;
    const prefix = "/stats/test/download/";
    const filePath = path.startsWith(prefix) ? path.slice(prefix.length) : path.replace(/^\/+/, "");
    return `/api/webrtc/stats/test/download/${filePath}?origin=${encodeURIComponent(origin)}`;
  }

  async function loadSelectedSessionCsv() {
    const select = document.getElementById("testSessionCsvSelect");
    if (!select || !select.value) {
      setText("testSessionCsvPanel", "session_csv_waiting");
      return { ok: false, files: [] };
    }
    const origin = document.getElementById("webrtcOriginInput").value.trim();
    const selected = JSON.parse(select.value);
    const response = await fetch(dashboardCsvDownloadUrl(selected.download_url, origin));
    const text = await response.text();
    const name = selected.filename || `${selected.test_session_id}-${selected.remote_peer_id}.csv`;
    return analyzeCsvTexts([{ name, text }]);
  }

  async function analyzeSelectedCsvFiles() {
    const input = document.getElementById("csvFileInput");
    const files = input && input.files ? Array.from(input.files) : [];
    if (!files.length) {
      const result = { ok: false, files: [] };
      renderCsvAnalysis(result);
      setText("csvState", "csv_waiting");
      return result;
    }
    const entries = await Promise.all(files.map(async (file) => {
      return { name: file.name, text: await file.text() };
    }));
    return analyzeCsvTexts(entries);
  }

  function candidatePair(sample) {
    const localType = metric(sample, "local_candidate_type");
    const remoteType = metric(sample, "remote_candidate_type");
    const protocol = metric(sample, "candidate_pair_protocol");
    if (!localType && !remoteType && !protocol) {
      return "-";
    }
    return `${localType || "?"}/${remoteType || "?"} ${protocol || ""}`.trim();
  }

  function latestSampleForPeerPair(samples, peer) {
    return newestSample((samples || []).filter((sample) => {
      return sample.peer_id === peer.peer_id &&
        sample.remote_peer_id === peer.remote_peer_id;
    }));
  }

  function selectedMetricLabel(sample) {
    const metricName = liveStatsState.metric;
    const metricConfig = LIVE_METRICS[metricName] || LIVE_METRICS.rtt_ms;
    const value = sample ? metric(sample, metricName) : null;
    return `${metricConfig.label} ${formatMetric(value, metricConfig.suffix)}`;
  }

  function renderPeerPairs(peers, labels, latestSamples) {
    const list = document.getElementById("peerPairList");
    if (!list) {
      return;
    }
    list.innerHTML = "";
    for (const peer of peers || []) {
      const latest = latestSampleForPeerPair(latestSamples, peer);
      const item = document.createElement("li");
      item.textContent = [
        `[${lastSampleLabel(peer)}]`,
        peerPairLabel(peer.peer_id, peer.remote_peer_id, labels),
        selectedMetricLabel(latest)
      ].join(" | ");
      list.appendChild(item);
    }
  }

  function renderLivePeerPairOptions(peers, labels) {
    const select = document.getElementById("livePeerPairSelect");
    if (!select) {
      return;
    }
    const current = liveStatsState.selectedPeerPair;
    const options = [{ value: "all", label: "All pairs" }];
    for (const peer of peers || []) {
      options.push({
        value: peerPairKey(peer.peer_id, peer.remote_peer_id),
        label: peerPairLabel(peer.peer_id, peer.remote_peer_id, labels)
      });
    }

    const existingValues = Array.from(select.options).map((option) => option.value);
    const nextValues = options.map((option) => option.value);
    const valuesChanged = existingValues.length !== nextValues.length ||
      existingValues.some((value, index) => value !== nextValues[index]);
    if (valuesChanged) {
      select.innerHTML = "";
      for (const optionData of options) {
        const option = document.createElement("option");
        option.value = optionData.value;
        option.textContent = optionData.label;
        select.appendChild(option);
      }
    } else {
      options.forEach((optionData, index) => {
        if (select.options[index].textContent !== optionData.label) {
          select.options[index].textContent = optionData.label;
        }
      });
    }

    liveStatsState.selectedPeerPair = nextValues.includes(current) ? current : "all";
    select.value = liveStatsState.selectedPeerPair;
  }

  function filteredSamples(samples) {
    return (samples || []).filter((sample) => {
      return selectedPairMatches(sample.peer_id, sample.remote_peer_id);
    });
  }

  function renderLatestStats(samples, labels) {
    const panel = document.getElementById("latestStatsPanel");
    if (!panel) {
      return;
    }
    panel.innerHTML = "";
    const latest = newestSample(samples);
    if (!latest) {
      setText("nackSummary", "NACK: -");
      return;
    }
    setText(
      "nackSummary",
      `NACK: ${formatMetric(metric(latest, "nack_mode"), "")} / ${formatMetric(metric(latest, "nack_count"), "")}`
    );

    const missing = missingFields(latest);
    const rows = [
      ["Peer (通信对端)", peerPairLabel(latest.peer_id, latest.remote_peer_id, labels)],
      ["Connection (连接状态)", formatMetric(metric(latest, "connection_state"), "")],
      ["ICE (ICE连接状态)", formatMetric(metric(latest, "ice_connection_state"), "")],
      ["Candidate Pair (候选地址对)", candidatePair(latest)],
      ["RTT (往返时延)", formatMetric(metric(latest, "rtt_ms"), " ms")],
      ["Loss (丢包数)", formatMetric(metric(latest, "packets_lost"), "")],
      ["Loss Rate (丢包率)", formatMetric(metric(latest, "packet_loss_rate"), "%")],
      [
        "Packets (数据包)",
        `${formatMetric(metric(latest, "packets_sent"), "")} sent / ${formatMetric(metric(latest, "packets_received"), "")} recv / ${formatMetric(metric(latest, "packets_lost"), "")} lost`
      ],
      ["Jitter (抖动)", formatMetric(metric(latest, "jitter_ms"), " ms")],
      ["Bitrate (码率)", formatMetric(metric(latest, "bitrate_kbps"), " kbps")],
      ["Available Out (可用上行码率)", formatMetric(metric(latest, "available_outgoing_bitrate_kbps"), " kbps")],
      [
        "Bytes (字节数)",
        `${formatMetric(metric(latest, "bytes_sent"), "")} sent / ${formatMetric(metric(latest, "bytes_received"), "")} recv`
      ],
      ["FPS (帧率)", formatMetric(metric(latest, "fps"), "")],
      [
        "Resolution (分辨率)",
        `${formatMetric(metric(latest, "frame_width"), "")} x ${formatMetric(metric(latest, "frame_height"), "")}`
      ],
      [
        "Frames (帧处理)",
        `${formatMetric(metric(latest, "frames_sent"), "")} sent / ${formatMetric(metric(latest, "frames_received"), "")} recv / ${formatMetric(metric(latest, "frames_decoded"), "")} decoded`
      ],
      ["Dropped (丢帧数)", formatMetric(metric(latest, "frames_dropped"), "")],
      ["Codec (编码格式)", formatMetric(metric(latest, "codec"), "")],
      ["NACK Enabled (NACK启用)", formatMetric(metric(latest, "nack_enabled"), "")],
      ["NACK Mode (NACK模式)", formatMetric(metric(latest, "nack_mode"), "")],
      ["Recovery (丢包恢复)", `NACK ${formatMetric(metric(latest, "nack_count"), "")} / PLI ${formatMetric(metric(latest, "pli_count"), "")} / FIR ${formatMetric(metric(latest, "fir_count"), "")}`],
      ["Missing Fields (缺失字段)", missing.length ? missing.join(", ") : "none"]
    ];

    for (const [label, value] of rows) {
      const term = document.createElement("dt");
      const detail = document.createElement("dd");
      term.textContent = label;
      detail.textContent = value;
      panel.append(term, detail);
    }
  }

  function renderHistoryRows(samples, labels) {
    const body = document.querySelector("#statsHistoryTable tbody");
    if (!body) {
      return;
    }
    body.innerHTML = "";
    for (const sample of (samples || []).slice(-20).reverse()) {
      const row = document.createElement("tr");
      const cells = [
        sampleTimeLabel(sample),
        peerLabel(sample.peer_id, labels),
        peerLabel(sample.remote_peer_id, labels),
        formatMetric(metric(sample, "rtt_ms"), " ms"),
        formatMetric(metric(sample, "packets_lost"), ""),
        `${formatMetric(metric(sample, "packets_received"), "")} recv / ${formatMetric(metric(sample, "packets_lost"), "")} lost`,
        `NACK ${formatMetric(metric(sample, "nack_count"), "")}`,
        formatMetric(metric(sample, "frames_decoded"), ""),
        formatMetric(metric(sample, "frames_dropped"), ""),
        formatMetric(metric(sample, "bytes_received"), ""),
        `${formatMetric(metric(sample, "frame_width"), "")} x ${formatMetric(metric(sample, "frame_height"), "")}`,
        formatMetric(metric(sample, "jitter_ms"), " ms"),
        formatMetric(metric(sample, "bitrate_kbps"), " kbps"),
        formatMetric(metric(sample, "fps"), "")
      ];
      for (const value of cells) {
        const cell = document.createElement("td");
        cell.textContent = value === undefined || value === null ? "-" : String(value);
        row.appendChild(cell);
      }
      body.appendChild(row);
    }
  }

  function liveTrendSeries(samples) {
    const metricName = liveStatsState.metric;
    return (samples || [])
      .slice()
      .sort((a, b) => (a.sample_index || a.timestamp || 0) - (b.sample_index || b.timestamp || 0))
      .map((sample, index) => {
        return {
          x: sample.sample_index || index + 1,
          y: Number(metric(sample, metricName))
        };
      })
      .filter((point) => Number.isFinite(point.y));
  }

  function liveTrendWindowSamples(samples, serverTime) {
    const rows = samples || [];
    const numericTimes = rows
      .map((sample) => Number(sample.timestamp))
      .filter((value) => Number.isFinite(value));
    const endTime = Number.isFinite(Number(serverTime))
      ? Number(serverTime)
      : (numericTimes.length ? Math.max(...numericTimes) : null);
    if (endTime === null) {
      return rows.slice(-LIVE_TREND_WINDOW_SECONDS);
    }
    const startTime = endTime - LIVE_TREND_WINDOW_SECONDS;
    return rows.filter((sample) => {
      const timestamp = Number(sample.timestamp);
      return Number.isFinite(timestamp) && timestamp >= startTime && timestamp <= endTime;
    });
  }

  function liveTrendSeriesGroups(samples, labels) {
    const groups = new Map();
    for (const sample of samples || []) {
      const key = samplePairKey(sample);
      if (!groups.has(key)) {
        groups.set(key, {
          key,
          label: peerPairLabel(sample.peer_id, sample.remote_peer_id, labels),
          points: []
        });
      }
      groups.get(key).points.push(sample);
    }
    return Array.from(groups.values())
      .map((group) => {
        return {
          key: group.key,
          label: group.label,
          points: liveTrendSeries(group.points)
        };
      })
      .filter((group) => group.points.length > 0)
      .sort((left, right) => left.label.localeCompare(right.label));
  }

  function renderLiveTrend(samples, labels, serverTime) {
    const chart = document.getElementById("liveTrendChart");
    if (!chart) {
      return;
    }
    chart.innerHTML = "";
    const metricName = liveStatsState.metric;
    const metricConfig = LIVE_METRICS[metricName] || LIVE_METRICS.rtt_ms;
    const groups = liveTrendSeriesGroups(liveTrendWindowSamples(samples, serverTime), labels);
    const points = groups.flatMap((group) => group.points);
    if (points.length < 1) {
      const empty = document.createElement("div");
      empty.className = "live-trend-empty";
      empty.textContent = "trend_waiting";
      chart.appendChild(empty);
      return;
    }

    const width = 820;
    const height = 240;
    const padLeft = 60;
    const padRight = 24;
    const padTop = 34;
    const padBottom = 38;
    const plotWidth = width - padLeft - padRight;
    const plotHeight = height - padTop - padBottom;
    const minX = Math.min(...points.map((point) => point.x));
    const maxX = Math.max(...points.map((point) => point.x));
    const minY = Math.min(...points.map((point) => point.y));
    const maxY = Math.max(...points.map((point) => point.y));
    const xRange = maxX - minX || 1;
    const yRange = maxY - minY || 1;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", `${metricConfig.label} live trend`);

    const title = document.createElementNS("http://www.w3.org/2000/svg", "text");
    title.setAttribute("x", String(width / 2));
    title.setAttribute("y", "20");
    title.setAttribute("text-anchor", "middle");
    title.setAttribute("fill", "#15202b");
    title.setAttribute("font-size", "13");
    title.setAttribute("font-weight", "bold");
    title.textContent = `${metricConfig.label} Trend`;
    svg.appendChild(title);

    for (let index = 0; index <= 4; index += 1) {
      const y = padTop + (plotHeight * index / 4);
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", String(padLeft));
      line.setAttribute("y1", String(Number(y.toFixed(1))));
      line.setAttribute("x2", String(padLeft + plotWidth));
      line.setAttribute("y2", String(Number(y.toFixed(1))));
      line.setAttribute("stroke", "#e5eaed");
      svg.appendChild(line);
      const yValue = minY + yRange * (1 - index / 4);
      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute("x", String(padLeft - 6));
      label.setAttribute("y", String(Number((y + 3).toFixed(1))));
      label.setAttribute("text-anchor", "end");
      label.setAttribute("fill", "#53636b");
      label.setAttribute("font-size", "10");
      label.textContent = String(Number(yValue.toFixed(1)));
      svg.appendChild(label);
    }

    const axis = document.createElementNS("http://www.w3.org/2000/svg", "path");
    axis.setAttribute("d", `M ${padLeft} ${padTop} L ${padLeft} ${padTop + plotHeight} L ${padLeft + plotWidth} ${padTop + plotHeight}`);
    axis.setAttribute("fill", "none");
    axis.setAttribute("stroke", "#9aa8af");
    axis.setAttribute("stroke-width", "1.5");
    svg.appendChild(axis);

    const colors = ["#23576b", "#ad4e15", "#5f6f18", "#7a3f8f", "#2d6f50", "#9a3455"];
    for (const [index, group] of groups.entries()) {
      const polyline = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
      polyline.setAttribute("points", group.points.map((point) => {
        const x = padLeft + ((point.x - minX) / xRange) * plotWidth;
        const y = padTop + plotHeight - ((point.y - minY) / yRange) * plotHeight;
        return `${Number(x.toFixed(1))},${Number(y.toFixed(1))}`;
      }).join(" "));
      polyline.setAttribute("fill", "none");
      polyline.setAttribute("stroke", colors[index % colors.length]);
      polyline.setAttribute("stroke-width", "2.5");
      polyline.setAttribute("data-peer-pair", group.key);
      polyline.setAttribute("aria-label", group.label);
      svg.appendChild(polyline);
    }

    const caption = document.createElement("div");
    caption.className = "live-trend-empty";
    caption.textContent = `${metricConfig.label}: ${points.length} samples / ${groups.length} pairs / last ${LIVE_TREND_WINDOW_SECONDS}s${metricConfig.suffix ? ` (${metricConfig.suffix.trim()})` : ""}`;
    const legend = document.createElement("div");
    legend.className = "live-trend-empty";
    legend.textContent = groups.map((group) => group.label).join(" | ");
    chart.append(svg, caption, legend);
  }

  function renderMeshTopology(snapshot, labels) {
    const state = document.getElementById("meshTopologyState");
    const list = document.getElementById("meshTopology");
    if (!state || !list) {
      return;
    }

    const peers = snapshot.peers || [];
    list.innerHTML = "";
    if (peers.length === 0) {
      state.textContent = "mesh_waiting_for_stats";
      return;
    }

    for (const peer of peers) {
      const sample = (snapshot.latest || []).find((candidate) => {
        return candidate.peer_id === peer.peer_id &&
          candidate.remote_peer_id === peer.remote_peer_id;
      }) || {};
      const item = document.createElement("li");
      item.dataset.peerPair = peerPairKey(peer.peer_id, peer.remote_peer_id);
      item.textContent = [
        peerPairLabel(peer.peer_id, peer.remote_peer_id, labels),
        `Connection ${formatMetric(metric(sample, "connection_state"), "")}/${formatMetric(metric(sample, "ice_connection_state"), "")}`,
        `RTT ${formatMetric(metric(sample, "rtt_ms"), " ms")}`,
        `Loss ${formatMetric(metric(sample, "packets_lost"), "")}`,
        `Jitter ${formatMetric(metric(sample, "jitter_ms"), " ms")}`,
        `Bitrate ${formatMetric(metric(sample, "bitrate_kbps"), " kbps")}`,
        `FPS ${formatMetric(metric(sample, "fps"), "")}`,
        `NACK ${formatMetric(metric(sample, "nack_count"), "")}`,
        `Candidate ${candidatePair(sample)}`
      ].join(" | ");
      list.appendChild(item);
    }
    state.textContent = peers.length >= 6 ? "mesh_online" : "mesh_partial";
  }

  function renderSnapshot(snapshot) {
    const labels = buildPeerLabelsFromMembers(snapshot.members || []);
    const peers = snapshot.peers || [];
    renderLivePeerPairOptions(peers, labels);
    const visiblePeers = peers.filter((peer) => selectedPairMatches(peer.peer_id, peer.remote_peer_id));
    const visibleLatest = filteredSamples(snapshot.latest || []);
    const visibleHistory = filteredSamples(snapshot.history || []);
    renderPeerPairs(visiblePeers, labels, snapshot.latest || []);
    renderLatestStats(visibleLatest, labels);
    renderHistoryRows(visibleHistory, labels);
    renderLiveTrend(visibleHistory, labels, snapshot.server_time);
    renderMeshTopology(snapshot, labels);
    if (peers.length === 0) {
      setText("statsState", "service_online_but_no_stats");
    } else {
      setText("statsState", "stats_online");
    }
    setText("statsRefreshState", `stats_last_updated: ${formatEpochSeconds(snapshot.server_time) || formatLocalTime(new Date())}`);
  }

  async function readJsonResponse(response) {
    const text = await response.text();
    try {
      return JSON.parse(text);
    } catch (error) {
      return {
        ok: false,
        error: {
          code: "non_json_response",
          message: error.message,
          details: {
            status: response.status,
            body: text.slice(0, 200)
          }
        }
      };
    }
  }

  async function checkService() {
    const input = document.getElementById("webrtcOriginInput");
    const origin = input.value.trim();
    setText("serviceState", "service_checking");

    const response = await fetch(`/api/webrtc/members?origin=${encodeURIComponent(origin)}`);
    const payload = await readJsonResponse(response);
    if (!payload.ok) {
      setText("serviceState", payload.error.code);
      setText("roomSummary", "0 rooms");
      return payload;
    }

    setText("serviceState", "service_online");
    setText("roomSummary", roomCountLabel(payload.data.rooms));
    return payload;
  }

  async function fetchLiveStats() {
    const origin = document.getElementById("webrtcOriginInput").value.trim();
    const roomId = document.getElementById("statsRoomInput").value.trim() || "room1";
    const requestSeq = ++liveStatsState.requestSeq;

    if (!liveStatsState.snapshotAvailable) {
      return await fetchLegacyLiveStats(origin, roomId, requestSeq);
    }

    const snapshotResponse = await fetch(`/api/webrtc/dashboard/snapshot?origin=${encodeURIComponent(origin)}&room_id=${encodeURIComponent(roomId)}`);
    const snapshotPayload = await readJsonResponse(snapshotResponse);
    if (!snapshotPayload.ok) {
      if (
        snapshotPayload.error &&
        snapshotPayload.error.code === "non_json_response" &&
        snapshotPayload.error.details &&
        snapshotPayload.error.details.status === 404
      ) {
        liveStatsState.snapshotAvailable = false;
      }
      const fallbackPayload = await fetchLegacyLiveStats(origin, roomId, requestSeq);
      if (fallbackPayload.ok) {
        return fallbackPayload;
      }
      if (requestSeq === liveStatsState.requestSeq) {
        setText("statsState", fallbackPayload.error ? fallbackPayload.error.code : snapshotPayload.error.code);
      }
      return fallbackPayload.error ? fallbackPayload : snapshotPayload;
    }
    if (requestSeq !== liveStatsState.requestSeq || liveStatsState.clearing) {
      return snapshotPayload;
    }

    liveStatsState.snapshot = snapshotPayload.data;
    renderSnapshot(snapshotPayload.data);
    return {
      ok: true,
      data: {
        latest: snapshotPayload.data.latest || [],
        history: snapshotPayload.data.history || [],
        peers: snapshotPayload.data.peers || [],
        snapshot: snapshotPayload.data
      }
    };
  }

  async function fetchLegacyLiveStats(origin, roomId, requestSeq) {
    const membersResponse = await fetch(`/api/webrtc/members?origin=${encodeURIComponent(origin)}`);
    const membersPayload = await readJsonResponse(membersResponse);
    if (!membersPayload.ok) {
      return membersPayload;
    }
    const rooms = membersPayload.data ? membersPayload.data.rooms || {} : {};
    const members = rooms[roomId] ? rooms[roomId].members || [] : [];

    const peersResponse = await fetch(`/api/webrtc/stats/peers?origin=${encodeURIComponent(origin)}&room_id=${encodeURIComponent(roomId)}`);
    const peersPayload = await readJsonResponse(peersResponse);
    if (!peersPayload.ok) {
      return peersPayload;
    }

    const latestResponse = await fetch(`/api/webrtc/stats?origin=${encodeURIComponent(origin)}&room_id=${encodeURIComponent(roomId)}`);
    const latestPayload = await readJsonResponse(latestResponse);
    if (!latestPayload.ok) {
      return latestPayload;
    }

    const historyResponse = await fetch(`/api/webrtc/stats/history?origin=${encodeURIComponent(origin)}&room_id=${encodeURIComponent(roomId)}`);
    const historyPayload = await readJsonResponse(historyResponse);
    if (!historyPayload.ok) {
      return historyPayload;
    }

    const snapshot = {
      room_id: roomId,
      stats_revision: null,
      server_time: Date.now() / 1000,
      members,
      peers: peersPayload.data.peers || [],
      latest: latestPayload.data.samples || [],
      history: historyPayload.data.samples || []
    };
    if (requestSeq === liveStatsState.requestSeq && !liveStatsState.clearing) {
      liveStatsState.snapshot = snapshot;
      renderSnapshot(snapshot);
    }
    return {
      ok: true,
      data: {
        latest: snapshot.latest,
        history: snapshot.history,
        peers: snapshot.peers,
        snapshot
      }
    };
  }

  async function loadLiveStats() {
    if (liveStatsRefreshPromise) {
      return liveStatsRefreshPromise;
    }
    liveStatsRefreshPromise = fetchLiveStats();
    try {
      return await liveStatsRefreshPromise;
    } finally {
      liveStatsRefreshPromise = null;
    }
  }

  async function clearLiveStats() {
    const origin = document.getElementById("webrtcOriginInput").value.trim();
    const roomId = document.getElementById("statsRoomInput").value.trim() || "room1";
    liveStatsState.clearing = true;
    liveStatsState.requestSeq += 1;
    setText("statsState", "stats_clearing");
    try {
      const response = await fetch(`/api/webrtc/clear_stats?origin=${encodeURIComponent(origin)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room_id: roomId })
      });
      const payload = await readJsonResponse(response);
      if (!payload.ok) {
        setText("statsState", payload.error.code);
        return payload;
      }

      const snapshot = payload.data.snapshot || {
        room_id: roomId,
        server_time: Date.now() / 1000,
        members: [],
        peers: [],
        latest: [],
        history: []
      };
      liveStatsState.snapshot = snapshot;
      renderSnapshot(snapshot);
      return payload;
    } finally {
      liveStatsState.clearing = false;
    }
  }

  function setLivePeerPair(pairKey) {
    liveStatsState.selectedPeerPair = pairKey || "all";
    const select = document.getElementById("livePeerPairSelect");
    if (select && select.value !== liveStatsState.selectedPeerPair) {
      select.value = liveStatsState.selectedPeerPair;
    }
    if (liveStatsState.snapshot) {
      renderSnapshot(liveStatsState.snapshot);
    }
    return liveStatsState.selectedPeerPair;
  }

  function setLiveMetric(metricName) {
    liveStatsState.metric = LIVE_METRICS[metricName] ? metricName : "rtt_ms";
    const select = document.getElementById("liveMetricSelect");
    if (select && select.value !== liveStatsState.metric) {
      select.value = liveStatsState.metric;
    }
    if (liveStatsState.snapshot) {
      renderSnapshot(liveStatsState.snapshot);
    }
    return liveStatsState.metric;
  }

  function bootstrapDashboard() {
    if (window.__RTCTrainingDashboardTestHooks) {
      return;
    }

    const input = document.getElementById("webrtcOriginInput");
    const origin = queryParam("webrtc_origin");
    if (origin && input) {
      input.value = origin;
    }
    const queryRoomId = queryParam("room_id");
    const roomInput = document.getElementById("statsRoomInput");
    if (queryRoomId && roomInput) {
      roomInput.value = queryRoomId;
    }

    addClickListener("checkServiceButton", () => {
      checkService().catch((error) => {
        setText("serviceState", "service_error");
        setText("roomSummary", error.message);
      });
    });
    addClickListener("clearStatsButton", () => {
      clearLiveStats().catch((error) => {
        setText("statsState", "stats_clear_failed");
        setText("statsRefreshState", error.message);
      });
    });
    addClickListener("csvAnalyzeButton", () => {
      analyzeSelectedCsvFiles().catch((error) => {
        setText("csvState", "csv_error");
        setText("csvValidationPanel", error.message);
      });
    });
    addClickListener("loadSessionCsvListButton", () => {
      loadTestSessionCsvList().catch((error) => {
        setText("testSessionCsvPanel", error.message);
      });
    });
    addClickListener("loadSelectedSessionCsvButton", () => {
      loadSelectedSessionCsv().catch((error) => {
        setText("csvState", "csv_error");
        setText("csvValidationPanel", error.message);
      });
    });
    const csvMetricSelect = document.getElementById("csvMetricSelect");
    if (csvMetricSelect) {
      csvMetricSelect.addEventListener("change", (event) => {
        setCsvMetric(event.target.value);
      });
    }
    const livePeerPairSelect = document.getElementById("livePeerPairSelect");
    if (livePeerPairSelect) {
      livePeerPairSelect.addEventListener("change", (event) => {
        setLivePeerPair(event.target.value);
      });
    }
    const liveMetricSelect = document.getElementById("liveMetricSelect");
    if (liveMetricSelect) {
      liveMetricSelect.addEventListener("change", (event) => {
        setLiveMetric(event.target.value);
      });
    }

    window.__RTCTrainingDashboardTestHooks = {
      checkService,
      loadLiveStats,
      clearLiveStats,
      analyzeCsvTexts,
      analyzeSelectedCsvFiles,
      setCsvMetric,
      setLivePeerPair,
      setLiveMetric,
      loadTestSessionCsvList,
      loadSelectedSessionCsv,
      getServiceState() {
        return document.getElementById("serviceState").textContent;
      },
      getStatsState() {
        return document.getElementById("statsState").textContent;
      },
      getStatsRefreshState() {
        return document.getElementById("statsRefreshState").textContent;
      },
      getRoomSummary() {
        return document.getElementById("roomSummary").textContent;
      }
    };

    checkService().catch((error) => {
      setText("serviceState", "service_error");
      setText("roomSummary", error.message);
    });
    loadLiveStats().catch(() => {
      setText("statsState", "stats_error");
    });
    window.setInterval(() => {
      loadLiveStats().catch(() => {
        setText("statsState", "stats_error");
      });
    }, 1000);
  }

  if (document.readyState === "loading") {
    window.addEventListener("DOMContentLoaded", bootstrapDashboard);
  } else {
    bootstrapDashboard();
  }
})();
