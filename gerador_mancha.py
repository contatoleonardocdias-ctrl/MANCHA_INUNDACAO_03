import pandas as pd
import geopandas as gpd
import rasterio
import numpy as np
from shapely.geometry import shape, Point
from rasterio.features import shapes
from scipy.ndimage import binary_dilation
import os
import requests

# Configurações
FILE_ID = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su"
MDE_NOME = "23S48_ZN.tif"
OUTPUT_NAME = "MANCHA_FINAL_ESTAVEL"

def download_mde(id, destination):
    if not os.path.exists(destination):
        print("Baixando MDE do Google Drive...")
        url = f"https://docs.google.com/uc?export=download&id={id}"
        r = requests.get(url, stream=True)
        with open(destination, "wb") as f:
            for chunk in r.iter_content(32768): f.write(chunk)

def main():
    download_mde(FILE_ID, MDE_NOME)
    
    # 1. Dados do CSV
    df = pd.read_csv('barragens.csv')
    row = df.iloc[0]
    x, y, cota_max = row['x_utm'], row['y_utm'], row['cota_ruptura']
    epsg = int(row['epsg'])

    print(f"Processando cota {cota_max}m no EPSG {epsg}...")

    # 2. Abrir MDE e Processar Inundação
    with rasterio.open(MDE_NOME) as src:
        raster = src.read(1)
        nodata = src.nodata
        transform = src.transform

        # Passo A: Máscara de Cota (Tudo abaixo de 745m)
        mask_cota = (raster <= cota_max) & (raster != nodata)

        # Passo B: Limitar a Jusante (Lógica de Conectividade)
        # Identificamos o pixel da barragem
        py, px = src.index(x, y)
        
        # Criamos uma semente (ponto de início)
        seed = np.zeros_like(mask_cota, dtype=bool)
        seed[py, px] = True

        # "Espalhamos" a inundação apenas para pixels conectados que respeitam a cota
        # Isso impede que a água 'pule' para outros vales
        inundacao = np.zeros_like(mask_cota, dtype=bool)
        for _ in range(500): # Número de iterações para 'correr' o rio abaixo
            expandida = binary_dilation(seed, structure=np.ones((3,3)))
            seed = expandida & mask_cota
            inundacao |= seed
            if not seed.any(): break

        # 3. Vetorização
        print("Vetorizando resultados...")
        results = (
            {'properties': {'id': 1}, 'geometry': s}
            for i, (s, v) in enumerate(shapes(inundacao.astype('int16'), 
                                             mask=inundacao==1, 
                                             transform=transform))
        )
        
        geoms = [shape(res['geometry']) for res in resultados]

    if geoms:
        if not os.path.exists('output'): os.makedirs('output')
        gdf = gpd.GeoDataFrame(geometry=geoms, crs=f"EPSG:{epsg}")
        gdf = gdf.dissolve() # Unifica a mancha
        gdf.to_file(f"output/{OUTPUT_NAME}.shp")
        print(f"Sucesso! Salvo em output/{OUTPUT_NAME}.shp")
    else:
        print("Erro: Nenhuma mancha gerada. Verifique as coordenadas.")

if __name__ == "__main__":
    main()
