import pandas as pd
import geopandas as gpd
import rasterio
import numpy as np
from shapely.geometry import shape
from rasterio.features import shapes
from scipy.ndimage import binary_dilation
import os
import requests

# Link do seu MDE (Certifique-se que o ID está correto se você mudou o arquivo)
FILE_ID = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su"
MDE_NOME = "mde_final_31983.tif" 

def download_mde(id, destination):
    print(f"Baixando arquivo do Drive...")
    url = f"https://docs.google.com/uc?export=download&id={id}"
    session = requests.Session()
    response = session.get(url, stream=True)
    with open(destination, "wb") as f:
        for chunk in response.iter_content(32768):
            if chunk: f.write(chunk)
    print("Download concluído.")

def main():
    download_mde(FILE_ID, MDE_NOME)
    
    # Lendo o CSV
    try:
        df = pd.read_csv('barragens.csv')
        row = df.iloc[0]
        x, y = float(row['x_utm']), float(row['y_utm'])
        cota_ruptura = float(row['cota_ruptura'])
        epsg_csv = int(row['epsg'])
    except Exception as e:
        print(f"Erro no CSV: {e}")
        return

    # Abrindo o MDE
    with rasterio.open(MDE_NOME) as src:
        # Pega a posição do pixel
        py, px = src.index(x, y)
        
        # VERIFICAÇÃO DE SEGURANÇA: O ponto está no mapa?
        if py < 0 or py >= src.height or px < 0 or px >= src.width:
            print(f"❌ ERRO: O ponto ({x}, {y}) está fora do mapa!")
            print(f"Limites do mapa: {src.bounds}")
            return

        raster = src.read(1)
        nodata = src.nodata
        
        # Criar máscara de cota: tudo que é menor ou igual a 745m
        # E que não seja o valor de NoData (vazio)
        mask_cota = (raster <= cota_ruptura) & (raster != nodata)

        # Lógica de inundação conectada (Flood Fill)
        # Começamos apenas no pixel do barramento e 'espalhamos' a água
        seed = np.zeros_like(mask_cota, dtype=bool)
        seed[py, px] = True
        
        inundacao = np.zeros_like(mask_cota, dtype=bool)
        
        print("Propagando mancha...")
        # 1500 iterações cobrem aproximadamente 45km em MDE de 30m
        for i in range(1500):
            # Expande a área inundada atual por 1 pixel
            expandida = binary_dilation(seed, structure=np.ones((3,3)))
            # A nova área inundada é a expansão limitada pela cota
            seed = expandida & mask_cota
            
            if not seed.any(): break
            inundacao |= seed

        # Transformar o resultado em Polígono (Vetor)
        results = (
            {'properties': {'id': 1}, 'geometry': s}
            for i, (s, v) in enumerate(shapes(inundacao.astype('int16'), 
                                             mask=inundacao==1, 
                                             transform=src.transform))
        )
        geometrias = [shape(res['geometry']) for res in results]

    if geometrias:
        if not os.path.exists('output'): os.makedirs('output')
        gdf = gpd.GeoDataFrame(geometry=geometrias, crs=f"EPSG:{epsg_csv}")
        # Dissolve para virar uma mancha única e limpa
        gdf.dissolve().to_file("output/MANCHA_FINAL.shp")
        print("✅ SUCESSO: Mancha gerada em output/MANCHA_FINAL.shp")
    else:
        print("❌ ERRO: A inundação não conseguiu começar. Verifique a cota no CSV.")

if __name__ == "__main__":
    main()
