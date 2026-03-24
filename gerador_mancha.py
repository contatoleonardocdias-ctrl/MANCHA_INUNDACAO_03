import rasterio
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, box
import requests
import os
from rasterio.features import shapes
from rasterio.mask import mask as rio_mask

# --- CONFIGURAÇÃO ---
ID_DRIVE = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su" 
MDE_LOCAL = "data/mde.tif"
CSV_LOCAL = "barragens.csv"
OUTPUT_DIR = "output"
# --------------------

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

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
    
    # AMARRAÇÃO DO EPSG 31983 (SIRGAS 2000 / UTM 23S)
    epsg_projeto = "EPSG:31983" 

    try:
        with rasterio.open(MDE_LOCAL) as src:
            area_foco = box(x - 2500, y - 6000, x + 2500, y + 2000)
            out_image, out_transform = rio_mask(src, [area_foco], crop=True)
            raster = out_image[0]
            
            mask = ((raster <= cota) & (raster > 0)).astype('int16')
            results = ({'properties': {'cota': cota, 'barragem': nome}, 'geometry': s}
                       for i, (s, v) in enumerate(shapes(mask, mask=(mask == 1), transform=out_transform)))
            
            # Cria o GeoDataFrame amarrado ao CRS do MDE
            gdf_mancha = gpd.GeoDataFrame.from_features(list(results), crs=src.crs)
            
            if gdf_mancha.empty:
                print(f"⚠️ Mancha vazia para {nome}. Verifique a cota {cota}.")
                return

            # --- EXPORTAÇÃO PARA SHAPEFILE ---
            # O nome do arquivo será baseado na barragem (ex: Mancha_Genesis_I.shp)
            caminho_shp = os.path.join(OUTPUT_DIR, f"Mancha_{nome}.shp")
            
            # Salva o SHP (isso gera os arquivos .shp, .shx, .dbf e .prj)
            gdf_mancha.to_file(caminho_shp, driver='ESRI Shapefile')
            
            print(f"✅ Shapefile gerado com sucesso: {caminho_shp}")

    except Exception as e:
        print(f"❌ Erro ao gerar SHP para {nome}: {e}")

if __name__ == "__main__":
    try:
        baixar_mde(f"https://docs.google.com/uc?export=download&id={ID_DRIVE}", MDE_LOCAL)
        df = pd.read_csv(CSV_LOCAL)
        df.columns = df.columns.str.strip().str.lower()
        for _, row in df.iterrows():
            processar(row)
    except Exception as e:
        print(f"Erro ao iniciar: {e}")
