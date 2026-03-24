import pandas as pd
import geopandas as gpd
import rasterio
import numpy as np
from shapely.geometry import shape
from rasterio.features import shapes
import os
import requests
from pysheds.grid import Grid
from rasterio.crs import CRS

FILE_ID = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su"
MDE_NOME = "23S48_ZN.tif"
OUTPUT_NAME = "MANCHA_REFINADA_FINAL"

def download_mde(id, destination):
    if not os.path.exists(destination):
        print(f"Baixando MDE do Google Drive...")
        url = f"https://docs.google.com/uc?export=download&id={id}"
        session = requests.Session()
        response = session.get(url, stream=True)
        with open(destination, "wb") as f:
            for chunk in response.iter_content(32768):
                if chunk: f.write(chunk)
        print("Download concluído.")

def main():
    download_mde(FILE_ID, MDE_NOME)
    df = pd.read_csv('barragens.csv')
    row = df.iloc[0]
    x, y = row['x_utm'], row['y_utm']
    cota_ruptura = row['cota_ruptura']
    epsg_alvo = int(row['epsg'])

    print(f"Processando ruptura na cota {cota_ruptura}m para EPSG {epsg_alvo}...")

    # Forçar o CRS para evitar o erro de projeção anterior
    with rasterio.open(MDE_NOME, 'r+') as rst:
        rst.crs = CRS.from_epsg(epsg_alvo)
    
    grid = Grid.from_raster(MDE_NOME, data_name='dem')
    
    # CORREÇÃO AQUI: Passando o argumento 'dem' para o fill_pits
    print("Preenchendo depressões...")
    grid.fill_pits(data='dem', out_name='flooded_dem')
    grid.fill_depressions(data='flooded_dem', out_name='final_dem')
    
    print("Calculando direções de fluxo...")
    grid.flowdir(data='final_dem', out_name='dir')
    
    # Rastreio a Jusante para garantir que siga o rio
    print("Rastreando fluxo a jusante...")
    out_trace = grid.trace_downstream(x=x, y=y, data='dir', max_steps=5000)
    
    dem_data = grid.view('final_dem')
    # Lógica: Abaixo da cota E conectado ao fluxo de descida
    mancha_mask = (dem_data <= cota_ruptura) & (out_trace > 0)
    
    transform = grid.view('dem').transform
    resultados = (
        {'properties': {'id': 1}, 'geometry': s}
        for i, (s, v) in enumerate(shapes(mancha_mask.astype('int16'), 
                                         mask=mancha_mask==1, 
                                         transform=transform))
    )
    
    geometrias = [shape(res['geometry']) for res in resultados]
    
    if geometrias:
        if not os.path.exists('output'): os.makedirs('output')
        gdf = gpd.GeoDataFrame(geometry=geometrias, crs=f"EPSG:{epsg_alvo}")
        gdf_dissolved = gdf.dissolve() 
        output_path = f"output/{OUTPUT_NAME}.shp"
        gdf_dissolved.to_file(output_path)
        print(f"Sucesso! Arquivo gerado em: {output_path}")
    else:
        print("Erro: Nenhuma mancha gerada. Verifique se as coordenadas X/Y estão dentro do MDE.")

if __name__ == "__main__":
    main()
