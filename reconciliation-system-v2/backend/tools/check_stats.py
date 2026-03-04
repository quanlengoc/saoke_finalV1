import sqlite3
import json

conn = sqlite3.connect('data/app.db')
cur = conn.cursor()
cur.execute('SELECT batch_id, summary_stats FROM reconciliation_logs ORDER BY created_at DESC LIMIT 1')
row = cur.fetchone()
print('Batch:', row[0])
stats = json.loads(row[1]) if row[1] else {}
print('Keys in summary_stats:', list(stats.keys()))
print('matching_stats:', stats.get('matching_stats', 'NOT FOUND'))
conn.close()
