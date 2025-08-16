# Git-AutoBoot

Tired of typing `git add`, `git commit`, `git init`, `git remote`, and other Git commands just to start a project?  

**Git-AutoBoot** is a small CLI tool that automates the boring stuff for you:

- Auto-generate a `.gitignore`
- Add an MIT LICENSE
- Run optional dependency & security audits
- Initialize Git, create a GitHub repo, and push your code

---

## 1. Installation

Install via PyPI:

```bash
pip install git-autoboot
```
## 1. One-Time Git token initialization

- Go to GitHub Tokens - https://github.com/settings/tokens
- Generate a token with repo permissions.
- In your IDE Terminal Type:
```bash
setx GITHUB_TOKEN "ghp_yourtoken"
```
- Close your IDE and restart it

## 2. Pushing Code to GitHub
```bash
cd project-name
autoboot project-name  or  autoboot "project name"
```
More Features Coming soon
Suggest Any Improvements
