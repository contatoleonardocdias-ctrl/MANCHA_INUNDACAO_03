import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
from shapely.geometry import shape
from rasterio.features import shapes
from scipy.ndimage import binary_dilation
import os
import requests

# Configurações
FILE_ID = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su"
MDE_ORIGINAL = "original_mde.tif"
MDE_REPROJETADO = "mde_31983.tif"

def download_mde(id, destination):
    if not os.path.exists(destination):
        print("Baixando MDE do Google Drive...")
        url = f"https://docs.google.com/uc?export=download&id={id}"
        r = requests.get(url, stream=True)
        with open(destination, "wb") as f:
            for chunk in r.iter_content(32768): f.write(chunk)

def reprojetar_raster(input_path, output_path, dst_crs='EPSG:31983'):
    print(f"Reprojetando raster para {dst_crs}...")
    with rasterio.open(input_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds)
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': dst_crs,
            'transform': transform,
            'width': width,
            'height': height
        })

        with rasterio.open(output_path, 'w', **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.nearest)
    print("Reprojeção concluída.")

def main():
    download_mde(FILE_ID, MDE_ORIGINAL)
    
    # Lendo CSV
    df = pd.read_csv('barragens.csv')
    row = df.iloc[0]
    x, y, cota, epsg_csv = float(row['x_utm']), float(row['y_utm']), float(row['cota_ruptura']), int(row['epsg'])

    # 1. Converte o TIF para o EPSG do CSV (31983)
    reprojetar_raster(MDE_ORIGINAL, MDE_REPROJETADO, dst_crs=f'EPSG:{epsg_csv}')

    # 2. Processamento no Raster Corrigido
    with rasterio.open(MDE_REPROJETADO) as src:
        py, px = src.index(x, y)
        
        # Validação de segurança
        if py < 0 or py >= src.height or px < 0 or px >= src.width:
            print(f"ERRO: Ponto ({x}, {y}) ainda fora dos limites após reprojeção.")
            print(f"Limites do Raster Reprojetado: {src.bounds}")
            return

        raster = src.read(1)
        mask_cota = (raster <= cota) & (raster != src.nodata)
        
        # Propagação (Flood Fill)
        seed = np.zeros_like(mask_cota, dtype=bool)
        seed[py, px] = True
        inundacao = np.zeros_like(mask_cota, dtype=bool)
        for _ in range(1000):
            seed = binary_dilation(seed, structure=np.ones((3,3))) & mask_cota
            if not seed.any(): break
            inundacao |= seed

        # 3. Vetorização
        geoms = [shape(s) for s, v in shapes(inundacao.astype('int16'), mask=inundacao==1, transform=src.transform)]

    if geoms:
        os.makedirs('output', exist_ok=True)
        gdf = gpd.GeoDataFrame(geometry=geoms, crs=f"EPSG:{epsg_csv}")
        gdf.dissolve().to_file("output/MANCHA_FINAL.shp")
        print("SUCESSO: Mancha gerada com raster reprojetado.")

if __name__ == "__main__":
    main()
