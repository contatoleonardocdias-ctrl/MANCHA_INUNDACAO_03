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
from rasterio.windows import from_bounds

# --- CONFIGURAÇÃO ---
ID_DRIVE = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su" 
MDE_LOCAL = "data/mde.tif"
CSV_LOCAL = "barragens.csv"
OUTPUT_DIR = "output"
CRS_MDE = "EPSG:31983"
BUFFER = 3000  # 🔥 área de análise (3 km)
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

        print(f"CRS raster: {src.crs}")

        # 🔥 RECORTE AO REDOR DO PONTO
        xmin, xmax = x - BUFFER, x + BUFFER
        ymin, ymax = y - BUFFER, y + BUFFER

        window = from_bounds(xmin, ymin, xmax, ymax, src.transform)

        raster = src.read(1, window=window)
        transform = src.window_transform(window)

        # 🔥 MÁSCARA DE INUNDAÇÃO
        mask = (raster <= cota).astype('int16')

        results = (
            {'properties': {'cota': cota}, 'geometry': s}
            for (s, v) in shapes(mask, mask=(mask == 1), transform=transform)
        )

        features = list(results)

        if not features:
            print(f"Aviso: Nenhuma mancha gerada para {nome}")
            return

        # 🔥 GDF COM CRS CORRETO
        gdf_mancha = gpd.GeoDataFrame.from_features(features)
        gdf_mancha = gdf_mancha.set_crs(CRS_MDE)

        # 🔥 PONTO
        ponto = gpd.GeoDataFrame(
            {'geometry': [Point(x, y)]}, 
            crs=f"EPSG:{epsg_origem}"
        )

        # 🔥 REPROJEÇÃO
        gdf_mancha_3857 = gdf_mancha.to_crs(epsg=3857)
        ponto_3857 = ponto.to_crs(epsg=3857)

        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)

        # 🔥 SALVA SHP
        gdf_mancha_3857.to_file(f"{OUTPUT_DIR}/Mancha_{nome}.shp")

        # 🔥 MAPA
        fig, ax = plt.subplots(figsize=(12, 12))

        gdf_mancha_3857.plot(
            ax=ax, color='cyan', alpha=0.5, edgecolor='blue',
            label='Área de Inundação'
        )

        ponto_3857.plot(
            ax=ax, color='yellow', marker='*', markersize=300,
            label='Ponto de Ruptura'
        )

        try:
            cx.add_basemap(ax, source=cx.providers.Esri.WorldImagery)
        except Exception as e:
            print(f"Basemap falhou: {e}")

        ax.set_title(f"Relatório de Inundação: {nome} (Cota {cota}m)")
        plt.legend()

        path_pdf = f"{OUTPUT_DIR}/Mapa_{nome}.pdf"
        plt.savefig(path_pdf, bbox_inches='tight')
        plt.close()

        print(f"Sucesso: {path_pdf}")

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
