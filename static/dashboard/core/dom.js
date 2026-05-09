(function () {
  function setText(id, text) {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = text;
    }
  }

  function getText(id) {
    const element = document.getElementById(id);
    return element ? element.textContent : "";
  }

  function addClickListener(id, callback) {
    const element = document.getElementById(id);
    if (element) {
      element.addEventListener("click", callback);
    }
  }

  window.RTCTrainingDashboardDom = {
    setText,
    getText,
    addClickListener
  };
})();
