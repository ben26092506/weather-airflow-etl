import requests
import pandas as pd
from datetime import datetime, timezone

url = 'https://api.open-meteo.com/v1/forecast'
prarams = {
    'latitude': 48.2082,
    'longitude': 16.3738,
    'current_weather': True}

response = requests.get(url, params=prarams, timeout=10)
data = response.json()
current_weather = data.get('current_weather')


city: str = 'Vienna'
latitude: float = 48.2082
longitude: float = 16.3738
        
        
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
except (TypeError, VallueError) as e:
    raise ValueError(f'Type casting failed: {e}')
        
try:
     observation_time = datetime.fromisoformat(current_weather['time'].replace('Z', '+00:00'))
except ValueError as e:
    raise ValueError(f'Invalid time format: {e}')


        # add business key
business_key = f'{city}_{observation_time.isoformat()}'

        # Final load-ready record
records = {
    'business_key': business_key,
    'city': city,
    'latitude': latitude,
    'longitude': longitude,
    'temperature_°C': temperature_c,
    'wind_speed_kmh': wind_speed_kmh,
    'wind_direction_deg': wind_direction_deg,
    'weather_code': weather_code,
    'observation_time': observation_time,
    'ingestion_time': datetime.now(timezone.utc).isoformat()
        }

        # XCom-safe return
print(records)

rows = []

rows 

df_base = pd.DataFrame()
records_df = pd.DataFrame([records])
pd.concat([df_base, records_df], ignore_index=True)


"""
print('Current weather data:')
print(current_weather)

pd.set_option('display.max_columns', None)

current_weather_df = pd.DataFrame([current_weather])
current_weather_df['date'] = current_weather_df['time'].str.split('T').str[0]
current_weather_df['time_only'] = current_weather_df['time'].str.split('T').str[1]
current_weather_df['time'] = pd.to_datetime(current_weather_df['time'])
current_weather_df['is_day'] = current_weather_df['is_day'].map({1: 'day', 0: 'night'})

print(current_weather_df.info())
print('Current weather data as DataFrame:')
print(current_weather_df)
"""


