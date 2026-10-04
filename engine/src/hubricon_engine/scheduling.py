"""Scheduling the jobs that run on the founder's own machine.

Production runs in the cloud: the operator, the Monday sweep and the daily issue
job on GitHub Actions, the site and its functions on Vercel. A few jobs run on
the founder's machine instead, because they read public pages from a residential
connection (the Shopify sourcing) or need a person at the keyboard. Until
2026-10-03 that machine was a Mac and these were launchd agents; since then it is
the founder's Linux desktop, and they are systemd user timers, beside the content
pipeline's own `hubricon-content.timer`.

`install()` writes the right thing for the machine it runs on: on Linux a
`<name>.service` and `<name>.timer` under ~/.config/systemd/user, enabled; on a
Mac the launchd agent it always was. Either way a run missed while the machine
was off or asleep runs at the next start.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parents[2]


def _uv() -> str:
    return shutil.which("uv") or ("/opt/homebrew/bin/uv" if sys.platform == "darwin" else "/usr/bin/uv")


def systemd_units(name: str, description: str, args: list[str], hours: tuple[int, ...], minute: int,
                  engine_dir: Path = ENGINE_DIR, uv: str | None = None) -> tuple[str, str]:
    """The service and timer text for one job: `uv run hubricon <args>` in the
    engine directory at each hour:minute local, missed runs caught up at boot."""
    uv = uv or _uv()
    service = (
        "[Unit]\n"
        f"Description={description}\n\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"WorkingDirectory={engine_dir}\n"
        f"ExecStart={uv} run hubricon {' '.join(args)}\n"
        f"Environment=HOME={Path.home()}\n"
        "Environment=PYTHONUNBUFFERED=1\n"
        "Nice=10\n"
    )
    calendar = "\n".join(f"OnCalendar=*-*-* {h:02d}:{minute:02d}:00" for h in hours)
    timer = (
        "[Unit]\n"
        f"Description={description}, on schedule\n\n"
        "[Timer]\n"
        f"{calendar}\n"
        "Persistent=true\n"
        "RandomizedDelaySec=2min\n\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )
    return service, timer


def launchd_plist(label: str, args: list[str], hours: tuple[int, ...], minute: int, log_name: str,
                  engine_dir: Path = ENGINE_DIR, uv: str | None = None) -> dict:
    log_dir = Path.home() / "Library" / "Logs"
    return {
        "Label": label,
        "ProgramArguments": [uv or _uv(), "run", "hubricon", *args],
        "WorkingDirectory": str(engine_dir),
        "StartCalendarInterval": [{"Hour": h, "Minute": minute} for h in hours],
        "StandardOutPath": str(log_dir / f"{log_name}.log"),
        "StandardErrorPath": str(log_dir / f"{log_name}.err"),
        "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
                                 "PYTHONUNBUFFERED": "1"},  # the log is readable while the run is going
    }


def install(name: str, description: str, args: list[str], hours: tuple[int, ...], minute: int,
            engine_dir: Path = ENGINE_DIR, runner=subprocess.run, platform: str | None = None,
            home: Path | None = None) -> str:
    """Schedule `uv run hubricon <args>` on this machine. `name` is the unit name
    on Linux (hubricon-sourcing) and becomes com.<name with dots> on a Mac."""
    platform = platform or sys.platform
    home = home or Path.home()
    when = " and ".join(f"{h:02d}:{minute:02d}" for h in hours)
    command = f"uv run hubricon {' '.join(args)}"
    if platform == "darwin":
        label = "com." + name.replace("-", ".")
        plist_path = home / "Library" / "LaunchAgents" / f"{label}.plist"
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_path.write_bytes(plistlib.dumps(launchd_plist(label, args, hours, minute, name, engine_dir)))
        domain = f"gui/{os.getuid()}"
        runner(["launchctl", "bootout", domain, str(plist_path)], capture_output=True)
        res = runner(["launchctl", "bootstrap", domain, str(plist_path)], capture_output=True, text=True)
        state = "loaded" if res.returncode == 0 else f"launchctl said: {(res.stderr or res.stdout).strip()}"
        return (f"{plist_path}\n  runs `{command}` daily at {when} local (missed while asleep → runs at "
                f"next wake); logs in ~/Library/Logs/{name}.log\n  {state}")
    unit_dir = home / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    service, timer = systemd_units(name, description, args, hours, minute, engine_dir)
    (unit_dir / f"{name}.service").write_text(service)
    (unit_dir / f"{name}.timer").write_text(timer)
    runner(["systemctl", "--user", "daemon-reload"], capture_output=True)
    res = runner(["systemctl", "--user", "enable", "--now", f"{name}.timer"], capture_output=True, text=True)
    state = "enabled" if res.returncode == 0 else f"systemctl said: {(res.stderr or res.stdout).strip()}"
    return (f"{unit_dir / (name + '.timer')}\n  runs `{command}` daily at {when} local (missed while off → "
            f"runs at next start); logs: journalctl --user -u {name}\n  {state}")


def uninstall(name: str, runner=subprocess.run, platform: str | None = None, home: Path | None = None) -> str:
    platform = platform or sys.platform
    home = home or Path.home()
    if platform == "darwin":
        label = "com." + name.replace("-", ".")
        plist_path = home / "Library" / "LaunchAgents" / f"{label}.plist"
        runner(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist_path)], capture_output=True)
        plist_path.unlink(missing_ok=True)
        return f"{plist_path} removed"
    runner(["systemctl", "--user", "disable", "--now", f"{name}.timer"], capture_output=True)
    for ext in ("timer", "service"):
        (home / ".config" / "systemd" / "user" / f"{name}.{ext}").unlink(missing_ok=True)
    runner(["systemctl", "--user", "daemon-reload"], capture_output=True)
    return f"{name}.timer disabled and removed"
