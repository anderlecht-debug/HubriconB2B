"""The founder's own machine runs a few jobs; since 2026-10-03 it is a Linux
desktop, so `install` writes systemd user timers there, and the launchd agent
only on a Mac. Nothing here touches the real machine: a temp home and a fake
runner."""

import plistlib
from pathlib import Path

from hubricon_engine import scheduling
from hubricon_engine.harvest import run as harvest
from hubricon_engine.sourcing import run as sourcing


class Runner:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()


def test_the_timer_runs_the_command_at_each_hour_and_catches_up_after_the_machine_was_off():
    service, timer = scheduling.systemd_units("hubricon-sourcing", "Hubricon Shopify lead sourcing",
                                              ["source", "all"], (7, 19), 40, Path("/x/engine"), "/usr/bin/uv")
    assert "ExecStart=/usr/bin/uv run hubricon source all" in service
    assert "WorkingDirectory=/x/engine" in service and "Type=oneshot" in service
    assert "OnCalendar=*-*-* 07:40:00" in timer and "OnCalendar=*-*-* 19:40:00" in timer
    assert "Persistent=true" in timer and "WantedBy=timers.target" in timer


def test_on_linux_install_writes_the_units_and_enables_the_timer(tmp_path):
    r = Runner()
    out = scheduling.install("hubricon-sourcing", "Hubricon Shopify lead sourcing", ["source", "all"],
                             (7, 19), 40, runner=r, platform="linux", home=tmp_path)
    unit_dir = tmp_path / ".config" / "systemd" / "user"
    assert (unit_dir / "hubricon-sourcing.service").exists() and (unit_dir / "hubricon-sourcing.timer").exists()
    assert ["systemctl", "--user", "daemon-reload"] in r.calls
    assert ["systemctl", "--user", "enable", "--now", "hubricon-sourcing.timer"] in r.calls
    assert "journalctl --user -u hubricon-sourcing" in out and "enabled" in out
    assert not any(c[0] == "launchctl" for c in r.calls)
    scheduling.uninstall("hubricon-sourcing", runner=r, platform="linux", home=tmp_path)
    assert not (unit_dir / "hubricon-sourcing.timer").exists()
    assert ["systemctl", "--user", "disable", "--now", "hubricon-sourcing.timer"] in r.calls


def test_on_a_mac_install_is_the_launchd_agent_it_always_was(tmp_path):
    r = Runner()
    scheduling.install("hubricon-harvest", "Hubricon free lead harvest", ["harvest", "all"], (6, 18), 10,
                       runner=r, platform="darwin", home=tmp_path)
    plist = tmp_path / "Library" / "LaunchAgents" / "com.hubricon.harvest.plist"
    data = plistlib.loads(plist.read_bytes())
    assert data["Label"] == "com.hubricon.harvest"
    assert data["ProgramArguments"][1:] == ["run", "hubricon", "harvest", "all"]
    assert [x["Hour"] for x in data["StartCalendarInterval"]] == [6, 18]
    assert any(c[0] == "launchctl" for c in r.calls)


def test_both_jobs_install_through_the_one_scheduler(monkeypatch):
    seen = []
    monkeypatch.setattr(scheduling, "install", lambda name, desc, args, hours, minute, **kw: seen.append((name, args, hours, minute)) or "ok")
    harvest.install(), sourcing.install()
    assert seen == [("hubricon-harvest", ["harvest", "all"], harvest.RUN_HOURS, 10),
                    ("hubricon-sourcing", ["source", "all"], sourcing.RUN_HOURS, 40)]
    assert harvest.install_launchd is harvest.install and sourcing.install_launchd is sourcing.install
