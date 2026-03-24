import rasterio
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, box, shape
import os
from rasterio.features import shapes
from rasterio.mask import mask as rio_mask

# --- CONFIG ---
MDE_LOCAL = "data/mde.tif"
CSV_LOCAL = "barragens.csv"
OUTPUT_DIR = "output"
EPSG_PROJETO = "EPSG:31983"
# --------------

os.makedirs(OUTPUT_DIR, exist_ok=True)

def salvar_estilo_qgis(nome):
    qml = f"""<?xml version="1.0" encoding="UTF-8"?>
<qgis version="3.28">
  <renderer-v2 type="singleSymbol">
    <symbols>
      <symbol type="fill">
        <layer class="SimpleFill">
          <prop k="color" v="173,216,230,120"/>
          <prop k="outline_color" v="0,0,255,255"/>
          <prop k="outline_width" v="0.5"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>
"""
    with open(f"{OUTPUT_DIR}/{nome}_mancha.qml", "w") as f:
        f.write(qml)

def processar(row):
    nome = str(row['nome_barragem']).strip().replace(" ", "_")
    cota = float(row['cota_ruptura'])
    x, y = float(row['x_utm']), float(row['y_utm'])

    try:
        with rasterio.open(MDE_LOCAL) as src:

            print(f"\n📍 {nome}")

            # 🔍 valida posição
            if not (src.bounds.left <= x <= src.bounds.right and
                    src.bounds.bottom <= y <= src.bounds.top):
                print("❌ Fora do raster")
                return

            area_foco = box(x - 2500, y - 5000, x + 2500, y + 2000)

            out_image, out_transform = rio_mask(src, [area_foco], crop=True)

            # 💾 salvar MDE recortado
            mde_saida = f"{OUTPUT_DIR}/{nome}_mde.tif"

            out_meta = src.meta.copy()
            out_meta.update({
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform
            })

            with rasterio.open(mde_saida, "w", **out_meta) as dest:
                dest.write(out_image)

            # 🔹 gerar mancha
            banda = out_image[0]
            flood_mask = (banda <= cota) & (banda > 0)

            geoms = []
            for geom, val in shapes(
                flood_mask.astype('uint8'),
                mask=flood_mask,
                transform=out_transform
            ):
                if val == 1:
                    geoms.append(shape(geom))

            if len(geoms) == 0:
                geoms = [Point(x, y).buffer(150)]

            gdf_mancha = gpd.GeoDataFrame(
                {'nome': nome},
                geometry=geoms,
                crs=src.crs
            )

            gdf_ponto = gpd.GeoDataFrame(
                {'nome': nome},
                geometry=[Point(x, y)],
                crs=EPSG_PROJETO
            ).to_crs(src.crs)

            # 💾 salvar shapefiles
            gdf_mancha.to_file(f"{OUTPUT_DIR}/{nome}_mancha.shp")
            gdf_ponto.to_file(f"{OUTPUT_DIR}/{nome}_ponto.shp")

            # 🎨 estilo automático
            salvar_estilo_qgis(nome)

            print("✅ MDE + mancha + ponto gerados")

    except Exception as e:
        print(f"❌ Erro: {e}")


if __name__ == "__main__":
    df = pd.read_csv(CSV_LOCAL)
    df.columns = df.columns.str.strip().str.lower()

    for _, row in df.iterrows():
        processar(row)

    print("\n📁 Arquivos:", os.listdir(OUTPUT_DIR))
