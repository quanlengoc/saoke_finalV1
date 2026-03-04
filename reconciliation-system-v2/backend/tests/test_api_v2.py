"""
Quick test script for API v2
"""
import requests
import json

BASE_URL = "http://localhost:8001/api/v2"

def test_configs():
    """Test configs endpoint"""
    print("=" * 50)
    print("Testing GET /api/v2/configs/")
    print("=" * 50)
    
    try:
        response = requests.get(f"{BASE_URL}/configs/")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Total configs: {data.get('total', 0)}")
            for item in data.get('items', []):
                print(f"  - {item['partner_code']}/{item['service_code']}: {item['partner_name']}")
                print(f"    Data sources: {len(item.get('data_sources', []))}")
                print(f"    Workflow steps: {len(item.get('workflow_steps', []))}")
                print(f"    Output configs: {len(item.get('output_configs', []))}")
        else:
            print(f"Error: {response.text}")
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to server. Make sure it's running on port 8001")
    except Exception as e:
        print(f"Error: {e}")


def test_config_by_id(config_id=1):
    """Test get config by ID"""
    print("\n" + "=" * 50)
    print(f"Testing GET /api/v2/configs/{config_id}")
    print("=" * 50)
    
    try:
        response = requests.get(f"{BASE_URL}/configs/{config_id}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"Error: {response.text}")
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to server")
    except Exception as e:
        print(f"Error: {e}")


def test_data_sources(config_id=1):
    """Test data sources endpoint"""
    print("\n" + "=" * 50)
    print(f"Testing GET /api/v2/data-sources/by-config/{config_id}")
    print("=" * 50)
    
    try:
        response = requests.get(f"{BASE_URL}/data-sources/by-config/{config_id}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            for ds in data:
                print(f"  - {ds['source_name']}: {ds['source_type']} ({ds.get('display_name', 'N/A')})")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")


def test_workflows(config_id=1):
    """Test workflows endpoint"""
    print("\n" + "=" * 50)
    print(f"Testing GET /api/v2/workflows/by-config/{config_id}")
    print("=" * 50)
    
    try:
        response = requests.get(f"{BASE_URL}/workflows/by-config/{config_id}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            for ws in data:
                print(f"  Step {ws['step_order']}: {ws['step_name']}")
                print(f"    {ws['left_source']} <-> {ws['right_source']} => {ws['output_name']}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_configs()
    test_config_by_id(1)
    test_data_sources(1)
    test_workflows(1)
