# CSV Schema

CSV exports use one row per stats sample. Empty strings represent missing metric values.

| Field | Source | Meaning |
| --- | --- | --- |
| `sample_index` | sample metadata | Monotonic in-process sample index |
| `timestamp` | sample metadata | Unix timestamp in seconds |
| `room_id` | sample identity | Room identifier |
| `test_session_id` | sample identity | Test session identifier, empty for live samples |
| `peer_id` | sample identity | Local peer identifier |
| `remote_peer_id` | sample identity | Remote peer identifier |
| `connection_state` | metrics | Peer connection state |
| `ice_connection_state` | metrics | ICE connection state |
| `rtt_ms` | metrics | Candidate pair RTT in milliseconds |
| `packets_lost` | metrics | Lost inbound packets |
| `packet_loss_rate` | metrics | Loss percentage |
| `jitter_ms` | metrics | RTP jitter in milliseconds |
| `bitrate_kbps` | metrics | Local bitrate estimate in kbps |
| `available_outgoing_bitrate_kbps` | metrics | Browser available outgoing bitrate in kbps |
| `fps` | metrics | Frames per second |
| `frame_width` | metrics | Video frame width |
| `frame_height` | metrics | Video frame height |
| `codec` | metrics | Codec MIME type |
| `local_candidate_type` | metrics | Selected local ICE candidate type |
| `remote_candidate_type` | metrics | Selected remote ICE candidate type |
| `candidate_pair_protocol` | metrics | Selected candidate pair transport protocol |
| `packets_sent` | metrics | Sent RTP packets |
| `packets_received` | metrics | Received RTP packets |
| `bytes_sent` | metrics | Sent bytes |
| `bytes_received` | metrics | Received bytes |
| `frames_sent` | metrics | Sent frames |
| `frames_received` | metrics | Received frames |
| `frames_encoded` | metrics | Encoded frames |
| `frames_decoded` | metrics | Decoded frames |
| `frames_dropped` | metrics | Dropped frames |
| `nack_enabled` | metrics | Whether NACK was enabled for the experiment |
| `nack_mode` | metrics | NACK experiment mode |
| `nack_count` | metrics | NACK count |
| `pli_count` | metrics | PLI count |
| `fir_count` | metrics | FIR count |
| `quality_limitation_reason` | metrics | Browser quality limitation reason |
| `bitrate_mode` | metrics | Manual bitrate control mode |
| `sender_max_bitrate_bps` | metrics | Sender max bitrate in bps |
| `abr_mode` | metrics | Simplified ABR mode |
| `abr_target_bitrate_bps` | metrics | Simplified ABR target bitrate in bps |
| `abr_decision` | metrics | Last simplified ABR decision |
