import pandas as pd
import geopandas as gpd
import rasterio
import numpy as np
from shapely.geometry import shape
from rasterio.features import shapes
from scipy.ndimage import binary_dilation
import os
import requests

# Configurações do Google Drive (Seu MDT)
FILE_ID = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su"
MDE_NOME = "23S48_ZN.tif"
OUTPUT_NAME = "MANCHA_FINAL_ESTAVEL"

def download_mde(id, destination):
    if not os.path.exists(destination):
        print("Baixando MDT do Google Drive...")
        # URL de download direto do Google Drive
        url = f"https://docs.google.com/uc?export=download&id={id}"
        session = requests.Session()
        response = session.get(url, stream=True)
        with open(destination, "wb") as f:
            for chunk in response.iter_content(32768):
                if chunk: f.write(chunk)
        print("Download concluído.")

def main():
    # 1. Preparação
    download_mde(FILE_ID, MDE_NOME)
    
    # Lendo dados do CSV (coordenadas, cota e EPSG)
    try:
        df = pd.read_csv('barragens.csv')
        row = df.iloc[0]
        # Garantir que os nomes das colunas batam com o seu CSV
        x, y = float(row['x_utm']), float(row['y_utm'])
        cota_ruptura = float(row['cota_ruptura'])
        epsg_alvo = int(row['epsg'])
    except Exception as e:
        print(f"ERRO ao ler barragens.csv: {e}")
        return

    print(f"Iniciando: Ponto ({x}, {y}) | Cota de Ruptura: {cota_ruptura}m")

    # 2. Processamento do Raster com Rasterio e Scipy
    with rasterio.open(MDE_NOME) as src:
        raster = src.read(1)
        transform = src.transform
        nodata = src.nodata

        # --- VALIDAÇÃO DE COORDENADAS (Blindagem contra IndexError) ---
        # Converte coordenada UTM para índice de linha/coluna no raster
        try:
            py, px = src.index(x, y)
        except Exception:
            print(f"ERRO: Não foi possível converter as coordenadas ({x}, {y}) em índices do raster.")
            return
        
        # Verifica se o ponto está dentro dos limites geográficos do MDT
        if py < 0 or py >= src.height or px < 0 or px >= src.width:
            print(f"ERRO CRÍTICO: O ponto ({x}, {y}) está fora dos limites do MDT!")
            print(f"Limites do MDT (Bounds): {src.bounds}")
            return

        # Passo A: Criar Máscara de Cota (Tudo que pode potencialmente inundar)
        mask_cota = (raster <= cota_ruptura) & (raster != nodata)

        # Passo B: Lógica de Inundação Conectada (Flood Fill)
        # Começamos no ponto do barramento e espalhamos apenas para áreas conectadas e baixas
        seed = np.zeros_like(mask_cota, dtype=bool)
        seed[py, px] = True # Ponto de início da ruptura
        
        inundacao = np.zeros_like(mask_cota, dtype=bool)
        
        # Loop de propagação (1000 iterações cobrem uma distância considerável)
        print("Propagando inundação a jusante...")
        for i in range(1000):
            # Expande a área inundada atual por 1 pixel em todas as direções
            expandida = binary_dilation(seed, structure=np.ones((3,3)))
            # A nova área inundada é a expansão limitada pela cota e pelo terreno
            seed = expandida & mask_cota
            
            # Se não houver mais para onde expandir, para o loop
            if not seed.any(): 
                print(f"Propagação finalizada na iteração {i}.")
                break
            # Acumula a área inundada
            inundacao |= seed

        # 3. Vetorização (Transforma raster em Shapefile)
        print("Vetorizando resultados...")
        results = (
            {'properties': {'id': 1}, 'geometry': s}
            for i, (s, v) in enumerate(shapes(inundacao.astype('int16'), 
                                             mask=inundacao==1, 
                                             transform=transform))
        )
        
        geometrias = [shape(res['geometry']) for res in results]

    if geometrias:
        # Criar pasta output se não existir
        if not os.path.exists('output'): os.makedirs('output')
        
        # Criar GeoDataFrame com o EPSG correto
        gdf = gpd.GeoDataFrame(geometry=geometrias, crs=f"EPSG:{epsg_alvo}")
        
        # Unificar polígonos soltos em uma mancha única e limpa
        gdf_dissolved = gdf.dissolve() 
        
        output_path = f"output/{OUTPUT_NAME}.shp"
        gdf_dissolved.to_file(output_path)
        print(f"SUCESSO! Arquivo gerado em: {output_path}")
    else:
        print("ERRO: Nenhuma mancha gerada. Verifique se o ponto de ruptura está acima da cota do terreno no MDT.")

if __name__ == "__main__":
    main()
