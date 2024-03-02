"""OpenTelemetry cassio instrumentation"""

import logging
import cassio
from typing import Collection
from wrapt import wrap_function_wrapper

from opentelemetry import context as context_api
from opentelemetry.trace import get_tracer, SpanKind
from opentelemetry.trace.status import Status, StatusCode

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import (
    _SUPPRESS_INSTRUMENTATION_KEY,
    unwrap,
)
from opentelemetry.instrumentation.cassio.version import __version__

from opentelemetry.semconv.ai import SpanAttributes

logger = logging.getLogger(__name__)

_instruments = ("cassio >= 0.1.0",)

WRAPPED_METHODS = [
]


def _set_span_attribute(span, name, value):
    if value is not None:
        if value != "":
            span.set_attribute(name, value)
    return


def _set_input_attributes(span, kwargs):
    pass


def _set_response_attributes(span, response):
    pass


def _with_tracer_wrapper(func):
    """Helper for providing tracer for wrapper functions."""

    def _with_tracer(tracer, to_wrap):
        def wrapper(wrapped, instance, args, kwargs):
            return func(tracer, to_wrap, wrapped, instance, args, kwargs)

        return wrapper

    return _with_tracer


@_with_tracer_wrapper
def _wrap(tracer, to_wrap, wrapped, instance, args, kwargs):
    """Instruments and calls every function defined in TO_WRAP."""
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
        return wrapped(*args, **kwargs)

    name = to_wrap.get("span_name")
    with tracer.start_as_current_span(
        name,
        kind=SpanKind.CLIENT,
        attributes={
            SpanAttributes.VECTOR_DB_VENDOR: "cassio",
        },
    ) as span:
        try:
            if span.is_recording():
                _set_input_attributes(span, kwargs)

        except Exception as ex:  # pylint: disable=broad-except
            logger.warning(
                "Failed to set input attributes for openai span, error: %s", str(ex)
            )

        response = wrapped(*args, **kwargs)

        if response:
            try:
                if span.is_recording():
                    _set_response_attributes(span, response)

            except Exception as ex:  # pylint: disable=broad-except
                logger.warning(
                    "Failed to set response attributes for openai span, error: %s",
                    str(ex),
                )
            if span.is_recording():
                span.set_status(Status(StatusCode.OK))

        return response


class CassIOInstrumentor(BaseInstrumentor):
    """An instrumentor for CassIO library."""

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, __version__, tracer_provider)
        for wrapped_method in WRAPPED_METHODS:
            wrap_object = wrapped_method.get("object")
            wrap_method = wrapped_method.get("method")
            if getattr(cassio, wrap_object, None):
                wrap_function_wrapper(
                    "cassio",
                    f"{wrap_object}.{wrap_method}",
                    _wrap(tracer, wrapped_method),
                )

    def _uninstrument(self, **kwargs):
        for wrapped_method in WRAPPED_METHODS:
            wrap_object = wrapped_method.get("object")
            unwrap(f"cassio.{wrap_object}", wrapped_method.get("method"))
