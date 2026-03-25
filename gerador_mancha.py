import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
from shapely.geometry import shape, Point
from rasterio.features import shapes
from scipy.ndimage import binary_dilation
import os
import gdown

# Configurações
FILE_ID = "1sBJHHYr0wAKOtO4YHHKZ0fSDj_IiI56_"
MDE_ORIGINAL = "mde_original.tif"
MDE_UTM = "mde_convertido_utm.tif"
TARGET_CRS = 'EPSG:31983'

def converter_para_utm(entrada, saida):
    print(f"Convertendo {entrada} para {TARGET_CRS}...")
    with rasterio.open(entrada) as src:
        transform, width, height = calculate_default_transform(
            src.crs, TARGET_CRS, src.width, src.height, *src.bounds)
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': TARGET_CRS,
            'transform': transform,
            'width': width,
            'height': height
        })

        with rasterio.open(saida, 'w', **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=TARGET_CRS,
                    resampling=Resampling.nearest)
    print("Conversão concluída!")

def main():
    os.makedirs('output', exist_ok=True)
    
    # 1. Download do arquivo do Drive
    url = f"https://drive.google.com/uc?id={FILE_ID}"
    gdown.download(url, MDE_ORIGINAL, quiet=False)

    # 2. CONVERSÃO AUTOMÁTICA PARA UTM
    converter_para_utm(MDE_ORIGINAL, MDE_UTM)

    # 3. Dados da Genesis I (conforme seu CSV)
    x_utm, y_utm = 309435, 7406885

    try:
        with rasterio.open(MDE_UTM) as src:
            py, px = src.index(x_utm, y_utm)
            raster = src.read(1)
            
            # Pega a cota do terreno e define a inundação (+1m)
            cota_terreno = float(raster[py, px])
            cota_simulacao = cota_terreno + 1.0
            
            print(f"Cota terreno no mapa convertido: {cota_terreno:.2f}m")

            # Lógica de inundação
            mask = (raster <= cota_simulacao) & (raster != src.nodata)
            seed = np.zeros_like(mask, dtype=bool)
            seed[py, px] = True
            inundacao = np.zeros_like(mask, dtype=bool)
            
            for i in range(5000):
                expandida = binary_dilation(seed, structure=np.ones((3,3)))
                seed = expandida & mask
                if not seed.any(): break
                inundacao |= seed

            geoms = [shape(s) for s, v in shapes(inundacao.astype('int16'), mask=inundacao==1, transform=src.transform)]

        if geoms:
            gdf = gpd.GeoDataFrame(geometry=geoms, crs=TARGET_CRS)
            gdf.dissolve().to_file("output/MANCHA_REAL_FINAL.shp")
            print("✅ SUCESSO: Mancha gerada com o arquivo convertido em tempo de execução!")
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    main()
