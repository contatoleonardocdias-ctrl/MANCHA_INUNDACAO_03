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
    # Ajustado para as colunas do seu print: nome_barragem, x_utm, y_utm, epsg, cota_ruptura
    nome = str(row['nome_barragem']).strip().replace(" ", "_")
    cota = float(row['cota_ruptura'])
    x = float(row['x_utm'])
    y = float(row['y_utm'])
    crs_origem = f"EPSG:{int(row['epsg'])}"

    with rasterio.open(MDE_LOCAL) as src:
        raster = src.read(1)
        mask = (raster <= cota).astype('int16')
        
        # Vetorização da mancha
        results = ({'properties': {'cota': cota}, 'geometry': s}
                   for i, (s, v) in enumerate(shapes(mask, mask=(mask == 1), transform=src.transform)))
        
        gdf = gpd.GeoDataFrame.from_features(list(results), crs=src.crs)
        
        if gdf.empty:
            print(f"Aviso: Nenhuma área abaixo da cota {cota} para {nome}.")
            return

        # Converte para Web Mercator (EPSG:3857) para o mapa de satélite
        gdf = gdf.to_crs(epsg=3857)
        ponto = gpd.GeoDataFrame({'geometry': [Point(x, y)]}, crs=crs_origem).to_crs(epsg=3857)

        # 1. SALVAR SHAPEFILE (O produto bruto)
        if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
        base_path = f"{OUTPUT_DIR}/Inundacao_{nome}"
        gdf.to_file(f"{base_path}.shp")

        # 2. GERAR PDF (O relatório visual com satélite)
        fig, ax = plt.subplots(figsize=(12, 12))
        gdf.plot(ax=ax, color='cyan', alpha=0.5, edgecolor='blue', label='Mancha de Inundação')
        ponto.plot(ax=ax, color='red', marker='X', markersize=200, label='Ponto de Rompimento')
        
        try:
            cx.add_basemap(ax, source=cx.providers.Esri.WorldImagery)
        except:
            print("Erro ao carregar satélite, gerando sem fundo.")

        ax.set_title(f"Mapa de Inundação: {nome}\nCota de Corte: {cota}m", fontsize=15)
        plt.legend()
        
        pdf_path = f"{OUTPUT_DIR}/Mapa_{nome}.pdf"
        plt.savefig(pdf_path, bbox_inches='tight')
        plt.close()
        print(f"Sucesso: Arquivos gerados para {nome}")

if __name__ == "__main__":
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    url = f"https://docs.google.com/uc?export=download&id={ID_DRIVE}"
    
    try:
        baixar_mde(url, MDE_LOCAL)
        df = pd.read_csv(CSV_LOCAL)
        # Limpa nomes de colunas para evitar erros de espaço ou maiúsculas
        df.columns = df.columns.str.strip().str.lower()
        
        for _, row in df.iterrows():
            processar(row)
    except Exception as e:
        print(f"Erro fatal: {e}")
        sys.exit(1)
