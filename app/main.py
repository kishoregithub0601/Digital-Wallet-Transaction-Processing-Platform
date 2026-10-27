
from fastapi import FastAPI

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.routers.auth import router as auth_router
from app.routers.wallets import router as wallets_router
from app.routers.transactions import router as transactions_router
from app.routers.refunds import router as refunds_router
from app.routers.notifications import router as notifications_router
from app.routers.admin import router as admin_router
from app.routers.dashboard import router as dashboard_router


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "Digital Wallet & Transaction Processing Platform "
        "with wallet management, transfers, refunds and reporting."
    ),
)

register_exception_handlers(app)

app.include_router(auth_router)
app.include_router(wallets_router)
app.include_router(transactions_router)
app.include_router(refunds_router)
app.include_router(notifications_router)
app.include_router(admin_router)
app.include_router(dashboard_router)


@app.get("/", tags=["Health"])
def health_check():
    return {
        "success": True,
        "message": "Digital Wallet Platform API is configured.",
    }
