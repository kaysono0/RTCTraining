(function () {
  if (window.__RTCTrainingDashboardInlineBootstrap) {
    return;
  }

  function queryParam(name) {
    return new URLSearchParams(window.location.search).get(name);
  }

  function setText(id, text) {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = text;
    }
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

  function metric(sample, name) {
    return (sample.metrics || {})[name];
  }

  function renderPeerPairs(peers) {
    const list = document.getElementById("peerPairList");
    if (!list) {
      return;
    }
    list.innerHTML = "";
    for (const peer of peers || []) {
      const item = document.createElement("li");
      item.textContent = `${peer.peer_id} -> ${peer.remote_peer_id}`;
      list.appendChild(item);
    }
  }

  function renderLatestStats(samples) {
    const panel = document.getElementById("latestStatsPanel");
    if (!panel) {
      return;
    }
    panel.innerHTML = "";
    const latest = (samples || [])[0];
    if (!latest) {
      return;
    }

    const rows = [
      ["Peer", `${latest.peer_id} -> ${latest.remote_peer_id}`],
      ["RTT", formatMetric(metric(latest, "rtt_ms"), " ms")],
      ["Loss", formatMetric(metric(latest, "packets_lost"), "")],
      ["Jitter", formatMetric(metric(latest, "jitter_ms"), " ms")],
      ["Bitrate", formatMetric(metric(latest, "bitrate_kbps"), " kbps")],
      ["FPS", formatMetric(metric(latest, "fps"), "")],
      [
        "Resolution",
        `${formatMetric(metric(latest, "frame_width"), "")} x ${formatMetric(metric(latest, "frame_height"), "")}`
      ],
      ["Codec", formatMetric(metric(latest, "codec"), "")]
    ];

    for (const [label, value] of rows) {
      const term = document.createElement("dt");
      const detail = document.createElement("dd");
      term.textContent = label;
      detail.textContent = value;
      panel.append(term, detail);
    }
  }

  function renderHistoryRows(samples) {
    const body = document.querySelector("#statsHistoryTable tbody");
    if (!body) {
      return;
    }
    body.innerHTML = "";
    for (const sample of (samples || []).slice(-20).reverse()) {
      const row = document.createElement("tr");
      const cells = [
        sample.timestamp,
        sample.peer_id,
        sample.remote_peer_id,
        formatMetric(metric(sample, "rtt_ms"), " ms"),
        formatMetric(metric(sample, "packets_lost"), ""),
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

  async function checkService() {
    const input = document.getElementById("webrtcOriginInput");
    const origin = input.value.trim();
    setText("serviceState", "service_checking");

    const response = await fetch(`/api/webrtc/members?origin=${encodeURIComponent(origin)}`);
    const payload = await response.json();
    if (!payload.ok) {
      setText("serviceState", payload.error.code);
      setText("roomSummary", "0 rooms");
      return payload;
    }

    setText("serviceState", "service_online");
    setText("roomSummary", roomCountLabel(payload.data.rooms));
    return payload;
  }

  async function loadLiveStats() {
    const origin = document.getElementById("webrtcOriginInput").value.trim();
    const roomId = document.getElementById("statsRoomInput").value.trim() || "room1";
    setText("statsState", "stats_checking");

    const peersResponse = await fetch(`/api/webrtc/stats/peers?origin=${encodeURIComponent(origin)}&room_id=${encodeURIComponent(roomId)}`);
    const peersPayload = await peersResponse.json();
    if (!peersPayload.ok) {
      setText("statsState", peersPayload.error.code);
      return peersPayload;
    }

    const peers = peersPayload.data.peers || [];
    renderPeerPairs(peers);
    if (peers.length === 0) {
      renderLatestStats([]);
      renderHistoryRows([]);
      setText("statsState", "service_online_but_no_stats");
      return peersPayload;
    }

    const latestResponse = await fetch(`/api/webrtc/stats?origin=${encodeURIComponent(origin)}&room_id=${encodeURIComponent(roomId)}`);
    const latestPayload = await latestResponse.json();
    if (!latestPayload.ok) {
      setText("statsState", latestPayload.error.code);
      return latestPayload;
    }

    const historyResponse = await fetch(`/api/webrtc/stats/history?origin=${encodeURIComponent(origin)}&room_id=${encodeURIComponent(roomId)}`);
    const historyPayload = await historyResponse.json();
    if (!historyPayload.ok) {
      setText("statsState", historyPayload.error.code);
      return historyPayload;
    }

    renderLatestStats(latestPayload.data.samples || []);
    renderHistoryRows(historyPayload.data.samples || []);
    setText("statsState", "stats_online");
    return {
      ok: true,
      data: {
        latest: latestPayload.data.samples || [],
        history: historyPayload.data.samples || [],
        peers
      }
    };
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

    document.getElementById("checkServiceButton").addEventListener("click", () => {
      checkService().catch((error) => {
        setText("serviceState", "service_error");
        setText("roomSummary", error.message);
      });
    });

    window.__RTCTrainingDashboardTestHooks = {
      checkService,
      loadLiveStats,
      getServiceState() {
        return document.getElementById("serviceState").textContent;
      },
      getStatsState() {
        return document.getElementById("statsState").textContent;
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

  window.addEventListener("DOMContentLoaded", bootstrapDashboard);
})();
