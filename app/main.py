"""FastAPI-Anwendung. Ein Endpoint, der genau eine Sache richtig macht."""

import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from . import __version__
from .config import settings
from .filters import build_targets
from .upstream import AdsbClient, UpstreamError

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("adsb-proxy")

client: AdsbClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    # Fail closed. Ein leeres Token hat frueher die Pruefung stillschweigend
    # abgeschaltet - im LAN aergerlich, seit der Proxy ueber einen Tunnel am
    # Internet haengt untragbar. Ein Tippfehler in der Stack-Variable wuerde
    # sonst reichen, um /v1/traffic fuer jeden zu oeffnen. Lieber startet der
    # Container gar nicht: das faellt sofort auf, ein offener Endpoint nicht.
    if not settings.token:
        raise RuntimeError(
            "ADSB_TOKEN ist leer. Der Proxy startet nicht ohne Token - "
            "sonst waere /v1/traffic ohne jede Pruefung erreichbar."
        )

    client = AdsbClient()
    log.info("Provider: %s", client.provider.name)
    if client.provider.synthetic:
        log.warning("DEMO-MODUS: die ausgelieferten Ziele sind erfunden, kein echter Luftraum.")
    yield
    await client.aclose()


app = FastAPI(
    title="ADS-B Watch proxy",
    version=__version__,
    description="Liefert ein RAM-schonendes Verkehrsbild fuer die Garmin Instinct 2X.",
    lifespan=lifespan,
)


def require_token(x_api_token: str | None = Header(default=None)) -> None:
    """Simples Shared Secret. Verhindert, dass fremde Clients das Kontingent verbrennen.

    Zweiter Riegel zum Startcheck in `lifespan`: ein leeres Token laesst hier
    niemanden durch, sondern liefert 503. Erreichbar ist der Zweig nur, wenn das
    Token zur Laufzeit geleert wird - dann ist der Dienst kaputt, nicht offen.
    """
    if not settings.token:
        raise HTTPException(status_code=503, detail="server misconfigured: no token set")
    if x_api_token is None or not secrets.compare_digest(x_api_token, settings.token):
        raise HTTPException(status_code=401, detail="invalid token")


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "provider": settings.provider,
        "demo": client is not None and client.provider.synthetic,
    }


@app.get("/v1/traffic", dependencies=[Depends(require_token)])
async def traffic(
    lat: float = Query(..., ge=-90, le=90, description="Eigene Breite in Grad"),
    lon: float = Query(..., ge=-180, le=180, description="Eigene Laenge in Grad"),
    nm: int = Query(25, ge=1, le=250, description="Radius in nautischen Meilen"),
    alt_min: int = Query(0, ge=-1500, le=60000, description="Untergrenze Hoehenband in Fuss"),
    alt_max: int = Query(45000, ge=-1500, le=60000, description="Obergrenze Hoehenband in Fuss"),
    max_targets: int = Query(12, ge=1, le=50, alias="max", description="Maximale Anzahl Ziele"),
    fmt: str = Query("compact", pattern="^(compact|full)$"),
) -> JSONResponse:
    if alt_min > alt_max:
        raise HTTPException(status_code=422, detail="alt_min > alt_max")
    if client is None:
        raise HTTPException(status_code=503, detail="client not ready")

    try:
        raw = await client.fetch_point(lat, lon, nm)
    except UpstreamError as exc:
        log.warning("Upstream-Fehler: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    limit = min(max_targets, settings.max_targets)
    targets = build_targets(raw, lat, lon, nm, alt_min, alt_max, limit)

    if fmt == "compact":
        # Array of Arrays: kein Key-Overhead, minimaler Parse-Aufwand auf der Uhr.
        return JSONResponse([t.to_compact() for t in targets])

    return JSONResponse(
        {
            "count": len(targets),
            "provider": client.provider.name,
            "attribution": client.provider.attribution,
            "targets": [t.to_full() for t in targets],
        }
    )
