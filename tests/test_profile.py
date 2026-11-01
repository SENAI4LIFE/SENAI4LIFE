import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location("profile_assets", Path(__file__).resolve().parents[1] / "scripts/profile.py")
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


class Contributions(unittest.TestCase):
    def test_unfinished_day_preserves_yesterdays_streak(self):
        days = [("2026-10-29", 0, 0), ("2026-10-30", 2, 1), ("2026-10-31", 1, 1), ("2026-11-01", 0, 0)]
        self.assertEqual(profile.streaks(days), (2, 2))

    def test_gap_breaks_streak_but_keeps_longest(self):
        counts = [2, 1, 4, 0, 0, 1]
        self.assertEqual(profile.streaks([(str(i), count, 0) for i, count in enumerate(counts)]), (1, 3))
        self.assertEqual(profile.streaks([]), (0, 0))
        self.assertEqual(profile.streaks([("2026-11-01", 0, 0)]), (0, 0))

    def test_calendar_parses_counts_and_orders_column_markup(self):
        parser = profile.CalendarParser()
        for i in reversed(range(365)):
            date = profile.dt.date(2025, 11, 2) + profile.dt.timedelta(days=i)
            count = "No" if i == 0 else "1,200" if i == 364 else "1"
            parser.feed(f'<td data-date="{date}" id="contribution-day-{i}" data-level="1"></td><tool-tip for="contribution-day-{i}">{count} contributions on a day.</tool-tip>')
        days = parser.days()
        self.assertEqual(days[0], ("2025-11-02", 0, 1))
        self.assertEqual(days[-1], ("2026-11-01", 1200, 1))

    def test_incomplete_or_changed_markup_is_rejected(self):
        with self.assertRaises(ValueError):
            profile.CalendarParser().days()
        parser = profile.CalendarParser()
        with self.assertRaises(ValueError):
            parser.feed('<tool-tip for="contribution-day-1">Unexpected format</tool-tip>')


class Repositories(unittest.TestCase):
    def test_pagination_filters_private_forks_and_profile(self):
        calls = []
        def fetch(path):
            calls.append(path)
            if "page=2" in path:
                return [{"name": "final", "private": False, "fork": False}]
            repos = [{"name": f"project-{i}", "private": False, "fork": False} for i in range(100)]
            repos[0]["private"] = True
            repos[1]["fork"] = True
            repos[2]["name"] = profile.OWNER
            return repos
        repos = profile.public_repositories(fetch)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(repos), 98)
        self.assertEqual(repos[-1]["name"], "final")
        self.assertTrue(all(not r["private"] and not r["fork"] for r in repos))


class ContributionAnimation(unittest.TestCase):
    def test_route_eats_each_active_cell_on_its_first_visit(self):
        cells = {(0, 0): 1, (0, 1): 0, (0, 2): 2, (1, 0): 3, (1, 1): 0, (1, 2): 4}
        route, eaten = profile.contribution_route(cells)
        self.assertEqual(set(eaten), {position for position, count in cells.items() if count})
        self.assertTrue(cells[route[0]] > 0)
        for before, after in zip(route, route[1:]):
            self.assertIn(after, cells)
            self.assertEqual(abs(before[0]-after[0])+abs(before[1]-after[1]), 1)
        for position, step in eaten.items():
            self.assertEqual(step, route.index(position))

    def test_empty_calendar_has_no_food_or_moving_body(self):
        self.assertEqual(profile.contribution_route({(0, 0): 0}), ([], {}))

    def test_disconnected_food_is_rejected(self):
        with self.assertRaises(ValueError):
            profile.contribution_route({(0, 0): 1, (2, 0): 1})

    def test_food_disappears_and_resets_with_the_animation(self):
        days = [(f"2026-10-{25+i}", 1 if i in [0, 3] else 0, 1 if i in [0, 3] else 0) for i in range(7)]
        for theme in profile.THEMES:
            content = profile.trail(days, theme)
            tree = profile.ET.fromstring(content)
            food = [node for node in tree.iter() if node.attrib.get("class", "").startswith("food-")]
            self.assertEqual(len(food), 2)
            self.assertIn(f'100%{{fill:{profile.THEMES[theme]["empty"]}}}', content)
            self.assertIn('0%,0.090%{fill:#79506a}', content)
            self.assertIn('animation:none!important', content)
            self.assertTrue(all('motion' in node.attrib['class'] for node in food))


if __name__ == "__main__":
    unittest.main()
