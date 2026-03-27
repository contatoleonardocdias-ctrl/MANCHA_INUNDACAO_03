import os
import pandas as pd
import numpy as np
import rasterio
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
import gdown

# --- CONFIGURAÇÕES ---
ID_MDE_PADRAO = '1wijgoCGYzWcYplEqV0lewgh_xjjaimvf'
OUTPUT_DIR = 'manchas_output'
LAMINA_CHEIA_M50 = 2.0  # metros extras para o cenário M-50 (Ruptura + Cheia)

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def baixar_mde(file_id):
    """Baixa o MDE do Google Drive."""
    output = "terreno_estudo.tif"
    if not os.path.exists(output):
        print(f"Baixando MDE do Drive...")
        url = f'https://drive.google.com/uc?id={file_id}'
        gdown.download(url, output, quiet=False)
    return output

def gerar_manchas(row):
    nome = row['nome_barragem']
    mde_path = baixar_mde(ID_MDE_PADRAO)
    cota_m20 = row['cota_ruptura']
    x, y = row['x_utm'], row['y_utm']
    distancia_limite = row['distancia_km'] * 1000 

    with rasterio.open(mde_path) as src:
        dem = src.read(1)
        transform = src.transform
        crs = src.crs
        
        # 1. Definição de Cotas (M-20 e M-50)
        cota_m50 = cota_m20 + LAMINA_CHEIA_M50

        # 2. Máscaras de Inundação
        # Filtra valores inválidos do MDE (geralmente negativos ou zero)
        mask_base = (dem > -100) & (dem < 10000)
        
        # 3. Limite de 6km (Distância Euclidiana das coordenadas UTM)
        cols, rows_idx = np.meshgrid(np.arange(dem.shape[1]), np.arange(dem.shape[0]))
        xs, ys = rasterio.transform.xy(transform, rows_idx, cols)
        dist_matrix = np.sqrt((np.array(xs) - x)**2 + (np.array(ys) - y)**2)
        
        # Aplica lógica de cota + distância
        mask_m20 = (dem <= cota_m20) & mask_base & (dist_matrix <= distancia_limite)
        mask_m50 = (dem <= cota_m50) & mask_base & (dist_matrix <= distancia_limite)

        # 4. Vetorização para GeoJSON (Abrir no QGIS)
        for mask, sufixo, cota in [(mask_m20, 'M20', cota_m20), (mask_m50, 'M50', cota_m50)]:
            mask_int = mask.astype('int16')
            shape_gen = shapes(mask_int, mask=mask, transform=transform)
            geoms = [shape(s) for s, v in shape_gen if v == 1]
            
            if geoms:
                gdf = gpd.GeoDataFrame(geometry=geoms, crs=crs)
                gdf['barragem'] = nome
                gdf['cenario'] = sufixo
                gdf['cota_ref'] = cota
                output_file = f"{OUTPUT_DIR}/{nome.replace(' ', '_')}_{sufixo}.geojson"
                gdf.to_file(output_file, driver='GeoJSON')
                print(f"Sucesso: {output_file}")

if __name__ == "__main__":
    if os.path.exists('barragens.csv'):
        df = pd.read_csv('barragens.csv')
        for _, row in df.iterrows():
            try:
                gerar_manchas(row)
            except Exception as e:
                print(f"Erro ao processar {row.get('nome_barragem', 'Desconhecida')}: {e}")
    else:
        print("Arquivo barragens.csv não encontrado.")
