
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.services.wallet_service import WalletDomainError
from app.services.transaction_service import TransactionDomainError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(WalletDomainError)
    async def wallet_error_handler(
        request: Request,
        exc: WalletDomainError,
    ):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                },
            },
        )

    @app.exception_handler(TransactionDomainError)
    async def transaction_error_handler(
        request: Request,
        exc: TransactionDomainError,
    ):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                },
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request,
        exc: Exception,
    ):
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred.",
                },
            },
        )
