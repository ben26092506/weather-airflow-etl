CREATE TABLE IF NOT EXISTS raw_weather (
  business_key TEXT PRIMARY KEY,
  city TEXT NOT NULL,
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  temperature_c DOUBLE PRECISION,
  wind_speed_kmh DOUBLE PRECISION,
  wind_direction_deg INTEGER,
  weather_code INTEGER,
  observation_time TIMESTAMPTZ NOT NULL,
  ingestion_time TIMESTAMPTZ NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_raw_weather_city_observation_time
ON raw_weather (city, observation_time);