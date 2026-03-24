import pandas as pd
import geopandas as gpd
import rasterio
import numpy as np
from shapely.geometry import shape
from rasterio.features import shapes
from scipy.ndimage import binary_dilation
import os
import requests

# ATENÇÃO: Atualize este ID para o MDE de Santana de Parnaíba!
FILE_ID = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su"
MDE_NOME = "mde_santana_31983.tif"

def main():
    # Download
    url = f"https://docs.google.com/uc?export=download&id={FILE_ID}"
    with open(MDE_NOME, "wb") as f:
        f.write(requests.get(url).content)

    # Dados do CSV
    df = pd.read_csv('barragens.csv')
    row = df.iloc[0]
    x, y, cota = float(row['x_utm']), float(row['y_utm']), float(row['cota_ruptura'])
    
    with rasterio.open(MDE_NOME) as src:
        py, px = src.index(x, y)
        print(f"Buscando em: X={x}, Y={y} | Pixel: {py}, {px}")
        
        if py < 0 or py >= src.height or px < 0 or px >= src.width:
            print("❌ ERRO: O ponto de Santana de Parnaíba está FORA deste mapa!")
            return

        raster = src.read(1)
        print(f"Cota do terreno no ponto: {raster[py, px]}m")
        
        mask = (raster <= cota) & (raster != src.nodata)
        seed = np.zeros_like(mask, dtype=bool)
        seed[py, px] = True
        
        inundacao = np.zeros_like(mask, dtype=bool)
        for i in range(1500):
            seed = binary_dilation(seed, structure=np.ones((3,3))) & mask
            if not seed.any(): break
            inundacao |= seed

        geoms = [shape(s) for s, v in shapes(inundacao.astype('int16'), mask=inundacao==1, transform=src.transform)]

    if geoms:
        os.makedirs('output', exist_ok=True)
        gdf = gpd.GeoDataFrame(geometry=geoms, crs="EPSG:31983")
        gdf.dissolve().to_file("output/MANCHA_SANTANA.shp")
        print("✅ SUCESSO: Shapefile gerado!")
    else:
        print("❌ ERRO: A cota de ruptura é menor que o terreno.")

if __name__ == "__main__":
    main()
