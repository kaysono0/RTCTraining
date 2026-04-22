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

  function ensureRemoteVideo(remotePeerId, stream) {
    shared.state.remoteStreams[remotePeerId] = stream;
    const container = document.getElementById("remoteVideos");
    if (!container) {
      return;
    }
    let video = document.getElementById(`remoteVideo-${remotePeerId}`);
    if (!video) {
      video = document.createElement("video");
      video.id = `remoteVideo-${remotePeerId}`;
      video.autoplay = true;
      video.playsInline = true;
      container.appendChild(video);
    }
    if (video.srcObject !== stream) {
      video.srcObject = stream;
    }
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
          shared.addTimelineEvent("sent_candidate", {
            category: "signaling",
            direction: "outbound",
            remote_peer_id: remotePeerId
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
        remote_peer_id: remotePeerId
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
    await peerConnection.setLocalDescription(offer);
    await sendSignal(remotePeerId, "offer", peerConnection.localDescription.toJSON());
    shared.addTimelineEvent("sent_offer", {
      category: "signaling",
      direction: "outbound",
      remote_peer_id: remotePeerId
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
      remote_peer_id: remotePeerId
    });

    const answer = await peerConnection.createAnswer();
    await peerConnection.setLocalDescription(answer);
    await sendSignal(remotePeerId, "answer", peerConnection.localDescription.toJSON());
    shared.addTimelineEvent("sent_answer", {
      category: "signaling",
      direction: "outbound",
      remote_peer_id: remotePeerId
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
      remote_peer_id: remotePeerId
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
    shared.addTimelineEvent("received_candidate", {
      category: "signaling",
      direction: "inbound",
      remote_peer_id: remotePeerId
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
    const video = document.getElementById(`remoteVideo-${remotePeerId}`);
    if (video) {
      video.remove();
    }
  }

  async function handlePendingMessage(message) {
    if (message.type === "peer_joined") {
      const peer = message.payload;
      shared.state.peers[peer.peer_id] = peer;
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
    leaveRoom
  };
})();
