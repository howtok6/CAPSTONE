from contextlib import asynccontextmanager
from importlib.resources import files

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import Settings
from app.routes import router
from app.study import STUDY_FILES, UnknownStudyError
from app.study_routes import router as study_router
from app.tomtom import TomTomError, TomTomService


def create_app(
    settings: Settings | None = None,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx.AsyncClient(
            base_url="https://api.tomtom.com",
            timeout=settings.tomtom_timeout_seconds,
            transport=transport,
        ) as client:
            app.state.tomtom = TomTomService(client, settings)
            yield

    app = FastAPI(
        title="CAPSTONE · Backend de tránsito",
        description="Flujo e incidentes de tránsito obtenidos desde TomTom.",
        version="0.1.0",
        lifespan=lifespan,
    )
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET"],
            allow_headers=["Accept", "Content-Type"],
        )

    @app.exception_handler(TomTomError)
    async def handle_tomtom_error(request: Request, exc: TomTomError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(UnknownStudyError)
    async def handle_unknown_study(request: Request, exc: UnknownStudyError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.get("/health", tags=["Estado"])
    async def health():
        # No realiza llamadas de pago ni valida la clave contra el proveedor.
        return {"status": "ok", "tomtom_configured": settings.tomtom_configured}

    async def commune_table() -> HTMLResponse:
        html = files("app").joinpath("static/communes.html").read_text(encoding="utf-8")
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    for page in ("comunas", *STUDY_FILES):
        app.add_api_route(
            f"/{page}", commune_table, response_class=HTMLResponse, include_in_schema=False
        )

    app.include_router(router)
    app.include_router(study_router)
    return app


app = create_app()
