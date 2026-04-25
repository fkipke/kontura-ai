"""Tests fuer den Health-Check-Endpoint."""

from fastapi.testclient import TestClient

from kontura.main import app


def test_health_returns_ok() -> None:
    """Der Health-Endpoint muss Status 200 und Payload 'ok' zurueckgeben."""
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "Kontura AI"
    assert "version" in data
    assert "environment" in data


def test_health_version_matches_package() -> None:
    """Die im Health-Endpoint gemeldete Version muss der Package-Version entsprechen."""
    from kontura import __version__

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.json()["version"] == __version__
