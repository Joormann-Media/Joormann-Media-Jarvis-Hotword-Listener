# hotword-service

Port: `8106`

Der `hotword-service` ist jetzt die Zentrale fuer Hotword-Verwaltung, Samples, Speaker-Zuordnung, Runtime und lokale Modellverwaltung. Der bevorzugte Pfad ist lokal/offline zusammen mit dem `hotword-trainer`. Porcupine bleibt nur noch optional als Legacy-Engine.

## Runtime-Endpunkte
- `GET /health`
- `GET /runtime/status`
- `GET /runtime/config`
- `POST /runtime/start`
- `POST /runtime/reload-hotwords`
- `POST /runtime/test-trigger`
- `POST /runtime/stop`
- `POST /runtime/configure-listener` (setzt `HOTWORD_LISTENER_ENABLED` dauerhaft in `.env`)
- `GET /runtime/audio-devices`
- `POST /runtime/audio-input` (setzt `HOTWORD_RUNTIME_DEVICE_NAME` + optional Listener-Neustart)
- `GET /runtime/audio-tuning`
- `POST /runtime/audio-tuning` (Gain + Schwellwerte speichern)
- `POST /runtime/audio-probe` (3s Runtime-Testaufnahme mit RMS/Peak)
- `GET /runtime/audio-probe/{file_name}` (Playback der Probeaufnahme)
- `GET /ui`
- `GET /assistant` (Wizard UI für Hotword+Intent Flow)

## Wichtige Konfiguration
- `HOTWORD_ENGINE=local`
- `HOTWORD_TRAINER_URL=http://127.0.0.1:8107`
- `STT_SERVICE_URL=http://127.0.0.1:8101`
- `FAMILY_PANEL_URL=https://joormann-family.de`
- `FAMILY_PANEL_TRAINER_BOOTSTRAP_PATH=/api/jarvis/trainer/bootstrap`
- `FAMILY_PANEL_TRAINER_AUTO_TOKEN_PATH=/api/jarvis/trainer/auto-token`
- `FAMILY_PANEL_TRAINER_INGEST_PATH=/api/jarvis/trainer/ingest`
- `FAMILY_PANEL_TRAINER_TOKEN=...`
- `FAMILY_PANEL_SYNC_TOKEN=...` (oder `PORTAL_REGISTRY_PUSH_TOKEN`)
- `HOTWORD_LISTENER_ENABLED=false`
- `HOTWORD_RUNTIME_RECORDINGS_DIR=/media/djanebmb/AI 512 GB SSD/Jarvis-V2/runtime/recordings/live`
- `HOTWORD_RUNTIME_COOLDOWN_SECONDS=6`
- `HOTWORD_RUNTIME_RECORD_SECONDS=5`
- `HOTWORD_RUNTIME_RETRY_ON_EMPTY_TRANSCRIPT=true`
- `HOTWORD_RUNTIME_RETRY_EXTRA_SECONDS=3`
- `HOTWORD_RUNTIME_DEVICE_INDEX=-1`
- `HOTWORD_RUNTIME_DEVICE_NAME=` (optional, z. B. `pulse` oder `plughw:1,0`)
- `HOTWORD_RUNTIME_FOLLOWUP_SAMPLE_RATE=16000`
- `HOTWORD_RUNTIME_REQUIRED_HITS=2` (wie viele Treffer in Folge fuer einen Trigger)
- `HOTWORD_RUNTIME_MIN_SCORE=0.62` (Mindestscore gegen Fehltrigger)
- `HOTWORD_RUNTIME_MIN_RMS_FACTOR=0.35` (Mindestlautstaerke relativ zum Modell)
- `HOTWORD_RUNTIME_INPUT_GAIN=1.0` (Software-Verstärkung fuer Wakeword-Input)
- `HOTWORD_FOLLOWUP_USE_ARECORD=true`
- `HOTWORD_RUNTIME_DISPATCH_URL=http://127.0.0.1:8100/voice/command`
- `HOTWORD_RUNTIME_LOG_TO_STDOUT=true` (Runtime-Events zusätzlich in Konsole)
- `HOTWORD_RUNTIME_IGNORE_WHILE_SPEAKING=true`
- optional legacy: `HOTWORD_ACCESS_KEY=...` fuer Porcupine

## Lokal starten
```bash
cd "/media/djanebmb/AI 512 GB SSD/Jarvis-V2/services/hotword-service"
python -m pip install -r requirements.txt
python -m uvicorn src.main:app --host 127.0.0.1 --port 8106 --reload
```

### Dev-Startscript Live-Logs
- `scripts/start-dev.sh` tailt standardmäßig live:
  - `runtime/logs/hotword-service.log`
  - `runtime/logs/stt-service.log`
  - `runtime/logs/core-api.log`
- Deaktivieren: `JARVIS_DEV_FOLLOW_LOGS=0 ./scripts/start-dev.sh`

## Runtime ohne Browser (Service + Autostart)
- Service installieren:
  - `./scripts/service-install.sh <user>`
- Service-Autostart (systemd) an/aus:
  - `./scripts/service-enable.sh`
  - `./scripts/service-disable.sh`
- Runtime-Listener dauerhaft an/aus (unabhaengig vom Browser):
  - `./scripts/runtime-autostart-on.sh`  -> setzt `HOTWORD_LISTENER_ENABLED=true`
  - `./scripts/runtime-autostart-off.sh` -> setzt `HOTWORD_LISTENER_ENABLED=false`

## UI-Struktur
- `Dashboard`: Statuskarten, Runtime-Zusammenfassung, Rohdaten
- `Hotwords`: CRUD, Speaker-Zuordnung, Detection Mode, Runtime-Flags
- `Samples`: Upload, Browser-Aufnahme, Hotword-Details
- `Hotword Trainer`: Mikro aufnehmen oder Upload, als Hotword-Sample speichern, optional STT-Transkript anzeigen (kein Family-Ingest)
- `Intent Trainer`: Mikro aufnehmen oder Upload, STT-Transkript erzeugen und kompletten Intent/Slot/Memory-Datensatz ins Family-Panel schreiben
- `Modelle`: lokales Training vorbereiten, Job anlegen, Modell exportieren, Legacy-Import
- `Runtime`: Start, Stop, Reload, Test Trigger + Listener-Autostart EIN/AUS (persistiert)
- `Mikrofon Pegel & Empfindlichkeit`: Live-Meter (RMS/Peak + Waveform) + Mikrofon-Quellenwahl + Runtime-Tuning (Input Gain, Min Score, Min RMS, Required Hits)
- `Detection Test`: Testdatei hochladen und Detection pruefen

Hinweis zu Hotword-Phrasen:
- `phrase` bleibt der primäre Trigger.
- zusätzlich werden `phrases[]` gespeichert (Mehrfach-Eingabe in UI via Leerzeichen/Komma, auto-normalisiert).

## Assistant-Flow (`/assistant`)
- `Hotword-Assistent`:
1. Neues Hotword anlegen oder vorhandenes auswählen
2. Mehrere Samples nacheinander per Upload oder Browser-Aufnahme speichern
3. Abschluss und Übergabe zum Intent-Assistenten
- `Intent-Assistent`:
1. Vorhandenes Hotword wählen
2. Audio aufnehmen/hochladen und direkt über `/trainer/ingest` ins Family-Panel schreiben
- Zusatz:
  - Hotwords können priorisiert und als Default gesetzt werden (`priority`, `is_default`)
  - Serverseitige Sortierung erfolgt nach `is_default` und danach `priority`

## Trainer-API
- `GET /trainer/bootstrap` -> Auswahlwerte aus dem Family-Panel laden (Clients/User/Profile)
- `POST /trainer/hotword-sample` -> reines Hotword-Training (Sample speichern + optional STT)
- `POST /trainer/ingest` -> Intent-Training inkl. Family-Panel-Ingest

Hinweis:
- `FAMILY_PANEL_TRAINER_TOKEN` wird nur fuer `/trainer/bootstrap` und `/trainer/ingest` benoetigt.
- wenn kein `FAMILY_PANEL_TRAINER_TOKEN` gesetzt ist, versucht der Service automatisch den Token via `/trainer/auto-token` mit `FAMILY_PANEL_SYNC_TOKEN` zu holen.
- Der Hotword-Trainer (`/trainer/hotword-sample`) funktioniert auch ohne Family-Token.

## Lokal/offline Workflow
1. Samples pro Hotword sammeln
2. Datensatz im `hotword-trainer` vorbereiten
3. Trainingsjob lokal ausfuehren
4. JSON-Modellartefakt exportieren und dem Hotword zuordnen
5. Runtime-Hotwords neu laden

Aktueller Stand:
- der Trainer baut bereits echte normalisierte Datasets und ein reales lokales JSON-Artefakt
- die Runtime laedt lokale JSON-Modelle jetzt wirklich und nutzt einen ersten ehrlichen Matcher auf Basis des exportierten Artefakts
- der lokale Matcher ist bewusst einfach gehalten und kann weiter optimiert werden

## Lokale Runtime
Ein Hotword wird als lokales Runtime-Hotword geladen, wenn:
- `is_active=true`
- `runtime_enabled=true`
- `model_ready=true` (Modellpfad muss real existieren)
- `engine_type=local`
- `model_path` auf ein vorhandenes JSON-Modell zeigt

Die lokale Runtime:
- liest Mikrofon-Audio per `arecord`
- probiert Audio-Devices in Reihenfolge: `HOTWORD_RUNTIME_DEVICE_NAME` -> Index (`plughw/hw`) -> default -> `pulse` -> `sysdefault`
- zusaetzlich werden erkannte Capture-Devices aus `arecord -l` automatisch erkannt und priorisiert (USB/Bluetooth/Headset vor Onboard/HDMI)
- berechnet dieselbe einfache Amplituden-Huellkurven-Darstellung wie das Trainer-Artefakt
- vergleicht das eingehende Fenster gegen `prototype_envelope` und `avg_rms`
- feuert bei Score >= Threshold den bestehenden Folgeaufnahme-/Dispatch-Pfad

## Legacy
- Porcupine `.ppn`-Import bleibt per `POST /hotwords/{hotword_id}/model/upload` moeglich
- die UI markiert diesen Pfad bewusst nur noch als optional/legacy
