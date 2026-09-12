import glob
import html
import json
import os
import re
import sqlite3
import xml.etree.ElementTree as ET

DB_FILE = 'sugarcane.db'
YEAR_SEASON = '69/70'

kml_files = glob.glob('*.kml')
if not kml_files:
  print('❌ ไม่พบไฟล์ .kml ในโฟลเดอร์นี้')
  exit()

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# สร้างตารางหากยังไม่มี
cursor.execute("""
CREATE TABLE IF NOT EXISTS sugar_plots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plot_id TEXT,
    farmer_name TEXT,
    contractor TEXT,
    main_group TEXT,
    sub_group TEXT,
    year_season TEXT,
    geojson_data TEXT
);
""")

# ล้างข้อมูลเดิมของปีนี้เพื่อบันทึกใหม่
cursor.execute(
    'DELETE FROM sugar_plots WHERE year_season = ?;', (YEAR_SEASON,)
)
conn.commit()

inserted_count = 0


def clean_tag(tag):
  return tag.split('}')[-1] if '}' in tag else tag


def clean_text(raw_html):
  cleanr = re.compile(r'<.*?>')
  text = re.sub(cleanr, '', raw_html)
  return html.unescape(text).strip()


for file_path in kml_files:
  file_name = os.path.basename(file_path)
  print(f'กำลังอ่าน: {file_name}...')

  num_match = re.search(r'\d+', file_name)
  fallback_main_group = (
      f'กลุ่มคิว {num_match.group(0)}'
      if num_match
      else file_name.replace('.kml', '')
  )

  try:
    tree = ET.parse(file_path)
    root = tree.getroot()
  except Exception as e:
    print(f'  ⚠️ ข้ามไฟล์ {file_name}: {e}')
    continue

  for elem in root.iter():
    if clean_tag(elem.tag) == 'Placemark':
      props = {}

      # ดึงข้อมูลจากตาราง HTML ใน <description>
      desc_elem = elem.find('.//{*}description')
      if (
          desc_elem is not None
          and desc_elem.text
          and '<table' in desc_elem.text
      ):
        desc_raw = desc_elem.text

        # ดึงกลุ่มคิวจากแท็ก <p><b>กลุ่มคิว:</b> 31_001</p>
        sub_p_match = re.search(
            r'<b>\s*กลุ่มคิว:\s*</b>\s*([^<]+)', desc_raw, re.IGNORECASE
        )
        if sub_p_match:
          props['รหัสกลุ่มคิว'] = sub_p_match.group(1).strip()

        # ดึงแถว <tr> ทั้งหมด และอ่านค่าจาก <td ...>
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', desc_raw, re.DOTALL)
        for row in rows:
          tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
          if len(tds) >= 2:
            k = clean_text(tds[0])
            v = clean_text(tds[1])
            if k and v:
              props[k] = v

      # ดึงค่ารหัสแปลง
      name_elem = elem.find('{*}name')
      plot_name = (
          props.get('รหัสแปลง')
          or props.get('รหัสแปลง11')
          or props.get('PLOT_ID')
          or (
              name_elem.text.strip()
              if name_elem is not None and name_elem.text
              else 'ไม่มีรหัส'
          )
      )

      # ดึงค่าชาวไร่
      farmer_name = (
          props.get('ชาวไร่')
          or props.get('ชื่อชาวไร่')
          or props.get('ชื่อ-สกุล ชาวไร่')
          or ''
      )

      # ดึงค่าผู้รับเหมา
      contractor = (
          props.get('ชื่อ-สกุล รับเหมา')
          or props.get('ชื่อผู้รับเหมา')
          or props.get('ผู้รับเหมา')
          or 'ไม่ระบุผู้รับเหมา'
      )

      # ดึงค่ากลุ่มย่อย และกลุ่มหลัก
      sub_group = (
          props.get('รหัสกลุ่มคิว')
          or props.get('รหัสกลุ่ม')
          or props.get('กลุ่มคิว')
          or props.get('sub_group')
          or 'ทั่วไป'
      )
      main_group = fallback_main_group
      if '/' in sub_group:
        main_group = f"กลุ่มคิว {sub_group.split('/')[0]}"
      elif '_' in sub_group:
        main_group = f"กลุ่มคิว {sub_group.split('_')[0]}"

      # พิกัด Polygon
      coord_elem = elem.find('.//{*}coordinates')
      geojson_dict = None
      if coord_elem is not None and coord_elem.text:
        raw_coords = coord_elem.text.strip().split()
        coords_list = []
        for pt in raw_coords:
          parts = pt.split(',')
          if len(parts) >= 2:
            try:
              coords_list.append([float(parts[0]), float(parts[1])])
            except ValueError:
              continue

        if len(coords_list) >= 3:
          if coords_list[0] != coords_list[-1]:
            coords_list.append(coords_list[0])
          geojson_dict = {'type': 'Polygon', 'coordinates': [coords_list]}
        elif len(coords_list) == 1:
          geojson_dict = {'type': 'Point', 'coordinates': coords_list[0]}

      geojson_data = (
          json.dumps(geojson_dict, ensure_ascii=False) if geojson_dict else ''
      )

      cursor.execute(
          """
            INSERT INTO sugar_plots (plot_id, farmer_name, contractor, main_group, sub_group, year_season, geojson_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
          (
              plot_name,
              farmer_name,
              contractor,
              main_group,
              sub_group,
              YEAR_SEASON,
              geojson_data,
          ),
      )
      inserted_count += 1

conn.commit()
conn.close()
print(f'✅ ปรับปรุงและบันทึกข้อมูลสำเร็จ {inserted_count} แปลง!')