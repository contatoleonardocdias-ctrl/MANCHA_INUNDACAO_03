import pandas as pd
import rasterio
import os
import requests

# Use o ID do seu arquivo MDE no Drive aqui
FILE_ID = "1l0N_Zn4qV0JQwggbd_Wr_bTgYLcki1su"
MDE_NOME = "mde_diagnostico.tif"

def main():
    # Download rápido do MDE
    url = f"https://docs.google.com/uc?export=download&id={FILE_ID}"
    with open(MDE_NOME, "wb") as f:
        f.write(requests.get(url).content)

    # Lendo os dados do CSV que você mandou
    df = pd.read_csv('barragens.csv') # Ajuste o nome se necessário
    row = df.iloc[0]
    x, y = float(row['x_utm']), float(row['y_utm'])
    cota_csv = float(row['cota_ruptura'])

    with rasterio.open(MDE_NOME) as src:
        # Pega a linha/coluna do pixel
        py, px = src.index(x, y)
        
        print("\n--- DIAGNÓSTICO DE CORES ---")
        if py < 0 or py >= src.height or px < 0 or px >= src.width:
            print("❌ ERRO: O ponto está fora dos limites deste mapa MDE!")
            return

        # Lê a cota do terreno naquele pixel
        cota_terreno = src.read(1)[py, px]
        
        print(f"Sua coordenada CSV: X={x}, Y={y}")
        print(f"Sua Cota de Ruptura (CSV): {cota_csv}m")
        print(f"Cota real do terreno (no MDE): {cota_terreno}m")

        if cota_csv <= cota_terreno:
            print(f"\n❌ AQUI ESTÁ O ERRO: A cota de ruptura ({cota_csv}m) é menor ou igual à cota do chão ({cota_terreno}m).")
            print("Para gerar a mancha, a cota de ruptura PRECISA ser maior que o terreno.")
        else:
            print(f"\n✅ Cota OK: O terreno ({cota_terreno}m) é mais baixo que a ruptura. O erro é outro.")

if __name__ == "__main__":
    main()
