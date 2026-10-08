# HandBrake "Update always fails" fix — 2026-10-08 (v9.7.4)

## Report
After self-updating the app to v9.7.3, the user clicked **Update** next to
HandBrakeCLI in Tools & Encoders and got a failure dialog (screenshot unreadable
to the agent — reproduced instead from the installed `/opt/vconv` code).

## Reproduction (v9.7.3 installed code)
Only one tool had `update_available=True`: **handbrake** (installed 1.7.2 vs
latest 1.11.2 — ffmpeg 8.1 and NVEncC 9.38 were current).
Running `ToolUpdater().update('handbrake')` with a real `error_cb`:

```
[20%] Installing fr.handbrake.HandBrakeCLI via Flatpak…
[0%] Flatpak install failed: error: No remote chosen to resolve 'flathub'
     which exists in multiple installations
```

## Root cause (three stacked facts)
1. **HandBrake publishes no Linux HandBrakeCLI build**: GitHub release 1.11.2
   assets = Windows/macOS CLI zips/dmg, `HandBrake-…-source.tar.bz2`,
   `HandBrake-1.11.2-x86_64.flatpak` (GUI) — no Linux CLI tarball/deb/AppImage.
2. **The Flatpak app id was wrong**: `fr.handbrake.HandBrakeCLI` does not exist
   on Flathub (`flatpak remote-info` → "Can't find ref"). Flathub only has the
   GUI `fr.handbrake.ghb` (+ plugins); its manifest builds with `--flatpak`
   GUI options and no CLI.
3. **Even a correct `flatpak install flathub …` is ambiguous here**: flathub is
   configured for BOTH the system and the user installation ⇒
   "No remote chosen to resolve 'flathub'".
4. apt (Linux Mint 22.2 / noble) candidate == installed `1.7.2` — no distro
   upgrade path either. So the offered update was impossible from every angle.

## Fix (`utils/tool_updater.py`, `core/handbrake_manager.py`)
- New `_find_linux_cli_asset(assets)`: accepts `HandBrakeCLI*` assets that are
  `.tar.*`/`.AppImage`/`.deb` (or a `.zip` with an explicit `linux` marker) and
  rejects Windows/macOS/source/dmg assets (bare HandBrake zips are Windows).
- `status_handbrake()`: gates `update_available` on that helper; when absent →
  `update_available=False` + note "1.11.2 ships no Linux HandBrakeCLI build
  (Windows/macOS/GUI-Flatpak only) — your 1.7.2 is the newest prebuilt CLI"
  (rendered gray under the row; Update button disabled).
- `_install_handbrake()`: dead flatpak path **removed**. Now downloads/extracts
  a real Linux asset (tar → `_extract_strip`, zip → `zipfile`, deb → `dpkg-deb
  -x`, AppImage → move+chmod), finds the `HandBrakeCLI` binary
  case-insensitively, chmod +x, symlinks into `tools/bin` (prepended to PATH),
  cleans old `handbrake-*` dirs. No Linux asset ⇒ honest `error_cb` message,
  no subprocess at all.
- `_extract_strip()`: `tarfile.open(..., "r:xz")` → `"r:*"` (any compression).
- Removed dead `FLATPAK_CLI_HELPER` constant from `core/handbrake_manager.py`.
  (Its separate apt path `_ensure_handbrake_cli` → `HandBrakeManager.check_for_update`
  was always honest: apt candidate == installed ⇒ no update.)

## Tests — 198 checks ALL PASS
`tests/test_tool_updater.py` 56 → **85 checks** (+29):
- `test_mocked_statuses`: handbrake with no Linux asset → not offered + note;
  same release *with* a Linux asset → offered again.
- `test_find_linux_cli_asset`: 9 cases (win zip/dmg/source/bare zip rejected;
  linux tar/AppImage/zip/deb accepted; empty → None).
- `test_install_handbrake_no_linux_asset`: update → False; message contains the
  honest reason; does NOT contain `flatpak install` / `fr.handbrake`;
  `subprocess.run` monkeypatched to raise ⇒ proves no subprocess runs.
- `test_install_handbrake_from_linux_asset`: end-to-end tar.xz **and** zip with
  a synthetic release → success, symlink into (patched) BIN_DIR, exec bit set,
  progress 100, old `handbrake-1.7.0` dir cleaned.

Full suite: conversion_flags 23 · e2e_format 6 · encoder_engine 36 ·
format_radio 14 · self_update 16 · tools_startup_smoke 10 ·
tool_updater 85 · tool_worker 8 = **198**.

## Live verification (real GitHub release, dev checkout)
```
installed: 1.7.2 | latest: 1.11.2
update_available: False
note: 1.11.2 ships no Linux HandBrakeCLI build (Windows/macOS/GUI-Flatpak only)
      — your 1.7.2 is the newest prebuilt CLI
update() -> False
error: HandBrake 1.11.2 ships no prebuilt Linux HandBrakeCLI (only Windows/macOS
       binaries and a GUI Flatpak are published) — your installed version stays current.
```
Dialog rendering (`ToolsDialog._apply_status`): row shows
"installed **1.7.2** · latest **1.11.2** · *current*" + gray note; Update
button disabled (button gated on `update_available`).

## Docs updated
AGENTS.md (Tool Auto-Updater: HandBrake bullet rewritten + v9.7.4 fix note),
CHANGELOG.md [Unreleased] → this file.
