# Weather Provider Notes

This skill queries a no-key weather stack backed by MET Norway and Nominatim through the plugin executor.

Primary outputs:
- current temperature
- weather condition text
- humidity
- wind speed
- UV index
- short-term daily forecast

The executor resolves city names through geocoding before requesting weather data.
