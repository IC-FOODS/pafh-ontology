import unittest
from unittest.mock import patch

import main


class CapabilitiesEndpointTests(unittest.IsolatedAsyncioTestCase):
    @patch("main._fetch_accessible_sources_for_user")
    async def test_capabilities_anonymous_uses_demo_mode_and_public_sources(self, mock_fetch):
        mock_fetch.return_value = [
            {
                "name": "Wikidata",
                "type": "external_api",
                "security_policy": {"query_domains": ["public"]},
                "allow_write_back": False,
            },
            {
                "name": "Private Ontop",
                "type": "ontop",
                "security_policy": {"query_domains": ["internal"]},
                "allow_write_back": True,
                "can_admin": True,
            },
        ]

        response = await main.get_capabilities(authorization=None)

        self.assertEqual(response["mode"], "demo")
        self.assertFalse(response["authenticated"])
        self.assertIsNone(response["user"])
        self.assertEqual(response["sources"]["public"], ["wikidata"])
        self.assertEqual(response["sources"]["private"], [])
        self.assertEqual(response["sources"]["accessible"], ["wikidata"])
        self.assertFalse(response["features"]["can_write_back"])
        self.assertFalse(response["features"]["can_manage_sources"])

    @patch("main._fetch_accessible_sources_for_user")
    @patch("main._validate_user_token")
    async def test_capabilities_authenticated_uses_integrated_mode(self, mock_validate, mock_fetch):
        mock_validate.return_value = {"user_id": 7, "username": "alice"}
        mock_fetch.return_value = [
            {
                "name": "Wikidata",
                "type": "external_api",
                "security_policy": {"query_domains": ["public"]},
                "allow_write_back": False,
            },
            {
                "name": "Private Ontop",
                "type": "ontop",
                "security_policy": {"query_domains": ["internal"]},
                "allow_write_back": True,
                "can_manage": True,
            },
        ]

        response = await main.get_capabilities(authorization="Bearer token123")

        self.assertEqual(response["mode"], "integrated")
        self.assertTrue(response["authenticated"])
        self.assertEqual(response["user"]["user_id"], 7)
        self.assertEqual(response["sources"]["public"], ["wikidata"])
        self.assertEqual(response["sources"]["private"], ["private_ontop"])
        self.assertEqual(response["sources"]["accessible"], ["private_ontop", "wikidata"])
        self.assertTrue(response["features"]["can_view_private"])
        self.assertTrue(response["features"]["can_write_back"])
        self.assertTrue(response["features"]["can_manage_sources"])


if __name__ == "__main__":
    unittest.main()
