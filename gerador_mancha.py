import pandas as pd
import geopandas as gpd
import rasterio
import numpy as np
from shapely.geometry import shape
from rasterio.features import shapes
from scipy.ndimage import binary_dilation
import os
import requests

# ATENÇÃO: Verifique se o ID e o NOME do arquivo no Drive estão corretos
FILE_ID = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su"
MDE_NOME = "mde_final_31983.tif" 

def download_mde(id, destination):
    print(f"Baixando arquivo do Drive: {id}...")
    url = f"https://docs.google.com/uc?export=download&id={id}"
    r = requests.get(url, stream=True)
    with open(destination, "wb") as f:
        for chunk in r.iter_content(32768): f.write(chunk)
    print("Download concluído.")

def main():
    download_mde(FILE_ID, MDE_NOME)
    
    # 1. Leitura do CSV com tratamento de erro
    try:
        df = pd.read_csv('barragens.csv')
        row = df.iloc[0]
        x, y = float(row['x_utm']), float(row['y_utm'])
        cota_ruptura = float(row['cota_ruptura'])
        epsg_csv = int(row['epsg'])
    except Exception as e:
        print(f"ERRO ao ler o CSV: {e}")
        return

    # 2. Processamento
    with rasterio.open(MDE_NOME) as src:
        print(f"--- INFO DO MAPA ---")
        print(f"Sistema (CRS): {src.crs}")
        print(f"Limites (Bounds): {src.bounds}")
        
        # Converte coordenada para pixel
        py, px = src.index(x, y)
        print(f"Tentando iniciar no Pixel: Linha {py}, Coluna {px}")

        # VALIDAÇÃO CRÍTICA
        if py < 0 or py >= src.height or px < 0 or px >= src.width:
            print(f"❌ ERRO: O ponto ({x}, {y}) está FORA dos limites do mapa!")
            print(f"Verifique se o X e Y no CSV estão corretos para o EPSG {epsg_csv}.")
            return

        raster = src.read(1)
        # Se o pixel de início for NoData, a inundação não começa
        if raster[py, px] == src.nodata:
            print(f"❌ ERRO: O ponto de início caiu em uma área sem dados (NoData).")
            return

        # Lógica de Inundação
        mask_cota = (raster <= cota_ruptura) & (raster != src.nodata)
        seed = np.zeros_like(mask_cota, dtype=bool)
        seed[py, px] = True
        inundacao = np.zeros_like(mask_cota, dtype=bool)
        
        print("Propagando mancha pelo vale...")
        for i in range(2000): # Aumentado para garantir alcance
            expandida = binary_dilation(seed, structure=np.ones((3,3)))
            seed = expandida & mask_cota
            if not seed.any(): break
            inundacao |= seed

        # Vetorização
        geoms = [shape(s) for s, v in shapes(inundacao.astype('int16'), 
                                             mask=inundacao==1, 
                                             transform=src.transform)]

    if geoms:
        os.makedirs('output', exist_ok=True)
        gdf = gpd.GeoDataFrame(geometry=geoms, crs=f"EPSG:{epsg_csv}")
        gdf.dissolve().to_file("output/MANCHA_FINAL.shp")
        print("✅ SUCESSO: Arquivo gerado em output/MANCHA_FINAL.shp")
    else:
        print("❌ ERRO: O algoritmo rodou mas não encontrou áreas para inundar. A cota de ruptura é menor que a cota do terreno no ponto?")

if __name__ == "__main__":
    main()
