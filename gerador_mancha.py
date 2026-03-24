import rasterio
import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
import contextily as cx
from shapely.geometry import Point, box
import requests
import os
from rasterio.features import shapes
from rasterio.mask import mask as rio_mask

# --- CONFIGURAÇÃO ---
ID_DRIVE = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su" 
MDE_LOCAL = "data/mde.tif"
CSV_LOCAL = "barragens.csv"
OUTPUT_DIR = "output"
# --------------------

# Garante a criação da pasta para o GitHub não falhar no upload
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def baixar_mde(url, destino):
    if not os.path.exists('data'): os.makedirs('data')
    if not os.path.exists(destino):
        print("Baixando MDE do Google Drive...")
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(destino, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): f.write(chunk)

def processar(row):
    nome = str(row['nome_barragem']).strip().replace(" ", "_")
    cota = float(row['cota_ruptura']) # Cota 745.00 conforme seu CSV
    x, y = float(row['x_utm']), float(row['y_utm'])
    
    # AMARRAÇÃO: Forçamos o EPSG 31983 (SIRGAS 2000 / UTM 23S)
    epsg_projeto = "EPSG:31983" 

    try:
        with rasterio.open(MDE_LOCAL) as src:
            # Criamos uma área de busca (buffer) ao redor da coordenada
            area_foco = box(x - 2500, y - 5000, x + 2500, y + 2000)
            
            out_image, out_transform = rio_mask(src, [area_foco], crop=True)
            raster = out_image[0]
            
            # Gera a máscara de inundação baseada na cota
            mask = ((raster <= cota) & (raster > 0)).astype('int16')
            results = ({'properties': {'cota': cota}, 'geometry': s}
                       for i, (s, v) in enumerate(shapes(mask, mask=(mask == 1), transform=out_transform)))
            
            # FORÇA CRS DA MANCHA: Herda do arquivo MDE original
            gdf_mancha = gpd.GeoDataFrame.from_features(list(results), crs=src.crs)
            
            if gdf_mancha.empty:
                print(f"⚠️ Mancha vazia para {nome}. Gerando ponto de segurança.")
                gdf_mancha = gpd.GeoDataFrame({'geometry': [Point(x, y).buffer(150)]}, crs=src.crs)

            # FORÇA CRS DO PONTO: Amarra ao EPSG:31983 antes de converter para o mapa
            ponto_gdf = gpd.GeoDataFrame({'geometry': [Point(x, y)]}, crs=epsg_projeto).to_crs(epsg=3857)
            gdf_mancha_3857 = gdf_mancha.to_crs(epsg=3857)

            # Estilo Visual (Padrão SP Águas enviado por você)
            fig, ax = plt.subplots(figsize=(14, 10))
            
            # Mancha em Cyan com borda azul
            gdf_mancha_3857.plot(ax=ax, color='#00FFFF', alpha=0.45, label='Área de Inundação')
            gdf_mancha_3857.boundary.plot(ax=ax, color='blue', linewidth=0.8)
            
            # Ponto de Ruptura (Marcador Vermelho)
            ponto_gdf.plot(ax=ax, color='red', markersize=250, marker='X', label='Ponto de Ruptura', zorder=10)

            # Adiciona o mapa de satélite (converte 31983 -> 3857 internamente)
            try:
                cx.add_basemap(ax, source=cx.providers.Esri.WorldImagery, zoom=15)
            except Exception as e:
                print(f"Aviso: Falha ao carregar mapa de fundo: {e}")

            plt.title(f"Simulação de Dam Break: {nome}\nCota de Ruptura: {cota}m (SIRGAS 2000 / UTM 23S)", fontsize=14)
            plt.legend()
            
            # Salva o arquivo na pasta que o GitHub Actions está procurando
            output_file = f"{OUTPUT_DIR}/Relatorio_{nome}.pdf"
            plt.savefig(output_file, bbox_inches='tight', dpi=300)
            plt.close()
            print(f"✅ Relatório gerado: {output_file}")

    except Exception as e:
        print(f"❌ Erro fatal no processamento de {nome}: {e}")

if __name__ == "__main__":
    try:
        baixar_mde(f"https://docs.google.com/uc?export=download&id={ID_DRIVE}", MDE_LOCAL)
        df = pd.read_csv(CSV_LOCAL)
        df.columns = df.columns.str.strip().str.lower()
        for _, row in df.iterrows():
            processar(row)
    except Exception as e:
        print(f"Erro ao iniciar script: {e}")
