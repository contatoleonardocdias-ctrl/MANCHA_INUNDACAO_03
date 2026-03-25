import pandas as pd
import geopandas as gpd
import rasterio
import numpy as np
from shapely.geometry import shape, Point
from rasterio.features import shapes
from scipy.ndimage import binary_dilation
import os
import gdown

# Configurações de arquivos
FILE_ID = "1sBJHHYr0wAKOtO4YHHKZ0fSDj_IiI56_"
MDE_NOME = "mde_final_utm.tif"

def main():
    # Garante que a pasta de saída existe
    os.makedirs('output', exist_ok=True)
    
    # 1. Carrega os dados do seu barragens.csv
    df = pd.read_csv('barragens.csv')
    dados = df.iloc[0]
    x_utm, y_utm = dados['x_utm'], dados['y_utm']
    nome_barragem = dados['nome_barragem']

    # 2. Download do seu MDE reprojetado
    url = f"https://drive.google.com/uc?id={FILE_ID}"
    gdown.download(url, MDE_NOME, quiet=False)

    try:
        with rasterio.open(MDE_NOME) as src:
            # Localiza o pixel exato da coordenada
            py, px = src.index(x_utm, y_utm)
            raster = src.read(1)
            
            # --- CAPTURA AUTOMÁTICA DE COTA ---
            cota_terreno = float(raster[py, px])
            # Definimos a ruptura 1 metro acima do terreno para garantir o fluxo
            cota_simulacao = cota_terreno + 1.0
            
            print(f"\n--- DIAGNÓSTICO DE TERRENO ---")
            print(f"Barragem: {nome_barragem}")
            print(f"Cota identificada no MDE: {cota_terreno:.2f}m")
            print(f"Iniciando simulação em: {cota_simulacao:.2f}m")
            print(f"------------------------------\n")

            # Lógica de inundação baseada no relevo
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
            gdf = gpd.GeoDataFrame(geometry=geoms, crs="EPSG:31983")
            gdf.dissolve().to_file(f"output/MANCHA_{nome_barragem}.shp")
            print(f"✅ SUCESSO: Arquivo MANCHA_{nome_barragem}.shp gerado!")
        else:
            # Caso o relevo ainda barre, gera um ponto de controle para conferência
            print("⚠️ Relevo barrou a expansão. Gerando ponto de conferência.")
            ponto = Point(x_utm, y_utm)
            gpd.GeoDataFrame(geometry=[ponto.buffer(50)], crs="EPSG:31983").to_file("output/PONTO_TESTE.shp")

    except Exception as e:
        print(f"❌ Erro ao processar o raster: {e}")

if __name__ == "__main__":
    main()
