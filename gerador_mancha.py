import os
import numpy as np
import rasterio
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
import elevation # Biblioteca para download automático

# --- CONFIGURAÇÃO TÉCNICA (Gênesis I) ---
X_UTM, Y_UTM = 309435.0, 7406885.0
COTA_M20 = 745.0
COTA_M50 = 747.0 # M-20 + 2.0m de lâmina de cheia
RAIO_M = 6000.0   # Limite de 6km
ARQUIVO_LOCAL = '23S48_ZN.tif'
ARQUIVO_AUTO = 'mde_srtm_nasa.tif'

def obter_mde():
    # Prioriza o arquivo que você pegou no Topodata
    if os.path.exists(ARQUIVO_LOCAL):
        print(f"-> Usando arquivo local do Topodata: {ARQUIVO_LOCAL}")
        return ARQUIVO_LOCAL
    
    # Se não houver arquivo, baixa automaticamente da NASA
    print("-> Baixando relevo SRTM automaticamente (NASA)...")
    # Bbox aproximada para Santana de Parnaíba/Gênesis I
    bounds = (-46.92, -23.50, -46.78, -23.38) 
    elevation.clip(bounds=bounds, output=ARQUIVO_AUTO)
    elevation.clean()
    return ARQUIVO_AUTO

def gerar_manchas():
    try:
        mde_path = obter_mde()
        with rasterio.open(mde_path) as src:
            dem = src.read(1)
            # Matriz de distância para travar o raio de 6km
            cols, rows = np.meshgrid(np.arange(dem.shape[1]), np.arange(dem.shape[0]))
            xs, ys = rasterio.transform.xy(src.transform, rows, cols)
            dist = np.sqrt((np.array(xs) - X_UTM)**2 + (np.array(ys) - Y_UTM)**2)
            
            os.makedirs('manchas_output', exist_ok=True)
            
            for cota, label in [(COTA_M20, 'M20'), (COTA_M50, 'M50')]:
                # Lógica: Terreno <= Cota E dentro do raio de 6km
                mask = (dem <= cota) & (dem > 0) & (dist <= RAIO_M)
                
                gen = shapes(mask.astype('int16'), mask=mask, transform=src.transform)
                geoms = [shape(s) for s, v in gen if v == 1]
                
                if geoms:
                    gdf = gpd.GeoDataFrame(geometry=geoms, crs=src.crs)
                    gdf.to_file(f'manchas_output/Mancha_{label}.geojson', driver='GeoJSON')
                    print(f" ✅ Sucesso: Cenário {label} gerado!")
    except Exception as e:
        print(f" ❌ Erro: {e}")

if __name__ == "__main__":
    gerar_manchas()
