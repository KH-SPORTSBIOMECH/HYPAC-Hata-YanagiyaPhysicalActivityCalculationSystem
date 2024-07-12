# -*- coding: utf-8 -*-
"""
Ver. 1.0

@author: KH

In this program, we provide the estimation methods for the physical activity during 
locomotion without distinguishing between running and walking based on the GPS data.
It needs a .fit file of walking and/or running. The .fit file is the activity data 
and can be obtained from some of the smart watch such as Garmin, Caros and thomething.
Use the sample.fit data and try this code.

Most smartwatches can record altitude data, which is also stored in .fit files. 
However, the data can be inaccurate, especially when running in the weather. 
This is probably because the altitude is calculated by the built-in barometric altimeter. 
Therefore, this code has adopted a mechanism to obtain altitude by referencing API data 
from the Geospatial Information Authority (GSI) in Japan via the Internet, based on latitude 
and longitude information recorded by GPS. Note that once over the network, the working speed would be busy. 
Also, since this program uses the API of the GSI in Japan, if you want to use it in another country, 
you will need to use the API of the GSI in your country or use a dataset with linked altitude and latitude/longitude data.
"""


import tkinter
from tkinter import filedialog
import pandas as pd
import numpy as np
import math
from geopy.distance import geodesic
from tqdm import trange
import requests
import fitdecode
#%% FUNCTION
# STEP1 #############################################################################################################################################
# Import the .fit data
def File_Select():
    root = tkinter.Tk()
    root.title("Select File")
    root.geometry("400x30")
    
    idir = "C:/Users/"
    filetype = [("Garmin fit file", ".fit")]
    file_path = filedialog.askopenfilename(filetypes=filetype, initialdir=idir)
    
    root.destroy()
    
    return file_path

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
    ## The coordinates (latitude and longitude) in .fit file are represented in hexadecimal and encoded as 32-bit integers during export.
    ## This fuction is convert 32-bit integers to decimal the latitude and longitude.
    degrees = int_value * (180.0 / 2**31)
    return degrees


# STEP2 #############################################################################################################################################
# get Altitude and dAltitude
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

#Preparete GPS dataset
def getGPSdataset(Data):
    Latitude  = decode_lat_long(Data["position_lat"])
    Longitude = decode_lat_long(Data["position_long"])
    [Altitude, dAltitude] = getAltitude(Latitude, Longitude)

    ## Distance considering the slope
    Distance_list = [0]
    dAltitude_list = []
    for i in range(0,Latitude.size-1):
        location1 = (Latitude.iloc[i], Longitude.iloc[i])
        location2 = (Latitude.iloc[i+1], Longitude.iloc[i+1])
        distance_i = round((geodesic(location1, location2).km), 10)

        dAltitude_i = (Altitude[i+1] - Altitude[i])/1000 # (km)
        dAltitude_list.append(dAltitude_i)

        Distance_c_i = math.sqrt(distance_i**2 + dAltitude_i**2)
        Distance_list.append(Distance_c_i)

    #Distance_list.append(0)
    TotalDistance = float(pd.DataFrame(Distance_list).sum().values) #(km)

    print(pd.DataFrame(Distance_list).size)

    GPS_dataset = pd.DataFrame({
        "Latitude": Latitude,
        "Longitude": Longitude,
        "Altitude (km)": Altitude/1000,
        "dAltitude (km)": dAltitude/1000,
        "Distance (km)": Distance_list,
        "dTime (s)": Data['timestamp'].diff().dt.total_seconds(),
        "dTime (min)": Data['timestamp'].diff() / pd.Timedelta('1 minutes'),
        "dTime (h)": Data['timestamp'].diff() / pd.Timedelta('1 hour')
    })
    
    GPS_dataset[GPS_dataset != GPS_dataset] = 0
    return GPS_dataset


# STEP3 #############################################################################################################################################
def calEnergyExpenditure(GPS_datdaset, BW, REE):
    dTime = GPS_datdaset["dTime (h)"]

    ### Velocity (km/h)
    Velocity = GPS_datdaset["Distance (km)"] / GPS_datdaset["dTime (h)"]

    ### Grade (%)
    Grade = ((GPS_datdaset["dAltitude (km)"]/GPS_datdaset["Distance (km)"])*100).replace([np.inf, -np.inf], np.nan).fillna(0)

    VO2rate_GRADE_list = []
    Grade_factor_list = []
    RUNorWALK = []
    METs_raw_list = []
    METs_list = []
    VO2_list = []
    EnergyExpenditure_list = []
    for i in trange(0, Velocity.size):
        ### STEP1: Velocity ###################################################################################
        def Velocity_METs(Velocity):
            # Regression equation fractionated at low and high speed, 
            # speed intersected is set at 8.689214 km/h from the relationship between lnMETs and running speed.
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

        METs_Velocity_i = Velocity_METs(Velocity[i])


        ### STEP2: Grade ######################################################################################
        """
        Relationship between VO2 and Grade
        Based on Minetti et al., 2002, J Appl Physiol 93
        """
        def VO2_GRADE(GRADE):
            a = 0.00136524
            b = 0.051921
            c = 1

            # 傾斜に対するVO2増加率
            VO2_GRADE = a * GRADE**2 + b * GRADE + c
            VO2_GRADE0 = a * 0**2 + b * 0 + c

            VO2rate_GRADE = VO2_GRADE / VO2_GRADE0
            VO2_GRADE = pd.DataFrame({"Grade": GRADE,
                                      "VO2": VO2_GRADE,
                                      "VO2 rate": VO2rate_GRADE
                                      })
            return VO2_GRADE

        GRADE = np.arange(-200,200.1)
        VO2rate_GRADE = VO2_GRADE(GRADE)


        if Grade[i] > 200:
          Grade_i = 200
          VO2rate_GRADE_i = float(VO2rate_GRADE.query("Grade==200")["VO2 rate"].values.item())
        elif Grade[i] < -200:
          Grade_i = -200
          VO2rate_GRADE_i = float(VO2rate_GRADE.query("Grade==-200")["VO2 rate"].values.item())
        else:
          Grade_i = round(Grade[i], 0)
          VO2rate_GRADE_i = float(VO2rate_GRADE.query("Grade==@Grade_i")["VO2 rate"].values.item())

          VO2rate_GRADE_list.append(VO2rate_GRADE_i)
        VO2rate_GRADE = pd.DataFrame(VO2rate_GRADE_list)


        ### STEP3: Estimate Enery expediture ###################################################################
        # Multiply METs by the Grade coefficient.
        METs_grade_i = METs_Velocity_i * VO2rate_GRADE_i #(MET) *Taking into account the grade factor
        Grade_factor_list.append(VO2rate_GRADE_i)

        METs_grade_i = float(METs_grade_i)

        METs_raw_list.append(METs_Velocity_i)
        METs_list.append(METs_grade_i)

        VO2_i = (METs_grade_i * REE) #(mL/min/kg)
        VO2_list.append(VO2_i)

        EnergyExpenditure_i = (METs_grade_i * dTime[i]) #(METs*hr)
        EnergyExpenditure_list.append(EnergyExpenditure_i) #(kcal)

    METs = pd.DataFrame(METs_list) #(MET)
    VO2 = pd.DataFrame(VO2_list) #(L/kg/h)
    EnergyExpenditure = pd.DataFrame(EnergyExpenditure_list) #(METs-h)

    RESULTS = pd.DataFrame()
    RESULTS["Velocity(km/h)"] = Velocity
    RESULTS["METs"] = METs_raw_list            #METs estimated from running speed
    RESULTS["METs(cal grade factor)"] = METs   #METs where grade factor is taken into account.
    RESULTS["Grade factor"] = Grade_factor_list
    RESULTS["VO2(mL/min/kg)"] = VO2
    RESULTS["EnergyExpenditure(METs-h)"] = EnergyExpenditure

    RESULTS[RESULTS != RESULTS] = 0
    return RESULTS


#%% SETTING
"""
BodyMass: Body mass including the body weight and all gears (shoes, bagpack, and something like that)
REE: Resting Energy Expenditure (mL/min/kg), default value is set at 3.5 mL/min/kg. 
HEAT: Heat production (kcal), default value is set at 4.85 kcal.
"""
BodyMass = 60
REE  = 3.5
HEAT = 4.85
#%%
Data = pd.DataFrame(GarminDataSet(File_Select())) #Select Garmin data
GPS_dataset = getGPSdataset(Data)
GPS_RESULTS = calEnergyExpenditure(GPS_dataset, BodyMass, REE)
