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
# Cole aqui o ID do seu arquivo MDE que está no Google Drive
ID_DRIVE = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su" 
MDE_LOCAL = "data/mde.tif"
CSV_LOCAL = "barragens.csv"
OUTPUT_DIR = "output"
# --------------------

def baixar_mde_pesado(url, destino):
    """Cria a pasta data e baixa o arquivo MDE se não existir"""
    if not os.path.exists('data'):
        os.makedirs('data')
    if not os.path.exists(destino):
        print(f"Iniciando download do MDE...")
        response = requests.get(url, stream=True)
        response.raise_for_status() 
        with open(destino, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download concluído!")
    else:
        print(f"Arquivo {destino} já existe.")

def processar_inundacao(row):
    nome = row['nome_barragem']
    cota = row['cota_ruptura']
    lat_ruptura = row['latitude_ruptura']
    lon_ruptura = row['longitude_ruptura']
    mde_path = MDE_LOCAL

    print(f"\n>>> Processando: {nome} (Cota {cota}m)")
    
    with rasterio.open(mde_path) as src:
        raster = src.read(1)
        # Cria a máscara da mancha
        mask = (raster <= cota).astype('int16')
        
        # Vetoriza a mancha
        results = (
            {'properties': {'raster_val': v}, 'geometry': s}
            for i, (s, v) in enumerate(shapes(mask, mask=(mask == 1), transform=src.transform))
        )
        
        gdf = gpd.GeoDataFrame.from_features(list(results), crs=src.crs)
        
        # Converte para Web Mercator (EPSG:3857) para o mapa de satélite
        gdf = gdf.to_crs(epsg=3857)
             
        # Cria o Ponto de Rompimento
        ponto_gdf = gpd.GeoDataFrame(
            {'geometry': [Point(lon_ruptura, lat_ruptura)]}, 
            crs="EPSG:4326"
        ).to_crs(epsg=3857)

        # --- GERAÇÃO DO PDF ---
        fig, ax = plt.subplots(figsize=(12, 12))
        
        # 1. Desenha a Mancha (Azul)
        gdf.plot(ax=ax, color='blue', alpha=0.4, label='Área de Inundação')
        
        # 2. Desenha o Ponto de Rompimento (Estrela Vermelha)
        ponto_gdf.plot(ax=ax, color='red', marker='*', markersize=250, label='Ponto de Rompimento', zorder=5)
        
        # 3. Adiciona Satélite de Fundo
        try:
             cx.add_basemap(ax, source=cx.providers.Esri.WorldImagery)
        except Exception as e:
             print(f"Aviso: Satélite não carregado. Erro: {e}")

        ax.set_title(f"Mapa de Inundação Simplificado: {nome}\nCota de Corte: {cota}m", fontsize=15)
        plt.legend(loc='upper right')
        
        # Salva o PDF
        if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
        pdf_name = f"{OUTPUT_DIR}/Relatorio_{nome}.pdf"
        plt.savefig(pdf_name, bbox_inches='tight')
        plt.close()
        print(f"Sucesso: {pdf_name} gerado.")

if __name__ == "__main__":
    url_mde = f"https://docs.google.com/uc?export=download&id={ID_DRIVE}"
    
    try:
        baixar_mde_pesado(url_mde, M
