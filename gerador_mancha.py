import os
import numpy as np
import rasterio
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
import pandas as pd

# --- CONFIGURAÇÃO ---
# Alterado para o novo arquivo que você subiu
MDT_FILE = 'MDT_GENESIS.tif'  
CSV_FILE = 'barragens.csv'  
RAIO_M = 15000.0           
OUTPUT_DIR = 'manchas_output'

def processar():
    if not os.path.exists(MDT_FILE):
        print(f"❌ Arquivo MDT '{MDT_FILE}' não encontrado!")
        return
    if not os.path.exists(CSV_FILE):
        print(f"❌ Arquivo CSV '{CSV_FILE}' não encontrado!")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with rasterio.open(MDT_FILE) as src:
        dem = src.read(1)
        # Cria malha de coordenadas baseada no arquivo TIF (UTM)
        cols, rows = np.meshgrid(np.arange(dem.shape[1]), np.arange(dem.shape[0]))
        xs, ys = rasterio.transform.xy(src.transform, rows, cols)
        xs = np.array(xs)
        ys = np.array(ys)

        df = pd.read_csv(CSV_FILE)

        for index, row in df.iterrows():
            nome = str(row['nome']).replace(" ", "_")
            # Usa as colunas utm_x e utm_y do seu CSV
            x_barragem, y_barragem = row['utm_x'], row['utm_y']
            cota_m20 = row['cota_ruptura']
            cota_m50 = cota_m20 + 2.0  # Margem de segurança IPT
            
            print(f"-> Processando: {nome} | Cota Ruptura: {cota_m20}m")

            # Cálculo de distância real em metros (UTM)
            dist = np.sqrt((xs - x_barragem)**2 + (ys - y_barragem)**2)

            for cota, label in [(cota_m20, 'M20'), (cota_m50, 'M50')]:
                # Máscara: pixels abaixo da cota, maiores que zero e dentro do raio de 15km
                mask = (dem <= cota) & (dem > 0) & (dist <= RAIO_M)
                
                if np.any(mask):
                    gen = shapes(mask.astype('int16'), mask=mask, transform=src.transform)
                    geoms = [shape(s) for s, v in gen if v == 1]
                    
                    if geoms:
                        gdf = gpd.GeoDataFrame(geometry=geoms, crs=src.crs)
                        nome_saida = f'{OUTPUT_DIR}/Mancha_{nome}_{label}.geojson'
                        gdf.to_file(nome_saida, driver='GeoJSON')
                        print(f"   ✅ Gerado: {nome_saida}")
                else:
                    print(f"   ⚠️ Nenhuma área inundada encontrada para {nome} na cota {cota}")

if __name__ == "__main__":
    processar()
