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
# --------------------

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
    
    # Define o código EPSG de forma robusta
    epsg_cod = int(row['epsg'])
    crs_origem = f"EPSG:{epsg_cod}"

    with rasterio.open(MDE_LOCAL) as src:
        raster = src.read(1)
        mask = (raster <= cota).astype('int16')
        
        # Vetorização com tratamento de CRS
        results = ({'properties': {'cota': cota}, 'geometry': s}
                   for i, (s, v) in enumerate(shapes(mask, mask=(mask == 1), transform=src.transform)))
        
        # Correção aqui: Define o CRS do MDE no momento da criação
        gdf = gpd.GeoDataFrame.from_features(list(results), crs=src.crs)
        
        if gdf.empty:
            print(f"Aviso: Nenhuma mancha para {nome}")
            return

        # Converte para Web Mercator (EPSG:3857) para o satélite
        gdf = gdf.to_crs(epsg=3857)
        
        # CRIAÇÃO DO PONTO COM CRS EXPLÍCITO (Resolve o erro do log)
        ponto = gpd.GeoDataFrame(
            {'geometry': [Point(x, y)]}, 
            crs=crs_origem  # Define antes de transformar
        ).to_crs(epsg=3857)

        # GERAÇÃO DOS ARQUIVOS
        if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
        
        # Salva Shapefile
        gdf.to_file(f"{OUTPUT_DIR}/Mancha_{nome}.shp")

        # Salva PDF com Satélite
        fig, ax = plt.subplots(figsize=(12, 12))
        gdf.plot(ax=ax, color='cyan', alpha=0.5, edgecolor='blue', label='Mancha')
        ponto.plot(ax=ax, color='red', marker='X', markersize=200, label='Ponto de Rompimento')
        
        try:
            cx.add_basemap(ax, source=cx.providers.Esri.WorldImagery)
        except:
            print("Aviso: Satélite não disponível.")

        ax.set_title(f"Inundação: {nome} (Cota {cota}m)")
        plt.legend()
        plt.savefig(f"{OUTPUT_DIR}/Mapa_{nome}.pdf", bbox_inches='tight')
        plt.close()
        print(f"Sucesso: {nome}")

if __name__ == "__main__":
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    url = f"https://docs.google.com/uc?export=download&id={ID_DRIVE}"
    try:
        baixar_mde(url, MDE_LOCAL)
        df = pd.read_csv(CSV_LOCAL)
        df.columns = df.columns.str.strip().str.lower()
        for _, row in df.iterrows():
            processar(row)
    except Exception as e:
        print(f"Erro fatal: {e}")
        sys.exit(1)
