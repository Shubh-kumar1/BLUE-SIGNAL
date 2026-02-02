import requests
import json

def test_backend():
    base_url = "http://127.0.0.1:5000"
    
    print("Testing BlueSignal Backend...")
    
    try:
        response = requests.get(f"{base_url}/api/health")
        print(f"Health check: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"Health check failed: {e}")
        return False
    
    try:
        test_user = {
            "username": "testcitizen",
            "email": "test@example.com",
            "password": "testpass123",
            "role": "citizen",
            "full_name": "Test Citizen"
        }
        
        response = requests.post(f"{base_url}/api/auth/register", json=test_user)
        print(f"Registration test: {response.status_code} - {response.json()}")
        
        if response.status_code == 201:
            login_data = {
                "username": "testcitizen",
                "password": "testpass123"
            }
            
            response = requests.post(f"{base_url}/api/auth/login", json=login_data)
            print(f"Login test: {response.status_code} - {response.json()}")
            
    except Exception as e:
        print(f"Auth test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    test_backend()
