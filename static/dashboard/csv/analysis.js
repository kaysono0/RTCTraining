(function () {
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

  function parseCsvText(text) {
    return window.RTCTrainingDashboardCsvParser.parseCsvText(text);
  }

  function numberFromRow(row, field) {
    const value = Number(row[field]);
    return Number.isFinite(value) ? value : null;
  }

  function extractValues(rows, field) {
    return rows
      .map((row) => numberFromRow(row, field))
      .filter((value) => value !== null);
  }

  function average(rows, field) {
    const values = extractValues(rows, field);
    if (values.length === 0) {
      return null;
    }
    return Number((values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(2));
  }

  function minValue(rows, field) {
    const values = extractValues(rows, field);
    if (values.length === 0) {
      return null;
    }
    return Number(Math.min(...values).toFixed(2));
  }

  function maxValue(rows, field) {
    const values = extractValues(rows, field);
    if (values.length === 0) {
      return null;
    }
    return Number(Math.max(...values).toFixed(2));
  }

  function uniqueLabel(rows, field) {
    const values = [...new Set(rows.map((row) => row[field]).filter(Boolean))];
    if (values.length === 0) {
      return "-";
    }
    return values.length === 1 ? values[0] : `${values[0]} +${values.length - 1}`;
  }

  function summarizeCsvFile(entry) {
    const parsed = parseCsvText(entry.text);
    const missing = REQUIRED_CSV_FIELDS.filter((field) => !parsed.headers.includes(field));
    if (missing.length) {
      return {
        name: entry.name,
        ok: false,
        missing,
        sample_count: parsed.rows.length
      };
    }
    return {
      name: entry.name,
      ok: true,
      missing: [],
      sample_count: parsed.rows.length,
      room_id: uniqueLabel(parsed.rows, "room_id"),
      test_session_id: uniqueLabel(parsed.rows, "test_session_id"),
      peer_id: uniqueLabel(parsed.rows, "peer_id"),
      remote_peer_id: uniqueLabel(parsed.rows, "remote_peer_id"),
      avg_rtt_ms: average(parsed.rows, "rtt_ms"),
      min_rtt_ms: minValue(parsed.rows, "rtt_ms"),
      max_rtt_ms: maxValue(parsed.rows, "rtt_ms"),
      avg_packet_loss_rate: average(parsed.rows, "packet_loss_rate"),
      min_packet_loss_rate: minValue(parsed.rows, "packet_loss_rate"),
      max_packet_loss_rate: maxValue(parsed.rows, "packet_loss_rate"),
      avg_jitter_ms: average(parsed.rows, "jitter_ms"),
      min_jitter_ms: minValue(parsed.rows, "jitter_ms"),
      max_jitter_ms: maxValue(parsed.rows, "jitter_ms"),
      avg_bitrate_kbps: average(parsed.rows, "bitrate_kbps"),
      min_bitrate_kbps: minValue(parsed.rows, "bitrate_kbps"),
      max_bitrate_kbps: maxValue(parsed.rows, "bitrate_kbps"),
      avg_fps: average(parsed.rows, "fps"),
      min_fps: minValue(parsed.rows, "fps"),
      max_fps: maxValue(parsed.rows, "fps"),
      rows: parsed.rows
    };
  }

  window.RTCTrainingDashboardCsvAnalysis = {
    REQUIRED_CSV_FIELDS,
    numberFromRow,
    extractValues,
    average,
    minValue,
    maxValue,
    uniqueLabel,
    summarizeCsvFile
  };
})();
