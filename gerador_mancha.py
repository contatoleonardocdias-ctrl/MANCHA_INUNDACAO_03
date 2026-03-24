import rasterio
from rasterio.features import shapes
import geopandas as gpd
import pandas as pd
import os
import requests

def baixar_mde_pesado(url, destino):
    """Cria a pasta data e baixa o arquivo MDE do Google Drive se ele não existir"""
    if not os.path.exists('data'):
        os.makedirs('data')
        print("Pasta 'data' criada.")
    
    if not os.path.exists(destino):
        print(f"Iniciando download do MDE pesado para: {destino}")
        # Link de download direto formatado para o Google Drive
        response = requests.get(url, stream=True)
        response.raise_for_status() 
        with open(destino, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download concluído com sucesso!")
    else:
        print(f"O arquivo {destino} já existe localmente, pulando download.")

def gerar_mancha():
    # --- CONFIGURAÇÃO AJUSTADA COM SEU LINK ---
    # Link de download direto gerado a partir do seu compartilhamento
    ID_DRIVE = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su"
    url_mde = f"https://docs.google.com/uc?export=download&id={ID_DRIVE}"
    
    mde_local = "data/23S48_ZN.tif"
    arquivo_csv = "barragens.csv" 
    # ------------------------------------------

    # 1. Tenta baixar o MDE do Drive
    try:
        baixar_mde_pesado(url_mde, mde_local)
    except Exception as e:
        print(f"Erro ao obter arquivo do Google Drive: {e}")
        print("Verifique se o arquivo no Drive está com acesso para 'Qualquer pessoa com o link'.")
        return

    # 2. Verifica se a planilha existe na raiz
    if not os.path.exists(arquivo_csv):
        print(f"Erro: Arquivo {arquivo_csv} não encontrado!")
        return
    
    # 3. Processamento dos dados
    df = pd.read_csv(arquivo_csv)
    for _, row in df.iterrows():
        nome = row['nome_barragem']
        cota = row['cota_ruptura']
        # O script usa o nome do arquivo definido na planilha
        mde_path = f"data/{row['arquivo_mde']}"
        
        if not os.path.exists(mde_path):
            print(f"Aviso: Arquivo {mde_path} não encontrado para {nome}. Verifique o nome no CSV.")
            continue

        print(f"Processando inundação para: {nome} (Cota: {cota}m)...")
        with rasterio.open(mde_path) as src:
            raster = src.read(1)
            
            # Lógica: Seleciona pixels com altitude menor ou igual à cota de ruptura
            mask = (raster <= cota).astype('int16')
            
            # Transforma os pixels selecionados (valor 1) em polígonos vetoriais
            results = (
                {'properties': {'raster_val': v}, 'geometry': s}
                for i, (s, v) in enumerate(shapes(mask, mask=(mask == 1), transform=src.transform))
            )

            # Cria o GeoDataFrame (formato espacial)
            gdf = gpd.GeoDataFrame.from_features(list(results), crs=src.crs)
            
            if not os.path.exists('output'): 
                os.makedirs('output')
            
            # Salva o resultado final como Shapefile
            output_name = f"output/mancha_{nome}.shp"
            gdf.to_file(output_name)
            print(f"Sucesso: Arquivo gerado em {output_name}")

if __name__ == "__main__":
    gerar_mancha()
