import pandas as pd
import geopandas as gpd
import rasterio
import numpy as np
from shapely.geometry import shape
from rasterio.features import shapes
from scipy.ndimage import binary_dilation
import os
import requests

# 1. CONFIGURAÇÕES - Verifique se o ID do seu novo TIF no Drive é este:
FILE_ID = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su"
MDE_NOME = "mde_final_31983.tif" 

def download_mde(id, destination):
    print(f"Baixando MDE do Drive...")
    url = f"https://docs.google.com/uc?export=download&id={id}"
    r = requests.get(url, stream=True)
    with open(destination, "wb") as f:
        for chunk in r.iter_content(32768):
            if chunk: f.write(chunk)
    print("Download concluído.")

def main():
    download_mde(FILE_ID, MDE_NOME)
    
    # Leitura do CSV
    try:
        df = pd.read_csv('barragens.csv')
        row = df.iloc[0]
        x, y = float(row['x_utm']), float(row['y_utm'])
        cota_ruptura = float(row['cota_ruptura'])
        epsg_csv = int(row['epsg'])
    except Exception as e:
        print(f"ERRO no CSV: {e}")
        return

    # Processamento do Raster
    with rasterio.open(MDE_NOME) as src:
        print(f"INFO: Mapa carregado. Sistema: {src.crs}")
        print(f"INFO: Limites do Mapa: {src.bounds}")
        
        # Converte UTM para posição no Pixel
        py, px = src.index(x, y)
        
        # VALIDAÇÃO CRÍTICA: Se o ponto cair fora, o log avisará aqui
        if py < 0 or py >= src.height or px < 0 or px >= src.width:
            print(f"❌ ERRO: O ponto ({x}, {y}) está FORA dos limites do mapa!")
            print(f"Verifique se o X e Y no CSV estão corretos para o EPSG {epsg_csv}.")
            return

        raster = src.read(1)
        nodata = src.nodata
        
        # Máscara de Cota (Tudo abaixo ou igual a 745m)
        mask_cota = (raster <= cota_ruptura) & (raster != nodata)

        # Lógica de Propagação Conectada (Flood Fill)
        # Começa no pixel do barramento e 'escorre' pelo terreno baixo
        seed = np.zeros_like(mask_cota, dtype=bool)
        seed[py, px] = True
        inundacao = np.zeros_like(mask_cota, dtype=bool)
        
        print("Propagando mancha a jusante...")
        for i in range(2000): # Cobre aproximadamente 60km em MDE de 30m
            expandida = binary_dilation(seed, structure=np.ones((3,3)))
            seed = expandida & mask_cota
            if not seed.any(): break
            inundacao |= seed

        # Vetorização (Transforma em Shapefile)
        geoms = [shape(s) for s, v in shapes(inundacao.astype('int16'), 
                                             mask=inundacao==1, 
                                             transform=src.transform)]

    if geoms:
        os.makedirs('output', exist_ok=True)
        gdf = gpd.GeoDataFrame(geometry=geoms, crs=f"EPSG:{epsg_csv}")
        gdf.dissolve().to_file("output/MANCHA_FINAL.shp")
        print("✅ SUCESSO: Arquivo gerado em output/MANCHA_FINAL.shp")
    else:
        print("❌ ERRO: Nenhuma mancha gerada. Verifique se o ponto está no leito do rio.")

if __name__ == "__main__":
    main()
