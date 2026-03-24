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
DISTANCIA_VALE = 4000 # 4km a jusante
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
    epsg_origem = int(row['epsg'])

    with rasterio.open(MDE_LOCAL) as src:
        # 1. Cria área de foco para evitar pegar o oceano ou o continente todo
        area_foco = box(x - 1500, y - DISTANCIA_VALE, x + 1500, y + 1000)
        
        try:
            out_image, out_transform = rio_mask(src, [area_foco], crop=True)
            raster = out_image[0]
        except Exception as e:
            print(f"Ponto {nome} fora do MDE: {e}")
            return

        # 2. Gera mancha (filtra valores nulos e acima da cota)
        mask_inundacao = ((raster <= cota) & (raster > 0)).astype('int16')
        results = ({'properties': {'cota': cota}, 'geometry': s}
                   for i, (s, v) in enumerate(shapes(mask_inundacao, mask=(mask_inundacao == 1), transform=out_transform)))
        
        # 3. Garante o CRS no momento da criação para evitar erro "naive"
        gdf_mancha = gpd.GeoDataFrame.from_features(list(results), crs=src.crs)
        
        if gdf_mancha.empty:
            print(f"Nenhuma mancha para {nome}")
            return

        # 4. Reprojeção para Satélite
        ponto_gdf = gpd.GeoDataFrame({'geometry': [Point(x, y)]}, crs=f"EPSG:{epsg_origem}").to_crs(epsg=3857)
        gdf_mancha_3857 = gdf_mancha.to_crs(epsg=3857)

        # 5. Plotagem Profissional
        fig, ax = plt.subplots(figsize=(16, 10))
        gdf_mancha_3857.plot(ax=ax, color='#00FFFF', alpha=0.45, label='Mancha de Inundação')
        gdf_mancha_3857.boundary.plot(ax=ax, color='blue', linewidth=0.6)
        
        ponto_geom = ponto_gdf.geometry.iloc[0]
        ax.scatter(ponto_geom.x, ponto_geom.y, color='red', edgecolor='white', s=180, zorder=10, label='Barramento')

        try:
            cx.add_basemap(ax, source=cx.providers.Esri.WorldImagery, zoom=16)
        except: pass

        ax.set_axis_off()
        plt.title(f"Simulação de Dam Break: {nome.replace('_', ' ')}\nItuverava - SP", fontsize=15, pad=10)
        plt.legend()

        if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
        plt.savefig(f"{OUTPUT_DIR}/Mapa_{nome}.pdf", bbox_inches='tight', dpi=300)
        plt.close()
        print(f"✅ Sucesso: {nome}")

if __name__ == "__main__":
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    url_mde = f"https://docs.google.com/uc?export=download&id={ID_DRIVE}"
    try:
        baixar_mde(url_mde, MDE_LOCAL)
        df = pd.read_csv(CSV_LOCAL)
        df.columns = df.columns.str.strip().str.lower()
        for _, row in df.iterrows():
            processar(row)
    except Exception as e:
        print(f"Erro fatal: {e}")
