import os
import numpy as np
import rasterio
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
import fiona
import requests

# --- CONFIGURAÇÃO ---
KMZ_FILE = 'MANCHA_INUNDACAO.kmz'
COTA_M20 = 745.0
COTA_M50 = 747.0 # M-20 + 2m (Segurança de Barragens IPT)
RAIO_M = 15000.0 # 15km
MDE_FINAL = 'relevo_final.tif'

def baixar_mde_alternativo(lat, lon):
    """Baixa o relevo usando a API pública do OpenTopography (SRTM 30m)"""
    print(f"-> Baixando relevo via OpenTopography para Lat:{lat}, Lon:{lon}...")
    margin = 0.15
    west, south, east, north = lon - margin, lat - margin, lon + margin, lat + margin
    
    url = f"https://portal.opentopography.org/API/globaldem?demtype=SRTM30&west={west}&south={south}&east={east}&north={north}&outputFormat=GTiff"
    
    response = requests.get(url)
    if response.status_code == 200:
        with open(MDE_FINAL, 'wb') as f:
            f.write(response.content)
        return True
    else:
        print(f"❌ Erro na API: {response.status_code}")
        return False

def processar():
    if not os.path.exists(KMZ_FILE):
        print("❌ KMZ não encontrado!")
        return

    # 1. Localização pelo KMZ
    fiona.drvsupport.supported_drivers['KML'] = 'rw'
    fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'
    with fiona.open(f'zip://{KMZ_FILE}') as layer:
        gdf_kmz = gpd.GeoDataFrame.from_features(layer, crs=layer.crs)
        ponto = gdf_kmz.geometry.centroid.iloc[0]
        lon, lat = ponto.x, ponto.y

    # 2. Download do relevo (Nova tentativa via API direta)
    if baixar_mde_alternativo(lat, lon):
        with rasterio.open(MDE_FINAL) as src:
            dem = src.read(1)
            cols, rows = np.meshgrid(np.arange(dem.shape[1]), np.arange(dem.shape[0]))
            xs, ys = rasterio.transform.xy(src.transform, rows, cols)
            
            # Distância aproximada
            dist = np.sqrt((np.array(xs) - lon)**2 + (np.array(ys) - lat)**2) * 111320
            
            os.makedirs('manchas_output', exist_ok=True)
            
            for cota, label in [(COTA_M20, 'M20'), (COTA_M50, 'M50')]:
                mask = (dem <= cota) & (dem > 0) & (dist <= RAIO_M)
                gen = shapes(mask.astype('int16'), mask=mask, transform=src.transform)
                geoms = [shape(s) for s, v in gen if v == 1]
                
                if geoms:
                    gdf = gpd.GeoDataFrame(geometry=geoms, crs=src.crs)
                    gdf.to_file(f'manchas_output/Mancha_{label}_15km.geojson', driver='GeoJSON')
                    print(f" ✅ Sucesso: {label} gerado.")

if __name__ == "__main__":
    processar()
