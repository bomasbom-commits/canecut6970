import json
import sqlite3

DB_FILE = 'sugarcane.db'
OUTPUT_JSON = 'plots_data.json'

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# ดึงข้อมูลแปลงทั้งหมดออกมา
cursor.execute("""
    SELECT plot_id, farmer_name, contractor, main_group, sub_group, year_season, geojson_data
    FROM sugar_plots
""")
rows = cursor.fetchall()

features = []

for row in rows:
  plot_id, farmer_name, contractor, main_group, sub_group, year_season, geojson_str = (
      row
  )

  if not geojson_str:
    continue

  try:
    geometry = json.loads(geojson_str)
  except Exception:
    continue

  feature = {
      'type': 'Feature',
      'geometry': geometry,
      'properties': {
          'รหัสแปลง': plot_id,
          'ชาวไร่': farmer_name,
          'ผู้รับเหมา': contractor,
          'main_grp': main_group,
          'sub_grp': sub_group,
          'year_season': year_season,
      },
  }
  features.append(feature)

geojson_bundle = {'type': 'FeatureCollection', 'features': features}

with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
  json.dump(geojson_bundle, f, ensure_ascii=False)

conn.close()
print(
    f'✅ ส่งออกข้อมูลสำเร็จ! ได้ไฟล์ {OUTPUT_JSON} (ทั้งหมด {len(features)} แปลง)'
)