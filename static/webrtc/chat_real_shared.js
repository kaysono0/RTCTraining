(function () {
  const state = {
    clientId: `peer-${crypto.randomUUID()}`,
    roomId: "room1",
    connectionState: "idle",
    peers: {},
    peerConnections: {},
    remoteStreams: {},
    pendingCandidates: {},
    statsTimer: null,
    statsUploadInFlight: false,
    statsPrevious: {},
    statsUploadedCount: 0,
    latestStats: {},
    timeline: [],
    localStream: null,
    pollingTimer: null,
    localDisplayName: "Learner"
  };

  function setConnectionState(nextState) {
    state.connectionState = nextState;
    const label = document.getElementById("connectionState");
    if (label) {
      label.textContent = nextState;
    }
  }

  function formatLocalTime(epochSeconds) {
    const date = new Date(epochSeconds * 1000);
    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      fractionalSecondDigits: 3
    });
  }

  function appendField(parent, label, value) {
    if (value === null || value === undefined || value === "") {
      return;
    }
    const field = document.createElement("span");
    field.className = "timeline-field";
    field.textContent = `${label}: ${value}`;
    parent.appendChild(field);
  }

  function shortPeerId(peerId) {
    if (!peerId) {
      return "";
    }
    return peerId.length > 12 ? `${peerId.slice(0, 12)}...` : peerId;
  }

  function formatPeerLabel(peerId) {
    if (!peerId) {
      return "";
    }
    if (peerId === state.clientId) {
      return `${state.localDisplayName || "Local"} (${shortPeerId(peerId)})`;
    }
    const peer = state.peers[peerId];
    const displayName = peer && peer.display_name ? peer.display_name : "Unknown";
    return `${displayName} (${shortPeerId(peerId)})`;
  }

  function renderTimelineEvent(event) {
    const list = document.getElementById("timeline");
    if (!list) {
      return;
    }
    const item = document.createElement("li");
    item.className = `timeline-item ${event.category}`;

    const header = document.createElement("div");
    header.className = "timeline-header";
    header.textContent = `[${formatLocalTime(event.timestamp)}] ${event.type}`;
    item.appendChild(header);

    const meta = document.createElement("div");
    meta.className = "timeline-meta";
    appendField(meta, "direction", event.direction);
    appendField(meta, "from", formatPeerLabel(event.from_peer_id || event.peer_id));
    appendField(meta, "to", formatPeerLabel(event.to_peer_id));
    appendField(meta, "remote", formatPeerLabel(event.remote_peer_id));
    appendField(meta, "summary", event.summary);
    item.appendChild(meta);

    const preview = event.details && event.details.payload_preview;
    const full = event.details && event.details.payload_full;
    if (preview || full) {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = preview || "payload";
      details.appendChild(summary);
      if (full) {
        const code = document.createElement("pre");
        code.textContent = full;
        details.appendChild(code);
      }
      item.appendChild(details);
    }

    list.appendChild(item);
  }

  function addTimelineEvent(type, details) {
    const detailData = details || {};
    const event = {
      event_id: `event-${state.timeline.length + 1}`,
      timestamp: Date.now() / 1000,
      room_id: state.roomId,
      peer_id: state.clientId,
      from_peer_id: detailData.from_peer_id || state.clientId,
      to_peer_id: detailData.to_peer_id || null,
      remote_peer_id: detailData.remote_peer_id || null,
      category: detailData.category || "room",
      type,
      direction: detailData.direction || "local",
      summary: detailData.summary || type,
      details: detailData
    };
    state.timeline.push(event);
    renderTimelineEvent(event);
    return event;
  }

  window.RTCTrainingShared = {
    state,
    setConnectionState,
    addTimelineEvent
  };
})();
