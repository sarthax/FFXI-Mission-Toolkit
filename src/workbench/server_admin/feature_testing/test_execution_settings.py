"""One-screen setup for local test execution, replacing a dozen environment variables.

Settings live in a single JSON file (git-ignored, holds the generated tokens and the optional
read-only database login). Nothing is applied until the operator presses "Enable" on the Setup tab.
Real environment variables always win, so existing shell-based setups keep working unchanged.
Secrets are never returned by any function that feeds the web UI.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
_APPLIED: set[str] = set()   # env keys currently supplied by the settings file, not by the shell
_RESULT_DEFAULTS = {          # created under the data folder automatically; nobody should type these
    "MISSION_TOOLKIT_TEST_RESULTS_DB": "results.db",
    "MISSION_TOOLKIT_TEST_DRAFTS_DB": "drafts.db",
    "MISSION_TOOLKIT_TEST_JOBS_DB": "jobs.db",
}


def data_dir() -> Path:
    configured = os.environ.get("MISSION_TOOLKIT_TEST_DATA_DIR", "")
    if configured:
        return Path(configured)
    # Must live OUTSIDE the repo: the runner refuses artifact folders inside a source checkout.
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MissionToolkit" / "test_execution"


def _migrate_legacy() -> None:
    old = _REPO / "data" / "test_execution" / "settings.json"
    new = settings_path()
    if old.is_file() and not new.exists():
        new.parent.mkdir(parents=True, exist_ok=True)
        new.write_bytes(old.read_bytes())


def settings_path() -> Path:
    return data_dir() / "settings.json"


def _empty() -> dict:
    return {"enabled": False, "headless_root": "", "charids": [], "account": "",
            "db": {"user": "", "password": "", "name": "", "port": 3306},
            "tokens": {"operator": "", "supervisor": ""}}


def load() -> dict:
    if "MISSION_TOOLKIT_TEST_DATA_DIR" not in os.environ:
        _migrate_legacy()
    merged = _empty()
    try:
        raw = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return merged
    if isinstance(raw, dict):
        for key in ("enabled", "headless_root", "charids", "account"):
            if key in raw:
                merged[key] = raw[key]
        for key in ("db", "tokens"):
            if isinstance(raw.get(key), dict):
                merged[key].update(raw[key])
    return merged


def _save(settings: dict) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _token() -> str:
    return secrets.token_urlsafe(36)   # 48 chars, comfortably above the 32 the gateways require


def _env_values(settings: dict) -> dict[str, str]:
    root = data_dir()
    values = {"MISSION_TOOLKIT_TEST_ARTIFACTS_ROOT": str(root / "artifacts")}
    values.update({key: str(root / name) for key, name in _RESULT_DEFAULTS.items()})
    if settings["headless_root"]:
        values["MISSION_TOOLKIT_TEST_HEADLESS_ROOT"] = settings["headless_root"]
    if settings["charids"]:
        values["MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS"] = ",".join(str(c) for c in settings["charids"])
    db = settings["db"]
    for suffix, key in (("USER", "user"), ("PASSWORD", "password"), ("NAME", "name")):
        if db.get(key):
            values["MISSION_TOOLKIT_SUPERVISOR_DB_" + suffix] = str(db[key])
    values["MISSION_TOOLKIT_SUPERVISOR_DB_PORT"] = str(db.get("port") or 3306)
    if settings["tokens"]["operator"]:
        values["MISSION_TOOLKIT_TEST_OPERATOR_TOKEN"] = settings["tokens"]["operator"]
    if settings["tokens"]["supervisor"]:
        values["MISSION_TOOLKIT_SUPERVISOR_TOKEN"] = settings["tokens"]["supervisor"]
    return values


def apply_to_environ(settings: dict | None = None) -> list[str]:
    """Publish enabled settings into os.environ without overriding anything the shell set."""
    settings = settings or load()
    for key in list(_APPLIED):               # forget stale file-supplied values first
        os.environ.pop(key, None)
    _APPLIED.clear()
    if not settings["enabled"]:
        return []
    (data_dir() / "artifacts").mkdir(parents=True, exist_ok=True)
    for key, value in _env_values(settings).items():
        if key not in os.environ:
            os.environ[key] = value
            _APPLIED.add(key)
    return sorted(_APPLIED)


# Explicit per-process sandbox isolation is distinct from the ordinary Setup-tab
# environment precedence: an isolated data directory must never silently borrow
# shell supervisor authorization, regardless of UI or runner entry point.
_SANDBOX_EXECUTION_KEYS = (
    "MISSION_TOOLKIT_TEST_HEADLESS_ROOT",
    "MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS",
    "MISSION_TOOLKIT_SUPERVISOR_TOKEN",
    "MISSION_TOOLKIT_TEST_OPERATOR_TOKEN",
    "MISSION_TOOLKIT_SUPERVISOR_DB_USER",
    "MISSION_TOOLKIT_SUPERVISOR_DB_PASSWORD",
    "MISSION_TOOLKIT_SUPERVISOR_DB_NAME",
    "MISSION_TOOLKIT_SUPERVISOR_DB_PORT",
)
_SANDBOX_STORAGE_KEYS = (
    "MISSION_TOOLKIT_TEST_RESULTS_DB",
    "MISSION_TOOLKIT_TEST_DRAFTS_DB",
    "MISSION_TOOLKIT_TEST_JOBS_DB",
    "MISSION_TOOLKIT_TEST_ARTIFACTS_ROOT",
)


def _sandbox_directory_check() -> tuple[dict, Path | None]:
    """Scope decision used by operator UI and stricter launch preflight."""
    selected = os.environ.get("MISSION_TOOLKIT_TEST_DATA_DIR", "").strip()
    if not selected:
        return ({"isolated": False, "ok": True,
                 "reason": "Not in an explicit test sandbox"}, None)
    root = Path(selected)
    default = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MissionToolkit" / "test_execution"
    if (not root.is_absolute() or root.is_symlink()
            or root.resolve() == default.resolve()):
        return ({"isolated": True, "ok": False,
                 "reason": "Sandbox directory must be an absolute, separate non-symlink directory"}, None)
    return ({"isolated": True, "ok": True,
             "reason": "Explicit sandbox selected"}, root)


def _sandbox_local_path(key: str, root: Path) -> bool:
    value = os.environ.get(key, "")
    if not value:
        return False
    path = Path(value)
    return (path.is_absolute() and not path.is_symlink()
            and path.resolve().is_relative_to(root.resolve()))


def sandbox_operator_check() -> dict:
    """Guard operator/draft authorization with sandbox-OWNED token and storage.

    A draft-only sandbox does not need to configure supervisor, characters, or
    readback DB to review drafts. It may never use an inherited production
    operator token or a shared drafts/jobs file.
    """
    isolation, root = _sandbox_directory_check()
    if not isolation["isolated"] or not isolation["ok"]:
        return isolation
    sandbox_file = settings_path()
    if sandbox_file.is_symlink():
        return {"isolated": True, "ok": False,
                "reason": "Isolated supervisor settings must not be a linked external file"}
    settings = load()  # never migrate the production settings file in isolation
    if settings.get("enabled") is not True:
        return {"isolated": True, "ok": False,
                "reason": "Isolated operator setup is not explicitly enabled in this sandbox"}
    tokens = settings.get("tokens")
    token = tokens.get("operator") if isinstance(tokens, dict) else None
    if (not isinstance(token, str) or len(token) < 32
            or os.environ.get("MISSION_TOOLKIT_TEST_OPERATOR_TOKEN", "") != token):
        return {"isolated": True, "ok": False,
                "reason": "Isolated operator token is missing or overridden by unrelated environment variables"}
    if not all(_sandbox_local_path(k, root) for k in (
            "MISSION_TOOLKIT_TEST_DRAFTS_DB", "MISSION_TOOLKIT_TEST_JOBS_DB")):
        return {"isolated": True, "ok": False,
                "reason": "Isolated operator draft/job storage is missing or outside this sandbox"}
    return {"isolated": True, "ok": True,
            "reason": "Explicit sandbox operator token and storage match"}


def sandbox_execution_check() -> dict:
    """Fail-closed supervisor provenance check for explicitly isolated runs.

    Ordinary production shell-over-settings precedence remains unchanged.
    Unlike the draft-only operator gate, *execution* requires the sandbox-own
    supervisor token, runner, allowlist, readback configuration and storage.
    Neither check authenticates DSP/client evidence or authorizes a runner.
    No secrets or allowlisted identities are returned to the UI.
    """
    isolation = sandbox_operator_check()
    if not isolation["isolated"] or not isolation["ok"]:
        return isolation
    root = Path(os.environ["MISSION_TOOLKIT_TEST_DATA_DIR"].strip())
    settings = load()
    try:
        if (not isinstance(settings.get("charids"), list)
                or not isinstance(settings.get("headless_root"), str)
                or not isinstance(settings.get("tokens"), dict)
                or any(not isinstance(settings["tokens"].get(k), str)
                       for k in ("operator", "supervisor"))
                or not isinstance(settings.get("db"), dict)):
            raise ValueError("malformed isolated settings")
        expected = _env_values(settings)
    except (KeyError, TypeError, ValueError, AttributeError):
        return {"isolated": True, "ok": False,
                "reason": "Isolated supervisor configuration is incomplete or invalid"}
    for key in _SANDBOX_EXECUTION_KEYS:
        value = expected.get(key, "")
        if not value or os.environ.get(key, "") != value:
            return {"isolated": True, "ok": False,
                    "reason": "Isolated supervisor configuration is missing or overridden by unrelated environment variables"}
    try:
        charids = parse_charids(settings["charids"])
    except ValueError:
        charids = []
    if (len(settings["tokens"]["operator"]) < 32
            or len(settings["tokens"]["supervisor"]) < 32
            or settings["tokens"]["operator"] == settings["tokens"]["supervisor"]
            or not charids or charids != settings["charids"]):
        return {"isolated": True, "ok": False,
                "reason": "Isolated supervisor tokens or disposable-character approval are incomplete"}
    if not all(_sandbox_local_path(key, root) for key in _SANDBOX_STORAGE_KEYS):
        return {"isolated": True, "ok": False,
                "reason": "Test storage must remain within the isolated data directory"}
    return {"isolated": True, "ok": True,
            "reason": "Explicit isolated supervisor setup matches this sandbox"}


def ui_mode_active() -> bool:
    """True when the operator opted in through the Setup tab (no pasted token needed from the page)."""
    return (bool(load()["enabled"])
            and bool(os.environ.get("MISSION_TOOLKIT_TEST_OPERATOR_TOKEN"))
            and sandbox_operator_check()["ok"])


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def search_roots() -> list[Path]:
    extra = [Path(p) for p in os.environ.get("MISSION_TOOLKIT_TEST_SEARCH_ROOTS", "").split(os.pathsep) if p]
    return extra + [_REPO.parent / "FFXI-Tools" / "headless-research", _REPO.parent / "headless-research"]


def detect_headless_roots() -> list[dict]:
    """Find XiHeadless checkouts that contain the observation runner. Read-only."""
    found, seen = [], set()
    for base in search_roots():
        if not base.is_dir():
            continue
        for runner in sorted(base.glob("*/tools/observation_runner.py")):
            root = runner.parent.parent
            if root in seen or root.is_symlink():
                continue
            seen.add(root)
            dirty = _git(root, "status", "--porcelain", "--untracked-files=no")
            found.append({"path": str(root), "name": root.name,
                          "commit": _git(root, "rev-parse", "--short=10", "HEAD"),
                          "has_dll": (root / "bin" / "mcp" / "XiHeadless.dll").is_file(),
                          "clean": not dirty})
    found.sort(key=lambda c: (not (c["has_dll"] and c["clean"]), c["name"]))  # usable checkouts first
    return found


def parse_charids(text) -> list[int]:
    items = text if isinstance(text, list) else str(text).replace(";", ",").split(",")
    ids = []
    for item in items:
        item = str(item).strip()
        if item:
            if not item.isdigit() or not 0 < int(item) < 2**31:
                raise ValueError("character IDs must be positive whole numbers, e.g. 21833")
            if int(item) not in ids:
                ids.append(int(item))
    if len(ids) > 20:
        raise ValueError("at most 20 approved test characters")
    return ids


def update(*, headless_root: str | None = None, charids=None, db: dict | None = None, account: str | None = None) -> dict:
    """Validate and persist user-editable fields. The headless root must be a detected checkout."""
    settings = load()
    if headless_root is not None:
        allowed = {c["path"] for c in detect_headless_roots()}
        if headless_root and headless_root not in allowed:
            raise ValueError("choose one of the detected XiHeadless checkouts")
        settings["headless_root"] = headless_root
    if charids is not None:
        settings["charids"] = parse_charids(charids)
    if account is not None:
        if account and not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", account):
            raise ValueError("account names use letters, digits, - and _ (max 32)")
        settings["account"] = account
    if db is not None:
        for key in ("user", "name"):
            if key in db:
                value = str(db[key]).strip()
                if len(value) > 64 or any(c in value for c in "\r\n\0"):
                    raise ValueError("invalid database " + key)
                settings["db"][key] = value
        if db.get("password"):          # blank means "keep the stored password"
            settings["db"]["password"] = str(db["password"])
        if "port" in db:
            port = int(db["port"] or 3306)
            if not 1 <= port <= 65535:
                raise ValueError("invalid database port")
            settings["db"]["port"] = port
    _save(settings)
    apply_to_environ(settings)
    return settings


def set_enabled(enabled: bool) -> dict:
    settings = load()
    settings["enabled"] = bool(enabled)
    if enabled:
        for kind in ("operator", "supervisor"):
            if len(settings["tokens"][kind]) < 32:
                settings["tokens"][kind] = _token()
    _save(settings)
    apply_to_environ(settings)
    return settings


def status() -> dict:
    """Plain-language checklist for the Setup tab; contains no secrets."""
    from .execution_preflight import preflight
    settings = load()
    roots = detect_headless_roots()
    isolation = sandbox_execution_check()
    chosen = (settings["headless_root"] if isolation["isolated"]
              else os.environ.get("MISSION_TOOLKIT_TEST_HEADLESS_ROOT", "") or settings["headless_root"])
    db_ready = bool(os.environ.get("MISSION_TOOLKIT_SUPERVISOR_DB_USER")
                    and os.environ.get("MISSION_TOOLKIT_SUPERVISOR_DB_PASSWORD")
                    and os.environ.get("MISSION_TOOLKIT_SUPERVISOR_DB_NAME"))
    try:
        import pymysql  # noqa: F401
        driver = True
    except ImportError:
        try:
            import mysql.connector  # noqa: F401
            driver = True
        except ImportError:
            driver = False
    pre = preflight("moghancement", "MOG-09")
    if isolation["isolated"] and not isolation["ok"]:
        db_ready = False
    steps = [
        {"id": "sandbox_isolation", "ok": isolation["ok"],
         "title": "Isolated supervisor configuration",
         "fix": isolation["reason"]},
        {"id": "enabled", "ok": settings["enabled"], "title": "Test execution turned on",
         "fix": "Press \"Turn on test execution\" below. Tokens are generated for you."},
        {"id": "checkout", "ok": bool(chosen),
         "title": "XiHeadless checkout chosen", "fix": "Pick a detected checkout from the list. None listed? Build XiHeadless first (see the guide)."},
        {"id": "dll", "ok": bool(chosen) and (Path(chosen) / "bin" / "mcp" / "XiHeadless.dll").is_file(),
         "title": "XiHeadless is built (bin/mcp/XiHeadless.dll)", "fix": "Build XiHeadless into bin/mcp from a clean commit, then reload this page."},
        {"id": "characters", "ok": bool(settings["charids"]) and isolation["ok"] if isolation["isolated"]
         else bool(os.environ.get("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS")),
         "title": "Disposable test character approved", "fix": "Enter the character ID of a throwaway test account (never a real character)."},
        {"id": "database", "ok": db_ready and driver,
         "title": "Server database readable (read-only login)",
         "fix": "Enter the read-only database login. Without it a run cannot compare the client against saved data and will be BLOCKED." if driver
                else "No MySQL driver is installed in the Toolkit environment."},
    ]
    return {"enabled": settings["enabled"], "steps": steps, "headless_roots": roots,
            "selected_root": chosen, "charids": settings["charids"], "account": settings["account"],
            "db": {"user": settings["db"]["user"], "name": settings["db"]["name"],
                   "port": settings["db"]["port"], "password_saved": bool(settings["db"]["password"])},
            "ready_to_run": all(step["ok"] for step in steps) and bool(pre["ready_for_operator_review"]),
            "preflight": pre, "settings_file": str(settings_path())}
