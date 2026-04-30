import unittest

import requests

from tests._api_client import (
    BASE_URL,
    admin_login,
    auth_headers,
    ensure_server_up,
    unique_username,
)


class TestAdminRBAC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            ensure_server_up()
        except Exception as exc:
            raise unittest.SkipTest(
                f"Server is not reachable at {BASE_URL}: {exc}"
            ) from exc

        try:
            cls.super_token = admin_login()
        except Exception as exc:
            raise unittest.SkipTest(str(exc)) from exc

        cls.staff_username = unique_username()
        cls.staff_password = "staff123"
        cls.staff_id = None

        create_response = requests.post(
            f"{BASE_URL}/admin/api/admins",
            json={
                "username": cls.staff_username,
                "password": cls.staff_password,
                "is_superuser": False,
            },
            headers=auth_headers(cls.super_token),
            timeout=5,
        )
        if create_response.status_code not in (200, 400):
            raise unittest.SkipTest(
                f"Could not prepare staff user. Status: {create_response.status_code}"
            )

        users_response = requests.get(
            f"{BASE_URL}/admin/api/admins",
            headers=auth_headers(cls.super_token),
            timeout=5,
        )
        if users_response.status_code == 200:
            for user in users_response.json():
                if user["username"] == cls.staff_username:
                    cls.staff_id = user["id"]
                    break

        login_response = requests.post(
            f"{BASE_URL}/admin/login",
            data={"username": cls.staff_username, "password": cls.staff_password},
            timeout=5,
        )
        if login_response.status_code != 200:
            raise unittest.SkipTest("Could not login as generated staff user")

        cls.staff_token = login_response.json()["access_token"]

    @classmethod
    def tearDownClass(cls):
        if not getattr(cls, "staff_id", None):
            return
        requests.delete(
            f"{BASE_URL}/admin/api/admins/{cls.staff_id}",
            headers=auth_headers(cls.super_token),
            timeout=5,
        )

    def test_superuser_can_access_logs(self):
        response = requests.get(
            f"{BASE_URL}/admin/api/logs",
            headers=auth_headers(self.super_token),
            timeout=5,
        )
        self.assertEqual(response.status_code, 200)

    def test_staff_cannot_access_logs(self):
        response = requests.get(
            f"{BASE_URL}/admin/api/logs",
            headers=auth_headers(self.staff_token),
            timeout=5,
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_cannot_manage_admins(self):
        response = requests.get(
            f"{BASE_URL}/admin/api/admins",
            headers=auth_headers(self.staff_token),
            timeout=5,
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_can_access_activity_groups(self):
        response = requests.get(
            f"{BASE_URL}/admin/api/activity_groups",
            headers=auth_headers(self.staff_token),
            timeout=5,
        )
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
