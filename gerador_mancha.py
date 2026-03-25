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
    os.makedirs('output', exist_ok=True)
    
    # 1. Carrega coordenadas do CSV
    df = pd.read_csv('barragens.csv')
    dados = df.iloc[0]
    x_utm = dados['x_utm']
    y_utm = dados['y_utm']
    nome = dados['nome_barragem']

    # 2. Download do MDE
    url = f"https://drive.google.com/uc?id={FILE_ID}"
    gdown.download(url, MDE_NOME, quiet=False)

    try:
        with rasterio.open(MDE_NOME) as src:
            # --- AQUI ELE PEGA A COTA AUTOMATICAMENTE ---
            py, px = src.index(x_utm, y_utm)
            raster = src.read(1)
            
            # Extrai o valor do pixel (altitude do terreno)
            cota_terreno_automatica = float(raster[py, px])
            
            # Definimos a cota de inundação 1 metro acima do chão
            cota_simulacao = cota_terreno_automatica + 1.0
            
            print(f"\n" + "="*40)
            print(f"BARRAGEM: {nome}")
            print(f"COORDENADA: {x_utm}, {y_utm}")
            print(f"COTA EXTRAÍDA DO MAPA: {cota_terreno_automatica:.2f}m")
            print(f"COTA DE INUNDAÇÃO: {cota_simulacao:.2f}m")
            print("="*40 + "\n")

            # Lógica de Inundação
            mask = (raster <= cota_simulacao) & (raster != src.nodata)
            seed = np.zeros_like(mask, dtype=bool)
            seed[py, px] = True
            inundacao = np.zeros_like(mask, dtype=bool)
            
            print("Calculando esparramamento pelo vale...")
            for i in range(5000):
                expandida = binary_dilation(seed, structure=np.ones((3,3)))
                seed = expandida & mask
                if not seed.any(): break
                inundacao |= seed

            geoms = [shape(s) for s, v in shapes(inundacao.astype('int16'), mask=inundacao==1, transform=src.transform)]

        if geoms:
            gdf = gpd.GeoDataFrame(geometry=geoms, crs="EPSG:31983")
            gdf.dissolve().to_file(f"output/MANCHA_AUTO_{nome}.shp")
            print(f"✅ SUCESSO: Mancha gerada para {nome}!")
        else:
            print("⚠️ Erro: Não foi possível expandir a mancha do ponto inicial.")

    except Exception as e:
        print(f"❌ Erro ao processar: {e}")

if __name__ == "__main__":
    main()
