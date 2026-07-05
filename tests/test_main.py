import unittest

from main import app


class MainAppTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_root_and_health_routes_return_ok(self):
        for path in ("/", "/healthz"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"ok", response.data.lower())

    def test_webhook_alpha_get_is_safe(self):
        response = self.client.get("/webhook_alpha")
        self.assertIn(response.status_code, (200, 405))


if __name__ == "__main__":
    unittest.main()
