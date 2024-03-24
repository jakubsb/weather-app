from flask import Flask, render_template, request
from redis import Redis
import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry

app = Flask(__name__)
redis = Redis(host='redis', port=6379)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        redis.incr('clicks')
        coordinates = request.form['coordinates']
        latitude, longitude = map(float, coordinates.split(','))

        cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        openmeteo = openmeteo_requests.Client(session=retry_session)

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
			"daily": ["temperature_2m_max", "temperature_2m_min"],
			"timezone": "Europe/Berlin"
        }
        responses = openmeteo.weather_api(url, params=params)

        response = responses[0]
        coordinates_info = f"Coordinates: {response.Latitude()}°E {response.Longitude()}°N"
        elevation = f"Elevation: {response.Elevation()} m asl"
        timezone = f"Timezone: {response.Timezone().decode()} {response.TimezoneAbbreviation().decode()}"
        #utc_offset = f"Timezone difference to GMT+0: {response.UtcOffsetSeconds()/3600} h"

        daily = response.Daily()
        daily_temperature_2m_max = daily.Variables(0).ValuesAsNumpy()
        daily_temperature_2m_min = daily.Variables(1).ValuesAsNumpy()

        daily_data = {"date": pd.date_range(
            start = pd.to_datetime(daily.Time(), unit = "s"),
            end = pd.to_datetime(daily.TimeEnd(), unit = "s"),
            freq = pd.Timedelta(seconds = daily.Interval()),
            inclusive = "left"
        )}
        daily_data["min temperature [°C]"] = daily_temperature_2m_min
        daily_data["max temperature [°C]"] = daily_temperature_2m_max

        daily_dataframe = pd.DataFrame(data = daily_data)

        clicks = redis.get('clicks')
        if clicks is None:
            clicks = 0
        else:
            clicks = clicks.decode()

        return render_template('index.html', 
                               coordinates=coordinates_info, 
                               elevation=elevation,
                                timezone=timezone, 
                            #    utc_offset=utc_offset, 
                                daily_data=daily_dataframe.to_html(),
                                clicks=clicks)

    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)