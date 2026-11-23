import unittest

from auto_check_factcheck import PartInfo, patch_markdown_content


class CheckedPartNumberTest(unittest.TestCase):
    def test_stale_automatic_list_warns_without_replacing_it(self):
        content = (
            "## ファクトチェック（一次資料）\n"
            "- [x] **対象の実型番を決める**（入手履歴より自動確認 2026-05-30）\n"
            "  - TTL系: `DM74LS93N`\n"
        )
        updated, result = patch_markdown_content(
            content, "74x93", PartInfo(ttl=["DM74LS93N", "SN74LS93N"]), [], []
        )
        self.assertEqual(updated, content)
        self.assertFalse(result.modified)
        self.assertEqual(len(result.warnings), 1)

    def test_matching_list_and_manual_check_do_not_warn(self):
        for note in ("入手履歴より自動確認 2026-05-30", "手動確認"):
            with self.subTest(note=note):
                content = (
                    "## ファクトチェック（一次資料）\n"
                    f"- [x] **対象の実型番を決める**（{note}）\n"
                    "  - TTL系: `DM74LS93N`\n"
                )
                _, result = patch_markdown_content(
                    content, "74x93", PartInfo(ttl=["DM74LS93N"]), [], []
                )
                self.assertEqual(result.warnings, [])


if __name__ == "__main__":
    unittest.main()
