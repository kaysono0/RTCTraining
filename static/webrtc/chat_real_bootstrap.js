function bootstrapRTCTraining() {
  const shared = window.RTCTrainingShared;
  const session = window.RTCTrainingSession;

  document.getElementById("startMediaButton").addEventListener("click", () => {
    session.startMedia().catch((error) => {
      shared.setConnectionState("failed");
      shared.addTimelineEvent("media_error", { category: "error", summary: error.message });
    });
  });

  document.getElementById("joinRoomButton").addEventListener("click", () => {
    const roomId = document.getElementById("roomIdInput").value;
    const displayName = document.getElementById("displayNameInput").value;
    session.joinRoom(roomId, displayName).catch((error) => {
      shared.setConnectionState("failed");
      shared.addTimelineEvent("join_room_failed", { category: "error", summary: error.message });
    });
  });

  document.getElementById("leaveRoomButton").addEventListener("click", () => {
    session.leaveRoom().catch((error) => {
      shared.addTimelineEvent("leave_room_failed", { category: "error", summary: error.message });
    });
  });

  window.__RTCTrainingTestHooks = {
    getState() {
      return shared.state.connectionState;
    },
    getClientId() {
      return shared.state.clientId;
    },
    getRoomId() {
      return shared.state.roomId;
    },
    getPeers() {
      return shared.state.peers;
    },
    getTimeline() {
      return shared.state.timeline;
    },
    getConnectedPeerCount() {
      return Object.values(shared.state.peerConnections).filter((peerConnection) => {
        return ["connected", "completed"].includes(peerConnection.iceConnectionState) ||
          peerConnection.connectionState === "connected";
      }).length;
    },
    getRemoteVideoCount() {
      return document.querySelectorAll("#remoteVideos video").length;
    },
    getStatsUploadedCount() {
      return shared.state.statsUploadedCount;
    },
    getLatestStats() {
      return shared.state.latestStats;
    },
    startMedia() {
      return session.startMedia();
    },
    joinRoom(roomId, displayName) {
      return session.joinRoom(roomId, displayName);
    },
    leaveRoom() {
      return session.leaveRoom();
    }
  };
}

window.addEventListener("DOMContentLoaded", bootstrapRTCTraining);
