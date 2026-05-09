(function () {
  function queryParam(name) {
    return new URLSearchParams(window.location.search).get(name);
  }

  function currentOrigin() {
    return queryParam("webrtc_origin") || "https://localhost:8080";
  }

  function buildUrl(path, params) {
    const query = new URLSearchParams();
    query.set("origin", currentOrigin());
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        query.set(key, value);
      }
    });
    return `${path}?${query.toString()}`;
  }

  async function getJson(path, params) {
    const response = await fetch(buildUrl(path, params));
    return response.json();
  }

  async function postJson(path, params, body) {
    const response = await fetch(buildUrl(path, params), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    });
    return response.json();
  }

  window.RTCTrainingDashboardApiClient = {
    currentOrigin,
    buildUrl,
    getJson,
    postJson
  };
})();
