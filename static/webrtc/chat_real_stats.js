(function () {
  const shared = window.RTCTrainingShared;
  const STATS_INTERVAL_MS = 1000;

  function numberOrNull(value) {
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  }

  function updateBitrate(remotePeerId, bytesTotal) {
    const now = performance.now();
    const previous = shared.state.statsPrevious[remotePeerId];
    shared.state.statsPrevious[remotePeerId] = { bytesTotal, timestamp: now };
    if (!previous || bytesTotal < previous.bytesTotal) {
      return null;
    }
    const seconds = (now - previous.timestamp) / 1000;
    if (seconds <= 0) {
      return null;
    }
    return ((bytesTotal - previous.bytesTotal) * 8) / seconds / 1000;
  }

  async function collectPeerStats(remotePeerId, peerConnection) {
    const reports = await peerConnection.getStats();
    const reportById = {};
    reports.forEach((report) => {
      reportById[report.id] = report;
    });
    const metrics = {
      connection_state: peerConnection.connectionState,
      ice_connection_state: peerConnection.iceConnectionState,
      rtt_ms: null,
      packets_sent: 0,
      packets_received: 0,
      packets_lost: 0,
      packet_loss_rate: null,
      jitter_ms: null,
      bitrate_kbps: null,
      available_outgoing_bitrate_kbps: null,
      fps: null,
      frame_width: null,
      frame_height: null,
      codec: null,
      local_candidate_type: null,
      remote_candidate_type: null,
      candidate_pair_protocol: null,
      bytes_sent: 0,
      bytes_received: 0,
      frames_sent: 0,
      frames_received: 0,
      frames_encoded: 0,
      frames_decoded: 0,
      frames_dropped: 0,
      key_frames_encoded: 0,
      key_frames_decoded: 0,
      retransmitted_packets_sent: 0,
      retransmitted_packets_received: 0,
      retransmitted_bytes_sent: 0,
      retransmitted_bytes_received: 0,
      total_encode_time_ms: null,
      total_decode_time_ms: null,
      jitter_buffer_delay_ms: null,
      jitter_buffer_emitted_count: 0,
      jitter_buffer_target_delay_ms: null,
      quality_limitation_reason: null,
      nack_enabled: shared.state.nackMode === "enabled",
      nack_mode: shared.state.nackMode,
      bitrate_mode: shared.state.bitrateMode,
      sender_max_bitrate_bps: shared.state.senderMaxBitrateBps,
      nack_count: 0,
      pli_count: 0,
      fir_count: 0
    };

    reports.forEach((report) => {
      if (report.type === "candidate-pair" && report.state === "succeeded") {
        const rttSeconds = numberOrNull(report.currentRoundTripTime);
        if (rttSeconds !== null) {
          metrics.rtt_ms = rttSeconds * 1000;
        }
        const availableOutgoingBitrate = numberOrNull(report.availableOutgoingBitrate);
        if (availableOutgoingBitrate !== null) {
          metrics.available_outgoing_bitrate_kbps = availableOutgoingBitrate / 1000;
        }
        const localCandidate = reportById[report.localCandidateId];
        const remoteCandidate = reportById[report.remoteCandidateId];
        if (localCandidate) {
          metrics.local_candidate_type = localCandidate.candidateType || metrics.local_candidate_type;
          metrics.candidate_pair_protocol = localCandidate.protocol || metrics.candidate_pair_protocol;
        }
        if (remoteCandidate) {
          metrics.remote_candidate_type = remoteCandidate.candidateType || metrics.remote_candidate_type;
        }
      }

      if (report.type === "codec" && !metrics.codec && report.mimeType) {
        metrics.codec = report.mimeType;
      }

      if (report.type === "outbound-rtp" && !report.isRemote) {
        metrics.packets_sent += report.packetsSent || 0;
        metrics.bytes_sent += report.bytesSent || 0;
        metrics.frame_width = numberOrNull(report.frameWidth) || metrics.frame_width;
        metrics.frame_height = numberOrNull(report.frameHeight) || metrics.frame_height;
        metrics.fps = numberOrNull(report.framesPerSecond) || metrics.fps;
        metrics.frames_sent += report.framesSent || 0;
        metrics.frames_encoded += report.framesEncoded || 0;
        metrics.key_frames_encoded += report.keyFramesEncoded || 0;
        metrics.retransmitted_packets_sent += report.retransmittedPacketsSent || 0;
        metrics.retransmitted_bytes_sent += report.retransmittedBytesSent || 0;
        const totalEncodeTimeSeconds = numberOrNull(report.totalEncodeTime);
        if (totalEncodeTimeSeconds !== null) {
          metrics.total_encode_time_ms = totalEncodeTimeSeconds * 1000;
        }
        metrics.quality_limitation_reason = report.qualityLimitationReason || metrics.quality_limitation_reason;
        metrics.nack_count += report.nackCount || 0;
        metrics.pli_count += report.pliCount || 0;
        metrics.fir_count += report.firCount || 0;
      }

      if (report.type === "inbound-rtp" && !report.isRemote) {
        metrics.packets_received += report.packetsReceived || 0;
        metrics.packets_lost += report.packetsLost || 0;
        metrics.bytes_received += report.bytesReceived || 0;
        const jitterSeconds = numberOrNull(report.jitter);
        if (jitterSeconds !== null) {
          metrics.jitter_ms = jitterSeconds * 1000;
        }
        metrics.frame_width = numberOrNull(report.frameWidth) || metrics.frame_width;
        metrics.frame_height = numberOrNull(report.frameHeight) || metrics.frame_height;
        metrics.fps = numberOrNull(report.framesPerSecond) || metrics.fps;
        metrics.frames_received += report.framesReceived || 0;
        metrics.frames_decoded += report.framesDecoded || 0;
        metrics.frames_dropped += report.framesDropped || 0;
        metrics.key_frames_decoded += report.keyFramesDecoded || 0;
        metrics.retransmitted_packets_received += report.retransmittedPacketsReceived || 0;
        metrics.retransmitted_bytes_received += report.retransmittedBytesReceived || 0;
        const totalDecodeTimeSeconds = numberOrNull(report.totalDecodeTime);
        if (totalDecodeTimeSeconds !== null) {
          metrics.total_decode_time_ms = totalDecodeTimeSeconds * 1000;
        }
        const jitterBufferDelaySeconds = numberOrNull(report.jitterBufferDelay);
        if (jitterBufferDelaySeconds !== null) {
          metrics.jitter_buffer_delay_ms = jitterBufferDelaySeconds * 1000;
        }
        metrics.jitter_buffer_emitted_count += report.jitterBufferEmittedCount || 0;
        const jitterBufferTargetDelaySeconds = numberOrNull(report.jitterBufferTargetDelay);
        if (jitterBufferTargetDelaySeconds !== null) {
          metrics.jitter_buffer_target_delay_ms = jitterBufferTargetDelaySeconds * 1000;
        }
        metrics.nack_count += report.nackCount || 0;
        metrics.pli_count += report.pliCount || 0;
        metrics.fir_count += report.firCount || 0;
      }
    });

    const packetsExpected = metrics.packets_received + metrics.packets_lost;
    if (packetsExpected > 0) {
      metrics.packet_loss_rate = (metrics.packets_lost / packetsExpected) * 100;
    }

    metrics.bitrate_kbps = updateBitrate(
      remotePeerId,
      metrics.bytes_sent + metrics.bytes_received
    );

    return {
      room_id: shared.state.roomId,
      peer_id: shared.state.clientId,
      remote_peer_id: remotePeerId,
      test_session_id: null,
      timestamp: Date.now() / 1000,
      metrics
    };
  }

  async function uploadSample(sample) {
    const response = await fetch("/stats", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sample)
    });
    const payload = await response.json();
    if (!payload.ok) {
      throw new Error(payload.error.message);
    }
    shared.state.latestStats[sample.remote_peer_id] = payload.data.sample;
    shared.state.statsUploadedCount += 1;
    if (window.RTCTrainingSession && window.RTCTrainingSession.renderRemotePeerStats) {
      window.RTCTrainingSession.renderRemotePeerStats(sample.remote_peer_id);
    }
    return payload.data.sample;
  }

  async function uploadAllPeerStats() {
    if (shared.state.statsUploadInFlight) {
      return;
    }
    shared.state.statsUploadInFlight = true;
    try {
      const entries = Object.entries(shared.state.peerConnections);
      for (const [remotePeerId, peerConnection] of entries) {
        if (peerConnection.connectionState === "closed") {
          continue;
        }
        const sample = await collectPeerStats(remotePeerId, peerConnection);
        await uploadSample(sample);
      }
    } finally {
      shared.state.statsUploadInFlight = false;
    }
  }

  function start() {
    if (shared.state.statsTimer) {
      return;
    }
    uploadAllPeerStats().catch((error) => {
      shared.addTimelineEvent("stats_upload_failed", {
        category: "error",
        summary: error.message
      });
    });
    shared.state.statsTimer = window.setInterval(() => {
      uploadAllPeerStats().catch((error) => {
        shared.addTimelineEvent("stats_upload_failed", {
          category: "error",
          summary: error.message
        });
      });
    }, STATS_INTERVAL_MS);
  }

  function stop() {
    if (!shared.state.statsTimer) {
      return;
    }
    window.clearInterval(shared.state.statsTimer);
    shared.state.statsTimer = null;
    shared.state.statsUploadInFlight = false;
    shared.state.statsPrevious = {};
  }

  window.RTCTrainingStats = {
    start,
    stop,
    uploadAllPeerStats,
    collectPeerStats
  };
})();
