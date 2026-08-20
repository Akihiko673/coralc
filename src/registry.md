Full spec — coralc package system. Everything below is additive to the existing compiler; nothing about the language changes.
1. Concepts
Package — a versioned unit of .crl files, installable into the compiler's own lib/ tree. Identified by name@version. A package is just a folder layout (like std/, wallvm/, embed/ already in lib/lib2).
Registry — the database of known packages. Two copies exist:
- online registry — the canonical, canonical source of truth, hosted as coral-lang/registry on GitHub.
- local registry — lib/registry.json, bundled and shipped with the compiler. Fallback for offline use and the baseline for compare.
Install root — lib/ resolved relative to the compiler itself (<repo>/lib), never a system path. Both bundled packages and downloaded ones live there.
2. Package manifest — coral.json
Required, at package root. Smallest possible, validated strictly:
{
  "name": "godot",
  "version": "0.1.0",
  "description": "Godot GDExtension bindings",
  "src": ["godot/"],
  "license": "MIT",
  "author": "cerie",
  "min_coral": "0.1.0"
}
Rules:
- name — [a-z0-9_]+, lowercase-only, no dots, 1–64 chars. Global namespace.
- version — semver, strictly X.Y.Z (no prerelease for v0).
- src — list of folders relative to package root, exactly what ships. Everything else (tests, docs) is excluded from distribution.
- min_coral — optional minimum compiler version the package needs.
- Everything else (depends, etc.) is rejected as unknown keys for now — the schema is closed, to keep the validator honest.
3. The registry file
registry.json, top-level array of entries:
[
  {
    "name": "godot",
    "version": "0.1.0",
    "description": "Godot GDExtension bindings",
    "url": "https://github.com/coral-lang/registry/releases/download/godot-0.1.0/godot-0.1.0.tgz",
    "sha256": "8f3a…",
    "author": "cerie",
    "license": "MIT",
    "min_coral": "0.1.0"
  }
]
- One entry per name@version. Names may have multiple versions; at most one per (name, version).
- url must be https, sha256 must match the downloaded archive. Both are mandatory.
- The bundled lib/registry.json carries the versions known at compiler ship-time. Online is authoritative; local is the snapshot.
4. Where things live
<repo>/lib/registry.json          # bundled local registry (checked in, ships with coral)
<repo>/lib/.registry/godots.json  # cached copy of the online registry (generated)
<repo>/lib/.registry/lock.json    # what's actually installed (generated)
<repo>/lib/godot/…                # installed package (from coral.json src list)
add/sync/diff all operate on compiler-relative paths. The lock file makes add idempotent.
5. Commands
coralc add <package> [<package>…]
1. Resolve each name (optionally name@version) against the merged registry: online cache if present, else bundled local.
2. Version rule, applied in order:
- explicit name@X.Y.Z → that exact version;
- name@^X.Y.Z → highest compatible;
- bare name → highest.
3. Download url to a temp file (<lib>/.registry/tmp/…), validate:
- sha256 matches the registry entry;
- archive must be .tgz/.zip, extract;
- extracted package must contain coral.json whose name/version match the entry — protects against URL/registry mismatch.
4. Copy src folders to <lib>/<name>/, atomically: install into <lib>/<name>.tmp, then rename.
5. Write/update lock.json with name → version, sha256, installed_at.
6. Print added godot v0.1.0.
7. On any failure, clean the temp dir; installed state must be untouched (either fully installed or previous state, never half).
Errors: unknown name ("no such package: xyz — run coralc registry sync?"), checksum mismatch (fatal, exit 1), version not found in registry.
coralc registry sync
1. Fetch https://raw.githubusercontent.com/coral-lang/registry/main/registry.json into lib/.registry/godots.json.new, then atomically rename over the cache.
2. Re-validate: every entry must satisfy the schema above; sha256 fields must be 64 hex chars; urls https. A malformed online registry is rejected wholesale — local cache stays.
3. Print summary: synced: 12 packages, 34 versions.
4. Offline failure → non-fatal message, existing cache (or bundled) remains authoritative.
coralc registry diff
Compares the three layers and prints a table:
online            local(bundled)     installed
godot  0.2.0  →   –                  v0.1.0     NEW    update available
pixl   0.1.0  →   0.1.0              v0.1.0     up-to-date
drop    –      →   0.3.0             0.3.0      REMOVED from online
Built from the merged registry minus installed (lock.json). Used by us as developers, and as the user-facing "what's new" surface. format: table|json flag.
coralc registry init (in a package folder)
1. Validate the folder has .crl files.
2. Interactively scaffold coral.json (name from folder name, ask for version/author/license).
3. Prints the final manifest and what publish will do with it.
coralc publish (in a package folder)
1. Validate coral.json strictly. Missing/invalid → errors listing every field.
2. Sanity-compile: run the compiler's parse pass over every .crl in src (no codegen, no emit) — catches broken packages before they're registered.
3. Build <name>-<version>.tgz (.tar.gz, src folders only, deterministic order).
4. Compute sha256.
5. Output the registry entry as a ready-to-paste block:
name: godot
version: 0.1.0
url:   https://github.com/coral-lang/registry/releases/download/godot-0.1.0/godot-0.1.0.tgz
sha256: 8f3a…
6. With --push (only if GitHub token configured): uploads the tgz to the registry repo as a release asset named exactly godot-0.1.0.tgz, then prints the PR-ready registry.json entry. Opening the PR itself is manual by design — the registry is human-gated.
coralc remove <name>
1. Delete <lib>/<name>/, update lock.json.
2. Never touches other packages or the registry files. Uninstalling a package nothing else depends on is safe by construction, since packages are self-contained folders (no shared mutable state).
coralc list
Installed packages + versions from lock.json. <10 lines.
6. Merging rules (sync + resolution)
Merge logic, single function used by all commands:
1. Start from bundled local (lib/registry.json).
2. Overlay cached online (lib/.registry/godots.json) by (name, version):
- versions only in online → added;
- same version in both → sha256/url must be identical, else error out (either registry is stale or tampered — print diff, refuse);
- versions only in bundled → kept, marked "not on online" in diff;
3. Resolution targets the merged set; installed state (lock.json) never feeds resolution, only diff output.
Removed-from-online packages stay resolvable from bundled if already installed — never break the installed set on a sync.
7. Trust & security rules
- Every download is https + pinned sha256; mismatch kills the install.
- Installed package's own coral.json must re-declare the identical name/version — guards URL mixups on the registry side.
- Registry schema is closed; unknown keys are validation errors, so a compromised repo can't smuggle arbitrary fields (e.g. custom install paths).
- No arbitrary command execution anywhere — extract-then-copy only. No post-install scripts in this design. Packages can't touch anything outside <lib>/<name>/.
- Name-squatting gate is human: publishing requires a PR to coral-lang/registry. First-come on names; flagged as "community" until a maintainer blesses it, if you want a trusted tier later.
- Deterministic packaging (fixed file order in archive) so sha256 is reproducible.
8. Contributor flow (end to end)
1. git init your package repo, write .crl files.
2. coralc registry init → coral.json.
3. coralc publish → local tgz + entry block. Install-check locally with coralc add godot --from ./coral_godot-style dev path (or just copy the folder) to confirm it parses.
4. Tag the release godot-0.1.0 (or any tag), push.
5. coralc publish --push → tgz lands as a release asset on coral-lang/registry; you paste the entry into a PR adding it to registry.json.
6. Maintainer merges → coralc registry sync → everyone can coralc add godot.
7. New version later: bump coral.json, re-publish, re-PR, bump. The diff command shows users "update available" and (once added) coralc update godot upgrades to the lock-pinned newest.
9. Update command (small follow-up, cheap once the rest exists)
coralc update <name> — resolve merged registry for a higher version than lock.json, download+verify+swap, never downgrade without explicit name@version.
10. What we build first (tight order, each step self-testing)
1. lib/registry.json bundled + schema validator.
2. coralc add against bundled registry, local folder --from dev-path (dogfood immediately with the godot bindings).
3. publish (validate → tar → sha256 → entry output).
4. registry sync / diff (cache file + merge).
5. coral-lang/registry repo + release-asset upload in publish --push.
6. lock.json, update, remove, list polish.
Nothing here needs a server, credentials at rest, or language changes. The self-hosted compiler reimplements urllib/tarfile the same way add shells out to them today — the CLI contract stays identical, so packages and registry outlive the bootstrap.
