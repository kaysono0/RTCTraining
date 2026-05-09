from src.webrtc.domain.errors import ErrorCode
from src.webrtc.domain.stats_schema import CSV_FIELDS, STATS_IDENTITY_FIELDS
from src.webrtc.exports.stats_csv import CSV_FIELDS as EXPORT_CSV_FIELDS


def test_stats_schema_declares_identity_and_csv_fields():
    assert STATS_IDENTITY_FIELDS == (
        "room_id",
        "test_session_id",
        "peer_id",
        "remote_peer_id",
    )
    assert CSV_FIELDS == EXPORT_CSV_FIELDS


def test_domain_error_codes_match_public_envelope_codes():
    assert ErrorCode.BAD_REQUEST == "bad_request"
    assert ErrorCode.NOT_FOUND == "not_found"
    assert ErrorCode.SERVICE_UNREACHABLE == "service_unreachable"
    assert ErrorCode.UPSTREAM_ERROR == "upstream_error"
