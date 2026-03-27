import os
import pandas as pd
import numpy as np
import rasterio
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
import gdown

# --- CONFIGURAÇÕES FIXAS ---
ID_MDE_PADRAO = '1wijgoCGYzWcYplEqV0lewgh_xjjaimvf'
OUTPUT_DIR = 'manchas_output'
LAMINA_CHEIA_M50 = 2.0 

# Garante a criação da pasta de saída
os.makedirs(OUTPUT_DIR, exist_ok=True)

def baixar_mde(file_id):
    output = "terreno_estudo.tif"
    if not os.path.exists(output):
        print(f"-> Baixando MDE do Google Drive (ID: {file_id})...")
        url = f'https://drive.google.com/uc?id={file_id}'
        try:
            gdown.download(url, output, quiet=False)
        except Exception as e:
            print(f"Erro ao baixar do Drive: {e}")
    return output

def gerar_manchas(row):
    nome_original = str(row['nome_barragem'])
    nome_slug = nome_original.replace(' ', '_')
    mde_path = baixar_mde(ID_MDE_PADRAO)
    
    cota_m20 = float(row['cota_ruptura'])
    x, y = float(row['x_utm']), float(row['y_utm'])
    distancia_limite = float(row['distancia_km']) * 1000 

    print(f"\n[Processando: {nome_original}]")
    print(f" Coordenadas: {x}, {y} | Cota Ruptura: {cota_m20}m")

    with rasterio.open(mde_path) as src:
        dem = src.read(1)
        transform = src.transform
        crs = src.crs
        
        # 1. Definir Cotas
        cota_m50 = cota_m20 + LAMINA_CHEIA_M50

        # 2. Criar Máscara de Distância (Raio de 6km)
        cols, rows_idx = np.meshgrid(np.arange(dem.shape[1]), np.arange(dem.shape[0]))
        xs, ys = rasterio.transform.xy(transform, rows_idx, cols)
        dist_matrix = np.sqrt((np.array(xs) - x)**2 + (np.array(ys) - y)**2)
        
        # 3. Gerar Cenários
        for cota, sufixo in [(cota_m20, 'M20'), (cota_m50, 'M50')]:
            # Lógica: Terreno abaixo da cota E dentro do raio de 6km
            mask = (dem <= cota) & (dem > -50) & (dist_matrix <= distancia_limite)
            
            mask_int = mask.astype('int16')
            shape_gen = shapes(mask_int, mask=mask, transform=transform)
            geoms = [shape(s) for s, v in shape_gen if v == 1]
            
            if geoms:
                gdf = gpd.GeoDataFrame(geometry=geoms, crs=crs)
                gdf['barragem'] = nome_original
                gdf['cenario'] = sufixo
                gdf['cota_ref'] = cota
                
                output_file = os.path.join(OUTPUT_DIR, f"{nome_slug}_{sufixo}.geojson")
                gdf.to_file(output_file, driver='GeoJSON')
                print(f" ✅ Gerado: {output_file}")
            else:
                print(f" ⚠️ Aviso: Nenhuma área de inundação encontrada para {sufixo} nesta cota.")

if __name__ == "__main__":
    csv_file = 'barragens.csv'
    if os.path.exists(csv_file):
        df = pd.read_csv(csv_file)
        # Limpeza de colunas (remove espaços invisíveis)
        df.columns = df.columns.str.strip()
        
        for index, row in df.iterrows():
            try:
                gerar_manchas(row)
            except Exception as e:
                print(f" ❌ Erro na linha {index}: {e}")
    else:
        print(f" ❌ Erro: Arquivo {csv_file} não encontrado.")

    # Log final para o GitHub Actions
    arquivos_gerados = os.listdir(OUTPUT_DIR)
    print(f"\n--- Resumo Final ---")
    print(f"Arquivos na pasta {OUTPUT_DIR}: {arquivos_gerados}")
