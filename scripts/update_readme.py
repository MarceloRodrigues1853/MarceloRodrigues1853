"""Generate the profile README and its public portfolio feed; never run Git."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import re
import sys
import textwrap
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com"
NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def api_request(path, token=None, payload=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-readme-generator"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None if payload is None else json.dumps(payload).encode()
    if body:
        headers["Content-Type"] = "application/json"
    for attempt in range(3):
        try:
            with urlopen(Request(API + path, data=body, headers=headers), timeout=20) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError(f"GitHub HTTP {error.code} em {path}; nenhum arquivo atualizado.") from None
        except (URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError(f"Falha de conexão com GitHub em {path}; nenhum arquivo atualizado.") from None
        time.sleep(2 ** attempt)


def collect(profile, token=None, request=api_request, now=None):
    now = now or datetime.now(timezone.utc)
    owner = profile["owner"]
    user = request(f"/users/{owner}", token)
    if user.get("login", "").lower() != owner.lower() or not user.get("created_at"):
        raise ValueError("Resposta de usuário inválida.")
    repos = []
    page = 1
    while True:
        batch = request(f"/users/{owner}/repos?type=owner&sort=full_name&per_page=100&page={page}", token)
        if not isinstance(batch, list):
            raise ValueError("Resposta de repositórios inválida.")
        for repo in batch:
            if repo.get("private") or repo.get("visibility", "public") != "public":
                continue
            if repo.get("owner", {}).get("login", "").lower() != owner.lower():
                raise ValueError("Repositório pertence a outro usuário.")
            name = repo["name"]
            if not NAME.fullmatch(name):
                raise ValueError("Nome de repositório inválido.")
            repos.append({
                "name": name, "full_name": f"{owner}/{name}",
                "url": f"https://github.com/{owner}/{quote(name)}",
                "description": repo.get("description") or "Sem descrição no GitHub.",
                "language": repo.get("language"), "stars": repo["stargazers_count"],
                "pushed_at": repo.get("pushed_at"), "updated_at": repo.get("updated_at"),
                "fork": bool(repo.get("fork")), "archived": bool(repo.get("archived"))
            })
        if len(batch) < 100:
            break
        page += 1
    if len({repo["name"].lower() for repo in repos}) != len(repos):
        raise ValueError("Repositórios duplicados na paginação; tente novamente.")
    created = datetime.fromisoformat(user["created_at"].replace("Z", "+00:00"))
    age = now.year - created.year - ((now.month, now.day) < (created.month, created.day))
    own_repos = [repo for repo in repos if not repo["fork"]]
    languages = Counter(repo["language"] for repo in own_repos if repo["language"])
    total = sum(languages.values())
    contributions = None
    if token:
        # Collection defaults to the last year; no private repository names are requested.
        query = """query($login: String!) { user(login: $login) { contributionsCollection {
          startedAt endedAt totalCommitContributions totalIssueContributions
          totalPullRequestContributions totalPullRequestReviewContributions
        } } }"""
        try:
            result = request("/graphql", token, {"query": query, "variables": {"login": owner}})
            value = result.get("data", {}).get("user", {}).get("contributionsCollection")
            keys = ("totalCommitContributions", "totalIssueContributions", "totalPullRequestContributions", "totalPullRequestReviewContributions")
            if result.get("errors") or not isinstance(value, dict) or any(
                type(value.get(key)) is not int or value[key] < 0 for key in keys
            ) or not value.get("startedAt") or not value.get("endedAt"):
                raise ValueError("Estatísticas complementares indisponíveis.")
            contributions = value
        except (RuntimeError, ValueError, AttributeError):
            print("Estatísticas complementares indisponíveis; dados REST preservados.", file=sys.stderr)
    return {
        "schema_version": 1, "owner": owner,
        "collected_at": now.isoformat(timespec="seconds"),
        "profile": {key: profile[key] for key in ("name", "headline", "career_focus", "contacts", "featured_repositories")},
        "statistics": {"account_age_years": age, "public_repositories": len(repos),
                       "stars": sum(repo["stars"] for repo in own_repos), "contributions": contributions},
        "language_basis": "primary_language_per_public_nonfork_repository",
        "languages": [{"name": name, "repositories": count, "percent": round(count / total * 100, 1)}
                      for name, count in sorted(languages.items(), key=lambda item: (-item[1], item[0]))],
        "repositories": sorted(repos, key=lambda repo: repo["name"].lower())
    }


def markdown_text(value):
    value = " ".join(str(value).split())
    value = escape(value, quote=False)
    return re.sub(r"([\\`*_[\]{}])", r"\\\1", value)


def badge_url(label, color="334155", style="flat-square"):
    # Shields escapes literal hyphens and underscores by doubling them.
    encoded = quote(label.replace("-", "--").replace("_", "__"), safe="")
    return f"https://img.shields.io/badge/{encoded}-{color}?style={style}"


def badge(label, color="334155", style="flat-square"):
    return f"![{markdown_text(label)}]({badge_url(label, color, style)})"


def contact_links(profile, badges=False):
    labels = {"portfolio": "Portfólio", "linkedin": "LinkedIn", "instagram": "Instagram", "email": "E-mail"}
    hints = {"portfolio": "Visitar meu portfólio", "linkedin": "Abrir meu perfil no LinkedIn",
             "instagram": "Abrir meu perfil no Instagram", "email": "Abrir seu aplicativo de e-mail para escrever uma mensagem"}
    links = []
    for key, label in labels.items():
        url = profile["contacts"][key]
        if not url.startswith(("https://", "mailto:")) or any(c in url for c in "\n\r<>\" ()"):
            raise ValueError("Contato inválido.")
        content = badge(label, profile["contact_badge_colors"][key], style="for-the-badge") if badges else label
        links.append(f'[{content}]({url} "{hints[key]}")')
    return "\n".join(links) if badges else " · ".join(links)


def project_showcase(profile, snapshot):
    registry = profile.get("project_showcase", {})
    metadata = {repo["name"].lower(): repo for repo in snapshot["repositories"]}
    cards = []
    for name in profile["featured_repositories"]:
        if name not in registry:
            continue
        if not NAME.fullmatch(name):
            raise ValueError("Nome de projeto inválido na vitrine.")
        project = registry[name]
        repository_url = f"https://github.com/{profile['owner']}/{quote(name)}"
        documentation_url = repository_url + "#readme"
        demo = project.get("demo")
        if demo and (not demo.startswith("https://") or any(c in demo for c in "\n\r<>\" ()")):
            raise ValueError("Link de demo inválido.")
        card = '<td valign="top" width="33%">\n'
        image_path = project.get("image")
        if image_path:
            relative = Path(image_path)
            resolved = (ROOT / relative).resolve()
            if relative.is_absolute() or not resolved.is_relative_to((ROOT / "assets/projects").resolve()) or not resolved.is_file():
                raise ValueError("Captura ausente ou fora de assets/projects.")
        else:
            image_path = f"assets/projects/{name}.svg"
        target = demo or repository_url
        hint = "Abrir demonstração" if demo else "Abrir repositório"
        alt = escape(("Captura da interface de " if project.get("image") else "Capa de apresentação de ") + project["title"], quote=True)
        card += (f'<a href="{escape(target, quote=True)}" title="{hint}">'
                 f'<img src="{escape(image_path, quote=True)}" alt="{alt}" width="260" /></a>\n')
        card += "<h3>" + escape(project["title"]) + "</h3>\n"
        card += "<p>" + escape(project["description"]) + "</p>\n"
        card += "<p><strong>" + " · ".join(escape(t) for t in project["technologies"]) + "</strong></p>\n"
        repo = metadata.get(name.lower())
        if repo:
            pushed = escape((repo.get("pushed_at") or "")[:10] or "não informado")
            card += f"<p>Último push: {pushed} · Stars: {repo['stars']}</p>\n"
        decisions = "".join("<li>" + escape(item) + "</li>" for item in project["details"])
        card += ('<details><summary>Decisões documentadas</summary>\n<ul>' + decisions + "</ul>\n"
                 f'<p><a href="{documentation_url}">Ler documentação</a></p>\n</details>\n')
        if project.get("note"):
            card += "<p><sub>" + escape(project["note"]) + "</sub></p>\n"
        buttons = [f'<a href="{repository_url}" title="Abrir repositório"><img alt="Repositório" src="{escape(badge_url("Repositório"), quote=True)}" /></a>']
        if demo:
            buttons.append(f'<a href="{escape(demo, quote=True)}" title="Abrir demonstração do projeto"><img alt="Abrir demo" src="{escape(badge_url("Abrir demo", "1D4ED8"), quote=True)}" /></a>')
        else:
            buttons.append(f'<a href="{documentation_url}" title="Ler documentação"><img alt="Documentação" src="{escape(badge_url("Documentação", "1D4ED8"), quote=True)}" /></a>')
        card += "<p>" + " ".join(buttons) + "</p>\n</td>"
        cards.append(card)
    if not cards:
        return "[Explorar projetos no portfólio](" + profile["contacts"]["portfolio"] + ")"
    rows = ["<tr>\n" + "\n".join(cards[i:i + 3]) + "\n</tr>" for i in range(0, len(cards), 3)]
    return "<table>\n" + "\n".join(rows) + "\n</table>"


def project_cover(project):
    title = escape(project["title"])
    elements = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 400" role="img"><title>Capa de apresentação: {title}</title>',
                '<rect width="720" height="400" rx="12" fill="#161b22"/>',
                '<path d="M48 48H672" stroke="#3b82f6" stroke-width="3"/>',
                '<text x="48" y="94" fill="#9da7b3" font-family="Arial,sans-serif" font-size="20">PROJETO / DOCUMENTAÇÃO</text>']
    for index, line in enumerate(textwrap.wrap(project["title"], width=26)):
        elements.append(f'<text x="48" y="{175 + 54 * index}" fill="#79c0ff" font-family="Arial,sans-serif" font-size="40" font-weight="bold">{escape(line)}</text>')
    technologies = " / ".join(project["technologies"][:3])
    elements.append(f'<text x="48" y="340" fill="#9da7b3" font-family="Arial,sans-serif" font-size="21">{escape(technologies)}</text>')
    return "\n".join(elements + ["</svg>\n"])


def render(template, profile, snapshot):
    if snapshot.get("schema_version") != 1 or snapshot.get("owner") != profile["owner"]:
        raise ValueError("Snapshot incompatível com o perfil.")
    colors = profile["badge_colors"]
    stack_sections = []
    for category, names in profile["stack"].items():
        section = "### " + category + "\n\n" + "\n".join(badge(name, colors[name]) for name in names)
        note = profile.get("stack_notes", {}).get(category)
        if note:
            section += "\n\n" + markdown_text(note)
        stack_sections.append(section)
    stack = "\n\n".join(stack_sections)
    repos = [repo for repo in snapshot["repositories"] if not repo["fork"] and not repo["archived"]
             and repo["name"].lower() != profile["owner"].lower()]
    repos.sort(key=lambda repo: (repo.get("pushed_at") or "", repo["name"]), reverse=True)
    projects = []
    for repo in repos[:profile["recent_limit"]]:
        date = (repo.get("pushed_at") or "")[:10] or "não informado"
        language = markdown_text(repo["language"] or "não informada")
        projects.append(f"- **[{markdown_text(repo['name'])}]({repo['url']})** — {markdown_text(repo['description'])}\n"
                        f"  Linguagem principal: {language} · Stars: {repo['stars']} · Último push: {date}")
    langs = "\n".join(f"- **{markdown_text(lang['name'])}** — {lang['percent']:.1f}% ({lang['repositories']} repositórios)"
                      for lang in snapshot["languages"][:6])
    tokens = {
        "NAME": markdown_text(profile["name"]), "HEADLINE": markdown_text(profile["headline"]),
        "CONTACT_BADGES": contact_links(profile, True), "CONTACT_LINKS": contact_links(profile),
        "ABOUT": "\n\n".join(markdown_text(p) for p in profile["about"]),
        "PROFESSIONAL_PROFILE": "\n".join("- " + markdown_text(p) for p in profile["professional_profile"]),
        "SOFT_SKILLS": "\n".join(badge(skill) for skill in profile["soft_skills"]),
        "STACK": stack, "LANGUAGES": langs or "Nenhuma linguagem principal informada nos repositórios públicos.",
        "PROJECTS": "\n\n".join(projects) or "Nenhum projeto público elegível nesta consulta.",
        "PROJECT_SHOWCASE": project_showcase(profile, snapshot),
        "EDUCATION": "\n".join("- " + markdown_text(p) for p in profile["education"]),
        "UPDATED_AT": snapshot["collected_at"][:10]
    }
    for token, value in tokens.items():
        template = template.replace("{{ " + token + " }}", value)
    if "{{" in template or "}}" in template:
        raise ValueError("O template contém variáveis desconhecidas ou não preenchidas.")
    return template


def svg_card(title, rows):
    height = 68 + len(rows) * 35
    elements = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 {height}" width="520" height="{height}" role="img">',
                f"<title>{escape(title)}</title>",
                f'<rect width="520" height="{height}" rx="8" fill="#161b22"/>',
                f'<text x="24" y="34" fill="#e6edf3" font-family="Arial,sans-serif" font-size="17" font-weight="bold">{escape(title)}</text>']
    for index, (label, value) in enumerate(rows):
        y = 72 + index * 35
        elements.append(f'<text x="24" y="{y}" fill="#9da7b3" font-family="Arial,sans-serif" font-size="14">{escape(label)}</text>')
        elements.append(f'<text x="496" y="{y}" text-anchor="end" fill="#79c0ff" font-family="Arial,sans-serif" font-size="14">{escape(str(value))}</text>')
    return "\n".join(elements + ["</svg>\n"])


def outputs(template, profile, snapshot):
    stats = snapshot["statistics"]
    rows = [("Idade da conta (anos completos)", stats["account_age_years"]),
            ("Repositórios públicos", stats["public_repositories"]),
            ("Stars em repositórios próprios", stats["stars"])]
    if stats.get("contributions"):
        values = stats["contributions"]
        for label, key in [("Commits", "totalCommitContributions"), ("Issues", "totalIssueContributions"),
                           ("Pull requests", "totalPullRequestContributions"), ("Reviews", "totalPullRequestReviewContributions")]:
            rows.append((label + " (últimos 12 meses)", values[key]))
    languages = [(lang["name"], f"{lang['percent']:.1f}% · {lang['repositories']} repos") for lang in snapshot["languages"][:6]]
    if not languages:
        languages = [("Linguagens", "Não informadas")]
    # Keep current editorial fields even when using a cached GitHub snapshot.
    feed = dict(snapshot)
    feed["profile"] = {key: profile[key] for key in ("name", "headline", "career_focus", "contacts", "featured_repositories")}
    generated = {
        ROOT / "README.md": render(template, profile, snapshot),
        ROOT / "data/github.json": json.dumps(feed, ensure_ascii=False, indent=2) + "\n",
        ROOT / "assets/github-stats.svg": svg_card("Estatísticas do GitHub", rows),
        ROOT / "assets/languages.svg": svg_card("Linguagens principais por repositório", languages)
    }
    for name in profile["featured_repositories"]:
        project = profile.get("project_showcase", {}).get(name)
        if project and not project.get("image"):
            generated[ROOT / f"assets/projects/{name}.svg"] = project_cover(project)
    return generated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Renderizar com a última consulta real, sem acessar a API.")
    args = parser.parse_args()
    profile = json.loads((ROOT / "data/profile.json").read_text(encoding="utf-8-sig"))
    if not NAME.fullmatch(profile["owner"]) or not 1 <= profile["recent_limit"] <= 20:
        raise ValueError("Configuração de perfil inválida.")
    snapshot = json.loads((ROOT / "data/github.json").read_text(encoding="utf-8")) if args.offline else collect(
        profile, os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    generated = outputs((ROOT / "docs/TEMPLATE.md").read_text(encoding="utf-8-sig"), profile, snapshot)
    # All remote reads and rendering succeed before replacing output files.
    for path, content in generated.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8", newline="\n")
        temporary.replace(path)
    print(f"README e feed gerados com {len(snapshot['repositories'])} repositórios públicos; consulta: {snapshot['collected_at']}.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, RuntimeError, OSError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        sys.exit(1)
