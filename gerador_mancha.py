import pandas as pd
import geopandas as gpd
import rasterio
import numpy as np
from shapely.geometry import shape
from rasterio.features import shapes
import os

def gerar_mancha_por_cota(mde_path, x, y, cota_max):
    """
    Gera uma mancha baseada na cota de inundação usando o MDE.
    """
    with rasterio.open(mde_path) as src:
        # 1. Transformar coordenada UTM para posição do pixel no mapa
        row, col = src.index(x, y)
        
        # 2. Ler os dados de altitude
        raster_data = src.read(1)
        nodata = src.nodata
        
        # 3. Criar a máscara: pixels abaixo da cota de ruptura
        # Criamos uma matriz booleana onde True = Inundado
        mancha_mask = (raster_data <= cota_max) & (raster_data != nodata)
        
        # Converter para int16 para o rasterio processar
        mancha_mask = mancha_mask.astype('int16')

        # 4. Vetorizar os pixels inundados (Transformar raster em Polígono)
        resultados = (
            {'properties': {'raster_val': v}, 'geometry': s}
            for i, (s, v) in enumerate(shapes(mancha_mask, mask=mancha_mask==1, transform=src.transform))
        )
        
        geometrias = [shape(res['geometry']) for res in resultados]
        return geometrias

def main():
    print("Iniciando processamento baseado em MDE...")
    
    # Ler CSV
    df = pd.read_csv('barragens.csv')
    row = df.iloc[0] # Pega a primeira barragem
    
    mde_nome = row['arquivo_mde'].strip()
    x, y = row['x_utm'], row['y_utm']
    cota = row['cota_ruptura']
    epsg = int(row['epsg'])

    if not os.path.exists(mde_nome):
        print(f"Erro: O arquivo de relevo {mde_nome} não foi encontrado no repositório!")
        return

    print(f"Analisando inundação para cota {cota}m a partir de ({x}, {y})...")

    # Gerar a mancha
    geoms = gerar_mancha_por_cota(mde_nome, x, y, cota)

    if geoms:
        # Criar GeoDataFrame
        gdf = gpd.GeoDataFrame({'id': range(len(geoms))}, geometry=geoms, crs=f"EPSG:{epsg}")
        
        # Salvar Shapefile
        output_name = "MANCHA_NOVO_03.shp"
        gdf.to_file(output_name)
        print(f"Sucesso! Mancha salva em {output_name}")
    else:
        print("Nenhuma área inundada encontrada abaixo dessa cota.")

if __name__ == "__main__":
    main()
