(function () {
  const shared = window.RTCTrainingShared;

  function renderTestSession() {
    const label = document.getElementById("testSessionState");
    if (label) {
      label.textContent = `test_session_${shared.state.testSessionStatus}`;
    }
  }

  function readUiOptions(overrides) {
    const presetSelect = document.getElementById("testPresetSelect");
    const weakNetworkInput = document.getElementById("testWeakNetworkInput");
    const noteInput = document.getElementById("testSessionNoteInput");
    const options = overrides || {};
    return {
      preset: options.preset || (presetSelect ? presetSelect.value : "manual"),
      metadata: options.metadata || {
        note: noteInput ? noteInput.value : ""
      },
      weak_network: options.weak_network || {
        profile: weakNetworkInput ? weakNetworkInput.value : ""
      }
    };
  }

  async function postJson(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const payload = await response.json();
    if (!payload.ok) {
      throw new Error(payload.error.message);
    }
    return payload.data.session;
  }

  async function startTestSession(options) {
    const uiOptions = readUiOptions(options);
    const session = await postJson("/stats/test/start", {
      room_id: shared.state.roomId,
      peer_id: shared.state.clientId,
      preset: uiOptions.preset,
      metadata: uiOptions.metadata,
      weak_network: uiOptions.weak_network
    });
    shared.state.testSessionId = session.test_session_id;
    shared.state.testSessionStatus = session.status;
    shared.state.testSession = session;
    renderTestSession();
    shared.addTimelineEvent("test_session_started", {
      category: "test",
      summary: session.test_session_id
    });
    return session;
  }

  async function finishTestSession() {
    if (!shared.state.testSessionId) {
      return null;
    }
    const session = await postJson("/stats/test/finish", {
      test_session_id: shared.state.testSessionId
    });
    shared.state.testSessionStatus = session.status;
    shared.state.testSession = session;
    renderTestSession();
    shared.addTimelineEvent("test_session_finished", {
      category: "test",
      summary: `${session.test_session_id} samples=${session.sample_count}`
    });
    return session;
  }

  async function cancelTestSession() {
    if (!shared.state.testSessionId) {
      return null;
    }
    const session = await postJson("/stats/test/cancel", {
      test_session_id: shared.state.testSessionId
    });
    shared.state.testSessionStatus = session.status;
    shared.state.testSession = session;
    shared.state.testSessionId = null;
    renderTestSession();
    shared.addTimelineEvent("test_session_canceled", {
      category: "test",
      summary: session.test_session_id
    });
    return session;
  }

  window.RTCTrainingTestSession = {
    renderTestSession,
    startTestSession,
    finishTestSession,
    cancelTestSession
  };
})();
