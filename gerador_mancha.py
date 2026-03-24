import pandas as pd
import geopandas as gpd
import rasterio
import numpy as np
from shapely.geometry import shape
from rasterio.features import shapes
from scipy.ndimage import binary_dilation
import os
import requests

# 1. COLOQUE O ID DO NOVO ARQUIVO '23S48_ZN_01.tif' AQUI:
FILE_ID = "SUBSTITUA_PELO_NOVO_ID_DO_DRIVE" 
MDE_NOME = "mde_final_utm.tif"

def main():
    print("Baixando MDE reprojetado (UTM 23S)...")
    url = f"https://docs.google.com/uc?export=download&id={FILE_ID}"
    r = requests.get(url, stream=True)
    with open(MDE_NOME, "wb") as f:
        for chunk in r.iter_content(32768):
            if chunk: f.write(chunk)

    # Coordenadas da Genesis I e Cota de Coroamento (743m)
    x, y, cota_rup = 309435, 7406885, 743.0 

    with rasterio.open(MDE_NOME) as src:
        # Localiza o pixel exato no mapa métrico
        py, px = src.index(x, y)
        raster = src.read(1)
        nodata = src.nodata

        # Proteção contra erro de 'out of bounds'
        if py < 0 or py >= src.height or px < 0 or px >= src.width:
            print(f"❌ ERRO: O ponto ({x}, {y}) caiu fora do mapa exportado!")
            return

        # Ajuste de ignição: Garante que a água saia do ponto inicial
        if raster[py, px] >= cota_rup:
            raster[py, px] = cota_rup - 0.5

        # Máscara de inundação baseada na topografia (pixels <= 743m)
        mask = (raster <= cota_rup) & (raster != nodata)
        
        # Algoritmo de 'Flood Fill' (Propagação Conectada)
        seed = np.zeros_like(mask, dtype=bool)
        seed[py, px] = True
        inundacao = np.zeros_like(mask, dtype=bool)
        
        print("Modelando deslocamento jusante e esparramamento lateral...")
        # Aumentamos para 5000 iterações para a mancha ir longe no vale
        for i in range(5000):
            expandida = binary_dilation(seed, structure=np.ones((3,3)))
            seed = expandida & mask
            if not seed.any(): break
            inundacao |= seed

        # Vetorização: Converte os pixels inundados em Polígono
        geoms = [shape(s) for s, v in shapes(inundacao.astype('int16'), 
                                             mask=inundacao==1, 
                                             transform=src.transform)]

    if geoms:
        os.makedirs('output', exist_ok=True)
        gdf = gpd.GeoDataFrame(geometry=geoms, crs="EPSG:31983")
        # Dissolve para gerar um Shapefile único e limpo
        gdf.dissolve().to_file("output/MANCHA_ESTUDO_HIDRO.shp")
        print("✅ SUCESSO: Mancha real gerada seguindo o relevo!")
    else:
        print("❌ ERRO: Nenhuma mancha gerada. Verifique se a cota está correta.")

if __name__ == "__main__":
    main()
