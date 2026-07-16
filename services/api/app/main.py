import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.backtest_routes import router as backtest_router
from .api.market_data_routes import router as market_data_router
from .api.strategy_routes import router as strategy_router
from .api.strategy_draft_routes import router as strategy_draft_router
from .core.database import using_postgres
from .schemas.error_schema import ErrorResponse

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


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "database_backend": "postgresql" if using_postgres() else "sqlite",
    }
