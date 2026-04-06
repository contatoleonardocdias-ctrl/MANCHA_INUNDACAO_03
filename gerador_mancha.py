import os
import numpy as np
import rasterio
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
import pandas as pd

# --- CONFIGURAÇÃO ---
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
        cols, rows = np.meshgrid(np.arange(dem.shape[1]), np.arange(dem.shape[0]))
        xs, ys = rasterio.transform.xy(src.transform, rows, cols)
        xs, ys = np.array(xs), np.array(ys)

        # --- CORREÇÃO DO CSV ---
        # Tenta ler com vírgula, se falhar tenta ponto e vírgula
        try:
            df = pd.read_csv(CSV_FILE, sep=None, engine='python')
        except Exception as e:
            print(f"❌ Erro ao ler CSV: {e}")
            return

        # Limpa espaços em branco nos nomes das colunas (ex: " nome" -> "nome")
        df.columns = df.columns.str.strip().str.lower()
        
        # Mapeamento de colunas para garantir que funcione mesmo se o nome variar um pouco
        col_map = {
            'nome': ['nome', 'name', 'barragem'],
            'x': ['utm_x', 'x', 'coord_x', 'longitude'],
            'y': ['utm_y', 'y', 'coord_y', 'latitude'],
            'cota': ['cota_ruptura', 'cota', 'nivel', 'cota_m20']
        }

        for index, row in df.iterrows():
            # Tenta encontrar o valor em possíveis variações de nomes de coluna
            try:
                nome_val = row.get('nome', row.get('name', 'barragem_sem_nome'))
                nome = str(nome_val).replace(" ", "_")
                x_barragem = row['utm_x']
                y_barragem = row['utm_y']
                cota_m20 = float(row['cota_ruptura'])
                cota_m50 = cota_m20 + 2.0
            except KeyError as e:
                print(f"❌ Coluna não encontrada no CSV: {e}")
                print(f"Colunas disponíveis: {list(df.columns)}")
                continue

            print(f"-> Processando: {nome} | Cota: {cota_m20}m")
            dist = np.sqrt((xs - x_barragem)**2 + (ys - y_barragem)**2)

            for cota, label in [(cota_m20, 'M20'), (cota_m50, 'M50')]:
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
                    print(f"   ⚠️ Sem inundação para {nome} na cota {cota}")

if __name__ == "__main__":
    processar()
