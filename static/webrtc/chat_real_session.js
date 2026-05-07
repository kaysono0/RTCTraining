(function () {
  const shared = window.RTCTrainingShared;
  const POLL_INTERVAL_MS = 250;

  function addLocalTracks(peerConnection) {
    if (!shared.state.localStream) {
      return;
    }
    for (const track of shared.state.localStream.getTracks()) {
      peerConnection.addTrack(track, shared.state.localStream);
    }
  }

  function updateConnectedState() {
    const connections = Object.values(shared.state.peerConnections);
    if (connections.length === 0) {
      return;
    }
    const connected = connections.filter((peerConnection) => {
      return ["connected", "completed"].includes(peerConnection.iceConnectionState) ||
        peerConnection.connectionState === "connected";
    });
    if (connected.length > 0) {
      shared.setConnectionState("connected");
      if (window.RTCTrainingStats) {
        window.RTCTrainingStats.start();
      }
    }
  }

  function remotePeerLabel(remotePeerId) {
    const peer = shared.state.peers[remotePeerId];
    if (peer && peer.display_name) {
      return peer.display_name;
    }
    return remotePeerId;
  }

  function shortPeerId(peerId) {
    if (!peerId) {
      return "";
    }
    return peerId.length > 12 ? `${peerId.slice(0, 12)}...` : peerId;
  }

  function setRemoteGridClass() {
    const container = document.getElementById("remoteVideos");
    if (!container) {
      return;
    }
    const count = container.querySelectorAll(".remote-tile").length;
    let gridClass = "grid-0";
    if (count === 1) {
      gridClass = "grid-1";
    } else if (count === 2) {
      gridClass = "grid-2";
    } else if (count <= 4) {
      gridClass = "grid-4";
    } else {
      gridClass = "grid-9";
    }
    container.className = `remote-video-grid ${gridClass}`;
  }

  function formatNumber(value, digits) {
    if (typeof value !== "number" || !Number.isFinite(value)) {
      return "--";
    }
    return value.toFixed(digits);
  }

  function renderRemotePeerStats(remotePeerId) {
    const tile = document.getElementById(`remoteTile-${remotePeerId}`);
    if (!tile) {
      return;
    }
    const sample = shared.state.latestStats[remotePeerId];
    const metrics = sample && sample.metrics ? sample.metrics : {};
    const resolution = metrics.frame_width && metrics.frame_height
      ? `${metrics.frame_width}x${metrics.frame_height}`
      : "--";
    const stats = tile.querySelector(".remote-stats");
    if (!stats) {
      return;
    }
    stats.innerHTML = "";
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
      stats.appendChild(item);
    }
  }

  function ensureRemoteTile(remotePeerId) {
    const container = document.getElementById("remoteVideos");
    if (!container) {
      return null;
    }
    let tile = document.getElementById(`remoteTile-${remotePeerId}`);
    if (tile) {
      const name = tile.querySelector(".remote-name");
      const peerId = tile.querySelector(".remote-peer-id");
      if (name) {
        name.textContent = remotePeerLabel(remotePeerId);
      }
      if (peerId) {
        peerId.textContent = shortPeerId(remotePeerId);
      }
      renderRemotePeerStats(remotePeerId);
      return tile;
    }

    tile = document.createElement("div");
    tile.id = `remoteTile-${remotePeerId}`;
    tile.className = "remote-tile";
    tile.dataset.peerId = remotePeerId;

    const video = document.createElement("video");
    video.id = `remoteVideo-${remotePeerId}`;
    video.autoplay = true;
    video.playsInline = true;
    tile.appendChild(video);

    const identity = document.createElement("div");
    identity.className = "remote-identity";
    const name = document.createElement("strong");
    name.className = "remote-name";
    name.textContent = remotePeerLabel(remotePeerId);
    const peerId = document.createElement("span");
    peerId.className = "remote-peer-id";
    peerId.textContent = shortPeerId(remotePeerId);
    identity.appendChild(name);
    identity.appendChild(peerId);
    tile.appendChild(identity);

    const stats = document.createElement("div");
    stats.className = "remote-stats";
    tile.appendChild(stats);

    container.appendChild(tile);
    setRemoteGridClass();
    renderRemotePeerStats(remotePeerId);
    return tile;
  }

  function refreshRemotePeerTile(remotePeerId) {
    ensureRemoteTile(remotePeerId);
  }

  function ensureRemoteVideo(remotePeerId, stream) {
    shared.state.remoteStreams[remotePeerId] = stream;
    const tile = ensureRemoteTile(remotePeerId);
    if (!tile) {
      return;
    }
    const video = tile.querySelector("video");
    if (video.srcObject !== stream) {
      video.srcObject = stream;
    }
  }

  function summarizeSessionDescription(description) {
    const sdp = description && description.sdp ? description.sdp : "";
    const mediaLines = sdp.split("\n").filter((line) => line.startsWith("m=")).length;
    const hasIceUfrag = sdp.includes("a=ice-ufrag:");
    return {
      payload_preview: `${description.type} sdp_len=${sdp.length} m_lines=${mediaLines} ice_ufrag=${hasIceUfrag}`,
      payload_full: JSON.stringify(description, null, 2)
    };
  }

  function summarizeCandidate(candidate) {
    const raw = candidate && candidate.candidate ? candidate.candidate : "";
    const parts = raw.split(" ");
    return {
      payload_preview: `candidate ${parts[7] || ""} ${parts[4] || ""}:${parts[5] || ""}`.trim(),
      payload_full: JSON.stringify(candidate, null, 2)
    };
  }

  async function sendSignal(remotePeerId, type, payload) {
    const response = await fetch("/signal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        room_id: shared.state.roomId,
        from_peer_id: shared.state.clientId,
        to_peer_id: remotePeerId,
        type,
        payload
      })
    });
    const result = await response.json();
    if (!result.ok) {
      throw new Error(result.error.message);
    }
    return result.data;
  }

  function ensurePeerConnection(remotePeerId) {
    if (shared.state.peerConnections[remotePeerId]) {
      return shared.state.peerConnections[remotePeerId];
    }

    const peerConnection = new RTCPeerConnection({ iceServers: [] });
    shared.state.peerConnections[remotePeerId] = peerConnection;
    shared.state.pendingCandidates[remotePeerId] = [];
    addLocalTracks(peerConnection);

    peerConnection.addEventListener("icecandidate", (event) => {
      if (!event.candidate) {
        return;
      }
      sendSignal(remotePeerId, "candidate", event.candidate.toJSON())
        .then(() => {
          const candidateSummary = summarizeCandidate(event.candidate.toJSON());
          shared.addTimelineEvent("sent_candidate", {
            category: "signaling",
            direction: "outbound",
            remote_peer_id: remotePeerId,
            from_peer_id: shared.state.clientId,
            to_peer_id: remotePeerId,
            summary: "ICE candidate",
            payload_preview: candidateSummary.payload_preview,
            payload_full: candidateSummary.payload_full
          });
        })
        .catch((error) => {
          shared.addTimelineEvent("signal_error", {
            category: "error",
            remote_peer_id: remotePeerId,
            summary: error.message
          });
        });
    });

    peerConnection.addEventListener("track", (event) => {
      ensureRemoteVideo(remotePeerId, event.streams[0]);
      shared.addTimelineEvent("remote_track", {
        category: "media",
        direction: "inbound",
        remote_peer_id: remotePeerId,
        from_peer_id: remotePeerId,
        to_peer_id: shared.state.clientId,
        summary: `${event.track.kind} track ${event.track.readyState}`,
        payload_preview: `track kind=${event.track.kind} stream=${event.streams[0] ? event.streams[0].id : "--"}`,
        payload_full: JSON.stringify({
          track_id: event.track.id,
          kind: event.track.kind,
          ready_state: event.track.readyState,
          stream_ids: event.streams.map((stream) => stream.id)
        }, null, 2)
      });
    });

    peerConnection.addEventListener("connectionstatechange", updateConnectedState);
    peerConnection.addEventListener("iceconnectionstatechange", updateConnectedState);

    return peerConnection;
  }

  async function flushPendingCandidates(remotePeerId) {
    const peerConnection = shared.state.peerConnections[remotePeerId];
    const candidates = shared.state.pendingCandidates[remotePeerId] || [];
    if (!peerConnection || !peerConnection.remoteDescription) {
      return;
    }
    shared.state.pendingCandidates[remotePeerId] = [];
    for (const candidate of candidates) {
      await peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
    }
  }

  async function createOffer(remotePeerId) {
    const peerConnection = ensurePeerConnection(remotePeerId);
    const offer = await peerConnection.createOffer();
    const localOffer = window.RTCTrainingNack
      ? window.RTCTrainingNack.prepareLocalDescription(offer)
      : offer;
    await peerConnection.setLocalDescription(localOffer);
    await sendSignal(remotePeerId, "offer", peerConnection.localDescription.toJSON());
    const offerSummary = summarizeSessionDescription(peerConnection.localDescription);
    shared.addTimelineEvent("sent_offer", {
      category: "signaling",
      direction: "outbound",
      remote_peer_id: remotePeerId,
      from_peer_id: shared.state.clientId,
      to_peer_id: remotePeerId,
      summary: "WebRTC offer",
      payload_preview: offerSummary.payload_preview,
      payload_full: offerSummary.payload_full
    });
  }

  async function handleOffer(message) {
    const remotePeerId = message.from_peer_id;
    const peerConnection = ensurePeerConnection(remotePeerId);
    await peerConnection.setRemoteDescription(new RTCSessionDescription(message.payload));
    await flushPendingCandidates(remotePeerId);
    shared.addTimelineEvent("received_offer", {
      category: "signaling",
      direction: "inbound",
      remote_peer_id: remotePeerId,
      from_peer_id: remotePeerId,
      to_peer_id: shared.state.clientId,
      summary: "WebRTC offer",
      payload_preview: summarizeSessionDescription(message.payload).payload_preview,
      payload_full: summarizeSessionDescription(message.payload).payload_full
    });

    const answer = await peerConnection.createAnswer();
    const localAnswer = window.RTCTrainingNack
      ? window.RTCTrainingNack.prepareLocalDescription(answer)
      : answer;
    await peerConnection.setLocalDescription(localAnswer);
    await sendSignal(remotePeerId, "answer", peerConnection.localDescription.toJSON());
    const answerSummary = summarizeSessionDescription(peerConnection.localDescription);
    shared.addTimelineEvent("sent_answer", {
      category: "signaling",
      direction: "outbound",
      remote_peer_id: remotePeerId,
      from_peer_id: shared.state.clientId,
      to_peer_id: remotePeerId,
      summary: "WebRTC answer",
      payload_preview: answerSummary.payload_preview,
      payload_full: answerSummary.payload_full
    });
  }

  async function handleAnswer(message) {
    const remotePeerId = message.from_peer_id;
    const peerConnection = ensurePeerConnection(remotePeerId);
    await peerConnection.setRemoteDescription(new RTCSessionDescription(message.payload));
    await flushPendingCandidates(remotePeerId);
    shared.addTimelineEvent("received_answer", {
      category: "signaling",
      direction: "inbound",
      remote_peer_id: remotePeerId,
      from_peer_id: remotePeerId,
      to_peer_id: shared.state.clientId,
      summary: "WebRTC answer",
      payload_preview: summarizeSessionDescription(message.payload).payload_preview,
      payload_full: summarizeSessionDescription(message.payload).payload_full
    });
  }

  async function handleCandidate(message) {
    const remotePeerId = message.from_peer_id;
    const peerConnection = ensurePeerConnection(remotePeerId);
    if (!peerConnection.remoteDescription) {
      shared.state.pendingCandidates[remotePeerId].push(message.payload);
      return;
    }
    await peerConnection.addIceCandidate(new RTCIceCandidate(message.payload));
    const candidateSummary = summarizeCandidate(message.payload);
    shared.addTimelineEvent("received_candidate", {
      category: "signaling",
      direction: "inbound",
      remote_peer_id: remotePeerId,
      from_peer_id: remotePeerId,
      to_peer_id: shared.state.clientId,
      summary: "ICE candidate",
      payload_preview: candidateSummary.payload_preview,
      payload_full: candidateSummary.payload_full
    });
  }

  function closePeer(remotePeerId) {
    const peerConnection = shared.state.peerConnections[remotePeerId];
    if (peerConnection) {
      peerConnection.close();
    }
    delete shared.state.peerConnections[remotePeerId];
    delete shared.state.peers[remotePeerId];
    delete shared.state.pendingCandidates[remotePeerId];
    delete shared.state.remoteStreams[remotePeerId];
    const tile = document.getElementById(`remoteTile-${remotePeerId}`);
    if (tile) {
      tile.remove();
      setRemoteGridClass();
    }
  }

  async function handlePendingMessage(message) {
    if (message.type === "peer_joined") {
      const peer = message.payload;
      shared.state.peers[peer.peer_id] = peer;
      refreshRemotePeerTile(peer.peer_id);
      shared.addTimelineEvent("peer_joined", {
        category: "room",
        remote_peer_id: peer.peer_id,
        summary: peer.display_name
      });
      return;
    }
    if (message.type === "peer_left") {
      closePeer(message.payload.peer_id);
      shared.addTimelineEvent("peer_left", {
        category: "room",
        remote_peer_id: message.payload.peer_id
      });
      return;
    }
    if (message.type === "offer") {
      await handleOffer(message);
      return;
    }
    if (message.type === "answer") {
      await handleAnswer(message);
      return;
    }
    if (message.type === "candidate") {
      await handleCandidate(message);
    }
  }

  async function pollPendingSignals() {
    if (!shared.state.roomId || shared.state.connectionState === "left") {
      return;
    }
    const params = new URLSearchParams({
      room_id: shared.state.roomId,
      client_id: shared.state.clientId
    });
    const response = await fetch(`/signal/pending?${params.toString()}`);
    const result = await response.json();
    if (!result.ok) {
      throw new Error(result.error.message);
    }
    for (const message of result.data.messages) {
      await handlePendingMessage(message);
    }
  }

  function startSignalPolling() {
    if (shared.state.pollingTimer) {
      return;
    }
    shared.state.pollingTimer = window.setInterval(() => {
      pollPendingSignals().catch((error) => {
        shared.addTimelineEvent("poll_signal_failed", {
          category: "error",
          summary: error.message
        });
      });
    }, POLL_INTERVAL_MS);
  }

  function stopSignalPolling() {
    if (!shared.state.pollingTimer) {
      return;
    }
    window.clearInterval(shared.state.pollingTimer);
    shared.state.pollingTimer = null;
  }

  async function startMedia() {
    shared.setConnectionState("media_requesting");
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
    shared.state.localStream = stream;
    const video = document.getElementById("localVideo");
    if (video) {
      video.srcObject = stream;
    }
    shared.setConnectionState("media_ready");
    shared.addTimelineEvent("local_media_ready", { category: "media" });
    return true;
  }

  async function joinRoom(roomId, displayName) {
    shared.state.roomId = roomId || "room1";
    shared.state.localDisplayName = displayName || "Learner";
    shared.setConnectionState("joining");
    const response = await fetch("/rooms/join", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        room_id: shared.state.roomId,
        client_id: shared.state.clientId,
        display_name: displayName || "Learner"
      })
    });
    const payload = await response.json();
    if (!payload.ok) {
      shared.setConnectionState("failed");
      throw new Error(payload.error.message);
    }
    for (const peer of payload.data.existing_peers) {
      shared.state.peers[peer.peer_id] = peer;
      refreshRemotePeerTile(peer.peer_id);
    }
    shared.setConnectionState("joined");
    shared.addTimelineEvent("joined_room", { category: "room", summary: shared.state.roomId });
    startSignalPolling();
    for (const peer of payload.data.existing_peers) {
      await createOffer(peer.peer_id);
    }
    return payload.data;
  }

  async function leaveRoom() {
    stopSignalPolling();
    if (window.RTCTrainingStats) {
      window.RTCTrainingStats.stop();
    }
    const response = await fetch("/rooms/leave", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        room_id: shared.state.roomId,
        client_id: shared.state.clientId
      })
    });
    const payload = await response.json();
    if (shared.state.localStream) {
      for (const track of shared.state.localStream.getTracks()) {
        track.stop();
      }
      shared.state.localStream = null;
    }
    for (const remotePeerId of Object.keys(shared.state.peerConnections)) {
      closePeer(remotePeerId);
    }
    shared.state.peers = {};
    shared.setConnectionState("left");
    shared.addTimelineEvent("left_room", { category: "room" });
    return payload.data;
  }

  window.RTCTrainingSession = {
    startMedia,
    joinRoom,
    leaveRoom,
    renderRemotePeerStats
  };
})();
