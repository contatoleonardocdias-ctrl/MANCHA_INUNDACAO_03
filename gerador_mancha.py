import os
import numpy as np
import rasterio
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
import elevation

# --- CONFIGURAÇÃO BLINDADA (Gênesis I) ---
NOME = 'Genesis_I'
X_UTM, Y_UTM = 309435.0, 7406885.0
COTA_M20 = 745.0
COTA_M50 = 747.0 # M-20 + 2m (Lâmina de cheia fixada)
RAIO_M = 6000.0
ARQUIVO_LOCAL = '23S48_ZN.tif'
ARQUIVO_AUTO = 'mde_srtm.tif'

def obter_mde():
    # 1. Tenta usar o arquivo que você baixou do Topodata
    if os.path.exists(ARQUIVO_LOCAL):
        print(f"-> Usando arquivo local do Topodata: {ARQUIVO_LOCAL}")
        return ARQUIVO_LOCAL
    
    # 2. Se não tiver o local, ele tenta baixar sozinho (NASA/SRTM)
    print("-> Arquivo local não encontrado. Tentando download automático (SRTM)...")
    bounds = (-46.90, -23.48, -46.80, -23.38) # Bbox da região
    elevation.clip(bounds=bounds, output=ARQUIVO_AUTO)
    elevation.clean()
    return ARQUIVO_AUTO

def processar():
    try:
        mde_path = obter_mde()
        with rasterio.open(mde_path) as src:
            dem = src.read(1)
            transform = src.transform
            crs = src.crs
            
            # Matriz de distância para travar nos 6km
            cols, rows = np.meshgrid(np.arange(dem.shape[1]), np.arange(dem.shape[0]))
            xs, ys = rasterio.transform.xy(transform, rows, cols)
            dist = np.sqrt((np.array(xs) - X_UTM)**2 + (np.array(ys) - Y_UTM)**2)
            
            os.makedirs('manchas_output', exist_ok=True)
            
            for cota, label in [(COTA_M20, 'M20'), (COTA_M50, 'M50')]:
                # Lógica: Terreno <= Cota E dentro do raio de 6km
                mask = (dem <= cota) & (dem > 0) & (dist <= RAIO_M)
                
                gen = shapes(mask.astype('int16'), mask=mask, transform=transform)
                geoms = [shape(s) for s, v in gen if v == 1]
                
                if geoms:
                    gdf = gpd.GeoDataFrame(geometry=geoms, crs=crs)
                    gdf['barragem'] = NOME
                    gdf['cenario'] = label
                    gdf.to_file(f'manchas_output/Mancha_{label}.geojson', driver='GeoJSON')
                    print(f" ✅ Gerado: {label}")
    except Exception as e:
        print(f" ❌ Erro no processamento: {e}")

if __name__ == "__main__":
    processar()
