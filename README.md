# Joormann-Media-Jarvis-Hotword-Listener

Reines Hotword-Listener-Lab fuer lokale Runtime + Family-Panel-Linking.

## Umfang
- Hotword Runtime Service (FastAPI/Uvicorn) aus dem Hotword-Lab
- Schlanker Manager (Flask) fuer:
  - `/link` (Portal URL + Registrierungstoken)
  - `/api/portal/status`
  - `/api/portal/sync`
  - `/api/portal/relink`
  - Runtime-Proxy-Endpunkte (`/api/runtime/*`)
- MCP/Fastpath-Basis-Flow ueber Intent-Sync ins Family-Panel

## Ports
- Manager (Flask): `5103`
- Hotword Runtime (Uvicorn): `8120`

## Start (Dev)
```bash
./scripts/start-dev.sh
```

## Stop
```bash
./scripts/stop-dev.sh
```

## Linking
1. `http://127.0.0.1:5103/link` aufrufen
2. `portal_url` und `registration_token` aus dem Family-Panel setzen
3. Nach erfolgreichem Register wird Node-Sync + MCP-Intent-Sync automatisch angestossen

## Runtime-Controls
- `GET /api/runtime/status`
- `POST /api/runtime/start`
- `POST /api/runtime/stop`
- `POST /api/runtime/reload-hotwords`
- `POST /api/runtime/test-trigger`

## Hinweise
- Machine-ID und Portal-URL werden bevorzugt aus dem Deviceportal aufgeloest.
- Lokale Konfiguration liegt in `config/portal.local.json`.
