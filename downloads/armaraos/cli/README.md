# ArmaraOS CLI install artifacts

Public download host for `curl -sSfL https://ainativelang.com/install.sh | sh` and `irm https://ainativelang.com/install.ps1 | iex`.

Built in private **`sbhooley/armara`**, published here (same storage pattern as desktop `.dmg` / `.exe` in `../`).

- `latest.json` — version manifest for install scripts and `armaraos update`
- `armaraos-<target>.tar.gz` / `.zip` — CLI binaries per platform (Windows uses `.zip`)
- Legacy `openfang-*` archives may remain for macOS until the next release sync renames them
- `install.sh` / `install.ps1` — copies of the canonical installers (ainativelang.com serves these via rewrite)

Do not hand-edit binaries; update via ArmaraOS release CI or a maintainer sync from a tagged build.

**Note:** CLI v0.8.1 on Windows cannot self-update (`armaraos update` requests legacy `openfang-*.zip` and mishandles zip archives). Re-run the installer or upgrade to **v0.8.2+** once published.
