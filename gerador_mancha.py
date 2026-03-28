import os
import numpy as np
import rasterio
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
import fiona
import elevation

# --- CONFIGURAÇÃO ---
KMZ_FILE = 'MANCHA_INUNDACAO.kmz'
COTA_M20 = 745.0
COTA_M50 = 747.0 # M-20 + 2m (Critério de Segurança)
RAIO_M = 15000.0 # 15km solicitado
MDE_TEMP = 'relevo_nasa.tif'

def processar():
    if not os.path.exists(KMZ_FILE):
        print("❌ KMZ não encontrado!")
        return

    # 1. Extrair localização do KMZ
    fiona.drvsupport.supported_drivers['KML'] = 'rw'
    fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'
    with fiona.open(f'zip://{KMZ_FILE}') as layer:
        gdf_kmz = gpd.GeoDataFrame.from_features(layer, crs=layer.crs)
        ponto = gdf_kmz.geometry.centroid.iloc[0]
        lon, lat = ponto.x, ponto.y

    # 2. Buscar elevações automaticamente (NASA/SRTM)
    print(f"-> Buscando relevo para Lat:{lat}, Lon:{lon}...")
    # Define uma área de busca (Bounding Box) ao redor do ponto
    margin = 0.15 # ~16km de margem
    bounds = (lon - margin, lat - margin, lon + margin, lat + margin)
    elevation.clip(bounds=bounds, output=MDE_TEMP)
    elevation.clean()

    # 3. Gerar as manchas de inundação
    with rasterio.open(MDE_TEMP) as src:
        dem = src.read(1)
        # Matriz de distância para o raio de 15km
        cols, rows = np.meshgrid(np.arange(dem.shape[1]), np.arange(dem.shape[0]))
        xs, ys = rasterio.transform.xy(src.transform, rows, cols)
        
        # Cálculo aproximado de distância (em graus para metros)
        dist = np.sqrt((np.array(xs) - lon)**2 + (np.array(ys) - lat)**2) * 111320
        
        os.makedirs('manchas_output', exist_ok=True)
        
        for cota, label in [(COTA_M20, 'M20'), (COTA_M50, 'M50')]:
            mask = (dem <= cota) & (dem > 0) & (dist <= RAIO_M)
            gen = shapes(mask.astype('int16'), mask=mask, transform=src.transform)
            geoms = [shape(s) for s, v in gen if v == 1]
            
            if geoms:
                gdf = gpd.GeoDataFrame(geometry=geoms, crs=src.crs)
                gdf.to_file(f'manchas_output/Mancha_{label}_15km.geojson', driver='GeoJSON')
                print(f" ✅ Sucesso: {label} gerado via SRTM/NASA.")

if __name__ == "__main__":
    processar()
