import requests

# Login first to get token
login_resp = requests.post('http://localhost:8000/api/v1/auth/login', json={'email': 'admin@vnpt.vn', 'password': 'admin123'})
token = login_resp.json().get('access_token')

# Get configs with include_inactive=true
configs_resp = requests.get('http://localhost:8000/api/v1/configs/?include_inactive=true', headers={'Authorization': f'Bearer {token}'})
print('Status:', configs_resp.status_code)
if configs_resp.status_code == 200:
    data = configs_resp.json()
    print('Count:', len(data))
    for c in data:
        print(f"  {c['id']}: {c['partner_code']} - {c['service_code']}")
else:
    print('Error:', configs_resp.text)
