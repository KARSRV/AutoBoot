import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
import requests

GITIGNORE_TEMPLATE = dedent("""
# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
*.so
*.egg-info/
dist/
build/

# Virtual env
.venv/
venv/
env/

# Editors
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Env and secrets
.env
*.env

# Streamlit
.streamlit/

# Jupyter
.ipynb_checkpoints
""").strip() + "\n"

MIT_LICENSE = dedent("""\
MIT License

Copyright (c) YOUR NAME

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
""")

def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the CompletedProcess."""
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)

def ensure_gitignore(root: Path) -> bool:
    """Create or update .gitignore. Return True if changed."""
    gi_path = root / ".gitignore"
    if not gi_path.exists():
        gi_path.write_text(GITIGNORE_TEMPLATE, encoding="utf-8")
        print("[gitignore] Created .gitignore")
        return True
    existing = gi_path.read_text(encoding="utf-8").splitlines()
    to_add = [ln for ln in GITIGNORE_TEMPLATE.splitlines() if ln and ln not in existing]
    if to_add:
        with gi_path.open("a", encoding="utf-8") as f:
            f.write("\n" + "\n".join(to_add) + "\n")
        print("[gitignore] Updated .gitignore")
        return True
    print("[gitignore] .gitignore is fine")
    return False

def create_license(root: Path) -> bool:
    """Create MIT LICENSE file. Return True if created, False if it exists."""
    license_path = root / "LICENSE"
    if license_path.exists():
        print("[license] LICENSE already exists")
        return False
    license_path.write_text(MIT_LICENSE, encoding="utf-8")
    print("[license] Created LICENSE (replace YOUR NAME with your name)")
    return True

def ensure_git_installed():
    try:
        out = run(["git", "--version"], check=True).stdout.strip()
        print(f"[git] {out}")
    except Exception:
        print("[git] git is not installed or not on PATH")
        sys.exit(1)

def init_git(root: Path):
    """Init repo and make an initial commit if needed."""
    if (root / ".git").exists():
        print("[git] Already a repository")
    else:
        run(["git", "init"], cwd=root)
        print("[git] Initialized repository")
    run(["git", "add", "-A"], cwd=root)
    try:
        run(["git", "commit", "-m", "initial commit"], cwd=root)
        print("[git] Created initial commit")
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or e.stdout or "").strip()
        if "user.name" in msg or "user.email" in msg:
            print("[git] Commit failed. Set your identity:")
            print('  git config --global user.name "Your Name"')
            print('  git config --global user.email "you@example.com"')
            sys.exit(1)
        else:
            print("[git] Nothing to commit or commit failed, continuing…")

def create_github_repo(repo_name: str, private: bool, token: str, description: str | None) -> dict:
    """Create repo via GitHub API. Return JSON with clone_url and html_url."""
    url = "https://api.github.com/user/repos"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    payload = {
        "name": repo_name,
        "private": private,
        "description": description or "Pushed by autoboot",
        "auto_init": False,
    }
    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
    if resp.status_code >= 300:
        raise RuntimeError(f"GitHub API error {resp.status_code}: {resp.text}")
    data = resp.json()
    if not data.get("clone_url"):
        raise RuntimeError("GitHub API did not return clone_url")
    print(f"[github] Created repo: {data.get('html_url')}")
    return data

def connect_remote_and_push(root: Path, clone_url: str, branch: str = "main"):
    """Add remote 'origin', set branch name, and push."""
    try:
        run(["git", "branch", "-M", branch], cwd=root)
    except subprocess.CalledProcessError:
        pass
    remotes = run(["git", "remote"], cwd=root, check=False).stdout.split()
    if "origin" not in remotes:
        run(["git", "remote", "add", "origin", clone_url], cwd=root)
        print(f"[git] Added remote origin -> {clone_url}")
    run(["git", "push", "-u", "origin", branch], cwd=root)
    print(f"[git] Pushed to {branch}")

def pip_audit(root: Path) -> str | None:
    req = root / "requirements.txt"
    if not req.exists():
        print("[audit] No requirements.txt found, skipping dependency audit")
        return None
    try:
        run([sys.executable, "-m", "pip_audit", "--version"], check=True)
    except subprocess.CalledProcessError:
        print("[audit] pip-audit not found. Installing…")
        try:
            run([sys.executable, "-m", "pip", "install", "pip-audit"], check=True)
        except subprocess.CalledProcessError:
            print("[audit] Could not install pip-audit. Skipping.")
            return None
    report_path = root / "pip-audit-report.txt"
    print("[audit] Running pip-audit…")
    result = subprocess.run(
        [sys.executable, "-m", "pip_audit", "-r", str(req)],
        text=True,
        capture_output=True,
    )
    report_path.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    if result.returncode == 0:
        print("[audit] No known vulnerabilities (see pip-audit-report.txt)")
    else:
        print("[audit] Vulnerabilities found (see pip-audit-report.txt)")
    return str(report_path)

def bandit_scan(root: Path) -> str | None:
    try:
        run([sys.executable, "-m", "bandit", "--version"], check=True)
    except subprocess.CalledProcessError:
        print("[bandit] bandit not found. Installing…")
        try:
            run([sys.executable, "-m", "pip", "install", "bandit"], check=True)
        except subprocess.CalledProcessError:
            print("[bandit] Could not install bandit. Skipping.")
            return None
    report_path = root / "bandit-report.txt"
    print("[bandit] Scanning…")
    result = subprocess.run(
        [sys.executable, "-m", "bandit", "-r", "."],
        text=True,
        capture_output=True,
    )
    report_path.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    print("[bandit] Finished (see bandit-report.txt)")
    return str(report_path)

def main():
    parser = argparse.ArgumentParser(
        prog="autoboot",
        description="Bootstrap a project: .gitignore, LICENSE, audits, git init, GitHub repo, push.",
    )
    parser.add_argument("name", nargs="?", help="GitHub repo name (default: current folder name)")
    parser.add_argument("--private", action="store_true", help="Create GitHub repo as private")
    parser.add_argument("--no-audit", action="store_true", help="Skip pip-audit dependency check")
    parser.add_argument("--bandit", action="store_true", help="Run bandit security scan")
    parser.add_argument("--desc", default=None, help="GitHub repo description")
    parser.add_argument("--branch", default="main", help='Default branch name (default: "main")')
    args = parser.parse_args()

    root = Path.cwd()
    repo_name = args.name or root.name

    ensure_git_installed()
    ensure_gitignore(root)
    create_license(root)
    init_git(root)

    if not args.no_audit:
        pip_audit(root)
    if args.bandit:
        bandit_scan(root)

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print(
            "[github] Missing token. Set GITHUB_TOKEN (repo scope) globally and rerun.\n"
            "Example (PowerShell): setx GITHUB_TOKEN \"ghp_yourtoken\"\n"
            "After that, restart your terminal or IDE before running autoboot."
        )
        sys.exit(2)

    try:
        data = create_github_repo(
            repo_name=repo_name,
            private=args.private,
            token=token,
            description=args.desc,
        )
        connect_remote_and_push(root, data["clone_url"], branch=args.branch)
    except Exception as e:
        print(f"[github] Error: {e}")
        sys.exit(3)

    print("\nDone.")
    print(f"- Repo: {data.get('html_url')}")
    print(f"- Branch: {args.branch}")

if __name__ == "__main__":
    main()
