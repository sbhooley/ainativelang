# ArmaraOS desktop installers (hosted on ainativelang)

Direct-download binaries for the marketing site ([ainativelang.com/armaraos](https://ainativelang.com/armaraos)).

| File | Platform |
|------|----------|
| `ArmaraOS_0.7.8_osxARM.dmg` | macOS Apple Silicon (M1/M2/M3/M4…) |
| `ArmaraOS_0.7.8_arm64-setup.exe` | Windows ARM64 (Surface Pro X, Snapdragon laptops, etc.) |

**Canonical URLs (after merge to `main`):**

```
https://raw.githubusercontent.com/sbhooley/ainativelang/main/downloads/armaraos/ArmaraOS_0.7.8_osxARM.dmg
https://raw.githubusercontent.com/sbhooley/ainativelang/main/downloads/armaraos/ArmaraOS_0.7.8_arm64-setup.exe
```

Large `.dmg` files use **Git LFS** (over GitHub’s 100 MiB blob limit).

Add new builds here when tagging a desktop release; update `ainativelangweb/public/downloads/armaraos/latest.json` and `config/site.ts` → `latestArmaraosReleaseTag` in the website repo.

Do not commit installers to `ainativelangweb` (Amplify artifact size limit).
