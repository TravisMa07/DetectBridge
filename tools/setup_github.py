"""Owner-run administration only. Default reports state; --apply performs selected setup."""

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "tools/hygiene/repository-policy.json").read_text())
REPO = POLICY["repository"]
BASE = f"repos/{REPO}"


def api(path, method="GET", body=None):
    args = ["gh", "api", path, "--method", method]
    if body is not None:
        args += ["--input", "-"]
    result = subprocess.run(
        args,
        input=json.dumps(body) if body is not None else None,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else None


def pages(path):
    result, page = [], 1
    separator = "&" if "?" in path else "?"
    while True:
        items = api(f"{path}{separator}per_page=100&page={page}")
        result.extend(items)
        if len(items) < 100:
            return result
        page += 1


def tracking():
    roadmap = (ROOT / "docs/roadmap.md").read_text()
    milestone_specs = re.findall(r"^\| (M\d+ — [^|]+) \| [^|]+ \| ([^|]+) \|$", roadmap, re.M)
    milestone_specs += [
        (
            "Expansion — Attack chains",
            "Define and qualify deterministic event-time correlation with evidence linkage.",
        ),
        (
            "Expansion — AI assistance",
            "Qualify optional local and hosted assistance with human approval and core-pipeline isolation.",
        ),
        (
            "Expansion — Selective forwarding",
            "Qualify shadow policies, evidence retention and coverage-aware routing.",
        ),
        (
            "Expansion — Distributed deployment",
            "Qualify shared state, scaling, replication, recovery and upgrades separately.",
        ),
    ]
    existing = {m["title"]: m for m in pages(BASE + "/milestones?state=all")}
    for title, description in milestone_specs:
        if title not in existing:
            existing[title] = api(
                BASE + "/milestones", "POST", {"title": title, "description": description}
            )
    labels = {label["name"] for label in pages(BASE + "/labels")}
    if "blocked" not in labels:
        api(
            BASE + "/labels",
            "POST",
            {
                "name": "blocked",
                "color": "b60205",
                "description": "Blocked by an explicit dependency or access requirement",
            },
        )
    issues = [i for i in pages(BASE + "/issues?state=all") if "pull_request" not in i]
    by_id = {}
    for issue in issues:
        match = re.match(r"^\[(P\d{2})\]", issue["title"])
        if match:
            if match[1] in by_id:
                raise RuntimeError(f"Ambiguous duplicate planning ID {match[1]}; resolve manually")
            by_id[match[1]] = issue
    created = []
    for match in re.finditer(
        r"^### (P\d{2}) — ([^\n]+)\n(.*?)(?=^### |^## |\Z)", roadmap, re.M | re.S
    ):
        ident, title, body = match.groups()
        if ident in by_id:
            continue  # preserve existing user changes, state and milestone assignments
        sections = list(re.finditer(r"^## (M\d+ — [^\n]+)", roadmap[: match.start()], re.M))
        milestone = existing[sections[-1][1]]["number"]
        state = "In progress" if ident == "P01" else "Backlog"
        issue_body = f"Planning ID: {ident}\n\nInitial workflow status: {state}. The project Status field becomes authoritative once configured.\n\n{body.strip()}\n"
        by_id[ident] = api(
            BASE + "/issues",
            "POST",
            {"title": f"[{ident}] {title}", "body": issue_body, "milestone": milestone},
        )
        created.append(ident)
    for ident in created:
        issue = by_id[ident]
        body = issue["body"]
        match = re.search(r"- Depends on: ([^\n]+)", body)
        if match:
            references = re.findall(r"P\d{2}", match[1])
            if references:
                body += (
                    "\nDependency issues: "
                    + ", ".join(f"#{by_id[ref]['number']} ({ref})" for ref in references)
                    + ".\n"
                )
                api(BASE + "/issues/" + str(issue["number"]), "PATCH", {"body": body})
    print(
        json.dumps(
            {
                "milestones": len(existing),
                "created_issues": len(created),
                "issues": {k: v["number"] for k, v in by_id.items()},
            },
            indent=2,
        )
    )


def policies():
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    checks = api(f"{BASE}/commits/{sha}/check-runs")["check_runs"]
    successes = [
        c
        for c in checks
        if c["name"] == "required-checks"
        and c["conclusion"] == "success"
        and c["app"]["id"] == 15368
    ]
    if not successes:
        raise RuntimeError(
            "Refusing policy changes before GitHub Actions required-checks succeeds on local HEAD"
        )
    api(BASE, "PATCH", POLICY["settings"])
    api(BASE + "/actions/permissions/workflow", "PUT", POLICY["workflow_permissions"])
    api(BASE + "/private-vulnerability-reporting", "PUT")
    rulesets = [r for r in pages(BASE + "/rulesets") if r["name"] == POLICY["ruleset"]["name"]]
    if len(rulesets) > 1:
        raise RuntimeError("Multiple matching rulesets; resolve ambiguity manually")
    if rulesets:
        current = api(BASE + "/rulesets/" + str(rulesets[0]["id"]))
        fields = ("name", "target", "enforcement", "bypass_actors", "conditions", "rules")
        if not contains_policy({k: current.get(k) for k in fields}, POLICY["ruleset"]):
            raise RuntimeError("Existing ruleset differs; review user changes before updating it")
    else:
        api(BASE + "/rulesets", "POST", POLICY["ruleset"])
    readback()


def readback():
    repo = api(BASE)
    print(
        json.dumps(
            {
                "settings": {k: repo[k] for k in POLICY["settings"]},
                "workflow_permissions": api(BASE + "/actions/permissions/workflow"),
                "private_reporting": api(BASE + "/private-vulnerability-reporting"),
                "rulesets": [
                    api(BASE + "/rulesets/" + str(r["id"])) for r in pages(BASE + "/rulesets")
                ],
            },
            indent=2,
        )
    )


def gh_json(*args):
    return json.loads(subprocess.check_output(["gh", *args, "--format", "json"], text=True))


def contains_policy(actual, desired):
    """GitHub adds server defaults: compare required keys without masking drift."""
    if isinstance(desired, dict):
        return isinstance(actual, dict) and all(
            k in actual and contains_policy(actual[k], v) for k, v in desired.items()
        )
    if isinstance(desired, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(desired)
            and all(contains_policy(a, b) for a, b in zip(actual, desired))
        )
    return actual == desired


def project():
    owner = REPO.split("/")[0]
    projects = gh_json("project", "list", "--owner", owner, "--limit", "100")["projects"]
    matches = [p for p in projects if p["title"] == "DetectBridge Roadmap"]
    if len(matches) > 1:
        raise RuntimeError("Duplicate roadmap projects; resolve manually")
    board = (
        matches[0]
        if matches
        else gh_json("project", "create", "--owner", owner, "--title", "DetectBridge Roadmap")
    )
    number, project_id = str(board["number"]), board["id"]
    fields = gh_json("project", "field-list", number, "--owner", owner)["fields"]
    status = next(f for f in fields if f["name"] == "Status")
    names = ["Backlog", "Ready", "In progress", "In review", "Done"]
    existing_names = [o["name"] for o in status["options"]]
    if existing_names != names:
        items = gh_json("project", "item-list", number, "--owner", owner, "--limit", "100")["items"]
        if items:
            raise RuntimeError(
                "Project has items and different status options; review before changing"
            )
        options = [
            {"name": name, "description": name, "color": color}
            for name, color in zip(names, ["GRAY", "BLUE", "YELLOW", "PURPLE", "GREEN"])
        ]
        api(
            "graphql",
            "POST",
            {
                "query": "mutation($input:UpdateProjectV2FieldInput!){updateProjectV2Field(input:$input){projectV2Field{... on ProjectV2SingleSelectField{id}}}}",
                "variables": {"input": {"fieldId": status["id"], "singleSelectOptions": options}},
            },
        )
        status = next(
            f
            for f in gh_json("project", "field-list", number, "--owner", owner)["fields"]
            if f["name"] == "Status"
        )
    option_ids = {o["name"]: o["id"] for o in status["options"]}
    subprocess.run(["gh", "project", "link", number, "--owner", owner, "--repo", REPO], check=True)
    subprocess.run(
        ["gh", "project", "edit", number, "--owner", owner, "--visibility", "PUBLIC"], check=True
    )
    existing = gh_json("project", "item-list", number, "--owner", owner, "--limit", "100")["items"]
    urls = {i.get("content", {}).get("url") for i in existing}
    for issue in pages(BASE + "/issues?state=all"):
        match = re.match(r"^\[(P\d{2})\]", issue["title"])
        if not match or issue["html_url"] in urls:
            continue
        item = gh_json("project", "item-add", number, "--owner", owner, "--url", issue["html_url"])
        initial = "In progress" if match[1] == "P01" else "Backlog"
        subprocess.run(
            [
                "gh",
                "project",
                "item-edit",
                "--id",
                item["id"],
                "--project-id",
                project_id,
                "--field-id",
                status["id"],
                "--single-select-option-id",
                option_ids[initial],
            ],
            check=True,
        )
    info = api(
        "graphql",
        "POST",
        {
            "query": "query($id:ID!){node(id:$id){... on ProjectV2{views(first:20){nodes{id name layout}} workflows(first:30){nodes{name enabled}}}}}",
            "variables": {"id": project_id},
        },
    )
    workflows = info["data"]["node"]["workflows"]["nodes"]
    active_status = [
        w["name"]
        for w in workflows
        if w["enabled"] and w["name"] != "Auto-add sub-issues to project"
    ]
    if active_status:
        raise RuntimeError(
            "Disable automatic status/closure workflows in project UI: " + ", ".join(active_status)
        )
    views = info["data"]["node"]["views"]["nodes"]
    if len(views) == 1 and views[0]["name"] == "View 1":
        api(
            "graphql",
            "POST",
            {
                "query": "mutation($input:UpdateProjectV2ViewInput!){updateProjectV2View(input:$input){projectV2View{id name layout}}}",
                "variables": {
                    "input": {
                        "viewId": views[0]["id"],
                        "name": "Roadmap board",
                        "layout": "BOARD_LAYOUT",
                    }
                },
            },
        )
    print(
        json.dumps(
            {
                "project": board["url"],
                "fields": gh_json("project", "field-list", number, "--owner", owner),
                "items": gh_json(
                    "project", "item-list", number, "--owner", owner, "--limit", "100"
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", choices=("tracking", "policies", "project"))
    args = parser.parse_args()
    try:
        if args.apply == "tracking":
            tracking()
        elif args.apply == "policies":
            policies()
        elif args.apply == "project":
            project()
        else:
            readback()
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(getattr(exc, "stderr", "") or str(exc))
        raise SystemExit(1)
