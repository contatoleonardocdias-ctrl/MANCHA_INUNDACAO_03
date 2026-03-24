import pandas as pd
import geopandas as gpd
import rasterio
import numpy as np
from shapely.geometry import shape
from rasterio.features import shapes
from scipy.ndimage import binary_dilation
import os
import requests

# 1. ID do arquivo que aparece na sua imagem do Drive
FILE_ID = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su"
MDE_NOME = "23S48_ZN.tif"

def main():
    # Download do MDE
    print("Baixando MDE do Google Drive...")
    url = f"https://docs.google.com/uc?export=download&id={FILE_ID}"
    r = requests.get(url, stream=True)
    with open(MDE_NOME, "wb") as f:
        for chunk in r.iter_content(32768):
            if chunk: f.write(chunk)

    # Lendo os dados do seu CSV (x=309435, y=7406885, cota=743.0)
    df = pd.read_csv('barragens.csv')
    row = df.iloc[0]
    x, y = float(row['x_utm']), float(row['y_utm'])
    # Usando 743.00 conforme a Ficha Técnica da Genesis
    cota_rup = 743.0 

    with rasterio.open(MDE_NOME) as src:
        py, px = src.index(x, y)
        raster = src.read(1)
        nodata = src.nodata

        # Ajuste de ignição: garante que a água 'saia' da barragem
        if raster[py, px] >= cota_rup:
            raster[py, px] = cota_rup - 0.5

        # Criando a máscara de onde a água pode entrar (áreas <= 743m)
        mask = (raster <= cota_rup) & (raster != nodata)
        
        # Algoritmo de propagação conectada (Flood Fill)
        seed = np.zeros_like(mask, dtype=bool)
        seed[py, px] = True
        inundacao = np.zeros_like(mask, dtype=bool)
        
        print("Calculando esparramamento lateral seguindo o talvegue...")
        for i in range(3500): # Aumentado para cobrir mais curso d'água
            expandida = binary_dilation(seed, structure=np.ones((3,3)))
            seed = expandida & mask
            if not seed.any(): break
            inundacao |= seed

        # Gerando as geometrias para o Shapefile
        geoms = [shape(s) for s, v in shapes(inundacao.astype('int16'), 
                                             mask=inundacao==1, 
                                             transform=src.transform)]

    if geoms:
        os.makedirs('output', exist_ok=True)
        gdf = gpd.GeoDataFrame(geometry=geoms, crs="EPSG:31983")
        # Dissolve para criar um polígono único da mancha real
        gdf.dissolve().to_file("output/MANCHA_GENESIS_REAL.shp")
        print("✅ SUCESSO: Shapefile da mancha real gerado!")
    else:
        print("❌ ERRO: O relevo não permitiu a propagação. Verifique o EPSG do MDE.")

if __name__ == "__main__":
    main()
