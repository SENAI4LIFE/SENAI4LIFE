import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("profile_publish", Path(__file__).resolve().parents[1] / "scripts/publish.py")
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)


class Publication(unittest.TestCase):
    @patch.object(publish.subprocess, "check_output", return_value="old-head\n")
    @patch.object(publish, "api", return_value={"object": {"sha": "new-head"}})
    def test_concurrent_change_prevents_all_writes(self, api, command):
        with self.assertRaises(RuntimeError):
            publish.publish()
        self.assertEqual(api.call_count, 1)
        self.assertEqual(len(api.call_args.args), 1)

    @patch.object(publish.subprocess, "check_output", side_effect=["head\n", "README.md\n"])
    @patch.object(publish, "api", return_value={"object": {"sha": "head"}})
    def test_non_asset_change_cannot_be_published(self, api, command):
        with self.assertRaises(ValueError):
            publish.publish()
        self.assertEqual(api.call_count, 1)

    @patch.object(publish.subprocess, "check_output", side_effect=["head\n", "assets/overview-dark.svg\n"])
    @patch.object(publish, "api")
    def test_publication_is_a_fast_forward_of_the_checked_head(self, api, command):
        api.side_effect = [
            {"object": {"sha": "head"}},
            {"sha": "blob"},
            {"tree": {"sha": "old-tree"}},
            {"sha": "new-tree"},
            {"sha": "new-commit"},
            {},
        ]
        publish.publish()
        self.assertEqual(api.call_args.args, ("git/refs/heads/main", {"sha": "new-commit", "force": False}))
        commit = api.call_args_list[-2].args[1]
        self.assertEqual(commit["parents"], ["head"])
        self.assertNotIn("author", commit)
        self.assertNotIn("committer", commit)


if __name__ == "__main__":
    unittest.main()
