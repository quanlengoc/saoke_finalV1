import sqlite3
conn = sqlite3.connect('data/app.db')
cur = conn.cursor()
cur.execute("SELECT matching_rules_b1b4 FROM partner_service_config WHERE partner_code='SACOMBANK' AND service_code='TOPUP'")
result = cur.fetchone()
print("matching_rules_b1b4:")
print(result[0] if result else None)
conn.close()
