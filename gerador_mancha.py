import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon, Point
import os
import math

# --- Configurações ---
ARQUIVO_BARRAGENS = 'barragens.csv'
NOME_ARQUIVO_SAIDA = 'MANCHA_NOVO_03.shp'

# Parâmetros simplificados para a mancha (exemplo, em METROS agora)
DISTANCIA_METROS = 5000       # Extensão da mancha rio abaixo (5 km)
LARGURA_FINAL_METROS = 2000   # Largura da mancha no final da extensão (2 km)

# Direção do fluxo em graus (0=Norte, 90=Leste, 180=Sul, 270=Oeste)
# *Ajuste este valor conforme a direção real do vale!*
# Exemplo: Sudeste = 135
DIRECAO_FLUXO_GRAUS = 135

def criar_mancha_simplificada_utm(x_utm, y_utm, distancia_m, largura_final_m, direcao_graus):
    """
    Cria uma geometria de mancha simplificada (triângulo/leque)
    trabalhando diretamente com coordenadas UTM (metros).
    """
    # Ponto da barragem (vértice do leque)
    ponto_barragem = Point(x_utm, y_utm)

    # Calcular o ponto final central do leque
    # Usando trigonometria simples (seno/cosseno) para calcular o deslocamento
    angulo_rad = math.radians(direcao_graus)
    dx = distancia_m * math.sin(angulo_rad)
    dy = distancia_m * math.cos(angulo_rad)

    ponto_final_centro = Point(x_utm + dx, y_utm + dy)

    # Calcular os pontos laterais do final (perpendiculares à direção do fluxo)
    # Metade da largura para cada lado
    angulo_perpendicular_rad = angulo_rad + math.pi/2
    dx_lat = (largura_final_m / 2.0) * math.sin(angulo_perpendicular_rad)
    dy_lat = (largura_final_m / 2.0) * math.cos(angulo_perpendicular_rad)

    ponto_final_dir = Point(ponto_final_centro.x + dx_lat, ponto_final_centro.y + dy_lat)
    ponto_final_esq = Point(ponto_final_centro.x - dx_lat, ponto_final_centro.y - dy_lat)

    # Criar o polígono (triângulo: barragem -> final esq -> final dir)
    coords = [
        (ponto_barragem.x, ponto_barragem.y),
        (ponto_final_esq.x, ponto_final_esq.y),
        (ponto_final_dir.x, ponto_final_dir.y)
    ]
    poligono_mancha = Polygon(coords)

    return poligono_mancha

def main():
    print("Iniciando geração de mancha simplificada (UTM)...")

    # 1. Ler os dados das barragens
    if not os.path.exists(ARQUIVO_BARRAGENS):
        print(f"Erro: Arquivo {ARQUIVO_BARRAGENS} não encontrado.")
        return

    try:
        # Lê o CSV especificando o separador como vírgula (padrão do GitHub preview)
        df_barragens = pd.read_csv(ARQUIVO_BARRAGENS)
    except Exception as e:
        print(f"Erro ao ler CSV: {e}")
        return

    # Limpar possíveis espaços em branco nos nomes das colunas e dados
    df_barragens.columns = df_barragens.columns.str.strip()

    # Verificar se as colunas necessárias existem com base na imagem do CSV
    colunas_esperadas = ['nome_barragem', 'x_utm', 'y_utm', 'epsg']
    if not all(col in df_barragens.columns for col in colunas_esperadas):
        print(f"Erro: O CSV deve conter as colunas: {', '.join(colunas_esperadas)}")
        print(f"Colunas encontradas: {', '.join(df_barragens.columns)}")
        return

    # Usar a primeira barragem como exemplo (Gênesis I)
    barragem_alvo = df_barragens.iloc[0]
    nome = barragem_alvo['nome_barragem']
    x = barragem_alvo['x_utm']
    y = barragem_alvo['y_utm']
    epsg_csv = int(barragem_alvo['epsg'])
    
    # Criar a string de CRS (ex: "EPSG:31983")
    crs_final = f"EPSG:{epsg_csv}"

    print(f"Processando barragem: {nome}")
    print(f"Coordenadas (UTM): {x}, {y} (Sistema: {crs_final})")

    # 2. Criar a geometria da mancha (trabalhando em metros)
    mancha_geom = criar_mancha_simplificada_utm(
        x, y,
        DISTANCIA_METROS,
        LARGURA_FINAL_METROS,
        DIRECAO_FLUXO_GRAUS
    )

    # 3. Criar um GeoDataFrame, definindo o CRS correto que veio do CSV
    data = {'nome_barragem': [nome], 'tipo': ['Mancha Simplificada']}
    gdf = gpd.GeoDataFrame(data, geometry=[mancha_geom], crs=crs_final)

    # 4. Salvar como Shapefile
    print(f"Salvando mancha em {NOME_ARQUIVO_SAIDA}...")
    # GeoPandas gerencia a criação dos múltiplos arquivos (.shp, .shx, .dbf, .prj)
    try:
        gdf.to_file(NOME_ARQUIVO_SAIDA, driver='ESRI Shapefile')
        print("Concluído com sucesso!")
    except Exception as e:
        print(f"Erro ao salvar Shapefile: {e}")

if __name__ == "__main__":
    main()
