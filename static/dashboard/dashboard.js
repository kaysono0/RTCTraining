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

  function bootstrapDashboard() {
    if (window.__RTCTrainingDashboardTestHooks) {
      return;
    }

    const input = document.getElementById("webrtcOriginInput");
    const origin = queryParam("webrtc_origin");
    if (origin && input) {
      input.value = origin;
    }

    document.getElementById("checkServiceButton").addEventListener("click", () => {
      checkService().catch((error) => {
        setText("serviceState", "service_error");
        setText("roomSummary", error.message);
      });
    });

    window.__RTCTrainingDashboardTestHooks = {
      checkService,
      getServiceState() {
        return document.getElementById("serviceState").textContent;
      },
      getRoomSummary() {
        return document.getElementById("roomSummary").textContent;
      }
    };

    checkService().catch((error) => {
      setText("serviceState", "service_error");
      setText("roomSummary", error.message);
    });
  }

  window.addEventListener("DOMContentLoaded", bootstrapDashboard);
})();
