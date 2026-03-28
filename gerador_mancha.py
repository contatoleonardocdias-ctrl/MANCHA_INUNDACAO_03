import os
import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.enums import Resampling
import geopandas as gpd
from shapely.geometry import shape
import fiona

# CONFIGURAÇÃO TÉCNICA - GÊNESIS I
KMZ_FILE = 'MANCHA_INUNDACAO.kmz'
MDE_FILE = '23S48_ZN.tif'
COTA_M20 = 745.0
COTA_M50 = 747.0 # Ruptura + 2m (M-50 conforme diretriz)
RAIO_M = 15000.0 # Raio de 15km solicitado

def processar_modelo_e_mancha():
    if not os.path.exists(KMZ_FILE) or not os.path.exists(MDE_FILE):
        print("❌ Erro: Certifique-se que o KMZ e o TIF real estão na raiz!")
        return

    # 1. Extrair localização do KMZ
    fiona.drvsupport.supported_drivers['KML'] = 'rw'
    fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'
    with fiona.open(f'zip://{KMZ_FILE}') as layer:
        gdf_kmz = gpd.GeoDataFrame.from_features(layer, crs=layer.crs)
        ponto = gdf_kmz.geometry.centroid.iloc[0]
        x_ref, y_ref = ponto.x, ponto.y

    # 2. Processar MDE com precisão de 5 metros
    with rasterio.open(MDE_FILE) as src:
        # Reamostragem para garantir a precisão solicitada
        upscale_factor = src.res[0] / 5.0 
        new_height = int(src.height * upscale_factor)
        new_width = int(src.width * upscale_factor)
        
        dem = src.read(1, out_shape=(new_height, new_width), resampling=Resampling.bilinear)
        transform = src.transform * src.transform.scale((src.width / dem.shape[1]), (src.height / dem.shape[0]))
        
        # Gerar matriz de distância para o raio de 15km
        cols, rows = np.meshgrid(np.arange(dem.shape[1]), np.arange(dem.shape[0]))
        xs, ys = rasterio.transform.xy(transform, rows, cols)
        dist = np.sqrt((np.array(xs) - x_ref)**2 + (np.array(ys) - y_ref)**2)

        os.makedirs('manchas_output', exist_ok=True)

        for cota, label in [(COTA_M20, 'M20'), (COTA_M50, 'M50')]:
            # Lógica: Terreno <= Cota E dentro do raio de 15km
            mask = (dem <= cota) & (dem > 0) & (dist <= RAIO_M)
            
            gen = shapes(mask.astype('int16'), mask=mask, transform=transform)
            geoms = [shape(s) for s, v in gen if v == 1]
            
            if geoms:
                gdf_result = gpd.GeoDataFrame(geometry=geoms, crs=src.crs)
                gdf_result.to_file(f'manchas_output/Mancha_{label}_15km.geojson', driver='GeoJSON')
                print(f" ✅ Sucesso: Cenário {label} gerado com precisão de 5m.")

if __name__ == "__main__":
    processar_modelo_e_mancha()
