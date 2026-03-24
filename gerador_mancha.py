import pandas as pd
import geopandas as gpd
import rasterio
import numpy as np
from shapely.geometry import shape
from rasterio.features import shapes
import os
import requests
from pysheds.grid import Grid

# Configurações do Google Drive (Seu link enviado)
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
    # 1. Preparação
    download_mde(FILE_ID, MDE_NOME)
    df = pd.read_csv('barragens.csv')
    row = df.iloc[0]
    x, y = row['x_utm'], row['y_utm']
    cota_ruptura = row['cota_ruptura']
    epsg = int(row['epsg'])

    print(f"Processando ruptura na cota {cota_ruptura}m...")

    # 2. Carregamento e Hidrologia com PySheds
    grid = Grid.from_raster(MDE_NOME, data_name='dem')
    
    # Preenchimento de depressões para não travar o fluxo
    grid.fill_pits(data='dem', out_name='flooded_dem')
    grid.fill_depressions(data='flooded_dem', out_name='final_dem')
    
    # Direção de fluxo (D8)
    grid.flowdir(data='final_dem', out_name='dir')
    
    # 3. Rastreio a Jusante (Downstream Trace)
    # Isso gera uma máscara que "anda" apenas para onde a água corre
    # O trace_downstream garante que não subiremos o morro nem o reservatório
    out_trace = grid.trace_downstream(x=x, y=y, data='dir', max_steps=5000)
    
    # 4. Criação da Mancha de Inundação
    # Combinamos: (Pixels abaixo da cota) + (Pixels na rota de descida)
    dem_data = grid.view('final_dem')
    
    # Lógica: Inunda se a cota for menor que a ruptura E se o pixel estiver 
    # conectado à rota de descida do rio (trace)
    mancha_mask = (dem_data <= cota_ruptura) & (out_trace > 0)
    
    # 5. Vetorização e Salvamento
    transform = grid.view('dem').transform
    resultados = (
        {'properties': {'id': 1}, 'geometry': s}
        for i, (s, v) in enumerate(shapes(mancha_mask.astype('int16'), 
                                         mask=mancha_mask==1, 
                                         transform=transform))
    )
    
    geoms = [shape(res['geometry']) for res in resultados]
    
    if geoms:
        # Criar pasta output se não existir
        if not os.path.exists('output'): os.makedirs('output')
        
        gdf = gpd.GeoDataFrame(geometry=geoms, crs=f"EPSG:{epsg}")
        # Dissolve para unificar a mancha em um polígono limpo
        gdf_dissolved = gdf.dissolve() 
        
        output_path = f"output/{OUTPUT_NAME}.shp"
        gdf_dissolved.to_file(output_path)
        print(f"Sucesso! Arquivo gerado em: {output_path}")
    else:
        print("Erro: Nenhuma mancha gerada. Verifique as cotas no CSV.")

if __name__ == "__main__":
    main()
