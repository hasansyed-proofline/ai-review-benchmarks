#!/usr/bin/env python3
import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVIDERS_PATH = ROOT / "benchmark" / "providers.json"
STATE_PATH = ROOT / "results" / "state.json"
RAW_DIR = ROOT / "results" / "raw"

QUOTA_WORDS = ("rate limit", "quota", "credit", "limit reached", "upgrade your plan")


def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"failed: {' '.join(cmd)}\n{res.stderr.strip()}")
    return res.stdout.strip()


def gh_api(path):
    out = run(["gh", "api", path])
    return json.loads(out) if out else []


def load_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def init_provider_repo(provider_name):
    providers = load_json(PROVIDERS_PATH, {})
    repo = providers[provider_name]["repo"]

    check = subprocess.run(["gh", "repo", "view", repo], capture_output=True)
    if check.returncode != 0:
        run(["gh", "repo", "create", repo, "--private"])
        print(f"created {repo}")
    else:
        print(f"using existing {repo}")

    base_sha = run(["git", "rev-parse", "upstream/pilot/base"])
    run(["git", "push", "--force", f"https://github.com/{repo}.git", f"{base_sha}:refs/heads/main"])
    print(f"pushed pilot/base ({base_sha[:8]}) -> {repo}:main")


def read_case(case_id, condition):
    folder = ROOT / "cases" / case_id
    title = (folder / "title.txt").read_text().strip()
    body = (folder / "body.md").read_text().strip()
    if condition == "with-snapshot":
        evidence = (folder / "evidence.md").read_text().strip()
        body = f"{body}\n\n## Deployment snapshot\n\n{evidence}"
    return title, body


def fetch_bot_feedback(repo, pr_num, me):
    def is_other(item):
        login = (item.get("user") or {}).get("login", "")
        return login and login.lower() != me.lower()

    reviews = [r for r in gh_api(f"repos/{repo}/pulls/{pr_num}/reviews") if is_other(r)]
    inline = [c for c in gh_api(f"repos/{repo}/pulls/{pr_num}/comments") if is_other(c)]
    comments = [c for c in gh_api(f"repos/{repo}/issues/{pr_num}/comments") if is_other(c)]
    return reviews, inline, comments


def check_status(reviews, inline, comments, timed_out):
    text = "\n".join(
        (x.get("body") or "") for x in (reviews + inline + comments)
    ).lower()
    if any(w in text for w in QUOTA_WORDS):
        return "quota_stop"
    if reviews or inline or comments:
        return "completed"
    return "timeout" if timed_out else "pending"


def run_cases(provider_name, cases, condition, run_id, timeout, collect_only):
    providers = load_json(PROVIDERS_PATH, {})
    cfg = providers[provider_name]
    repo = cfg["repo"]
    me = run(["gh", "api", "user", "--jq", ".login"])
    base_sha = run(["git", "rev-parse", "upstream/pilot/base"])
    state = load_json(STATE_PATH, {})

    for case_id in cases:
        key = f"{provider_name}_{case_id}_{condition}_{run_id}"
        out_file = RAW_DIR / f"{key}.json"

        if not collect_only and out_file.exists():
            prev = load_json(out_file, {})
            if prev.get("status") == "completed":
                print(f"skip {key} (already completed)")
                continue

        head_sha = run(["git", "rev-parse", f"upstream/pilot/{case_id}"])
        entry = state.get(key)

        if entry is None:
            if collect_only:
                print(f"skip {key} (no PR in state.json)")
                continue
            title, body = read_case(case_id, condition)
            branch = f"case-{case_id}-{condition}-{run_id}"
            run(["git", "push", "--force", f"https://github.com/{repo}.git", f"{head_sha}:refs/heads/{branch}"])
            pr_url = run([
                "gh", "pr", "create",
                "--repo", repo,
                "--base", "main",
                "--head", branch,
                "--title", title,
                "--body", body,
            ])
            pr_num = int(pr_url.rstrip("/").split("/")[-1])

            if cfg.get("trigger_comment"):
                run(["gh", "pr", "comment", str(pr_num), "--repo", repo, "--body", cfg["trigger_comment"]])

            entry = {
                "provider": provider_name,
                "case_id": case_id,
                "condition": condition,
                "run_id": run_id,
                "repo": repo,
                "pr_number": pr_num,
                "pr_url": pr_url,
                "base_sha": base_sha,
                "head_sha": head_sha,
                "opened_at": now_utc(),
            }
            state[key] = entry
            save_json(STATE_PATH, state)
            print(f"opened {key} -> {pr_url}")
        else:
            print(f"resuming {key} -> {entry['pr_url']}")

        deadline = time.time() + (0 if collect_only else timeout)
        while True:
            reviews, inline, comments = fetch_bot_feedback(repo, entry["pr_number"], me)
            status = check_status(reviews, inline, comments, timed_out=(time.time() >= deadline))
            if status != "pending":
                if status == "completed" and not collect_only:
                    time.sleep(20)
                    reviews, inline, comments = fetch_bot_feedback(repo, entry["pr_number"], me)
                break
            time.sleep(15)

        record = {
            **entry,
            "trigger": cfg["trigger"],
            "notes": cfg["notes"],
            "collected_at": now_utc(),
            "status": status,
            "reviews": reviews,
            "inline_comments": inline,
            "issue_comments": comments,
        }
        save_json(out_file, record)
        print(f"saved {key}: {status} (reviews={len(reviews)}, inline={len(inline)}, comments={len(comments)})")

        if status == "quota_stop":
            print(f"stopping {provider_name}: hit quota on case {case_id}")
            break


def main():
    p = argparse.ArgumentParser(description="Run AI PR review benchmarks.")
    sub = p.add_subparsers(required=True, dest="cmd")

    p_init = sub.add_parser("init")
    p_init.add_argument("provider")

    for cmd in ("run", "collect"):
        s = sub.add_parser(cmd)
        s.add_argument("--provider", required=True)
        s.add_argument("--cases", default="01,02,03,04,05,06,07,08")
        s.add_argument("--condition", choices=["code-only", "with-snapshot"], default="code-only")
        s.add_argument("--run-id", default="r1")
        s.add_argument("--timeout", type=int, default=600)

    args = p.parse_args()
    if args.cmd == "init":
        init_provider_repo(args.provider)
    else:
        cases = [c.strip().zfill(2) for c in args.cases.split(",") if c.strip()]
        run_cases(args.provider, cases, args.condition, args.run_id, args.timeout, collect_only=(args.cmd == "collect"))


if __name__ == "__main__":
    main()
