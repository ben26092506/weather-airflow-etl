import requests
from datetime import datetime, timezone
from airflow.decorators import dag, task
from airflow.hooks.base import BaseHook
import psycopg2
from psycopg2.extras import execute_values

@dag(
    dag_id="weather_extract_only",
    start_date=datetime(2025, 1, 1),
    schedule_interval='@hourly',
    catchup=False,
    tags=['weather', 'learning']
)
def weather_extract_only():

    @task
    def extract_weather():
        url = 'https://api.open-meteo.com/v1/forecast'
        params = {
            'latitude': 48.2082,
            'longitude': 16.3738,
            'current_weather': True
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        current_weather = data.get('current_weather')

        if not current_weather:
            raise ValueError('No current_weather in API response')
        
        print('Current weather data:')
        print(current_weather)

        return current_weather
    
    
    @task
    def transform_weather(current_weather: dict,
                          city: str = 'Vienna',
                          latitude: float = 48.2082,
                          longitude: float = 16.3738):
        
        
        # Transforms data which were extracted from Open-Meteo into normalized, load-ready structure
        
        # Check received data
        if not current_weather:
            raise ValueError('No current_weather data received')
        
        if not isinstance(current_weather, dict):
            raise TypeError('current_weather must be a dictionary')
        
        # required schema validation      
        required_fields = ['time', 'temperature', 'windspeed', 'winddirection', 'weathercode']
        for field in required_fields:
            if field not in current_weather:
                raise ValueError(f'Missing key in current_weather: {field}') 

        # value validation
        for field in required_fields:
            if current_weather[field] is None:
                raise ValueError(f'Value is None for key: {field}')
        

        # Type casting + narmalization
        try:
            temperature_c = float(current_weather['temperature'])
            wind_speed_kmh = float(current_weather['windspeed'])
            wind_direction_deg = int(current_weather['winddirection'])
            weather_code = int(current_weather['weathercode'])
        except (TypeError, ValueError) as e:
            raise ValueError(f'Type casting failed: {e}')
        
        try:
            observation_time = datetime.fromisoformat(current_weather['time'].replace('Z', '+00:00'))
        except ValueError as e:
            raise ValueError(f'Invalid time format: {e}')


        # add business key
        business_key = f'{city}_{observation_time.isoformat()}'

        # Final load-ready record
        record = {
            'business_key': business_key,
            'city': city,
            'latitude': latitude,
            'longitude': longitude,
            'temperature_c': temperature_c,
            'wind_speed_kmh': wind_speed_kmh,
            'wind_direction_deg': wind_direction_deg,
            'weather_code': weather_code,
            'observation_time': observation_time,
            'ingestion_time': datetime.now(timezone.utc).isoformat()
        }

        # XCom-safe return
        return [record]
    
    @task
    def load_weather(records: list[dict]):
       
       # check loaded data
       if not records:
           return 0
       
       conn = BaseHook.get_connection('weather_db')

       dsn = (
           f'dbname={conn.schema} user={conn.login} password={conn.password} '
           f'host={conn.host} port={conn.port}'
       )

       rows = []
       for r in records:
           rows.append((
               r['business_key'],
               r['city'],
               r['latitude'],
               r['longitude'],
               r.get('temperature_c'),
               r.get('wind_speed_kmh'),
               r.get('wind_direction_deg'),
               r.get('weather_code'),
               r['observation_time'],
               r['ingestion_time']
           ))
        
       sql = """
        INSERT INTO raw_weather (
          business_key, city, latitude, longitude,
          temperature_c, wind_speed_kmh, wind_direction_deg, weather_code,
          observation_time, ingestion_time
        )
        VALUES %s
        ON CONFLICT (business_key) DO NOTHING
        RETURNING business_key;
        """

       with psycopg2.connect(dsn) as pg:
           with pg.cursor() as cur:
               execute_values(cur, sql, rows)
               inserted = cur.fetchall()

       inserted_count = len(inserted)
       
       print(f'Inserted {inserted_count} new rows')

       return inserted_count
           
           
    weather = extract_weather()

    transformed_weather = transform_weather(weather)

    load_weather(transformed_weather)





weather_extract_only()