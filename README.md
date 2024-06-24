
# **Physical activity calculater during walking and running based on the GPS data**

In this program, we provide the estimation methods for the physical activity during locomotion without distinguishing between running and walking based on the GPS data.
It needs a .fit file of walking and/or running. The .fit file is the activity data and can be obtained from some of the smart watch such as Garmin, Caros and thomething.
Use the sample.fit data and try this code.

# Usage
## > **Import .fit data**

In the .fit file, the coordinates (latitude and longitude) are represented in hexadecimal and encoded as 32-bit integers during export.
`decode_lat_long` fuction is convert 32-bit integers to decimal the latitude and longitude as bellow:

```python
def GarminDataSet(file_path):
    datas = []
    with fitdecode.FitReader(file_path) as fit:
        for frame in fit:
    
            if isinstance(frame, fitdecode.FitDataMessage):
                if frame.name == 'record':
                    data = {}
                    for field in frame.fields:
                        data[field.name] = field.value
                        data[field.name + '_units'] = field.units
                    datas.append(data)
    return datas

# decode the coordinations
def decode_lat_long(int_value):
    degrees = int_value * (180.0 / 2**31)
    return degrees
```

## > **Calculate the altitude from latitude and longitude**

Most smartwatches can record altitude data, which is also stored in .fit files. However, the data can be inaccurate, especially when running in the weather. 
This is probably because the altitude is calculated by the built-in barometric altimeter. Therefore, this code has adopted a mechanism to obtain altitude by referencing API data from the Geospatial Information Authority (GSI) in Japan via the Internet, based on latitude and longitude information recorded by GPS. Note that once over the network, the working speed would be busy. Also, since this program uses the API of the GSI in Japan, if you want to use it in another country, you will need to use the `API` of the GSI in your country or use a dataset with linked altitude and latitude/longitude data.

```python
def getAltitude(Latitude, Longitude):
    Altitude_list = []
    dAltitude_list = []
    
    for i in trange(Latitude.size - 1):
        # Note again: It use the network, the operating speed would be busy. 
        API = "http://cyberjapandata2.gsi.go.jp/general/dem/scripts/getelevation.php/?lon=%s&lat=%s&outtype=%s" % (Longitude[i], Latitude[i], "JSON")

        retries = 5
        for _ in range(retries):
            response = requests.get(API)

            if response.status_code == 200:
                try:
                    APIdata = response.json()
                    Altitude_i = APIdata.get("elevation", 0)
                    Altitude_list.append(Altitude_i)
                    break
                except ValueError as e:
                    print(f"ValueError: {e}")

            else:
                print(f"Request failed with status code {response.status_code}")

        else:
            print("All retries failed for API request")
            Altitude_list.append(0)  # Append 0 as default value if all retries fail

    Altitude_list.append(0)
    Altitude = pd.Series(Altitude_list).replace("-----", 0).reset_index(drop=True)
    dAltitude = Altitude.diff().fillna(0)

    return Altitude, dAltitude
```

Network errors may interrupt the programme.
Increasing the value of `retries = 5` would solve it.

## > **Calculate the physical activities**

STEP1: Estimating the METs from walking and/or running speed (Fig.1)

```python
def Velocity_METs(Velocity):
     if Velocity < 8.689214: 
         a = 0.2245
         b = 0.2544
         LnMETs = (a * Velocity + b)
         METs = np.exp(LnMETs)
     else: 
         a = 0.0654
         b = 1.6367
         LnMETs = (a * Velocity + b)
         METs = np.exp(LnMETs)
     return float(METs)
```

![LnMETs-Speed相関関係](https://github.com/KH-SPORTSBIOMECH/HYPAC-Physical-Activity-Calculator/assets/92411916/6dd928b4-858c-4e4d-aa68-f77afbdd843f)

**Fig.1 The relationship between ln(METs) and walking and/or running speed**

The regression equations 1 (gray) and 2 (black) intersect at ln(METs) = 2.21 when the speed is 8.69 km/h. The regression equation for the approximate curve below 8.69 km/h speed (grey) was `ln(METs) = 0.2245 x speed + 0.2544`. The coefficient of determination was R2 = 0.98. The regression equation for the approximate curve over 8.69 km/h speed (black) was `ln(METs) = 0.0654 x speed + 1.6367`. The coefficient of determination was R2 = 0.99.

*ln(): the natural logarithm






















.
