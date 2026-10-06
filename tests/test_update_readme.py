import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("generator", ROOT / "scripts/update_readme.py")
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)
PROFILE = json.loads((ROOT / "data/profile.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 4, 12, tzinfo=timezone.utc)


def repository(name="project", **overrides):
    value = {"name": name, "owner": {"login": PROFILE["owner"]}, "private": False,
             "fork": False, "archived": False, "description": "API REST", "language": "Go",
             "stargazers_count": 2, "pushed_at": "2026-04-01T00:00:00Z", "updated_at": "2026-04-02T00:00:00Z"}
    value.update(overrides)
    return value


def request_with(repos):
    def request(path, token=None, payload=None):
        if path.startswith("/users/") and "/repos?" not in path:
            return {"login": PROFILE["owner"], "created_at": "2023-04-13T12:56:35Z"}
        if "/repos?" in path:
            page = int(path.rsplit("=", 1)[1])
            return repos[(page - 1) * 100:page * 100]
        raise RuntimeError("API complementar indisponível")
    return request


class GenerationTests(unittest.TestCase):
    def collect(self, repos, token=None):
        return generator.collect(PROFILE, token, request_with(repos), NOW)

    def test_paginates_beyond_first_hundred(self):
        snapshot = self.collect([repository(f"project-{i}") for i in range(105)])
        self.assertEqual(snapshot["statistics"]["public_repositories"], 105)
        self.assertEqual(snapshot["languages"][0]["repositories"], 105)

    def test_rejects_duplicate_pages_and_wrong_owner(self):
        with self.assertRaises(ValueError):
            self.collect([repository(), repository()])
        with self.assertRaises(ValueError):
            self.collect([repository(owner={"login": "someone-else"})])

    def test_filters_private_and_does_not_mix_forks_in_usage(self):
        snapshot = self.collect([repository(), repository("fork", fork=True, language="Python", stargazers_count=50),
                                 repository("private", private=True, description="Secret"), repository("docs", language=None)])
        self.assertEqual(snapshot["statistics"]["public_repositories"], 3)
        self.assertEqual(snapshot["statistics"]["stars"], 4)
        self.assertEqual(snapshot["languages"], [{"name": "Go", "repositories": 1, "percent": 100.0}])
        self.assertNotIn("Secret", json.dumps(snapshot))

    def test_age_uses_anniversary_not_year_subtraction(self):
        self.assertEqual(self.collect([])["statistics"]["account_age_years"], 2)

    def test_optional_statistics_failure_keeps_rest_data(self):
        snapshot = self.collect([repository()], "dummy-test-token")
        self.assertIsNone(snapshot["statistics"]["contributions"])
        self.assertEqual(snapshot["statistics"]["public_repositories"], 1)
        self.assertNotIn("dummy-test-token", json.dumps(snapshot))

    def test_authenticated_contributions_are_labeled_by_period(self):
        def request(path, token=None, payload=None):
            if path == "/graphql":
                return {"data": {"user": {"contributionsCollection": {
                    "startedAt": "2025-04-12T00:00:00Z", "endedAt": "2026-04-12T00:00:00Z",
                    "totalCommitContributions": 12, "totalIssueContributions": 1,
                    "totalPullRequestContributions": 2, "totalPullRequestReviewContributions": 3
                }}}}
            return request_with([repository()])(path, token)
        snapshot = generator.collect(PROFILE, "dummy", request, NOW)
        result = generator.outputs("{{ NAME }}", PROFILE, snapshot)
        self.assertIn("Commits (últimos 12 meses)", result[ROOT / "assets/github-stats.svg"])
        self.assertEqual(snapshot["statistics"]["contributions"]["totalCommitContributions"], 12)

    def test_malformed_optional_statistics_do_not_break_main_generation(self):
        def request(path, token=None, payload=None):
            if path == "/graphql":
                return {"data": {"user": {"contributionsCollection": {"totalCommitContributions": "invalid"}}}}
            return request_with([repository()])(path, token)
        snapshot = generator.collect(PROFILE, "dummy", request, NOW)
        self.assertIsNone(snapshot["statistics"]["contributions"])
        generator.outputs("{{ NAME }}", PROFILE, snapshot)

    def test_recent_list_excludes_profile_forks_and_archived(self):
        snapshot = self.collect([repository(PROFILE["owner"]), repository("fork", fork=True),
                                 repository("archive", archived=True), repository("recent", pushed_at="2026-04-10T00:00:00Z"),
                                 repository("older")])
        text = generator.render("{{ PROJECTS }}", PROFILE, snapshot)
        self.assertNotIn("/fork)", text)
        self.assertNotIn("/archive)", text)
        self.assertNotIn(f"/{PROFILE['owner']})", text)
        self.assertLess(text.index("recent"), text.index("older"))

    def test_escapes_untrusted_markdown_and_html(self):
        snapshot = self.collect([repository(description="<script>alert(1)</script>\n![x](https://evil.test) **bold**")])
        text = generator.render("{{ PROJECTS }}", PROFILE, snapshot)
        self.assertNotIn("<script>", text)
        self.assertNotIn("![x]", text)
        self.assertIn("&lt;script&gt;", text)
        self.assertNotIn("**bold**", text)

    def test_handles_no_languages_no_projects(self):
        snapshot = self.collect([])
        result = generator.outputs("{{ LANGUAGES }}\n{{ PROJECTS }}", PROFILE, snapshot)
        self.assertIn("Nenhuma linguagem", result[ROOT / "README.md"])
        self.assertIn("Nenhum projeto", result[ROOT / "README.md"])

    def test_fails_on_unresolved_template_or_wrong_snapshot(self):
        snapshot = self.collect([])
        with self.assertRaises(ValueError):
            generator.render("{{ UNKNOWN }}", PROFILE, snapshot)
        snapshot["owner"] = "someone-else"
        with self.assertRaises(ValueError):
            generator.render("{{ NAME }}", PROFILE, snapshot)

    def test_offline_refreshes_editorial_fields_without_faking_date(self):
        snapshot = self.collect([repository()])
        profile = copy.deepcopy(PROFILE)
        profile["name"] = "Updated Name"
        outputs = generator.outputs("{{ NAME }}", profile, snapshot)
        feed = json.loads(outputs[ROOT / "data/github.json"])
        self.assertEqual(feed["profile"]["name"], "Updated Name")
        self.assertEqual(feed["collected_at"], snapshot["collected_at"])

    def test_svg_escapes_remote_text(self):
        svg = generator.svg_card("Stats", [("<script>", "<img>")])
        self.assertNotIn("<script>", svg)
        self.assertIn("&lt;script&gt;", svg)

    def test_showcase_keeps_registered_previews_when_metadata_is_missing(self):
        text = generator.project_showcase(PROFILE, self.collect([]))
        self.assertIn('src="assets/projects/pedidos.png"', text)
        self.assertIn('src="assets/projects/nutrifit.png"', text)
        self.assertIn("Abrir demo", text)
        self.assertIn("<table>", text)
        self.assertEqual(text.count('<td valign="top" width="33%">'), 6)
        self.assertIn('alt="Capa de apresentação de Projeto Filmes AWS"', text)
        self.assertIn('alt="Documentação"', text)
        self.assertNotIn("Último push:", text)

    def test_showcase_metadata_uses_collected_values_and_closes_details(self):
        snapshot = self.collect([repository("Nutrift", stargazers_count=7)])
        text = generator.project_showcase(PROFILE, snapshot)
        self.assertIn("Último push: 2026-04-01 · Stars: 7", text)
        self.assertEqual(text.count("<details>"), text.count("</details>"))
        self.assertEqual(text.count("<summary>"), text.count("</summary>"))

    def test_showcase_rejects_missing_preview_and_non_https_demo(self):
        for key, value in [("image", "assets/projects/missing.png"), ("image", "../README.md"),
                           ("demo", "javascript:alert(1)")]:
            profile = copy.deepcopy(PROFILE)
            profile["project_showcase"]["Nutrift"][key] = value
            with self.assertRaises(ValueError):
                generator.project_showcase(profile, self.collect([]))

    def test_showcase_escapes_editorial_html_in_text_and_alt(self):
        profile = copy.deepcopy(PROFILE)
        profile["project_showcase"]["Nutrift"]["title"] = '<script>"x"</script>'
        profile["project_showcase"]["Nutrift"]["description"] = '<iframe src="bad">'
        text = generator.project_showcase(profile, self.collect([]))
        self.assertNotIn("<script>", text)
        self.assertNotIn("<iframe", text)
        self.assertIn("&quot;x&quot;", text)

    def test_http_failure_is_not_treated_as_valid_data(self):
        with patch.object(generator, "urlopen", side_effect=HTTPError("https://api.github.com", 403, "Forbidden", {}, None)):
            with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
                generator.api_request("/users/example")

    def test_transient_failure_has_bounded_retries(self):
        with patch.object(generator, "urlopen", side_effect=HTTPError("https://api.github.com", 503, "Unavailable", {}, None)) as fetch:
            with patch.object(generator.time, "sleep"):
                with self.assertRaisesRegex(RuntimeError, "HTTP 503"):
                    generator.api_request("/users/example")
        self.assertEqual(fetch.call_count, 3)


if __name__ == "__main__":
    unittest.main()
