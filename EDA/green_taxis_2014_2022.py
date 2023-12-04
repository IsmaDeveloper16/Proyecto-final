# -*- coding: utf-8 -*-
"""green_taxis_2014-2022.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1zIgNydMtICb8Hc8AF6Q3W5uYs_5FjXGq
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import re
from datetime import datetime

import matplotlib.pyplot as plt
import seaborn as sns

"""# Variables iniciales

Creamos las variables que van a contener los links de los datasets en la pagina de NYC OpenData y los nombres de los buckets del GCP donde cargar el archivo final.
"""

url_taxis = 'https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page'
green_link = 'https://d37ci6vzurychx.cloudfront.net/trip-data/green_tripdata_'

"""# Distritos

Leemos el CSV que contiene todo el listado de distritos de Nueva York para poder complementar nuestra tabla inicial.
"""

boroughs_ny = pd.read_csv('/content/drive/MyDrive/Nati/Henry/PF - NYC Taxis/Sources/Taxis-NY/taxi+_zone_lookup.csv')

"""# Funciones

def get_parquet_links(url, link, rango): Función para obtener los enlaces de descarga de archivos
"""

def get_parquet_links(url, link, rango):
    response = requests.get(url)
    parquet_links = []
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', href=True)
        for i in rango:
            link_str = str(link)
            parquet_links.extend([link['href'] for link in links if '.parquet' in link['href'] and link['href'].startswith(link_str + str(i))])
    return parquet_links

"""def descarga_df(parquet_link): Funcion que me descarga el df desde el origen, con un pequeño filtro segun el año y mes que indica el nombre del archivo."""

def descarga_df(parquet_link):
  file_response = requests.get(parquet_link)
  if file_response.status_code == 200:
    with open('archivo.parquet', 'wb') as f:
      f.write(file_response.content)

    # Leer el archivo Parquet usando pandas
    df = pd.read_parquet('archivo.parquet')

    # Se extrae el mes y año de la info del archivo para luego poder filtrar el dataset
    if parquet_link.endswith('.parquet'):
      year_month = parquet_link.split('_')[-1].split('.')[0]  # Extraer el año y mes desde el nombre del archivo
      year_month_date = pd.to_datetime(year_month, format='%Y-%m')
      year = year_month_date.year
      month = year_month_date.month

    # Filtramos el dataset para que unicamente tenga la informacion del mes correcto
    df['lpep_pickup_datetime'] = pd.to_datetime(df['lpep_pickup_datetime'])
    df = df[(df['lpep_pickup_datetime'].dt.year == year) & (df['lpep_pickup_datetime'].dt.month == month)]
    return df

  else:
    print("No se pudo descargar el archivo Parquet")

"""def filtrar_df(df): Funcion que me realiza ciertos filtros al dataframe"""

def filtrar_df(df):
  # Rellenamos las columnas clave
  df['trip_distance'].fillna(0, inplace=True)
  df['fare_amount'].fillna(0, inplace=True)
  df['passenger_count'].fillna(1, inplace=True)

  # Realizamos filtros basicos para normalizar las columnas
  df = df[(df['trip_distance'] > 0) & (df['trip_distance'] <= 20)]
  df = df[(df['PULocationID'] != 264) & (df['DOLocationID'] != 265)]
  df = df[(df['fare_amount'] > 0) & (df['fare_amount'] < 100)]
  df['passenger_count'] = df['passenger_count'].replace(0, 1)
  df['mta_tax'] = 0.5

  # Convertir valores negativos a positivos en columnas numéricas
  columnas_numericas = df.select_dtypes(include='number')
  df[columnas_numericas.columns] = df[columnas_numericas.columns].abs()

  return df

"""def groupby_df(df): Funcion que me agrupa según el dia y hora de recogida del viaje, ademas de el punto de partida y el punto final del recorrido y por ultimo el tipo de pago que se realiza."""

def groupby_df(df):
  # Merge para saber los boroughs, tanto de pickup como de dropoff
  df_unificado = pd.merge(df, boroughs_ny, left_on='PULocationID', right_on='LocationID', how='left')
  df_unificado = df_unificado.drop(columns=['VendorID','lpep_dropoff_datetime','store_and_fwd_flag', 'LocationID', 'Zone', 'service_zone'], axis=1)
  df_unificado.rename(columns={'Borough': 'pickup_borough'}, inplace=True)
  df_unificado = pd.merge(df_unificado, boroughs_ny, left_on='DOLocationID', right_on='LocationID', how='left')
  df_unificado.drop(columns=['LocationID', 'Zone','service_zone'],axis=1 ,inplace=True)
  df_unificado.rename(columns={'Borough': 'dropoff_borough'}, inplace=True)

  # Agregamos la columna pickup_day y pickup_hour para agrupar
  df_unificado['pickup_day'] = df_unificado['lpep_pickup_datetime'].dt.date
  df_unificado['pickup_hour'] = df_unificado['lpep_pickup_datetime'].dt.hour

  df_unificado['pickup_day'] = pd.to_datetime(df_unificado['pickup_day']).dt.strftime('%Y-%m-%d')

  # Agrupamos segun el dia, hora, borough de pickup y de dropoff y la forma de pago
  df_parcial = df_unificado.groupby(['pickup_day', 'pickup_hour', 'pickup_borough', 'dropoff_borough', 'trip_type','payment_type']).agg({
    'lpep_pickup_datetime': 'count',
    'passenger_count': 'sum',
    'trip_distance': 'sum',
    'fare_amount': 'sum',
    'extra': 'sum',
    'mta_tax': 'sum',
    'tip_amount': 'sum',
    'tolls_amount': 'sum',
    'improvement_surcharge': 'sum',
    'total_amount': 'sum',
    'congestion_surcharge': 'sum'
    }).reset_index()

  df_parcial['pickup_day'] = pd.to_datetime(df_parcial['pickup_day'])

  df_parcial.columns = ['pickup_day', 'pickup_hour', 'pickup_borough', 'dropoff_borough', 'trip_type', 'payment_type', 'total_trips', 'passenger_count', 'total_distance', 'fare_amount', 'extra_hour', 'tax', 'tip_amount', 'tolls_amount', 'improvement_surcharge', 'total_amount', 'congestion_surcharge']

  # Estandarizamos el tipo de dato
  columnas_int = ['trip_type', 'payment_type', 'total_trips', 'passenger_count']
  columnas_float = [ 'total_distance', 'fare_amount', 'extra_hour', 'tax', 'tip_amount', 'tolls_amount', 'improvement_surcharge', 'total_amount', 'congestion_surcharge']
  df_parcial[columnas_int] = df_parcial[columnas_int].astype(int)
  df_parcial[columnas_float] = df_parcial[columnas_float].astype(float)

  return df_parcial  # Devuelve el DataFrame leído desde el archivo Parquet

"""def concatenar_archivos(links): Funcion que concatena todos los dataframes que nos devuelve la funcion etl_dataset(parquet_link)"""

def concatenar_archivos(links):
  green_dfs = []

  for parquet_link in links:
      df_1 = descarga_df(parquet_link)
      df_2 = filtrar_df(df_1)
      df_parcial = groupby_df(df_2)
      green_dfs.append(df_parcial)

  # Concatenar todos los DataFrames fuera del bucle
  green_parcial = pd.concat(green_dfs).reset_index(drop=True)
  return green_parcial

"""def concatenar_dataframes(dataframes): Funcion que me une todos los datasets armados previamente."""

def concatenar_dataframes(dataframes):
  green_dfs = []

  for df in dataframes:
      green_dfs.append(df)

  # Concatenar todos los DataFrames fuera del bucle
  green_completo = pd.concat(green_dfs).reset_index(drop=True)
  return green_completo

"""# Green Taxis 2014-2022
Obtenemos los links de todos los archivos por año, en este caso decidimos separarlo primero por año ya que automatizarlo implicaba un costo de memoria RAM que supera el límite.
"""

green_link_2014 = get_parquet_links(url_taxis, green_link, range(2014,2015))
green_link_2015 = get_parquet_links(url_taxis, green_link, range(2015,2016))
green_link_2016 = get_parquet_links(url_taxis, green_link, range(2016,2017))
green_link_2017 = get_parquet_links(url_taxis, green_link, range(2017,2018))
green_link_2018 = get_parquet_links(url_taxis, green_link, range(2018,2019))
green_link_2019 = get_parquet_links(url_taxis, green_link, range(2019,2020))
green_link_2020 = get_parquet_links(url_taxis, green_link, range(2020,2021))
green_link_2021 = get_parquet_links(url_taxis, green_link, range(2021,2022))
green_link_2022 = get_parquet_links(url_taxis, green_link, range(2022,2023))
green_link_2023 = get_parquet_links(url_taxis, green_link, range(2023,2024))

"""Hacemos el mismo procedimiento para cada año por separado, para evitar colapsar la memoria RAM, y descargando un archivo .csv de cada año."""

green_2014 = concatenar_archivos(green_link_2014)

green_2014.to_csv('green_2014.csv', index=False)

green_2015 = concatenar_archivos(green_link_2015)

green_2015.to_csv('green_2015.csv', index=False)

green_2016 = concatenar_archivos(green_link_2016)

green_2016.to_csv('green_2016.csv', index=False)

green_2017 = concatenar_archivos(green_link_2017)

columnas_numericas = green_2017.select_dtypes(include='number')

filas_con_negativos = green_2017[(columnas_numericas < 0).any(axis=1)]
filas_con_negativos

green_2017.to_csv('green_2017.csv', index=False)

green_2018 = concatenar_archivos(green_link_2018)

columnas_numericas = green_2018.select_dtypes(include='number')

filas_con_negativos = green_2018[(columnas_numericas < 0).any(axis=1)]
filas_con_negativos

green_2018.to_csv('green_2018.csv', index=False)

green_2019 = concatenar_archivos(green_link_2019)

columnas_numericas = green_2019.select_dtypes(include='number')

filas_con_negativos = green_2019[(columnas_numericas < 0).any(axis=1)]
filas_con_negativos

green_2019.to_csv('green_2019.csv', index=False)

green_2020 = concatenar_archivos(green_link_2020)

green_2020.to_csv('green_2020.csv', index=False)

green_2021 = concatenar_archivos(green_link_2021)

green_2021.to_csv('green_2021.csv', index=False)

green_2022 = concatenar_archivos(green_link_2022)

green_2022.to_csv('green_2022.csv', index=False)

green_link_2023

green_2023 = concatenar_archivos(green_link_2023)

green_2023['pickup_day'].dt.month.unique()

ppp = pd.read_parquet('green_tripdata_2023-03.parquet')

qqq = pd.read_parquet('green_tripdata_2023-05.parquet')

rrr = pd.read_parquet('green_tripdata_2023-07.parquet')

sss = pd.read_parquet('green_tripdata_2023-08.parquet')

ttt = pd.read_parquet('green_tripdata_2023-09.parquet')

qqq.head(2)

# Convertir valores negativos a positivos en columnas numéricas
columnas_numericas = ttt.select_dtypes(include='number')
ttt[columnas_numericas.columns] = ttt[columnas_numericas.columns].abs()

# Merge para saber los boroughs, tanto de pickup como de dropoff
df_unificado = pd.merge(ttt, boroughs_ny, left_on='PULocationID', right_on='LocationID', how='left')
df_unificado = df_unificado.drop(columns=['VendorID','lpep_dropoff_datetime','store_and_fwd_flag', 'LocationID', 'Zone', 'service_zone'], axis=1)
df_unificado.rename(columns={'Borough': 'pickup_borough'}, inplace=True)
df_unificado = pd.merge(df_unificado, boroughs_ny, left_on='DOLocationID', right_on='LocationID', how='left')
df_unificado.drop(columns=['LocationID', 'Zone','service_zone'],axis=1 ,inplace=True)
df_unificado.rename(columns={'Borough': 'dropoff_borough'}, inplace=True)

# Agregamos la columna pickup_day y pickup_hour para agrupar
df_unificado['pickup_day'] = df_unificado['lpep_pickup_datetime'].dt.date
df_unificado['pickup_hour'] = df_unificado['lpep_pickup_datetime'].dt.hour

df_unificado['pickup_day'] = pd.to_datetime(df_unificado['pickup_day']).dt.strftime('%Y-%m-%d')

# Agrupamos segun el dia, hora, borough de pickup y de dropoff y la forma de pago
df_parcial = df_unificado.groupby(['pickup_day', 'pickup_hour', 'pickup_borough', 'dropoff_borough', 'trip_type','payment_type']).agg({
  'lpep_pickup_datetime': 'count',
  'passenger_count': 'sum',
  'trip_distance': 'sum',
  'fare_amount': 'sum',
  'extra': 'sum',
  'mta_tax': 'sum',
  'tip_amount': 'sum',
  'tolls_amount': 'sum',
  'improvement_surcharge': 'sum',
  'total_amount': 'sum',
  'congestion_surcharge': 'sum'
  }).reset_index()

df_parcial['pickup_day'] = pd.to_datetime(df_parcial['pickup_day'])

df_parcial.columns = ['pickup_day', 'pickup_hour', 'pickup_borough', 'dropoff_borough', 'trip_type', 'payment_type', 'total_trips', 'passenger_count', 'total_distance', 'fare_amount', 'extra_hour', 'tax', 'tip_amount', 'tolls_amount', 'improvement_surcharge', 'total_amount', 'congestion_surcharge']

# Estandarizamos el tipo de dato
columnas_int = ['trip_type', 'payment_type', 'total_trips', 'passenger_count']
columnas_float = [ 'total_distance', 'fare_amount', 'extra_hour', 'tax', 'tip_amount', 'tolls_amount', 'improvement_surcharge', 'total_amount', 'congestion_surcharge']
df_parcial[columnas_int] = df_parcial[columnas_int].astype(int)
df_parcial[columnas_float] = df_parcial[columnas_float].astype(float)

# Filtramos el dataset para que unicamente tenga la informacion del mes correcto
ttt = df_parcial[(df_parcial['pickup_day'].dt.year == 2023) & (df_parcial['pickup_day'].dt.month == 9)]

"""Hacemos un listado de todos los dataframes que creamos y luego ejecutamos la funcion anterior."""

green_df = [green_2014, green_2015, green_2016, green_2017, green_2018, green_2019, green_2020, green_2021, green_2022, green_2023, ppp, qqq, rrr, sss, ttt]

"""Concatenarmos todos los dataframes en uno solo y lo descargamos tipo .parquet"""

green_completo = concatenar_dataframes(green_df)

green_completo

green_completo.to_parquet('/content/drive/MyDrive/Nati/Henry/PF - NYC Taxis/Sources/Taxis-NY/green_ultimo.parquet', index=False)

green_completo.to_csv('/content/drive/MyDrive/Nati/Henry/PF - NYC Taxis/Sources/Taxis-NY/green_ultimo.csv', index=False)

green_completo.info()

"""# EDA"""

green_completo.describe()

# Asegúrate de que la columna 'pickup_day' sea de tipo datetime
green_completo['pickup_day'] = pd.to_datetime(green_completo['pickup_day'])

# Extraer el año de la columna 'pickup_day'
green_completo['pickup_year'] = green_completo['pickup_day'].dt.year

# Lista de columnas numéricas a graficar
columnas_numericas = ['total_trips', 'total_distance', 'fare_amount']  # Agrega aquí las columnas que deseas graficar

# Crear subgráficos individuales
fig, axs = plt.subplots(len(columnas_numericas), 1, figsize=(10, 6 * len(columnas_numericas)))

for i, columna in enumerate(columnas_numericas):
    # Calcular el total por año para cada columna numérica (excepto 'fare_amount')
    if columna != 'fare_amount':
        total_por_año = green_completo.groupby('pickup_year')[columna].sum()
    else:
        # Calcular el promedio por año para 'fare_amount'
        total_por_año = green_completo.groupby('pickup_year')[columna].mean()

    # Graficar cada columna numérica en su propio subgráfico
    axs[i].plot(total_por_año.index, total_por_año.values, marker='o')
    axs[i].set_title(f'Total por Año - {columna}' if columna != 'fare_amount' else f'Promedio por Año - {columna}')
    axs[i].set_xlabel('Año')
    axs[i].set_ylabel('Total' if columna != 'fare_amount' else 'Promedio')
    axs[i].grid(True)
    axs[i].set_xticks(total_por_año.index)  # Para asegurar que se muestren todos los años en el eje x

plt.tight_layout()
plt.show()

# Matriz de correlación para variables numéricas
correlation_matrix = green_completo.corr()

# Mapa de calor para visualizar la matriz de correlación
plt.figure(figsize=(12, 8))
sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', fmt='.2f')
plt.show()

# Suponiendo que df es tu DataFrame
# Tomar los valores únicos de las columnas categóricas
pickup_borough_counts = green_completo['pickup_borough'].value_counts()
dropoff_borough_counts = green_completo['dropoff_borough'].value_counts()

# Crear el gráfico de barras agrupadas
fig, ax = plt.subplots(figsize=(10, 6))

bar_width = 0.35
index = range(len(pickup_borough_counts))

bar1 = ax.bar(index, pickup_borough_counts, bar_width, label='Pickup Borough')
bar2 = ax.bar([i + bar_width for i in index], dropoff_borough_counts, bar_width, label='Dropoff Borough')

ax.set_xlabel('Boroughs')
ax.set_ylabel('Counts')
ax.set_title('Counts of Trips by Pickup and Dropoff Borough')
ax.set_xticks([i + bar_width / 2 for i in index])
ax.set_xticklabels(pickup_borough_counts.index, rotation=45)
ax.legend()

plt.tight_layout()
plt.show()

