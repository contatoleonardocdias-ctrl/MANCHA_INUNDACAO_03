import os
import numpy as np
import rasterio
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
import gdown

# --- VALORES FIXOS (Gênesis I) ---
# ID extraído do seu link: https://drive.google.com/file/d/1wijgoCGYzWcYplEqV0lewgh_xjjaimvf/view
ID_MDE = '1wijgoCGYzWcYplEqV0lewgh_xjjaimvf' 
NOME_BARRAGEM = 'Genesis_I'
X_UTM = 309435.0  #
Y_UTM = 7406885.0 #
COTA_M20 = 745.0  # Cota de Ruptura
COTA_M50 = 747.0  # Ruptura + 2m de Cheia de Projeto
DISTANCIA_LIMITE = 6000.0 # Limite de 6km

OUTPUT_DIR = 'manchas_output'
os.makedirs(OUTPUT_DIR, exist_ok=True)

def baixar_mde():
    output = "terreno_estudo.tif"
    if not os.path.exists(output):
        print(f"-> Baixando MDE do Google Drive...")
        url = f'https://drive.google.com/uc?id={ID_MDE}'
        gdown.download(url, output, quiet=False)
    return output

def gerar_mancha():
    mde_path = baixar_mde()
    
    with rasterio.open(mde_path) as src:
        dem = src.read(1)
        transform = src.transform
        crs = src.crs # EPSG:31983
        
        # Matriz de distâncias para travar em 6km
        cols, rows_idx = np.meshgrid(np.arange(dem.shape[1]), np.arange(dem.shape[0]))
        xs, ys = rasterio.transform.xy(transform, rows_idx, cols)
        dist_matrix = np.sqrt((np.array(xs) - X_UTM)**2 + (np.array(ys) - Y_UTM)**2)
        
        for cota, sufixo in [(COTA_M20, 'M20'), (COTA_M50, 'M50')]:
            print(f" Processando cenário {sufixo} (Cota: {cota}m)...")
            
            # Lógica: Abaixo da cota E dentro do raio de 6km
            mask = (dem <= cota) & (dem > -50) & (dist_matrix <= DISTANCIA_LIMITE)
            mask_int = mask.astype('int16')
            
            shape_gen = shapes(mask_int, mask=mask, transform=transform)
            geoms = [shape(s) for s, v in shape_gen if v == 1]
            
            if geoms:
                gdf = gpd.GeoDataFrame(geometry=geoms, crs=crs)
                gdf['barragem'] = NOME_BARRAGEM
                gdf['cenario'] = sufixo
                
                output_file = os.path.join(OUTPUT_DIR, f"{NOME_BARRAGEM}_{sufixo}.geojson")
                gdf.to_file(output_file, driver='GeoJSON')
                print(f" ✅ Arquivo gerado: {output_file}")
            else:
                print(f" ⚠️ Aviso: Nenhuma área encontrada para {sufixo}.")

if __name__ == "__main__":
    try:
        gerar_mancha()
    except Exception as e:
        print(f" ❌ Erro: {e}")
