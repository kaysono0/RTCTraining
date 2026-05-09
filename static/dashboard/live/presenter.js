(function () {
  function shortPeerId(peerId) {
    if (!peerId) {
      return "";
    }
    return peerId.length > 12 ? `${peerId.slice(0, 12)}...` : peerId;
  }

  function peerLabel(peerId, labels) {
    if (!peerId) {
      return "-";
    }
    const displayName = labels && labels[peerId];
    return displayName ? `${displayName} (${shortPeerId(peerId)})` : shortPeerId(peerId);
  }

  function peerPairLabel(peerId, remotePeerId, labels) {
    return `${peerLabel(peerId, labels)} -> ${peerLabel(remotePeerId, labels)}`;
  }

  function buildPeerLabelsFromMembers(members) {
    return (members || []).reduce((labels, member) => {
      labels[member.peer_id] = member.display_name;
      return labels;
    }, {});
  }

  function newestSample(samples) {
    return (samples || []).reduce((newest, sample) => {
      if (!newest) {
        return sample;
      }
      const newestOrder = newest.sample_index || newest.timestamp || 0;
      const sampleOrder = sample.sample_index || sample.timestamp || 0;
      return sampleOrder > newestOrder ? sample : newest;
    }, null);
  }

  window.RTCTrainingDashboardLivePresenter = {
    shortPeerId,
    peerLabel,
    peerPairLabel,
    buildPeerLabelsFromMembers,
    newestSample
  };
})();
