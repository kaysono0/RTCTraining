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
    pollingTimer: null
  };

  function setConnectionState(nextState) {
    state.connectionState = nextState;
    const label = document.getElementById("connectionState");
    if (label) {
      label.textContent = nextState;
    }
  }

  function addTimelineEvent(type, details) {
    const event = {
      event_id: `event-${state.timeline.length + 1}`,
      timestamp: Date.now() / 1000,
      room_id: state.roomId,
      peer_id: state.clientId,
      remote_peer_id: details && details.remote_peer_id ? details.remote_peer_id : null,
      category: details && details.category ? details.category : "room",
      type,
      direction: details && details.direction ? details.direction : "local",
      summary: details && details.summary ? details.summary : type,
      details: details || {}
    };
    state.timeline.push(event);

    const list = document.getElementById("timeline");
    if (list) {
      const item = document.createElement("li");
      item.textContent = `${event.type}: ${event.summary}`;
      list.appendChild(item);
    }
    return event;
  }

  window.RTCTrainingShared = {
    state,
    setConnectionState,
    addTimelineEvent
  };
})();
