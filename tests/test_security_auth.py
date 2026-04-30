import unittest

import requests

from tests._api_client import BASE_URL, ensure_server_up


class TestSecurityAndAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            ensure_server_up()
        except Exception as exc:
            raise unittest.SkipTest(
                f"Server is not reachable at {BASE_URL}: {exc}"
            ) from exc

    def test_invalid_login_is_rejected(self):
        response = requests.post(
            f"{BASE_URL}/admin/login",
            data={"username": "wrong-user", "password": "wrong-pass"},
            timeout=5,
        )
        self.assertEqual(response.status_code, 401)

    def test_protected_endpoint_requires_token(self):
        response = requests.get(f"{BASE_URL}/admin/api/activity_groups", timeout=5)
        self.assertEqual(response.status_code, 401)

    def test_malformed_token_is_rejected(self):
        response = requests.get(
            f"{BASE_URL}/admin/api/activity_groups",
            headers={"Authorization": "Bearer this-is-not-a-valid-jwt"},
            timeout=5,
        )
        self.assertEqual(response.status_code, 401)

    def test_unknown_api_endpoint_returns_404_not_500(self):
        response = requests.get(
            f"{BASE_URL}/api/../../etc/passwd",
            headers={"Accept": "application/json"},
            timeout=5,
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())


if __name__ == "__main__":
    unittest.main(verbosity=2)
