#!/usr/bin/env python3
# Vendored copy of Surrentum-Org/.github actions/no-github-artifacts/check.py (main 2026-11-13). This fork is public and
# public repos cannot use actions from that private repo, so surrentum-ci.yml runs this copy instead.
"""Fail when a workflow or action stores files on GitHub (owner 2026-11-13): Actions artifacts or release assets.

Everything goes to our own store instead: Surrentum-Org/.github/actions/store-artifact and fetch-artifact
(ci-artifacts.keffals.gg). GHCR images are fine (they do not count). A GitHub Release with notes only is fine.

Flags, in .github/workflows/*.y*ml and every action.y*ml outside node_modules:
  - actions/upload-artifact, actions/download-artifact, actions/upload-pages-artifact
  - softprops/action-gh-release (or any release action) given files: / artifacts: / asset inputs
  - gh release upload, and gh release create with file arguments
  - goreleaser (it uploads release assets)
A line can be allowed with a trailing `# gh-artifacts: allowed <reason>` comment (reviewed exceptions only).
Usage: check.py [repo-dir] [--exclude glob ...]
"""
import fnmatch
import os
import re
import shlex
import sys

USES = re.compile(r"uses:\s*['\"]?(actions/(upload-artifact|download-artifact|upload-pages-artifact)|"
                  r"goreleaser/goreleaser-action|actions/upload-release-asset|svenstaro/upload-release-action|"
                  r"shogo82148/actions-upload-release-asset)@", re.I)
RELEASE_ACTIONS = re.compile(r"uses:\s*['\"]?(softprops/action-gh-release|ncipollo/release-action)@", re.I)
ASSET_INPUT = re.compile(r"^\s*(files|artifacts|asset_path|assets):", re.I)
GORELEASER_RUN = re.compile(r"\bgoreleaser\b.*\brelease\b(?!.*--skip[= ]\S*publish)")
ALLOW = re.compile(r"#\s*gh-artifacts:\s*allowed\b")
# gh release create flags that take a value
VALUE_FLAGS = {"-t", "--title", "-n", "--notes", "-F", "--notes-file", "--target", "--discussion-category",
               "--notes-start-tag", "-R", "--repo", "--fail-on-no-commits"}


def joined_lines(text):
    """Yield (lineno, logical line) with backslash continuations folded."""
    buf, start = "", 0
    for i, line in enumerate(text.splitlines(), 1):
        if not buf:
            start = i
        if line.rstrip().endswith("\\"):
            buf += line.rstrip()[:-1] + " "
            continue
        yield start, buf + line
        buf = ""
    if buf:
        yield start, buf


def gh_release_create_has_files(line):
    m = re.search(r"\bgh\s+release\s+create\b(.*)", line)
    if not m:
        return False
    rest = m.group(1).split("#", 1)[0]
    rest = re.split(r"\s(?:&&|\|\||;|\|)\s", rest)[0]
    try:
        toks = shlex.split(rest)
    except ValueError:
        toks = rest.split()
    positional, skip = [], False
    for t in toks:
        if skip:
            skip = False
            continue
        if t.startswith("-"):
            if "=" not in t and t in VALUE_FLAGS:
                skip = True
            continue
        positional.append(t)
    return len(positional) > 1  # tag + at least one file


def scan(path):
    problems = []
    text = open(path, encoding="utf-8", errors="replace").read()
    lines = text.splitlines()
    in_release_step = None
    for no, line in joined_lines(text):
        if ALLOW.search(line):
            continue
        if USES.search(line):
            problems.append((no, line.strip()))
        if RELEASE_ACTIONS.search(line):
            in_release_step = len(line) - len(line.lstrip(" -"))
            continue
        if in_release_step is not None:
            indent = len(line) - len(line.lstrip(" "))
            if line.strip().startswith("- ") and indent <= in_release_step:
                in_release_step = None
            elif ASSET_INPUT.search(line):
                problems.append((no, "release action with " + line.strip()))
        if re.search(r"\bgh\s+release\s+upload\b", line) or gh_release_create_has_files(line) or GORELEASER_RUN.search(line):
            problems.append((no, line.strip()[:160]))
    return problems


def main(argv):
    root, excludes, i = ".", [], 1
    while i < len(argv):
        if argv[i] == "--exclude":
            excludes.append(argv[i + 1]); i += 2
        else:
            root = argv[i]; i += 1
    files = []
    wf = os.path.join(root, ".github", "workflows")
    if os.path.isdir(wf):
        files += [os.path.join(wf, f) for f in sorted(os.listdir(wf)) if f.endswith((".yml", ".yaml"))]
    for d, dirs, fs in os.walk(root):
        dirs[:] = [x for x in dirs if x not in ("node_modules", ".git", "vendor")]
        files += [os.path.join(d, f) for f in fs if f in ("action.yml", "action.yaml")]
    bad = 0
    for f in sorted(set(files)):
        rel = os.path.relpath(f, root)
        if any(fnmatch.fnmatch(rel, e) for e in excludes):
            continue
        for no, what in scan(f):
            bad += 1
            print(f"::error file={rel},line={no}::stores files on GitHub ({what}). Use "
                  f"Surrentum-Org/.github/actions/store-artifact and fetch-artifact (our artifact store) instead; "
                  f"releases carry notes only.")
    print(f"no-github-artifacts: {len(files)} file(s) checked, {bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
