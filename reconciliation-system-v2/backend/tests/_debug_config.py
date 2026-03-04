import sqlite3, json

conn = sqlite3.connect('data/app.db')
cursor = conn.cursor()

# Get config for id=1
cursor.execute('SELECT id, partner_code, service_code, report_template_path, report_cell_mapping FROM partner_service_config WHERE id=1')
row = cursor.fetchone()
print('=== Config ===')
print(f'ID: {row[0]}, Partner: {row[1]}, Service: {row[2]}')
print(f'Report template: {row[3]}')
if row[4]:
    rcm = json.loads(row[4])
    print(f'Report cell mapping: {json.dumps(rcm, indent=2)}')
else:
    print('Report cell mapping: None')

# Get workflow steps
cursor.execute('SELECT step_order, left_source, right_source, output_name, join_type, matching_rules, is_final_output FROM workflow_step WHERE config_id=1 ORDER BY step_order')
print('\n=== Workflow Steps ===')
for s in cursor.fetchall():
    print(f'Step {s[0]}: {s[1]} <-> {s[2]} -> {s[3]} (join={s[4]}, final={s[6]})')
    if s[5]:
        rules = json.loads(s[5])
        print(f'  Rules: {json.dumps(rules, indent=2)[:500]}')

# Get output configs
cursor.execute('SELECT output_name, display_name, columns_config, filter_status FROM output_config WHERE config_id=1')
print('\n=== Output Configs ===')
for o in cursor.fetchall():
    print(f'\n{o[0]} ({o[1]}):')
    if o[2]:
        cc = json.loads(o[2])
        print(f'  Columns: {json.dumps(cc, indent=2)}')
    print(f'  Filter: {o[3]}')

# Get data sources  
cursor.execute('SELECT source_name, display_name, source_type, file_config FROM data_source_config WHERE config_id=1')
print('\n=== Data Sources ===')
for d in cursor.fetchall():
    print(f'{d[0]} ({d[1]}): type={d[2]}')
    if d[3]:
        fc = json.loads(d[3])
        print(f'  file_config: {json.dumps(fc, indent=2)[:500]}')

conn.close()
