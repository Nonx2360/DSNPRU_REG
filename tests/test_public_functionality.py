import unittest

import requests

from tests._api_client import BASE_URL, ensure_server_up


class TestPublicFunctionality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            ensure_server_up()
        except Exception as exc:
            raise unittest.SkipTest(
                f"Server is not reachable at {BASE_URL}: {exc}"
            ) from exc

    def test_system_info_response_shape(self):
        response = requests.get(f"{BASE_URL}/api/system_info", timeout=5)
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        expected_keys = {
            "version",
            "environment",
            "status",
            "total_students",
            "total_activities",
            "total_registrations",
            "last_updated",
        }
        self.assertTrue(expected_keys.issubset(payload.keys()))

    def test_search_students_short_query_returns_empty(self):
        response = requests.get(f"{BASE_URL}/api/search_students", params={"q": "a"}, timeout=5)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_public_activities_endpoint_available(self):
        response = requests.get(f"{BASE_URL}/api/activities", timeout=5)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)


if __name__ == "__main__":
    unittest.main(verbosity=2)
