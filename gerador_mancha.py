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

def baixar_mde_pesado(url, destino):
    if not os.path.exists('data'):
        os.makedirs('data')
    if not os.path.exists(destino):
        print("Iniciando download do MDE...")
        response = requests.get(url, stream=True)
        response.raise_for_status() 
        with open(destino, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download concluído!")

def processar_inundacao(row):
    nome = row['nome_barragem']
    cota = row['cota_ruptura']
    lat_ruptura = row['latitude_ruptura']
    lon_ruptura = row['longitude_ruptura']

    if not os.path.exists(MDE_LOCAL):
        print(f"Erro: Arquivo {MDE_LOCAL} não encontrado.")
        return

    with rasterio.open(MDE_LOCAL) as src:
        raster = src.read(1)
        mask = (raster <= cota).astype('int16')
        
        results = (
            {'properties': {'val': v}, 'geometry': s}
            for i, (s, v) in enumerate(shapes(mask, mask=(mask == 1), transform=src.transform))
        )
        
        gdf = gpd.GeoDataFrame.from_features(list(results), crs=src.crs)
        gdf = gdf.to_crs(epsg=3857)
             
        ponto_gdf = gpd.GeoDataFrame(
            {'geometry': [Point(lon_ruptura, lat_ruptura)]}, 
            crs="EPSG:4326"
        ).to_crs(epsg=3857)

        fig, ax = plt.subplots(figsize=(12, 12))
        
        # Desenha a mancha
        gdf.plot(ax=ax, color='blue', alpha=0.4, label='Área de Inundação')
        
        # Desenha o ponto
        ponto_gdf.plot(ax=ax, color='red', marker='*', markersize=250, label='Ponto de Rompimento', zorder=5)
        
        # Adiciona o Satélite
        try:
             cx.add_basemap(ax, source=cx.providers.Esri.WorldImagery)
        except Exception as e:
             print(f"Aviso: Falha no mapa de fundo: {e}")

        ax.set_title(f"Relatório de Inundação: {nome}\nCorte na Cota: {cota}m")
        plt.legend()
        
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
            
        plt.savefig(f"{OUTPUT_DIR}/Relatorio_{nome}.pdf", bbox_inches='tight')
        plt.close()
        print(f"PDF para {nome} gerado com sucesso.")

if __name__ == "__main__":
    url_mde = f"https://docs.google.com/uc?export=download&id={ID_DRIVE}"
    
    try:
        baixar_mde_pesado(url_mde, MDE_LOCAL)
    except Exception as e:
        print(f"Erro no download: {e}")
        sys.exit(1)

    if not os.path.exists(CSV_LOCAL):
        print(f"Erro: {CSV_LOCAL} não encontrado.")
        sys.exit(1)

    df = pd.read_csv(CSV_LOCAL)
    for index, row in df.iterrows():
        try:
            processar_inundacao(row)
        except Exception as e:
            print(f"Erro ao processar {row.get('nome_barragem', index)}: {e}")

    print("Fim do processamento.")
