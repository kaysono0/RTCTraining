function bootstrapRTCTraining() {
  const shared = window.RTCTrainingShared;
  const session = window.RTCTrainingSession;
  const nack = window.RTCTrainingNack;

  function addClickListener(id, callback) {
    const element = document.getElementById(id);
    if (element) {
      element.addEventListener("click", callback);
    }
  }

  if (nack) {
    nack.renderNackMode();
    const nackModeSelect = document.getElementById("nackModeSelect");
    if (nackModeSelect) {
      nackModeSelect.addEventListener("change", (event) => {
        nack.setNackMode(event.target.value);
        shared.addTimelineEvent("nack_mode_changed", {
          category: "media",
          summary: shared.state.nackMode
        });
      });
    }
  }

  addClickListener("startMediaButton", () => {
    session.startMedia().catch((error) => {
      shared.setConnectionState("failed");
      shared.addTimelineEvent("media_error", session.describeMediaError(error));
    });
  });

  addClickListener("joinRoomButton", () => {
    const roomId = document.getElementById("roomIdInput").value;
    const displayName = document.getElementById("displayNameInput").value;
    session.joinRoom(roomId, displayName).catch((error) => {
      shared.setConnectionState("failed");
      if (["NotAllowedError", "NotFoundError", "NotReadableError", "NotSupportedError", "OverconstrainedError"].includes(error.name)) {
        shared.addTimelineEvent("media_error", session.describeMediaError(error));
        return;
      }
      shared.addTimelineEvent("join_room_failed", { category: "error", summary: error.message });
    });
  });

  addClickListener("leaveRoomButton", () => {
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
    getConnectedPeerIds() {
      return Object.entries(shared.state.peerConnections)
        .filter(([_remotePeerId, peerConnection]) => {
          return ["connected", "completed"].includes(peerConnection.iceConnectionState) ||
            peerConnection.connectionState === "connected";
        })
        .map(([remotePeerId]) => remotePeerId);
    },
    getRemoteVideoCount() {
      return document.querySelectorAll("#remoteVideos video").length;
    },
    getStatsUploadedCount() {
      return shared.state.statsUploadedCount;
    },
    getNackMode() {
      return shared.state.nackMode;
    },
    setNackMode(mode) {
      return nack.setNackMode(mode);
    },
    mungeNackSdp(sdp) {
      return nack.mungeSdp(sdp);
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
