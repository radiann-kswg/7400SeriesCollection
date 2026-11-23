import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MASTER = Path("overview/7400_series_ic_overview.json")


class RarityMergeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.plans = self.root / "getstarting"
        self.plans.mkdir()
        (self.root / "overview").mkdir()
        (self.root / "scripts").mkdir()
        self.script = self.root / "scripts/merge_fp.py"
        shutil.copyfile(ROOT / "scripts/merge_fp.py", self.script)

    def test_public_catalog_generates_one_rare_entry_for_74x1244(self):
        shutil.copyfile(ROOT / MASTER, self.root / MASTER)
        subprocess.run([sys.executable, self.script], cwd=self.root, check=True)

        catalog = json.loads((self.root / MASTER).read_text(encoding="utf-8"))
        rare_parts = [row["PartNumber"] for row in catalog if row["Rarity"] == "Rare"]
        self.assertEqual(rare_parts.count("74x1244"), 1)
        generated = []
        for path in self.plans.glob("*.json"):
            rows = json.loads(path.read_text(encoding="utf-8"))
            generated.extend(row["PartNumber"] for row in rows)
        self.assertCountEqual(generated, [row["PartNumber"] for row in catalog])
        path = self.plans / "7400_series_ic_purchase_plan_rare.json"
        rare_plan = json.loads(path.read_text(encoding="utf-8"))
        self.assertCountEqual([row["PartNumber"] for row in rare_plan], rare_parts)

    def test_retired_rarity_is_rejected_before_writing(self):
        row = {"PartNumber": "74x1244", "Category": "01_buffers_inverters", "Rarity": "Rare+"}
        (self.root / MASTER).write_text(json.dumps([row], indent=2, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run([sys.executable, self.script], cwd=self.root, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"Unknown Rarity 'Rare+' for PartNumber=74x1244", result.stderr)
        self.assertEqual(list(self.plans.iterdir()), [])
