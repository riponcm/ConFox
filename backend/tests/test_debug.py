from fastapi.testclient import TestClient

from app import main
from app.main import app


def test_break_is_hidden_by_default(monkeypatch):
    monkeypatch.setattr(main.settings, "enable_debug_endpoints", False)
    assert TestClient(app).post("/api/debug/break").status_code == 404


def test_unexpected_errors_are_still_500(monkeypatch):
    monkeypatch.setattr(main.settings, "enable_debug_endpoints", True)

    def reject(**_kwargs):
        raise RuntimeError("failed to parse date field [after-lunch]")

    monkeypatch.setattr(main.es, "search", reject)
    r = TestClient(app, raise_server_exceptions=False).post("/api/debug/break?mode=es")
    assert r.status_code == 500


def _bad_request(reason: str):
    from elastic_transport import ApiResponseMeta, HttpHeaders, NodeConfig
    from elasticsearch import BadRequestError

    meta = ApiResponseMeta(
        status=400, http_version="1.1", headers=HttpHeaders(), duration=0.0, node=NodeConfig("http", "localhost", 9200)
    )
    body = {
        "error": {
            "root_cause": [{"type": "parse_exception", "reason": reason}],
            "type": "search_phase_execution_exception",
        }
    }
    return BadRequestError(message="search_phase_execution_exception", meta=meta, body=body)


def test_invalid_query_is_a_400_with_the_reason(monkeypatch):
    monkeypatch.setattr(main.settings, "enable_debug_endpoints", True)

    def reject(**_kwargs):
        raise _bad_request("failed to parse date field [after-lunch]")

    monkeypatch.setattr(main.es, "search", reject)
    r = TestClient(app, raise_server_exceptions=False).post("/api/debug/break?mode=es")
    assert r.status_code == 400
    assert r.json() == {"error": "invalid_query", "detail": "failed to parse date field [after-lunch]"}
