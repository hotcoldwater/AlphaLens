import logging
import os
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.backtest_routes import router as backtest_router
from .api.market_data_routes import router as market_data_router
from .api.strategy_routes import router as strategy_router
from .api.strategy_draft_routes import router as strategy_draft_router
from .core.database import connect, execute, using_postgres
from .core.logging import configure_logging
from .schemas.error_schema import ErrorResponse

configure_logging()
logger = logging.getLogger("alphalens.api")

app = FastAPI(title="AlphaLens API", version="0.1.0")
local_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
configured_origins = [
    origin.strip()
    for origin in os.getenv("ALPHALENS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[*local_origins, *configured_origins],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(strategy_router)
app.include_router(strategy_draft_router)
app.include_router(backtest_router)
app.include_router(market_data_router)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - started) * 1000
    logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
        request_id, request.method, request.url.path, response.status_code, duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exception: RequestValidationError
) -> JSONResponse:
    details = [
        {"type": error["type"], "loc": list(error["loc"]), "msg": error["msg"]}
        for error in exception.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            code="VALIDATION_ERROR",
            message="request validation failed",
            details=details,
        ).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exception: HTTPException) -> JSONResponse:
    code = "NOT_FOUND" if exception.status_code == 404 else "HTTP_ERROR"
    message = exception.detail if isinstance(exception.detail, str) else "request failed"
    details = exception.detail if isinstance(exception.detail, list) else []
    return JSONResponse(
        status_code=exception.status_code,
        content=ErrorResponse(code=code, message=message, details=details).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exception: Exception) -> JSONResponse:
    """Catch anything that isn't an HTTPException/RequestValidationError (for
    example an unexpected KeyError deep in the backtest engine) so every
    error response — expected or not — has the same ErrorResponse shape."""
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "unhandled exception request_id=%s method=%s path=%s",
        request_id, request.method, request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            code="INTERNAL_ERROR",
            message="unexpected server error",
            details=[],
        ).model_dump(),
    )


@app.get("/health")
def health() -> dict:
    database_connected = True
    try:
        with connect() as connection:
            execute(connection, "SELECT 1")
    except Exception:
        logger.exception("health check failed to reach the database")
        database_connected = False
    return {
        "status": "ok" if database_connected else "degraded",
        "version": app.version,
        "database_backend": "postgresql" if using_postgres() else "sqlite",
        "database_connected": database_connected,
    }
