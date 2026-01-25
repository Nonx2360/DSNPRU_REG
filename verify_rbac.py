
import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def log(msg):
    with open("verification_result.txt", "a") as f:
        f.write(msg + "\n")
    print(msg)

def login(username, password):
    response = requests.post(f"{BASE_URL}/admin/login", data={"username": username, "password": password})
    if response.status_code == 200:
        return response.json()["access_token"]
    return None

def test_rbac():
    # Clear previous log
    with open("verification_result.txt", "w") as f:
        f.write("Starting Verification\n")

    log("1. Login as Admin (Superuser)...")
    admin_token = login("admin", "admin123")
    if not admin_token:
        log("FAIL: Could not login as admin")
        return
    log("SUCCESS: Logged in as admin")

    log("\n2. Create Staff User...")
    staff_data = {"username": "test_staff", "password": "staff123", "is_superuser": False}
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.post(f"{BASE_URL}/admin/api/admins", json=staff_data, headers=headers)
    if response.status_code == 200:
        log("SUCCESS: Created staff user")
    elif response.status_code == 400 and "already exists" in response.text: # Thai text might be tricky to match exactly if encoding issue
         log("INFO: Staff user already exists, proceeding")
    else:
        log(f"FAIL: Could not create staff user: {response.text}")

    log("\n3. Login as Staff...")
    staff_token = login("test_staff", "staff123")
    if not staff_token:
        log("FAIL: Could not login as staff")
        return
    log("SUCCESS: Logged in as staff")

    log("\n4. Staff Access Check: Logs (Should be 403)...")
    headers = {"Authorization": f"Bearer {staff_token}"}
    response = requests.get(f"{BASE_URL}/admin/api/logs", headers=headers)
    if response.status_code == 403:
        log("SUCCESS: Access denied for logs (403)")
    else:
        log(f"FAIL: Staff accessed logs with status {response.status_code}")

    log("\n5. Staff Access Check: Manage Admins (Should be 403)...")
    response = requests.get(f"{BASE_URL}/admin/api/admins", headers=headers)
    if response.status_code == 403:
        log("SUCCESS: Access denied for admin management (403)")
    else:
        log(f"FAIL: Staff accessed admin management with status {response.status_code}")

    log("\n6. Staff Access Check: Activity Groups (Should be 200)...")
    response = requests.get(f"{BASE_URL}/admin/api/activity_groups", headers=headers)
    if response.status_code == 200:
        log("SUCCESS: Staff accessed activity groups")
    else:
        log(f"FAIL: Staff could not access activity groups with status {response.status_code}")
    
    log("\n7. Cleanup: Delete Staff User...")
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{BASE_URL}/admin/api/admins", headers=headers)
    staff_id = None
    if response.status_code == 200:
        for user in response.json():
            if user["username"] == "test_staff":
                staff_id = user["id"]
                break
    
    if staff_id:
        response = requests.delete(f"{BASE_URL}/admin/api/admins/{staff_id}", headers=headers)
        if response.status_code == 204:
            log("SUCCESS: Deleted test_staff user")
        else:
             log(f"FAIL: Could not delete test_staff user: {response.status_code}")
    else:
        log("FAIL: Could not find test_staff user to delete")

if __name__ == "__main__":
    try:
        test_rbac()
    except Exception as e:
        log(f"An error occurred: {e}")
