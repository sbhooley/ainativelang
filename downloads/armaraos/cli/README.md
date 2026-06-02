# ArmaraOS CLI install artifacts

Public download host for `curl -sSfL https://ainativelang.com/install.sh | sh`.

Built in private **`sbhooley/armara`**, published here (same storage pattern as desktop `.dmg` / `.exe` in `../`).

- `latest.json` — version manifest for install scripts and `armaraos update`
- `openfang-<target>.tar.gz` / `.zip` — CLI binaries per platform
- `install.sh` / `install.ps1` — copies of the canonical installers (ainativelang.com serves these via rewrite)

Do not hand-edit binaries; update via ArmaraOS release CI or a maintainer sync from a tagged build.
