from fastapi import FastAPI

from app.core.lifespan import lifespan
from app.core.settings import get_settings


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": "AlphaLab AI", "version": "0.1.0"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
