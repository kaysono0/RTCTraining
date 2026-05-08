function bootstrapRTCTraining() {
  const shared = window.RTCTrainingShared;
  const session = window.RTCTrainingSession;
  const nack = window.RTCTrainingNack;
  const bitrate = window.RTCTrainingBitrate;
  const testSession = window.RTCTrainingTestSession;

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

  if (bitrate) {
    bitrate.renderBitrateMode();
    bitrate.renderAbrMode();
    addClickListener("applyBitrateButton", () => {
      const input = document.getElementById("senderBitrateInput");
      bitrate.setSenderBitrateKbps(input ? input.value : "").then((mode) => {
        shared.addTimelineEvent("bitrate_mode_changed", {
          category: "media",
          summary: mode
        });
      }).catch((error) => {
        shared.addTimelineEvent("bitrate_apply_failed", {
          category: "error",
          summary: error.message
        });
      });
    });
    const abrModeSelect = document.getElementById("abrModeSelect");
    if (abrModeSelect) {
      abrModeSelect.addEventListener("change", (event) => {
        bitrate.setAbrMode(event.target.value).then((mode) => {
          shared.addTimelineEvent("abr_mode_changed", {
            category: "media",
            summary: mode
          });
        }).catch((error) => {
          shared.addTimelineEvent("abr_apply_failed", {
            category: "error",
            summary: error.message
          });
        });
      });
    }
  }

  if (testSession) {
    testSession.renderTestSession();
    addClickListener("startTestSessionButton", () => {
      testSession.startTestSession().catch((error) => {
        shared.addTimelineEvent("test_session_start_failed", {
          category: "error",
          summary: error.message
        });
      });
    });
    addClickListener("finishTestSessionButton", () => {
      testSession.finishTestSession().catch((error) => {
        shared.addTimelineEvent("test_session_finish_failed", {
          category: "error",
          summary: error.message
        });
      });
    });
    addClickListener("cancelTestSessionButton", () => {
      testSession.cancelTestSession().catch((error) => {
        shared.addTimelineEvent("test_session_cancel_failed", {
          category: "error",
          summary: error.message
        });
      });
    });

    const presetSelect = document.getElementById("testPresetSelect");
    if (presetSelect && testSession.applyTestPreset) {
      presetSelect.addEventListener("change", (event) => {
        testSession.applyTestPreset(event.target.value).catch((error) => {
          shared.addTimelineEvent("test_preset_apply_failed", {
            category: "error",
            summary: error.message
          });
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
    setSenderBitrateKbps(value) {
      return bitrate.setSenderBitrateKbps(value);
    },
    getBitrateMode() {
      return shared.state.bitrateMode;
    },
    getSenderMaxBitrateBps() {
      return shared.state.senderMaxBitrateBps;
    },
    setAbrMode(mode) {
      return bitrate.setAbrMode(mode);
    },
    runAbrDecision(metrics) {
      return bitrate.runAbrDecision(metrics);
    },
    getAbrMode() {
      return shared.state.abrMode;
    },
    getAbrTargetBitrateBps() {
      return shared.state.abrTargetBitrateBps;
    },
    getAbrLastDecision() {
      return shared.state.abrLastDecision;
    },
    startTestSession(options) {
      return testSession.startTestSession(options);
    },
    finishTestSession() {
      return testSession.finishTestSession();
    },
    cancelTestSession() {
      return testSession.cancelTestSession();
    },
    getTestSessionId() {
      return shared.state.testSessionId;
    },
    getTestSessionStatus() {
      return shared.state.testSessionStatus;
    },
    applyTestPreset(presetName) {
      return testSession.applyTestPreset(presetName);
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
