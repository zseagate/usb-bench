import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import usb_bench  # noqa: E402


class TestVerdict(unittest.TestCase):
    def test_good(self):
        v, _ = usb_bench.verdict(50, 5)
        self.assertEqual(v, "GOOD")

    def test_pass(self):
        v, _ = usb_bench.verdict(20, 2)
        self.assertEqual(v, "PASS")

    def test_warn(self):
        v, _ = usb_bench.verdict(10, 1)
        self.assertEqual(v, "WARN")

    def test_fail_seq_write(self):
        v, _ = usb_bench.verdict(9.9, 2)
        self.assertEqual(v, "FAIL")

    def test_fail_rand_write(self):
        v, _ = usb_bench.verdict(100, 0.9)
        self.assertEqual(v, "FAIL")

    def test_asolid(self):
        v, _ = usb_bench.verdict(1.87, 0.27)
        self.assertEqual(v, "FAIL")


class TestHelpers(unittest.TestCase):
    def test_md_cell_none(self):
        self.assertEqual(usb_bench.md_cell(None), "-")

    def test_md_cell_float(self):
        self.assertEqual(usb_bench.md_cell(1.234), "1.23")

    def test_human_gib(self):
        self.assertEqual(usb_bench.human_gib(128 * 1024 ** 3), "128.0 GiB")

    def test_notes_bot_write_through(self):
        notes = usb_bench.notes_for({
            "seq_read_mbs": 200,
            "fsync4k_mbs": 0.13,
            "protocol": "BOT (Bulk-Only)",
            "write_cache": "write through",
            "fstype": "ext4",
        })
        text = "\n".join(notes)
        self.assertIn("BOT", text)
        self.assertIn("write through", text)
        self.assertIn("fsync", text)


if __name__ == "__main__":
    unittest.main()
