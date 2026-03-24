import rasterio
from rasterio.features import shapes
import geopandas as gpd
import pandas as pd
import os

def gerar_mancha():
    if not os.path.exists('configs/barragens.csv'):
        print("Planilha nao encontrada!")
        return
    
    df = pd.read_csv('configs/barragens.csv')
    for _, row in df.iterrows():
        nome = row['nome_barragem']
        cota = row['cota_ruptura']
        mde_path = f"data/{row['arquivo_mde']}"
        
        if not os.path.exists(mde_path):
            print(f"Arquivo {mde_path} nao encontrado na pasta data/")
            continue

        with rasterio.open(mde_path) as src:
            raster = src.read(1)
            # Cria a mancha (1 inunda, 0 nao)
            mask = (raster <= cota).astype('int16')
            
            # Transforma em poligono APENAS o valor 1 (Mancha)
            # Isso elimina o quadrado azul automaticamente
            results = (
                {'properties': {'raster_val': v}, 'geometry': s}
                for i, (s, v) in enumerate(shapes(mask, mask=(mask == 1), transform=src.transform))
            )

            gdf = gpd.GeoDataFrame.from_features(list(results), crs=src.crs)
            if not os.path.exists('output'): os.makedirs('output')
            gdf.to_file(f"output/mancha_{nome}.shp")
            print(f"Mancha {nome} gerada com sucesso!")

if __name__ == "__main__":
    gerar_mancha()
