import os
from contextlib import contextmanager

_configured = False


def configure_telemetry():
    global _configured
    if _configured:
        return True
    connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        return False
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=connection_string)
        _configured = True
        return True
    except Exception:
        return False


def _get_tracer():
    try:
        from opentelemetry import trace

        return trace.get_tracer("ragpipeline")
    except Exception:
        return None


@contextmanager
def span(name, **attributes):
    tracer = _get_tracer()
    if tracer is None:
        yield None
        return
    with tracer.start_as_current_span(name) as current:
        for key, value in attributes.items():
            try:
                current.set_attribute(key, value)
            except Exception:
                pass
        yield current
