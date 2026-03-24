import pandas as pd
import geopandas as gpd
import rasterio
import numpy as np
from shapely.geometry import shape
from rasterio.features import shapes
from scipy.ndimage import binary_dilation
import os
import gdown

# ID extraído do seu link de compartilhamento
FILE_ID = "1sBJHHYr0wAKOtO4YHHKZ0fSDj_IiI56_"
MDE_NOME = "mde_final_utm.tif"

def main():
    # 1. Download Robusto via gdown (evita arquivos corrompidos)
    print("Iniciando download do MDE (UTM 23S) do Google Drive...")
    url = f"https://drive.google.com/uc?id={FILE_ID}"
    gdown.download(url, MDE_NOME, quiet=False)

    # 2. Dados de Santana de Parnaíba (Barragem Genesis I)
    # x, y em UTM 23S e cota do coroamento conforme Ficha Técnica
    x, y, cota_rup = 309435, 7406885, 743.0 

    try:
        with rasterio.open(MDE_NOME) as src:
            # Converte a coordenada métrica para o índice do pixel
            py, px = src.index(x, y)
            raster = src.read(1)
            nodata = src.nodata
            
            # Validação: se o índice for negativo, o mapa ainda está em graus
            if py < 0 or py >= src.height or px < 0 or px >= src.width:
                print(f"❌ ERRO: O ponto ({x}, {y}) está fora dos limites do mapa!")
                return

            # Ajuste de ignição: Garante que a água comece a fluir
            if raster[py, px] >= cota_rup:
                raster[py, px] = cota_rup - 0.5

            # Máscara de inundação (Tudo que for menor ou igual a 743m)
            mask = (raster <= cota_rup) & (raster != nodata)
            
            # Algoritmo de Propagação (Flood Fill)
            seed = np.zeros_like(mask, dtype=bool)
            seed[py, px] = True
            inundacao = np.zeros_like(mask, dtype=bool)
            
            print("Modelando deslocamento a jusante e esparramamento lateral...")
            for i in range(5000): # Aumentado para cobrir maior extensão do vale
                expandida = binary_dilation(seed, structure=np.ones((3,3)))
                seed = expandida & mask
                if not seed.any(): break
                inundacao |= seed

            # Transforma os pixels inundados em Polígono (Vetor)
            geoms = [shape(s) for s, v in shapes(inundacao.astype('int16'), 
                                                 mask=inundacao==1, 
                                                 transform=src.transform)]

        if geoms:
            os.makedirs('output', exist_ok=True)
            gdf = gpd.GeoDataFrame(geometry=geoms, crs="EPSG:31983")
            # Une todos os polígonos em uma única mancha
            gdf.dissolve().to_file("output/MANCHA_ESTUDO_HIDRO.shp")
            print("✅ SUCESSO: Mancha real gerada com base no relevo!")
        else:
            print("❌ ERRO: A propagação não encontrou áreas conectadas abaixo da cota.")
            
    except Exception as e:
        print(f"❌ ERRO CRÍTICO ao processar o raster: {e}")

if __name__ == "__main__":
    main()
