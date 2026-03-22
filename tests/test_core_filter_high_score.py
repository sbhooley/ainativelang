import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.adapters.builtins import CoreBuiltinAdapter


class TestFilterHighScore(unittest.TestCase):
    def test_keeps_by_score_key(self):
        adp = CoreBuiltinAdapter()
        items = [{"id": "a", "score": 7}, {"id": "b", "score": 9}]
        out = adp.call("filter_high_score", [items, 8], {})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["id"], "b")

    def test_relevance_alias(self):
        adp = CoreBuiltinAdapter()
        items = [{"id": "x", "relevance": 10}]
        out = adp.call("filter_high_score", [items, 8], {})
        self.assertEqual(out, items)

    def test_resolves_list_var_name_from_frame(self):
        adp = CoreBuiltinAdapter()
        items = [{"id": "a", "score": 9}]
        frame = {"scored_list": items}
        out = adp.call("filter_high_score", ["scored_list", 8], frame)
        self.assertEqual(out, items)


if __name__ == "__main__":
    unittest.main()
