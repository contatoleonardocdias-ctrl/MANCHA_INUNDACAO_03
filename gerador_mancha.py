import rasterio 
import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
import contextily as cx
from shapely.geometry import Point
import requests
import os
import sys
from rasterio.features import shapes

# --- CONFIGURAÇÃO ---
ID_DRIVE = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su" 
MDE_LOCAL = "data/mde.tif"
CSV_LOCAL = "barragens.csv"
OUTPUT_DIR = "output"
CRS_MDE = "EPSG:31983"  # 🔥 DEFINIDO MANUALMENTE
# --------------------

def baixar_mde(url, destino):
    if not os.path.exists('data'):
        os.makedirs('data')
    if not os.path.exists(destino):
        print("Iniciando download do MDE...")
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(destino, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download do MDE concluído.")

def processar(row):
    nome = str(row['nome_barragem']).strip().replace(" ", "_")
    cota = float(row['cota_ruptura'])
    x, y = float(row['x_utm']), float(row['y_utm'])
    epsg_origem = int(row['epsg'])

    with rasterio.open(MDE_LOCAL) as src:
        raster = src.read(1)

        print(f"CRS original do raster: {src.crs}")

        # Gera máscara
        mask = (raster <= cota).astype('int16')

        # Extração de polígonos
        results = (
            {'properties': {'cota': cota}, 'geometry': s}
            for (s, v) in shapes(mask, mask=(mask == 1), transform=src.transform)
        )

        features = list(results)

        if not features:
            print(f"Aviso: Nenhuma mancha gerada para {nome}")
            return

        # 🔥 CRIA GDF SEM CRS E DEFINE MANUALMENTE
        gdf_mancha = gpd.GeoDataFrame.from_features(features)
        gdf_mancha = gdf_mancha.set_crs(CRS_MDE)

        print("CRS mancha definido como:", gdf_mancha.crs)

        # --- PONTO ---
        ponto_original = gpd.GeoDataFrame(
            {'geometry': [Point(x, y)]}, 
            crs=f"EPSG:{epsg_origem}"
        )

        # --- REPROJEÇÃO ---
        gdf_mancha_3857 = gdf_mancha.to_crs(epsg=3857)
        ponto_3857 = ponto_original.to_crs(epsg=3857)

        # --- OUTPUT ---
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)

        # Shapefile
        shp_path = f"{OUTPUT_DIR}/Mancha_{nome}.shp"
        gdf_mancha_3857.to_file(shp_path)

        # PDF
        fig, ax = plt.subplots(figsize=(12, 12))
        gdf_mancha_3857.plot(ax=ax, color='cyan', alpha=0.5, edgecolor='blue', label='Área de Inundação')
        ponto_3857.plot(ax=ax, color='red', marker='X', markersize=200, label='Ponto de Rompimento')

        try:
            cx.add_basemap(ax, source=cx.providers.Esri.WorldImagery)
        except Exception as e:
            print(f"Aviso: Satélite offline ({e})")

        ax.set_title(f"Relatório de Inundação: {nome} (Cota {cota}m)")
        plt.legend()

        path_pdf = f"{OUTPUT_DIR}/Mapa_{nome}.pdf"
        plt.savefig(path_pdf, bbox_inches='tight')
        plt.close()

        print(f"Sucesso: {path_pdf} gerado.")

if __name__ == "__main__":
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    url = f"https://docs.google.com/uc?export=download&id={ID_DRIVE}"
    
    try:
        baixar_mde(url, MDE_LOCAL)

        df = pd.read_csv(CSV_LOCAL)
        df.columns = df.columns.str.strip().str.lower()

        for _, row in df.iterrows():
            processar(row)

    except Exception as e:
        print(f"Erro fatal durante a execução: {e}")
        sys.exit(1)
