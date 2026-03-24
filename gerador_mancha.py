import rasterio
import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
import contextily as cx
from shapely.geometry import Point
import requests
import os

# --- CONFIGURAÇÃO ---
ID_DRIVE = "seu_id_do_google_drive_aqui"  # Substitua pelo ID real do arquivo MDE
MDE_LOCAL = "data/mde.tif"
CSV_LOCAL = "barragens.csv"
OUTPUT_DIR = "output"
# --------------------

def baixar_mde_pesado(url, destino):
    """Cria a pasta data e baixa o arquivo MDE do Google Drive se ele não existir"""
    if not os.path.exists('data'):
        os.makedirs('data')
    if not os.path.exists(destino):
        print(f"Iniciando download do MDE...")
        # Link de download direto formatado para o Google Drive
        response = requests.get(url, stream=True)
        response.raise_for_status() 
        with open(destino, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download concluído com sucesso!")
    else:
        print(f"O arquivo {destino} já existe, pulando download.")

def processar_inundacao(row):
    nome = row['nome_barragem']
    cota = row['cota_ruptura']
    lat_ruptura = row['latitude_ruptura']
    lon_ruptura = row['longitude_ruptura']
    mde_path = MDE_LOCAL

    if not os.path.exists(mde_path):
        print(f"Erro: MDE não encontrado para {nome}.")
        return

    print(f"Processando inundação para {nome} (Cota {cota}m)...")
    
    with rasterio.open(mde_path) as src:
        # Lógica: Seleciona pixels com altitude menor ou igual à cota
        raster = src.read(1)
        mask = (raster <= cota).astype('int16')
        
        # Transforma os pixels selecionados em polígonos vetoriais
        from rasterio.features import shapes
        results = (
            {'properties': {'raster_val': v}, 'geometry': s}
            for i, (s, v) in enumerate(shapes(mask, mask=(mask == 1), transform=src.transform))
        )
        
        # Cria o GeoDataFrame (formato espacial)
        gdf = gpd.GeoDataFrame.from_features(list(results), crs=src.crs)
        # Converte para o sistema de coordenadas UTM do MDE, se necessário
        if src.crs.is_geographic:
             # Se for geográfico (WGS84), tenta converter para UTM (melhor para medição)
             # Neste caso, vamos direto para Web Mercator (EPSG:3857) para o Contextily
             gdf = gdf.to_crs(epsg=3857)
        else:
             # Se já for UTM, converte para Web Mercator (EPSG:3857) para o Contextily
             gdf = gdf.to_crs(epsg=3857)
             
        # Cria o Ponto de Rompimento a partir das coordenadas
        ponto_ruptura_wgs84 = gpd.GeoDataFrame({'nome': [f"Rompimento {nome}"]}, 
                                              geometry=[Point(lon_ruptura, lat_ruptura)], crs="EPSG:4326")
        # Converte o ponto para Web Mercator (EPSG:3857) para sobrepor no mapa
        ponto_ruptura = ponto_ruptura_wgs84.to_crs(epsg=3857)

        # --- GERAÇÃO DO MAPA PDF ---
        print(f"Gerando PDF do mapa para {nome}...")
        fig, ax = plt.subplots(figsize=(12, 12))
        
        # 1. Mancha de Inundação (Azul semi-transparente)
        gdf.plot(ax=ax, color='blue', edgecolor='black', alpha=0.5)
        
        # 2. Ponto de Rompimento (Vermelho)
        ponto_ruptura.plot(ax=ax, color='red', marker='X', markersize=200, label='Ponto de Rompimento')
        
        # 3. Adiciona Mapa de Satélite (Contextily)
        try:
             # Tenta adicionar o mapa de satélite da Esri. Pode falhar se não houver internet no servidor.
             cx.add_basemap(ax, crs=gdf.crs.to_string(), source=cx.providers.Esri.WorldImagery)
        except Exception as e:
             print(f"Aviso: Falha ao carregar mapa de satélite: {e}")
             ax.set_facecolor('white') # Fundo branco como plano B

        # Configurações do gráfico
        ax.set_title(f"Mancha de Inundação - {nome} (Cota {cota}m)")
        ax.legend()
        plt.tight_layout()
        
        # Salva o resultado final como PDF
        pdf_name = f"{OUTPUT_DIR}/mapa_inundacao_{nome}.pdf"
        plt.savefig(pdf_name, bbox_inches='tight')
        plt.close()
        print(f"PDF gerado com sucesso em: {pdf_name}")

if __name__ == "__main__":
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    url_mde = f"https://docs.google.com/uc?export=download&id={ID_DRIVE}"
    
    # 1. Tenta baixar o MDE
    try:
        baixar_mde_pesado(url_mde, MDE_LOCAL)
    except Exception as e:
        print(f"Erro ao obter arquivo do Drive: {e}")
        return

    # 2. Verifica o CSV
    if not os.path.exists(CSV_LOCAL):
        print(f"Erro: Arquivo {CSV_LOCAL} não encontrado!")
        return

    # 3. Processa cada barragem
    df = pd.read_csv(CSV_LOCAL)
    for _, row in df.iterrows():
        try:
            processar_inundacao(row)
        except Exception as e:
            print(f"Erro ao processar barragem {row['nome_barragem']}: {e}")

    print("Processamento concluído.")
