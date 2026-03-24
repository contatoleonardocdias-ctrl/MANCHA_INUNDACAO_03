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

# Configurações do Google Drive
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
    # 1. Preparação dos Dados
    download_mde(FILE_ID, MDE_NOME)
    df = pd.read_csv('barragens.csv')
    row = df.iloc[0]
    x, y = row['x_utm'], row['y_utm']
    cota_ruptura = row['cota_ruptura']
    epsg_alvo = int(row['epsg'])

    print(f"Processando: Cota {cota_ruptura}m | EPSG {epsg_alvo}")

    # Forçar CRS no arquivo original para evitar erro de cabeçalho
    with rasterio.open(MDE_NOME, 'r+') as rst:
        rst.crs = CRS.from_epsg(epsg_alvo)
    
    # 2. Processamento Hidrológico com PySheds
    grid = Grid.from_raster(MDE_NOME, data_name='dem')
    
    print("Preenchendo depressões (Pits & Depressions)...")
    # Correção da sintaxe: passando 'dem' como primeiro argumento
    grid.fill_pits('dem', out_name='flooded_dem')
    grid.fill_depressions('flooded_dem', out_name='final_dem')
    
    print("Calculando direções de fluxo...")
    grid.flowdir('final_dem', out_name='dir')
    
    # 3. Rastreio a Jusante (Downstream Trace)
    # Isso garante que a mancha siga o leito (linha laranja) e ignore o reservatório
    print("Rastreando fluxo a jusante...")
    # O trace_downstream cria o caminho preferencial da água
    out_trace = grid.trace_downstream(x=x, y=y, data='dir', max_steps=5000)
    
    # 4. Criação da Mancha de Inundação
    dem_data = grid.view('final_dem')
    
    # Lógica: Inunda se (Cota <= Ruptura) E (Está na rota de descida do fluxo)
    # Convertemos out_trace para booleano (onde passou água é True)
    mancha_mask = (dem_data <= cota_ruptura) & (out_trace > 0)
    
    # 5. Vetorização e Salvamento
    transform = grid.view('dem').transform
    # Transformar pixels True em polígonos
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
        # Dissolve para unificar em um único objeto (estilo a imagem de Ituverava)
        gdf_dissolved = gdf.dissolve() 
        
        output_path = f"output/{OUTPUT_NAME}.shp"
        gdf_dissolved.to_file(output_path)
        print(f"SUCESSO: Arquivo gerado em {output_path}")
    else:
        print("ERRO: Nenhuma mancha gerada. Verifique se o ponto X,Y está correto no MDE.")

if __name__ == "__main__":
    main()
