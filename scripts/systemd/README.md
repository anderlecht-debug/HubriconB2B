# Unattended content pipeline

    mkdir -p ~/.config/systemd/user
    cp scripts/systemd/hubricon-content.{service,timer} ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable --now hubricon-content.timer
    loginctl enable-linger lp9          # ticks fire without a login session (sudo if refused)

Pause:   `touch content/.runner/STOP`      Resume: `rm content/.runner/STOP`
Stop:    `systemctl --user stop hubricon-content.timer`
Logs:    `journalctl --user -u hubricon-content` and `content/.runner/log`
Dry run: `CONTENT_DRY_RUN=1 scripts/content-tick.sh` (proves headless auth with a two-turn prompt)

The service runs `scripts/content-tick.sh` from the `content` worktree (`../HubriconB2B-content`), which is
permanent; secrets are read from the main checkout's `.env`.
