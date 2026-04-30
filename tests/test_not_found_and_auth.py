import os
import unittest

import requests


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")


class TestNotFoundAndUnauthorizedPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            response = requests.get(f"{BASE_URL}/", timeout=3)
            response.raise_for_status()
        except Exception as exc:
            raise unittest.SkipTest(
                f"Server is not reachable at {BASE_URL}: {exc}"
            ) from exc

    def test_unknown_page_returns_404_template(self):
        response = requests.get(
            f"{BASE_URL}/this-page-should-not-exist",
            headers={"Accept": "text/html"},
            timeout=5,
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("ไม่พบหน้าที่คุณต้องการ", response.text)
        self.assertIn("ERROR 404", response.text)

    def test_unauthorized_admin_html_request_shows_not_found_page(self):
        response = requests.get(
            f"{BASE_URL}/admin/api/admins",
            headers={"Accept": "text/html"},
            timeout=5,
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("ไม่พบหน้าที่คุณต้องการ", response.text)

    def test_unknown_api_json_request_returns_json_error(self):
        response = requests.get(
            f"{BASE_URL}/api/endpoint-does-not-exist",
            headers={"Accept": "application/json"},
            timeout=5,
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("application/json", response.headers.get("content-type", ""))
        self.assertIn("detail", response.json())


if __name__ == "__main__":
    unittest.main(verbosity=2)
