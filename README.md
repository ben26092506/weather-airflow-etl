📌 Weather Data Pipeline with Apache Airflow

This project implements a production-style ETL pipeline using Apache Airflow, Docker, and PostgreSQL.

The pipeline extracts current weather data from the Open-Meteo API, validates and transforms it, and loads it into a PostgreSQL database in an idempotent and auditable way.

🏗️ Architecture Overview
Open-Meteo API
      |
      v
Extract (Airflow Task)
      |
      v
Transform (Schema + Type Validation)
      |
      v
Load (PostgreSQL, Idempotent)


Core technologies:

Apache Airflow 2.10 (TaskFlow API)

Docker & Docker Compose

PostgreSQL 16

psycopg2

REST API ingestion

🧠 Design Decisions
Why two PostgreSQL databases?

airflow-postgres → Airflow metadata (scheduler, DAG state)

weather-postgres → business data (raw weather records)

This mirrors real-world production setups where orchestration metadata and domain data are separated.

Idempotency & Deduplication

Each weather record uses a business key:

{city}_{observation_time}


This guarantees:

safe re-runs

no duplicate data

deterministic loads

ON CONFLICT (business_key) DO NOTHING

🧪 Data Quality & Validation

The transform step enforces:

schema validation (required fields)

null checks

explicit type casting

timestamp normalization

Invalid data fails fast and does not reach the database.

🗂️ Database Schema (raw_weather)
raw_weather (
  business_key TEXT PRIMARY KEY,
  city TEXT,
  latitude FLOAT,
  longitude FLOAT,
  temperature_c FLOAT,
  wind_speed_kmh FLOAT,
  wind_direction_deg INTEGER,
  weather_code INTEGER,
  observation_time TIMESTAMP,
  ingestion_time TIMESTAMP
)

▶️ How to Run
1. Start the stack
docker compose up -d

2. Open Airflow UI
http://localhost:8080


Login:

user: airflow

password: airflow

3. Trigger the DAG

DAG name:

weather_extract_only

📈 Example Output

Each DAG run inserts only new records and reports:

Inserted X new rows


Inserted rows can be inspected directly in PostgreSQL.

🚀 Possible Extensions

multiple cities

aggregation DAG (daily averages)

monitoring / alerting

downstream analytics layer

👤 Author

Ben
Data Engineering / Analytics Portfolio Project