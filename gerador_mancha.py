import rasterio
import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
import contextily as cx
from shapely.geometry import Point, box
import requests
import os
import sys
from rasterio.features import shapes
from rasterio.mask import mask as rio_mask

# --- CONFIGURAÇÃO ---
ID_DRIVE = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su" 
MDE_LOCAL = "data/mde.tif"
CSV_LOCAL = "barragens.csv"
OUTPUT_DIR = "output" # Pasta que o GitHub vai procurar
# --------------------

# GARANTIA: Cria a pasta antes de qualquer coisa
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def baixar_mde(url, destino):
    if not os.path.exists('data'): os.makedirs('data')
    if not os.path.exists(destino):
        print("Baixando MDE...")
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(destino, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): f.write(chunk)

def processar(row):
    nome = str(row['nome_barragem']).strip().replace(" ", "_")
    cota = float(row['cota_ruptura'])
    x, y = float(row['x_utm']), float(row['y_utm'])
    epsg_origem = int(row['epsg'])

    with rasterio.open(MDE_LOCAL) as src:
        # Área de foco ampliada
        area_foco = box(x - 2000, y - 5000, x + 2000, y + 2000)
        
        try:
            out_image, out_transform = rio_mask(src, [area_foco], crop=True)
            raster = out_image[0]
            
            # Filtro de inundação
            mask = ((raster <= cota) & (raster > 0)).astype('int16')
            results = ({'properties': {'cota': cota}, 'geometry': s}
                       for i, (s, v) in enumerate(shapes(mask, mask=(mask == 1), transform=out_transform)))
            
            # FIX: Seta o CRS explicitamente (resolve o erro da imagem 0cf851)
            gdf_mancha = gpd.GeoDataFrame.from_features(list(results), crs=src.crs)
            
            if gdf_mancha.empty:
                print(f"Aviso: Mancha vazia para {nome}. Criando ponto de referência.")
                gdf_mancha = gpd.GeoDataFrame({'geometry': [Point(x, y).buffer(100)]}, crs=src.crs)

            ponto_gdf = gpd.GeoDataFrame({'geometry': [Point(x, y)]}, crs=f"EPSG:{epsg_origem}").to_crs(epsg=3857)
            gdf_mancha_3857 = gdf_mancha.to_crs(epsg=3857)

            fig, ax = plt.subplots(figsize=(12, 10))
            gdf_mancha_3857.plot(ax=ax, color='#00FFFF', alpha=0.45)
            gdf_mancha_3857.boundary.plot(ax=ax, color='blue', linewidth=0.5)
            ponto_gdf.plot(ax=ax, color='red', markersize=150, marker='X')

            try:
                cx.add_basemap(ax, source=cx.providers.Esri.WorldImagery, zoom=15)
            except: pass

            plt.title(f"Simulação de Inundação: {nome} (Cota {cota}m)")
            plt.savefig(f"{OUTPUT_DIR}/Relatorio_{nome}.pdf", bbox_inches='tight')
            plt.close()
            print(f"✅ PDF salvo em {OUTPUT_DIR}")

        except Exception as e:
            print(f"Erro ao processar {nome}: {e}")

if __name__ == "__main__":
    try:
        baixar_mde(f"https://docs.google.com/uc?export=download&id={ID_DRIVE}", MDE_LOCAL)
        df = pd.read_csv(CSV_LOCAL)
        df.columns = df.columns.str.strip().str.lower()
        for _, row in df.iterrows():
            processar(row)
    except Exception as e:
        print(f"Erro fatal: {e}")
