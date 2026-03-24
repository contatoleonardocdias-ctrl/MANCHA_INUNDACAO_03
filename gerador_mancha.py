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
DISTANCIA_JUSANTE = 4000 # Extensão da análise em metros
# --------------------

def baixar_mde(url, destino):
    if not os.path.exists('data'): os.makedirs('data')
    if not os.path.exists(destino):
        r = requests.get(url, stream=True)
        with open(destino, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): f.write(chunk)

def processar(row):
    nome = str(row['nome_barragem']).strip().replace(" ", "_")
    cota = float(row['cota_ruptura'])
    x, y = float(row['x_utm']), float(row['y_utm'])
    epsg_origem = int(row['epsg'])

    with rasterio.open(MDE_LOCAL) as src:
        # Define área de estudo focada na jusante (abaixo da barragem)
        area_estudo = box(x - 1000, y - DISTANCIA_JUSANTE, x + 1000, y + 1000)
        
        try:
            out_image, out_transform = rio_mask(src, [area_estudo], crop=True)
            raster = out_image[0]
        except: return

        # Gera mancha detalhada
        mask_inundacao = ((raster <= cota) & (raster > -100)).astype('int16')
        results = ({'properties': {'cota': cota}, 'geometry': s}
                   for i, (s, v) in enumerate(shapes(mask_inundacao, mask=(mask_inundacao == 1), transform=out_transform)))
        
        gdf_mancha = gpd.GeoDataFrame.from_features(list(results), crs=src.crs)
        if gdf_mancha.empty: return

        # Reprojeção para Satélite
        ponto_gdf = gpd.GeoDataFrame({'geometry': [Point(x, y)]}, crs=f"EPSG:{epsg_origem}").to_crs(epsg=3857)
        gdf_mancha_3857 = gdf_mancha.to_crs(epsg=3857)

        # --- PLOTAGEM ESTILO SP ÁGUAS ---
        fig, ax = plt.subplots(figsize=(15, 10))
        
        # Mancha com preenchimento suave e borda forte (estilo técnico)
        gdf_mancha_3857.plot(ax=ax, color='#00FFFF', alpha=0.4, label='Mancha de inundação')
        gdf_mancha_3857.boundary.plot(ax=ax, color='blue', linewidth=0.8)
        
        # Ponto do Barramento (Pin vermelho)
        ponto_3857 = ponto_gdf.geometry.iloc[0]
        ax.scatter(ponto_3857.x, ponto_3857.y, color='red', edgecolor='white', s=150, marker='o', label='Barramento', zorder=10)

        # Mapa de Fundo de Alta Resolução
        try:
            cx.add_basemap(ax, source=cx.providers.Esri.WorldImagery, zoom=15)
        except: pass

        # Ajuste de Layout (Sem eixos e com título limpo)
        ax.set_axis_off()
        plt.title(f"Simulação de Dam Break - {nome.replace('_', ' ')}", fontsize=16, pad=20)
        plt.legend(loc='upper right', frameon=True)

        if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
        plt.savefig(f"{OUTPUT_DIR}/Mapa_{nome}.pdf", bbox_inches='tight', dpi=300)
        plt.close()
        print(f"✅ Mapa de alta definição gerado para {nome}")

if __name__ == "__main__":
    baixar_mde(f"https://docs.google.com/uc?export=download&id={ID_DRIVE}", MDE_LOCAL)
    df = pd.read_csv(CSV_LOCAL)
    df.columns = df.columns.str.strip().str.lower()
    for _, row in df.iterrows(): processar(row)
