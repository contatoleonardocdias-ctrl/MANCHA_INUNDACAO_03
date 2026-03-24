import pandas as pd
import geopandas as gpd
import rasterio
import numpy as np
from shapely.geometry import shape, Point
from rasterio.features import shapes
from scipy.ndimage import binary_dilation
import os
import gdown

# ID do seu arquivo no Drive (23S48_ZN_01.tif)
FILE_ID = "1sBJHHYr0wAKOtO4YHHKZ0fSDj_IiI56_"
MDE_NOME = "mde_final_utm.tif"

def main():
    os.makedirs('output', exist_ok=True)
    
    print("Baixando MDE...")
    url = f"https://drive.google.com/uc?id={FILE_ID}"
    gdown.download(url, MDE_NOME, quiet=False)

    # Suas coordenadas exatas
    x, y = 309435, 7406885

    try:
        with rasterio.open(MDE_NOME) as src:
            # 1. PEGAR A COTA REAL DO TERRENO NO PONTO
            py, px = src.index(x, y)
            raster = src.read(1)
            cota_terreno = float(raster[py, px])
            
            # 2. DEFINIR COTA DE RUPTURA (1 metro acima do terreno para garantir fluxo)
            # Se a cota do coroamento for 743m e o terreno for 740m, ele usa 743m.
            cota_rup = max(743.0, cota_terreno + 1.0)
            
            print(f"DEBUG: Cota no terreno: {cota_terreno:.2f}m")
            print(f"DEBUG: Cota de ruptura simulada: {cota_rup:.2f}m")

            # MÁSCARA E PROPAGAÇÃO
            mask = (raster <= cota_rup) & (raster != src.nodata)
            seed = np.zeros_like(mask, dtype=bool)
            seed[py, px] = True
            inundacao = np.zeros_like(mask, dtype=bool)
            
            print("Modelando esparramamento lateral...")
            for i in range(5000):
                expandida = binary_dilation(seed, structure=np.ones((3,3)))
                seed = expandida & mask
                if not seed.any(): break
                inundacao |= seed

            geoms = [shape(s) for s, v in shapes(inundacao.astype('int16'), mask=inundacao==1, transform=src.transform)]

        if geoms:
            gdf = gpd.GeoDataFrame(geometry=geoms, crs="EPSG:31983")
            gdf.dissolve().to_file("output/MANCHA_REAL_FINAL.shp")
            print("✅ SUCESSO: Mancha real gerada!")
        else:
            # Se falhar, gera o ponto para você conferir a localização no QGIS
            print("⚠️ RELEVO BARROU: Gerando ponto de conferência.")
            ponto = Point(x, y)
            gpd.GeoDataFrame(geometry=[ponto.buffer(50)], crs="EPSG:31983").to_file("output/CONFERIR_PONTO.shp")

    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    main()
