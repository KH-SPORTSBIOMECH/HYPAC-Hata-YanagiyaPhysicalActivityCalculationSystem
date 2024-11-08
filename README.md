
# **HYPAC: Hata-Yanagiya Physical activity calculation system during walking and running based on the GPS data**

In this program, we provide the estimation methods for the physical activity during locomotion without distinguishing between running and walking based on the GPS data.
It needs a .fit file of walking and/or running. The .fit file is the activity data and can be obtained from some of the smart watch such as Garmin, Caros and something.
Use the sample.fit data and try this code!!

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

The regression equations 1 (gray) and 2 (black) intersect at ln(METs) = 2.21 when the speed is 8.69 km/h. The regression equation for the approximate curve below 8.69 km/h speed (grey) was **ln(METs) = 0.2245・speed + 0.2544**. The coefficient of determination was R2 = 0.98. The regression equation for the approximate curve over 8.69 km/h speed (black) was **ln(METs) = 0.0654・speed + 1.6367**. The coefficient of determination was R2 = 0.99.

*ln(): the natural logarithm

## > **Considering the grade in the course**

STEP2: Calibration of the physical activity by the grade factor.

```python
def VO2_GRADE(GRADE):
    a = 0.00136524
    b = 0.051921
    c = 1
            
    VO2_GRADE = a * GRADE**2 + b * GRADE + c
    VO2_GRADE0 = a * 0**2 + b * 0 + c
            
    VO2rate_GRADE = VO2_GRADE / VO2_GRADE0
            
    VO2_GRADE = pd.DataFrame({"Grade": GRADE,
                              "VO2": VO2_GRADE,
                              "VO2 rate": VO2rate_GRADE
                              })
    return VO2_GRADE
```

![Grade-RunningCost500x385](https://github.com/user-attachments/assets/40ff9fad-e1aa-4f0a-98b0-8a411005310f)


**Fig.2 The relationship between oxygen consumption (Cost) and grade**

The quadratic regression equation was **Cost = 13.6524・10<sup>-4</sup> ・grade<sup>2</sup> + 5.1921・10<sup>-2</sup> ・grade + 1** and the coefficient of determination was R2 = 0.99. This equation was abtained based on the [Minetti et al., 2002](https://journals.physiology.org/doi/full/10.1152/japplphysiol.01177.2001).

## > **Calcurating the VO2 and Energy expenditure**

```python
VO2 = METs * REE #(mL/min/kg)
```

`REE` indicates the resting energy expenditure and is set at 3.5 in default.

 ```python
EnergyExpenditure = VO2 * HEAT * dTime #(METs*hr)
```

`HEAT` indicates the heat production (kcal) and is set at 4.85 in default.


## > **Graphical result output**

In this code you can get the graphical result of the physical activity according to your running course (Fig. 3).

```python

map_center = [GPS_dataset["Latitude"].loc[1], GPS_dataset["Longitude"].loc[1]]

mymap = folium.Map(location=map_center, zoom_start=15.5)

HeatMap(list(zip(GPS_dataset["Latitude"], GPS_dataset["Longitude"], GPS_RESULTS["VO2(mL/min/kg)"])), radius=10, blur=10).add_to(mymap)

mymap.save('/content/sample_data/map_VO2.html')

```

![map](https://github.com/user-attachments/assets/8728c5c9-9e95-40b6-8814-93164b1239e1)

**Fig.3 Grapical result for physical activity during running**

The trajectory indicates the running route, and the red and green colours indicate a higher VO2 and a lower VO2 respectively.
