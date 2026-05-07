(function () {
  if (window.__RTCTrainingDashboardInlineBootstrap) {
    return;
  }

  let liveStatsRefreshPromise = null;
  const liveStatsState = {
    requestSeq: 0,
    clearing: false,
    snapshot: null,
    snapshotAvailable: true
  };

  function queryParam(name) {
    return new URLSearchParams(window.location.search).get(name);
  }

  function setText(id, text) {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = text;
    }
  }

  function addClickListener(id, callback) {
    const element = document.getElementById(id);
    if (element) {
      element.addEventListener("click", callback);
    }
  }

  function getText(id) {
    const element = document.getElementById(id);
    return element ? element.textContent : "";
  }

  function roomCountLabel(rooms) {
    const count = Object.keys(rooms || {}).length;
    return `${count} ${count === 1 ? "room" : "rooms"}`;
  }

  function formatMetric(value, suffix) {
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

  function shortPeerId(peerId) {
    if (!peerId) {
      return "";
    }
    return peerId.length > 12 ? `${peerId.slice(0, 12)}...` : peerId;
  }

  function peerLabel(peerId, labels) {
    if (!peerId) {
      return "-";
    }
    const displayName = labels && labels[peerId];
    return displayName ? `${displayName} (${shortPeerId(peerId)})` : shortPeerId(peerId);
  }

  function peerPairLabel(peerId, remotePeerId, labels) {
    return `${peerLabel(peerId, labels)} -> ${peerLabel(remotePeerId, labels)}`;
  }

  function buildPeerLabelsFromMembers(members) {
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

  function candidatePair(sample) {
    const localType = metric(sample, "local_candidate_type");
    const remoteType = metric(sample, "remote_candidate_type");
    const protocol = metric(sample, "candidate_pair_protocol");
    if (!localType && !remoteType && !protocol) {
      return "-";
    }
    return `${localType || "?"}/${remoteType || "?"} ${protocol || ""}`.trim();
  }

  function renderPeerPairs(peers, labels) {
    const list = document.getElementById("peerPairList");
    if (!list) {
      return;
    }
    list.innerHTML = "";
    for (const peer of peers || []) {
      const item = document.createElement("li");
      item.textContent = `[${lastSampleLabel(peer)}] ${peerPairLabel(peer.peer_id, peer.remote_peer_id, labels)}`;
      list.appendChild(item);
    }
  }

  function renderLatestStats(samples, labels) {
    const panel = document.getElementById("latestStatsPanel");
    if (!panel) {
      return;
    }
    panel.innerHTML = "";
    const latest = (samples || [])[0];
    if (!latest) {
      return;
    }

    const missing = missingFields(latest);
    const rows = [
      ["Peer", peerPairLabel(latest.peer_id, latest.remote_peer_id, labels)],
      ["Connection", formatMetric(metric(latest, "connection_state"), "")],
      ["ICE", formatMetric(metric(latest, "ice_connection_state"), "")],
      ["Candidate Pair", candidatePair(latest)],
      ["RTT", formatMetric(metric(latest, "rtt_ms"), " ms")],
      ["Loss", formatMetric(metric(latest, "packets_lost"), "")],
      ["Loss Rate", formatMetric(metric(latest, "packet_loss_rate"), "%")],
      [
        "Packets",
        `${formatMetric(metric(latest, "packets_sent"), "")} sent / ${formatMetric(metric(latest, "packets_received"), "")} recv / ${formatMetric(metric(latest, "packets_lost"), "")} lost`
      ],
      ["Jitter", formatMetric(metric(latest, "jitter_ms"), " ms")],
      ["Bitrate", formatMetric(metric(latest, "bitrate_kbps"), " kbps")],
      ["Available Out", formatMetric(metric(latest, "available_outgoing_bitrate_kbps"), " kbps")],
      [
        "Bytes",
        `${formatMetric(metric(latest, "bytes_sent"), "")} sent / ${formatMetric(metric(latest, "bytes_received"), "")} recv`
      ],
      ["FPS", formatMetric(metric(latest, "fps"), "")],
      [
        "Resolution",
        `${formatMetric(metric(latest, "frame_width"), "")} x ${formatMetric(metric(latest, "frame_height"), "")}`
      ],
      [
        "Frames",
        `${formatMetric(metric(latest, "frames_sent"), "")} sent / ${formatMetric(metric(latest, "frames_received"), "")} recv / ${formatMetric(metric(latest, "frames_decoded"), "")} decoded`
      ],
      ["Dropped", formatMetric(metric(latest, "frames_dropped"), "")],
      ["Codec", formatMetric(metric(latest, "codec"), "")],
      ["NACK Enabled", formatMetric(metric(latest, "nack_enabled"), "")],
      ["NACK Mode", formatMetric(metric(latest, "nack_mode"), "")],
      ["Recovery", `NACK ${formatMetric(metric(latest, "nack_count"), "")} / PLI ${formatMetric(metric(latest, "pli_count"), "")} / FIR ${formatMetric(metric(latest, "fir_count"), "")}`],
      ["Missing Fields", missing.length ? missing.join(", ") : "none"]
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
      item.textContent = [
        peerPairLabel(peer.peer_id, peer.remote_peer_id, labels),
        formatMetric(metric(sample, "connection_state"), "connected"),
        `RTT ${formatMetric(metric(sample, "rtt_ms"), " ms")}`,
        `Loss ${formatMetric(metric(sample, "packets_lost"), "")}`,
        `Bitrate ${formatMetric(metric(sample, "bitrate_kbps"), " kbps")}`
      ].join(" | ");
      list.appendChild(item);
    }
    state.textContent = peers.length >= 6 ? "mesh_online" : "mesh_partial";
  }

  function renderSnapshot(snapshot) {
    const labels = buildPeerLabelsFromMembers(snapshot.members || []);
    const peers = snapshot.peers || [];
    renderPeerPairs(peers, labels);
    renderLatestStats(snapshot.latest || [], labels);
    renderHistoryRows(snapshot.history || [], labels);
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

    window.__RTCTrainingDashboardTestHooks = {
      checkService,
      loadLiveStats,
      clearLiveStats,
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
