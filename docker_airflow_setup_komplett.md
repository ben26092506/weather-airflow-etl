# Docker + Airflow Lernprojekt (Open‑Meteo → Postgres) – Vollständige Setup‑Dokumentation

Diese Datei ist eine **vollständige** Zusammenfassung unseres gesamten Docker-/Airflow-Setups inkl. aller typischen Fehler, Erkennungszeichen, Fixes und der wichtigsten Bash-Commands (inkl. Erklärung der Flags).

Ziel des Projekts (MUSS-Version):
- Airflow in Docker (minimal, ohne unnötige Services)
- Weather-Postgres (Projektdaten) getrennt von Airflow-Metadata-Postgres
- DAGs und Logs über Volumes auf dem Host verfügbar
- Open‑Meteo API → Transform → Load in Postgres (später)

---

## 1) Grundprinzipien (kurz, aber wichtig)

### Docker Image vs Container vs docker-compose
- **Image**: vorgefertigtes Dateisystem + Software (z. B. `apache/airflow:2.10.1`, `postgres:16`)
- **Container**: laufende Instanz eines Images
- **docker-compose.yaml**: beschreibt mehrere Container (Services), Netzwerke, Volumes, Env-Variablen

### Host-Pfade vs Container-Pfade
- Code läuft im Container → im DAG müssen **Container-Pfade** genutzt werden.
- Host-Pfade sind dem Container nur bekannt, wenn gemountet (Volume/Bind Mount).

Merksatz:
> Docker sieht nur, was du explizit mountest.

---

## 2) Zielarchitektur (Minimal & professionell)

Wir nutzen **LocalExecutor** (kein Celery/Redis/Worker nötig für Lernprojekt).

Services:
1. `weather-postgres` (Postgres 16) – Zielsystem für Wetterdaten
2. `airflow-postgres` (Postgres 16) – Airflow Metadata DB
3. `airflow-init` – einmaliger Initialisierungs-Job: DB init + Admin-User anlegen
4. `airflow-scheduler` – DAGs parsen + scheduling
5. `airflow-webserver` – UI

Wichtig:
- **init, scheduler und webserver müssen konsistente Airflow-Konfiguration haben** (insb. Executor + DB-Conn).

---

## 3) Projektstruktur auf dem Host (WSL/Ubuntu)

Beispiel:
```
~/airflow-docker_v1/
├─ docker-compose.yaml
├─ .env
├─ dags/
├─ logs/
└─ db_init/
   └─ 01_create_raw_weather.sql
```

### Ordner anlegen
```bash
cd ~/airflow-docker_v1
mkdir -p dags logs db_init
touch .env
```

Flags:
- `mkdir -p`: erstellt Parent-Ordner, kein Fehler wenn existiert
- `touch`: erstellt leere Datei oder aktualisiert Timestamp

---

## 4) docker-compose.yaml – Referenz (Minimal-Stack)

Hinweis:
- `./dags:/opt/airflow/dags` und `./logs:/opt/airflow/logs` sind Bind-Mounts
- Postgres-Daten über Named Volumes (`*_pg_data`) persistent

```yaml
version: "3.9"

services:
  # ---------------------------
  # Weather Data Postgres (Projekt-Daten)
  # ---------------------------
  weather-postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: weather
      POSTGRES_PASSWORD: weather
      POSTGRES_DB: weather
    volumes:
      - weather_pg_data:/var/lib/postgresql/data
      - ./db_init:/docker-entrypoint-initdb.d:ro
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U weather -d weather"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ---------------------------
  # Airflow Metadata Postgres
  # ---------------------------
  airflow-postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: airflow
      POSTGRES_DB: airflow
    volumes:
      - airflow_pg_data:/var/lib/postgresql/data

  # ---------------------------
  # Airflow Init (einmalig)
  # ---------------------------
  airflow-init:
    image: apache/airflow:2.10.1
    depends_on:
      - airflow-postgres
    environment:
      # WICHTIG: Muss zum Scheduler/Webserver passen!
      AIRFLOW__CORE__EXECUTOR: airflow.executors.local_executor.LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@airflow-postgres:5432/airflow
      AIRFLOW__CORE__LOAD_EXAMPLES: "false"
      # optional: zusätzliche Pakete (für schnelle Tests)
      _PIP_ADDITIONAL_REQUIREMENTS: requests
    entrypoint: /bin/bash
    command:
      - -c
      - |
        airflow db init
        airflow users create \
          --username airflow \
          --password airflow \
          --firstname Admin \
          --lastname User \
          --role Admin \
          --email admin@example.com

  # ---------------------------
  # Airflow Scheduler
  # ---------------------------
  airflow-scheduler:
    image: apache/airflow:2.10.1
    depends_on:
      - airflow-postgres
      - weather-postgres
      - airflow-init
    environment:
      # WICHTIG: Muss zum Init/Webserver passen!
      AIRFLOW__CORE__EXECUTOR: airflow.executors.local_executor.LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@airflow-postgres:5432/airflow
      AIRFLOW__CORE__LOAD_EXAMPLES: "false"

      # Weather-DB als Airflow Connection (Connection-ID: weather_db)
      AIRFLOW_CONN_WEATHER_DB: postgresql+psycopg2://weather:weather@weather-postgres:5432/weather

      # optional: zusätzliche Pakete (für schnelle Tests)
      _PIP_ADDITIONAL_REQUIREMENTS: requests

    volumes:
      - ./dags:/opt/airflow/dags
      - ./logs:/opt/airflow/logs
    command: scheduler

  # ---------------------------
  # Airflow Webserver
  # ---------------------------
  airflow-webserver:
    image: apache/airflow:2.10.1
    depends_on:
      - airflow-init
      - airflow-scheduler
    environment:
      # WICHTIG: Muss zum Init/Scheduler passen!
      AIRFLOW__CORE__EXECUTOR: airflow.executors.local_executor.LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@airflow-postgres:5432/airflow
      AIRFLOW__CORE__LOAD_EXAMPLES: "false"
      AIRFLOW_CONN_WEATHER_DB: postgresql+psycopg2://weather:weather@weather-postgres:5432/weather
      _PIP_ADDITIONAL_REQUIREMENTS: requests
    volumes:
      - ./dags:/opt/airflow/dags
      - ./logs:/opt/airflow/logs
    ports:
      - "8080:8080"
    command: webserver

volumes:
  weather_pg_data:
  airflow_pg_data:
```

### Erklärung wichtiger YAML-Teile

#### `volumes:` bei Postgres
- `weather_pg_data:/var/lib/postgresql/data`
  - Links: Named Volume (Docker verwaltet)
  - Rechts: Pfad im Container (Postgres speichert dort seine DB-Daten)
- `./db_init:/docker-entrypoint-initdb.d:ro`
  - Bind Mount: Host-Ordner `./db_init` in Container unter `/docker-entrypoint-initdb.d`
  - Postgres-Image führt beim ersten Initialisieren alle `.sql` Dateien dort aus.
  - `:ro` = read-only Mount (Container darf den Ordner nicht verändern)

#### Ports (Beispiel `5433:5432`)
- `HOST:CONTAINER`
- Container-Postgres hört auf `5432`
- Auf dem Host wollen wir Konflikte vermeiden → `5433` außen
- Zugriff vom Host: `localhost:5433`
- Zugriff von anderen Containern im gleichen Compose-Netz: `weather-postgres:5432` (ohne Host-Port!)

#### `depends_on`
- Steuert Start-Reihenfolge (nicht zwingend "ready")
- `airflow-init` muss existieren, sonst Validierungsfehler
- Für echte "ready"-Abhängigkeit wären Healthchecks/Conditions nötig (optional)

#### `command`
- überschreibt Standardcommand des Images (`scheduler`, `webserver`)
- `airflow-init` nutzt bash-scripted command (siehe entrypoint)

#### `entrypoint: /bin/bash`
- überschreibt den Entrypoint des Images, damit wir mehrere Commands ausführen können (`airflow db init` + User-Create)
- Achtung: `/usr/bin/bash` war falsch und führte zu „cannot execute binary file“

---

## 5) Setup starten (Bash-Kommandos & Flags)

### 5.1 Container starten
```bash
docker compose up -d
```

Flags:
- `-d` = detached (im Hintergrund), Terminal bleibt frei

### 5.2 Status prüfen
```bash
docker ps
```
Zeigt nur laufende Container.

Alle Container (inkl. Exited) zeigen:
```bash
docker ps -a
```
- wichtig für `airflow-init` (soll **Exited (0)** sein)

### 5.3 Logs ansehen
```bash
docker logs <container-name> --tail 80
```

Flags:
- `--tail 80` zeigt nur die letzten 80 Zeilen (praktisch fürs Debugging)

Live folgen:
```bash
docker logs -f <container-name>
```
Flags:
- `-f` = follow (live stream)

### 5.4 Stack stoppen / entfernen
```bash
docker compose down
```

Alles inkl. Volumes entfernen (Reset!):
```bash
docker compose down -v
```

Flags:
- `-v` = removes named volumes (löscht DB-Daten im Volume)
  - nutzen, wenn Metadb kaputt/inkonsistent ist oder du komplett neu starten willst

---

## 6) Airflow UI öffnen

URL:
- http://localhost:8080

Login (wie im Init angelegt):
- user: `airflow`
- pass: `airflow`

---

## 7) Postgres (Weather DB) testen

### In den Container rein
```bash
docker exec -it airflow-docker_v1-weather-postgres-1 psql -U weather -d weather
```

Flags:
- `docker exec`: führe Kommando in laufendem Container aus
- `-it`: interactive + TTY (damit `psql` interaktiv ist)
- `psql -U <user> -d <db>`: DB-Client, User/DB wählen

Tabellen anzeigen:
```sql
\dt
```

Beenden:
```sql
\q
```

---

## 8) Log-Ordner: Ownership/Permissions (SEHR WICHTIG)

### Problem: Scheduler/Webserver crashen wegen PermissionError
Typische Fehlermeldungen:
- `PermissionError: [Errno 13] Permission denied: '/opt/airflow/logs/...`
- `Unable to configure handler ...`

Warum?
- `./logs` ist Host-Ordner
- Airflow läuft im Container als User mit UID (oft 50000)
- Wenn der Host-Ordner root gehört oder falsche Rechte hat → Container darf nicht schreiben

### Schnell erkennen (immer zuerst bei Scheduler-Problemen!)
```bash
docker logs airflow-docker_v1-airflow-scheduler-1 --tail 120
```
Wenn dort `PermissionError` → Ownership ist der erste Verdacht.

### Fix (Host)
```bash
sudo chown -R 50000:50000 logs dags
```

- `sudo`: Adminrechte
- `chown`: ownership ändern
- `-R`: rekursiv (inkl. Unterordner/Files)
- `50000:50000`: owner:group (Airflow User im offiziellen Image)

Danach:
```bash
docker compose up -d
```

---

## 9) Die wichtigsten Fehler, wie man sie schnell erkennt und löst

### Fehler A: YAML-Syntax/Keys falsch (`depends on` statt `depends_on`)
Erkennen:
- `additional properties ... not allowed`
Fix:
- Key exakt schreiben (`depends_on`)

### Fehler B: Service-Name fehlt (z. B. `airflow-init` referenced, aber nicht definiert)
Erkennen:
- `depends on undefined service "airflow-init"`
Fix:
- `airflow-init` unter `services:` definieren, Name exakt matchen

### Fehler C: Falscher Bash-Pfad (`/usr/bin/bash`)
Erkennen:
- `cannot execute binary file` in init logs
Fix:
- `entrypoint: /bin/bash`

### Fehler D: DB nicht initialisiert
Erkennen:
- Webserver-Logs: `You need to initialize the database. Please run airflow db init`
Fix:
- `airflow-init` Service korrekt konfigurieren; danach `docker ps -a` → init sollte `Exited (0)` sein

### Fehler E: Executor falsch gesetzt (nur `LocalExecutor` statt vollem Pfad)
Erkennen:
- ImportError/ConfigException im Webserver oder Scheduler
Fix:
- `AIRFLOW__CORE__EXECUTOR: airflow.executors.local_executor.LocalExecutor`

### Fehler F: SQLite-Fallback bei LocalExecutor
Erkennen:
- Scheduler-Log: `cannot use SQLite with the LocalExecutor`
Ursachen:
- `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` fehlt oder falsch geschrieben (z. B. `SQL_ALCHEYMY_CONN`)
Fix:
- ENV-Key exakt richtig schreiben
- ggf. Reset: `docker compose down -v && docker compose up -d`

### Fehler G: DAGs werden nicht gefunden
Erkennen:
- UI zeigt 0 DAGs, aber du hast Dateien auf dem Host
Fix:
- im Container prüfen:
  ```bash
  docker exec -it airflow-docker_v1-airflow-scheduler-1 ls /opt/airflow/dags
  ```
- häufige Ursache: falscher Mount-Pfad (z. B. `/opt/airlfow/dags` Tippfehler)

### Fehler H: Connection ENV falsch (Weather DB)
Erkennen:
- `airflow connections get weather_db` zeigt nicht existierend
Fix:
- korrekt: `AIRFLOW_CONN_WEATHER_DB=...`
  (nicht `AIRFLOW__CONN...` und keine Punkte/Leerzeichen im Key)

### Fehler I: Du suchst Logs im falschen Ordner
Airflow-Logstruktur (typisch):
```
logs/dag_id=<DAG>/run_id=<RUN>/task_id=<TASK>/attempt=1.log
```
Fix:
```bash
find logs -type f | head
cat logs/dag_id=weather_extract_only/run_id=*/task_id=extract_weather/attempt=*.log
```

---

## 10) Schnell-Diagnose-Checkliste (in 60 Sekunden)

1) Container laufen?
```bash
docker ps
```

2) Scheduler-Logs (WICHTIGSTE Quelle)
```bash
docker logs airflow-docker_v1-airflow-scheduler-1 --tail 120
```
- `PermissionError` → `sudo chown -R 50000:50000 logs dags`
- `SQLite with LocalExecutor` → DB-ENV falsch/fehlt
- `Broken DAG` / `ImportError` → DAG oder Dependency

3) Mounts prüfen:
```bash
docker exec -it airflow-docker_v1-airflow-scheduler-1 ls /opt/airflow/dags
docker exec -it airflow-docker_v1-airflow-webserver-1 ls /opt/airflow/logs
```

4) Init-Status prüfen:
```bash
docker ps -a | grep airflow-init
```
- Erwartet: `Exited (0)`

---

## 11) Warum init/scheduler/webserver gleiche Environment brauchen

Airflow ist verteilt:
- jeder Container liest seine Config selbst
- wenn der Init Container die DB initialisiert, muss er auf **dieselbe Metadb** zeigen wie scheduler/webserver
- wenn scheduler auf SQLite fällt, aber webserver auf Postgres → UI läuft evtl., scheduler crasht
- wenn executor inkonsistent ist → Import-/Config-Fehler

Merksatz:
> **Airflow-Konfiguration ist pro Container – nicht global.**  
> **Init, Scheduler, Webserver müssen dieselben Kern-Settings teilen** (Executor + Metadb-Conn).

---

## 12) Optional: „sauberer“ als `_PIP_ADDITIONAL_REQUIREMENTS`

Für schnelle Tests ok:
- `_PIP_ADDITIONAL_REQUIREMENTS: requests`

Best practice (später):
- eigenes Dockerfile + requirements.txt
- reproduzierbar, kontrollierte Dependencies

---

Ende.
