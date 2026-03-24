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
OUTPUT_DIR = "output"
# --------------------

if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)

def baixar_mde(url, destino):
    if not os.path.exists('data'): os.makedirs('data')
    if not os.path.exists(destino):
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(destino, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): f.write(chunk)

def processar(row):
    nome = str(row['nome_barragem']).strip().replace(" ", "_")
    cota = float(row['cota_ruptura'])
    x, y = float(row['x_utm']), float(row['y_utm'])
    
    # AQUI ENTRA A INFORMAÇÃO DO SIRGAS 2000 UTM 23S
    epsg_projeto = 31983 

    with rasterio.open(MDE_LOCAL) as src:
        # Criamos uma área de busca ao redor da coordenada UTM
        area_foco = box(x - 2000, y - 4000, x + 2000, y + 1000)
        
        try:
            out_image, out_transform = rio_mask(src, [area_foco], crop=True)
            raster = out_image[0]
            
            # Gera a mancha baseada na cota do CSV (745.0)
            mask = ((raster <= cota) & (raster > 0)).astype('int16')
            results = ({'properties': {'cota': cota}, 'geometry': s}
                       for i, (s, v) in enumerate(shapes(mask, mask=(mask == 1), transform=out_transform)))
            
            # SOLUÇÃO DO ERRO: Define o CRS original (do MDE) para a mancha
            gdf_mancha = gpd.GeoDataFrame.from_features(list(results), crs=src.crs)
            
            if gdf_mancha.empty:
                gdf_mancha = gpd.GeoDataFrame({'geometry': [Point(x, y).buffer(100)]}, crs=src.crs)

            # SOLUÇÃO DO ERRO: Define EPSG:31983 para o ponto do CSV
            ponto_gdf = gpd.GeoDataFrame({'geometry': [Point(x, y)]}, crs=f"EPSG:{epsg_projeto}").to_crs(epsg=3857)
            gdf_mancha_3857 = gdf_mancha.to_crs(epsg=3857)

            # PADRÃO VISUAL SOLICITADO (Cyan + Borda Azul)
            fig, ax = plt.subplots(figsize=(12, 10))
            gdf_mancha_3857.plot(ax=ax, color='#00FFFF', alpha=0.4, label='Mancha de Inundação')
            gdf_mancha_3857.boundary.plot(ax=ax, color='blue', linewidth=0.7)
            
            # Ponto de Ruptura (Estilo SP Águas)
            ponto_gdf.plot(ax=ax, color='red', markersize=200, marker='X', label='Barramento', zorder=10)

            try:
                cx.add_basemap(ax, source=cx.providers.Esri.WorldImagery, zoom=15)
            except: pass

            plt.title(f"Simulação de Dam Break: {nome}\nCota de Ruptura: {cota}m", fontsize=14)
            plt.savefig(f"{OUTPUT_DIR}/Relatorio_{nome}.pdf", bbox_inches='tight', dpi=300)
            plt.close()
            print(f"✅ Mapa gerado para {nome}")

        except Exception as e:
            print(f"❌ Erro ao processar: {e}")

if __name__ == "__main__":
    baixar_mde(f"https://docs.google.com/uc?export=download&id={ID_DRIVE}", MDE_LOCAL)
    df = pd.read_csv(CSV_LOCAL)
    df.columns = df.columns.str.strip().str.lower()
    for _, row in df.iterrows():
        processar(row)
