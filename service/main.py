# ###########################################################################
#
#  CLOUDERA APPLIED MACHINE LEARNING PROTOTYPE (AMP)
#  (C) Cloudera, Inc. 2021
#  All rights reserved.
#
#  Applicable Open Source License: Apache 2.0
#
#  NOTE: Cloudera open source products are modular software products
#  made up of hundreds of individual components, each of which was
#  individually copyrighted.  Each Cloudera open source product is a
#  collective work under U.S. Copyright Law. Your license to use the
#  collective work is as provided in your written agreement with
#  Cloudera.  Used apart from the collective work, this file is
#  licensed for your use pursuant to the open source license
#  identified above.
#
#  This code is provided to you pursuant a written agreement with
#  (i) Cloudera, Inc. or (ii) a third-party authorized to distribute
#  this code. If you do not have a written agreement with Cloudera nor
#  with an authorized and properly licensed third party, you do not
#  have any rights to access nor to use this code.
#
#  Absent a written agreement with Cloudera, Inc. (“Cloudera”) to the
#  contrary, A) CLOUDERA PROVIDES THIS CODE TO YOU WITHOUT WARRANTIES OF ANY
#  KIND; (B) CLOUDERA DISCLAIMS ANY AND ALL EXPRESS AND IMPLIED
#  WARRANTIES WITH RESPECT TO THIS CODE, INCLUDING BUT NOT LIMITED TO
#  IMPLIED WARRANTIES OF TITLE, NON-INFRINGEMENT, MERCHANTABILITY AND
#  FITNESS FOR A PARTICULAR PURPOSE; (C) CLOUDERA IS NOT LIABLE TO YOU,
#  AND WILL NOT DEFEND, INDEMNIFY, NOR HOLD YOU HARMLESS FOR ANY CLAIMS
#  ARISING FROM OR RELATED TO THE CODE; AND (D)WITH RESPECT TO YOUR EXERCISE
#  OF ANY RIGHTS GRANTED TO YOU FOR THE CODE, CLOUDERA IS NOT LIABLE FOR ANY
#  DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, PUNITIVE OR
#  CONSEQUENTIAL DAMAGES INCLUDING, BUT NOT LIMITED TO, DAMAGES
#  RELATED TO LOST REVENUE, LOST PROFITS, LOSS OF INCOME, LOSS OF
#  BUSINESS ADVANTAGE OR UNAVAILABILITY, OR LOSS OR CORRUPTION OF
#  DATA.
#
# ###########################################################################

import functools
import logging
import sys
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from uvicorn.logging import DefaultFormatter

from .config import settings
from .routers import index

from dotenv import load_dotenv

load_dotenv(dotenv_path="../../.env")

_APP_PKG_NAME = __name__.split(".", maxsplit=1)[0]

logger = logging.getLogger(__name__)
_request_received_logger = logging.getLogger(_APP_PKG_NAME + ".access")


def _configure_logger() -> None:
    """Configure this module's setup/teardown logging formatting and verbosity."""
    # match uvicorn.error's formatting
    formatter = DefaultFormatter("%(levelprefix)s %(message)s")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.setLevel(settings.rag_log_level)
    # prevent duplicate outputs with the app logger
    logger.propagate = False


_configure_logger()


###################################
#  Lifespan events
###################################


@functools.cache
def _get_app_log_handler():
    """Format and return a reusable handler for application logging."""
    # match Java backend's formatting
    formatter = logging.Formatter(
        fmt=" ".join(
            [
                "%(asctime)s",
                "%(levelname)5s",
                "%(name)30s",
                "[trace_id=%(otelTraceID)s span_id=%(otelSpanID)s]",
                "%(message)s",
            ]
        )
    )
    # https://docs.python.org/3/library/logging.html#logging.Formatter.formatTime
    formatter.converter = time.gmtime
    formatter.default_time_format = "%H:%M:%S"
    formatter.default_msec_format = "%s.%03d"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    return handler


def _configure_app_logger(app_logger: logging.Logger) -> None:
    """Configure application logging formatting and verbosity."""
    # remove any existing stdout/stderr handlers to prevent duplicate outputs
    for handler in app_logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            if handler.stream in {sys.stderr, sys.stdout}:
                app_logger.removeHandler(handler)

    app_logger.addHandler(_get_app_log_handler())
    app_logger.setLevel(settings.rag_log_level)


def initialize_logging():
    logger.info("Initializing logging.")

    LoggingInstrumentor().instrument()
    _configure_app_logger(logging.getLogger("uvicorn.access"))
    _configure_app_logger(logging.getLogger(_APP_PKG_NAME))

    logger.info("Logging initialized.")


def _get_tracing_resource():
    return Resource(attributes={SERVICE_NAME: settings.otel.service_name})


def initialize_tracing():
    if not settings.otel.exporter_otlp_endpoint:
        logger.info("No OTLP export endpoint set. Skipping tracing initialization.")
        return

    logger.info("Initializing tracing.")

    # OTLP trace exporter
    processor = BatchSpanProcessor(span_exporter=OTLPSpanExporter())
    provider = TracerProvider(resource=_get_tracing_resource())
    provider.add_span_processor(processor)

    # W3C trace context propagator
    set_global_textmap(TraceContextTextMapPropagator())

    trace.set_tracer_provider(provider)

    logger.info("Tracing initialized.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_logging()
    initialize_tracing()
    yield


###################################
#  App
###################################


app = FastAPI(lifespan=lifespan)


###################################
#  Middleware
###################################


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# must precede FastAPIInstrumentor to capture trace and span IDs
@app.middleware("http")
async def log_request_received(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Log the incoming request method and path."""
    _request_received_logger.info(
        'received request "%s %s"',
        request.method,
        request.url.path,
    )
    return await call_next(request)


FastAPIInstrumentor.instrument_app(app)


###################################
#  Routes
###################################


app.include_router(index.router)