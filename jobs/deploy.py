"""One-shot deploy from the tokens in .env. Run from the repo root with the API venv:

    api/.venv/Scripts/python.exe -m jobs.deploy            # all steps
    api/.venv/Scripts/python.exe -m jobs.deploy repo secrets render vercel   # or a subset, in order

Steps
  repo     create the private GitHub repo (if missing), add `origin`, push main
  secrets  put DATABASE_URL / LLM keys / VAPID / ADMIN_TOKEN into GitHub Actions secrets, model ids into variables
  render   create (or reuse) the Render web service `finn-api` from the repo, with env vars from .env
  vercel   link + deploy web/ to Vercel with NEXT_PUBLIC_API_URL pointing at the Render URL

Idempotent: re-running updates secrets/env and redeploys. Nothing here is read by the app itself.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
REPO_NAME = os.environ.get("FINN_REPO", "finn")
RENDER_SERVICE = "finn-api"
VERCEL_PROJECT = "finn"
RENDER_REGION = os.environ.get("FINN_RENDER_REGION", "singapore")

APP_SECRETS = ["DATABASE_URL", "GEMINI_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "TAVILY_API_KEY",
               "VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT", "ADMIN_TOKEN"]
APP_VARS = ["CHEAP_MODEL", "CHEAP_MODEL_FALLBACK", "STRONG_MODEL", "STRONG_MODEL_FALLBACK"]


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    p = ROOT / ".env"
    if not p.exists():
        sys.exit(".env not found at repo root")
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.split(" #")[0].strip().strip('"').strip("'")
        env[k.strip()] = v
    return env


def need(env: dict[str, str], key: str) -> str:
    if not env.get(key):
        sys.exit(f"{key} is blank in .env")
    return env[key]


def git(*args: str, extra_header: str | None = None) -> str:
    cmd = ["git"]
    if extra_header:
        cmd += ["-c", "credential.helper=", "-c", f"http.https://github.com/.extraheader={extra_header}"]
    cmd += list(args)
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{r.stderr.strip()}")
    return r.stdout.strip()


# ---------------------------------------------------------------- github
def gh(env: dict[str, str]) -> httpx.Client:
    return httpx.Client(base_url="https://api.github.com", timeout=60,
                        headers={"Authorization": f"Bearer {need(env, 'GITHUB_TOKEN')}", "Accept": "application/vnd.github+json",
                                 "X-GitHub-Api-Version": "2022-11-28"})


def step_repo(env: dict[str, str]) -> str:
    with gh(env) as c:
        login = c.get("/user").raise_for_status().json()["login"]
        r = c.post("/user/repos", json={"name": REPO_NAME, "private": True, "has_wiki": False, "has_projects": False,
                                        "description": "FINN - mobile-first financial investment agent"})
        if r.status_code == 201:
            print(f"[repo] created github.com/{login}/{REPO_NAME} (private)")
        elif r.status_code == 422 and "already exists" in r.text:
            print(f"[repo] github.com/{login}/{REPO_NAME} already exists")
        else:
            r.raise_for_status()
    url = f"https://github.com/{login}/{REPO_NAME}.git"
    try:
        current = git("remote", "get-url", "origin")
        if current != url:
            git("remote", "set-url", "origin", url)
    except RuntimeError:
        git("remote", "add", "origin", url)
    auth = base64.b64encode(f"x-access-token:{env['GITHUB_TOKEN']}".encode()).decode()
    out = git("push", "-u", "origin", "main", extra_header=f"AUTHORIZATION: basic {auth}")
    print(f"[repo] pushed main{(' · ' + out) if out else ''}")
    return f"{login}/{REPO_NAME}"


def step_secrets(env: dict[str, str], full: str) -> None:
    try:
        from nacl import encoding, public
    except ImportError:
        sys.exit("pip install pynacl (needed to encrypt GitHub secrets)")
    with gh(env) as c:
        pk = c.get(f"/repos/{full}/actions/secrets/public-key").raise_for_status().json()
        box = public.SealedBox(public.PublicKey(pk["key"].encode(), encoding.Base64Encoder()))
        n = 0
        for k in APP_SECRETS:
            v = env.get(k, "")
            if not v:
                continue
            enc = base64.b64encode(box.encrypt(v.encode())).decode()
            c.put(f"/repos/{full}/actions/secrets/{k}", json={"encrypted_value": enc, "key_id": pk["key_id"]}).raise_for_status()
            n += 1
        print(f"[secrets] {n} secrets set")
        for k in APP_VARS:
            v = env.get(k, "")
            if not v:
                continue
            r = c.post(f"/repos/{full}/actions/variables", json={"name": k, "value": v})
            if r.status_code == 409:
                c.patch(f"/repos/{full}/actions/variables/{k}", json={"name": k, "value": v}).raise_for_status()
            elif r.status_code != 201:
                r.raise_for_status()
        print(f"[secrets] {len([k for k in APP_VARS if env.get(k)])} variables set")
    if env.get("DATABASE_URL", "").startswith("sqlite"):
        print("[secrets] WARNING: DATABASE_URL is SQLite; Actions runs will write to a throwaway DB. Put the Supabase URL in .env and re-run `secrets render`.")


# ---------------------------------------------------------------- render
def render_env(env: dict[str, str]) -> list[dict[str, str]]:
    keys = APP_SECRETS + APP_VARS + ["WEB_ORIGINS", "DATA_DIR"]
    out = [{"key": "PYTHON_VERSION", "value": "3.12.7"}, {"key": "PYTHONUTF8", "value": "1"}]
    out += [{"key": k, "value": env[k]} for k in keys if env.get(k)]
    return out


def step_render(env: dict[str, str], full: str) -> str:
    c = httpx.Client(base_url="https://api.render.com/v1", timeout=120,
                     headers={"Authorization": f"Bearer {need(env, 'RENDER_API_KEY')}", "Accept": "application/json"})
    owners = c.get("/owners", params={"limit": 20}).raise_for_status().json()
    owner_id = owners[0]["owner"]["id"]
    existing = [s["service"] for s in c.get("/services", params={"name": RENDER_SERVICE, "limit": 10}).raise_for_status().json()
                if s["service"]["name"] == RENDER_SERVICE]
    if existing:
        svc = existing[0]
        c.put(f"/services/{svc['id']}/env-vars", json=render_env(env)).raise_for_status()
        c.post(f"/services/{svc['id']}/deploys", json={"clearCache": "do_not_clear"}).raise_for_status()
        print(f"[render] updated env vars + redeploy triggered for {RENDER_SERVICE}")
    else:
        body = {
            "type": "web_service", "name": RENDER_SERVICE, "ownerId": owner_id,
            "repo": f"https://github.com/{full}", "branch": "main", "autoDeploy": "yes", "rootDir": ".",
            "envVars": render_env(env),
            "serviceDetails": {
                "env": "python", "plan": "free", "region": RENDER_REGION, "healthCheckPath": "/health",
                "envSpecificDetails": {"buildCommand": "pip install -r api/requirements.txt",
                                       "startCommand": "uvicorn api.main:app --host 0.0.0.0 --port $PORT"},
            },
        }
        r = c.post("/services", json=body)
        if r.status_code >= 400:
            print(f"[render] create failed {r.status_code}: {r.text[:400]}")
            print("[render] If the repo is not accessible: Render dashboard → Account settings → GitHub → install the Render app on the repo, then re-run `render`.")
            sys.exit(1)
        svc = r.json()["service"]
        print(f"[render] created {RENDER_SERVICE} in {RENDER_REGION}; first deploy started")
    url = svc.get("serviceDetails", {}).get("url") or f"https://{RENDER_SERVICE}.onrender.com"
    print(f"[render] API URL: {url}  (health: {url}/health; first build takes ~5 min)")
    if env.get("DATABASE_URL", "").startswith("sqlite"):
        print("[render] WARNING: DATABASE_URL is SQLite; the service boots but data is ephemeral. Put the Supabase URL in .env and re-run `render`.")
    return url


# ---------------------------------------------------------------- vercel
def step_vercel(env: dict[str, str], api_url: str) -> str:
    token = need(env, "VERCEL_TOKEN")
    web = ROOT / "web"
    npx = "npx.cmd" if os.name == "nt" else "npx"
    base = [npx, "--yes", "vercel@latest", "--token", token]

    def run(args: list[str], input_text: str | None = None) -> str:
        r = subprocess.run(base + args, cwd=web, capture_output=True, text=True, input=input_text)
        if r.returncode != 0:
            raise RuntimeError(f"vercel {' '.join(args[:2])} failed:\n{(r.stderr or r.stdout).strip()[-800:]}")
        return (r.stdout or "").strip()

    run(["link", "--yes", "--project", VERCEL_PROJECT])
    print(f"[vercel] linked web/ to project {VERCEL_PROJECT}")
    for target in ("production", "preview"):
        subprocess.run(base + ["env", "rm", "NEXT_PUBLIC_API_URL", target, "--yes"], cwd=web, capture_output=True, text=True)
        run(["env", "add", "NEXT_PUBLIC_API_URL", target], input_text=api_url + "\n")
    print(f"[vercel] NEXT_PUBLIC_API_URL = {api_url}")
    out = run(["deploy", "--prod", "--yes"])
    url = out.splitlines()[-1].strip() if out else "(see dashboard)"
    print(f"[vercel] production: {url}")
    print(f"[vercel] Add this origin to WEB_ORIGINS in .env if you use a custom domain (vercel.app origins are already allowed).")
    return url


# ---------------------------------------------------------------- main
def main(argv: list[str]) -> None:
    steps = argv or ["repo", "secrets", "render", "vercel"]
    env = load_env()
    full: str | None = None
    api_url: str | None = env.get("API_URL") or None
    for s in steps:
        if s == "repo":
            full = step_repo(env)
        elif s == "secrets":
            full = full or f"{gh(env).get('/user').raise_for_status().json()['login']}/{REPO_NAME}"
            step_secrets(env, full)
        elif s == "render":
            full = full or f"{gh(env).get('/user').raise_for_status().json()['login']}/{REPO_NAME}"
            api_url = step_render(env, full)
        elif s == "vercel":
            if not api_url:
                sys.exit("vercel step needs the API URL: run `render` first, or put API_URL=https://… in .env")
            step_vercel(env, api_url)
        else:
            sys.exit(f"unknown step {s}; choose from repo secrets render vercel")
    print("\nDone. Record the URLs in docs/STATE.md → Live URLs.")


if __name__ == "__main__":
    main(sys.argv[1:])
