from ragpipeline import telemetry
from ragpipeline.telemetry import configure_telemetry, span


def test_configure_telemetry_false_without_env(monkeypatch):
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    telemetry._configured = False
    assert configure_telemetry() is False


def test_span_does_not_raise():
    with span("unit-test", foo="bar"):
        pass
