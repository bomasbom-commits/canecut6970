import json
import os
import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

DB_FILE = r'D:\sugarcane--Group-yearรวมปี\รวมปี\6970\sugarcane.db'

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

class ReassignRequest(BaseModel):
  plot_id: str
  main_group: str
  sub_group: str

# 🟢 บังคับเสิร์ฟไฟล์หน้าเว็บโดยตรง (รองรับกรณี Windows ซ่อนนามสกุลไฟล์)
@app.get('/')
def serve_index():
  if os.path.exists('index.html'):
    return FileResponse('index.html')
  elif os.path.exists('index.html.html'):
    return FileResponse('index.html.html')
  else:
    raise HTTPException(status_code=404, detail='หาไฟล์หน้าเว็บไม่เจอ โปรดตรวจสอบว่าไฟล์ชื่อ index.html วางอยู่ในโฟลเดอร์เดียวกันแล้ว')

@app.get('/api/plots')
def get_plots():
  if not os.path.exists(DB_FILE):
    raise HTTPException(status_code=500, detail=f'ไม่พบไฟล์ฐานข้อมูลที่ {DB_FILE}')

  conn = sqlite3.connect(DB_FILE)
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()

  try:
    cursor.execute('SELECT plot_id, farmer_name, contractor, main_group, sub_group, geojson_data FROM sugar_plots')
    rows = cursor.fetchall()
  except Exception as e:
    conn.close()
    raise HTTPException(status_code=500, detail=f'SQL Error: {str(e)}')
  finally:
    conn.close()

  features = []
  for row in rows:
    geojson_raw = row['geojson_data']
    if not geojson_raw:
      continue

    try:
      parsed_geom = json.loads(geojson_raw) if isinstance(geojson_raw, str) else geojson_raw

      if isinstance(parsed_geom, list):
        geom = {"type": "Polygon", "coordinates": parsed_geom}
      elif isinstance(parsed_geom, dict):
        geom = parsed_geom.get('geometry') if parsed_geom.get('type') == 'Feature' else parsed_geom
      else:
        continue

      if not geom:
        continue

      features.append({
          'type': 'Feature',
          'geometry': geom,
          'properties': {
              'รหัสแปลง': str(row['plot_id'] or 'ไม่มีรหัส'),
              'ชาวไร่': str(row['farmer_name'] or ''),
              'ผู้รับเหมา': str(row['contractor'] or 'ไม่ระบุผู้รับเหมา'),
              'main_grp': str(row['main_group'] or 'ทั่วไป'),
              'sub_grp': str(row['sub_group'] or 'ทั่วไป'),
          },
      })
    except Exception as e:
      print(f"⚠️ ข้ามแปลง {row['plot_id']}: {e}")
      continue

  return JSONResponse(content={'type': 'FeatureCollection', 'features': features})

@app.post('/api/reassign')
def reassign_plot(data: ReassignRequest):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE sugar_plots SET main_group = ?, sub_group = ? WHERE plot_id = ?",
      (data.main_group, data.sub_group, data.plot_id),
  )
  conn.commit()
  conn.close()
  return {'status': 'success'}

if __name__ == '__main__':
  import uvicorn
  uvicorn.run('server:app', host='0.0.0.0', port=8000, reload=True)