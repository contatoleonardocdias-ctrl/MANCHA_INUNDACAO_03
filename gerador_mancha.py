import pandas as pd
import geopandas as gpd
import rasterio
import numpy as np
from shapely.geometry import shape
from rasterio.features import shapes
import os
import requests

def download_file_from_google_drive(id, destination):
    print(f"Baixando arquivo do Google Drive (ID: {id})...")
    URL = "https://docs.google.com/uc?export=download"
    session = requests.Session()
    response = session.get(URL, params={'id': id}, stream=True)
    
    with open(destination, "wb") as f:
        for chunk in response.iter_content(32768):
            if chunk: f.write(chunk)
    print("Download concluído.")

def gerar_mancha_por_cota(mde_path, x, y, cota_max):
    with rasterio.open(mde_path) as src:
        raster_data = src.read(1)
        nodata = src.nodata
        mancha_mask = (raster_data <= cota_max) & (raster_data != nodata)
        mancha_mask = mancha_mask.astype('int16')

        resultados = (
            {'properties': {'raster_val': v}, 'geometry': s}
            for i, (s, v) in enumerate(shapes(mancha_mask, mask=mancha_mask==1, transform=src.transform))
        )
        
        geometrias = [shape(res['geometry']) for res in resultados]
        return geometrias

def main():
    # ID do seu arquivo no Drive: 1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su
    FILE_ID = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su"
    MDE_NOME = "23S48_ZN.tif"

    # Baixa o arquivo se ele não existir
    if not os.path.exists(MDE_NOME):
        download_file_from_google_drive(FILE_ID, MDE_NOME)
    
    # Lendo o CSV
    df = pd.read_csv('barragens.csv')
    row = df.iloc[0]
    
    x, y = row['x_utm'], row['y_utm']
    cota = row['cota_ruptura']
    epsg = int(row['epsg'])

    print(f"\nProcessando Inundação: {MDE_NOME} | Cota: {cota}")

    geoms = gerar_mancha_por_cota(MDE_NOME, x, y, cota)

    if geoms:
        gdf = gpd.GeoDataFrame({'id': range(len(geoms))}, geometry=geoms, crs=f"EPSG:{epsg}")
        gdf.to_file("MANCHA_NOVO_03.shp")
        print("Sucesso: Shapefile gerado.")
    else:
        print("Aviso: Nenhuma área inundada encontrada.")

if __name__ == "__main__":
    main()
