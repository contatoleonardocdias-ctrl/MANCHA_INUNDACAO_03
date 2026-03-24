import rasterio
import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
import contextily as cx
from shapely.geometry import Point, box
import requests
import os
import sys
from rasterio.features import shapes
from rasterio.mask import mask as rio_mask

# --- CONFIGURAÇÃO (Amarrada aos seus dados de Ituverava) ---
ID_DRIVE = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su" 
MDE_LOCAL = "data/mde.tif"
CSV_LOCAL = "barragens.csv"
OUTPUT_DIR = "output"
DISTANCIA_VALE = 4500 # Metros a jusante
# -----------------------------------------------------------

def baixar_mde(url, destino):
    if not os.path.exists('data'): os.makedirs('data')
    if not os.path.exists(destino):
        print("Iniciando download do MDE...")
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(destino, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
        print("Download do MDE concluído.")

def processar(row):
    # Usa os nomes de colunas do seu CSV real
    nome = str(row['nome_barragem']).strip().replace(" ", "_")
    cota = float(row['cota_ruptura'])
    x, y = float(row['x_utm']), float(row['y_utm'])
    eps
