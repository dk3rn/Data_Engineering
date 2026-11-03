"""WSPR Data Ingestion via ClickHouse HTTP API.

Author: Peter Kern
"""

import io
import pandas as pd
import requests

# ClickHouse HTTP endpoint provided by wspr.live
URL = "https://db1.wspr.live/"

# SQL Query targeting the wspr.rx table
# Retrieves the latest 100 spots on the 20m band (band = 14) within the last hour
sql_query = """
SELECT 
    time, 
    tx_sign, 
    tx_loc, 
    rx_sign, 
    rx_loc, 
    band, 
    snr, 
    distance, 
    azimuth
FROM wspr.rx
WHERE time >= now() - INTERVAL 1 HOUR
  AND band = 14
ORDER BY time DESC
LIMIT 100
FORMAT CSVWithNames
"""

# Execute the HTTP GET request against the ClickHouse endpoint
response = requests.get(URL, params={"query": sql_query})
response.raise_for_status()

# Parse the incoming CSV stream directly into a pandas DataFrame
df = pd.read_csv(io.StringIO(response.text))

# Display the first few records
print(df.head())