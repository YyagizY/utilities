# ABOUTME: Parses client repo requirements files and checks out matching
# ABOUTME: versions of product libraries under /Desktop/repos/products/

import configparser
import re
import subprocess
from pathlib import Path

PRODUCTS_DIR = Path("/Users/yagiz.yaman/Desktop/repos/products")

# Map from package name to repo directory name.
# Order matters: more specific entries (invent-rocks.noob) must come before
# less specific ones (invent-rocks) to avoid prefix mismatches.
PACKAGE_TO_REPO = {
    "invent-rocks.future-visibility": "rocks-future-visibility",
    "invent-rocks.reporting": "rocks-reporting",
    "invent-rocks.rocket": "rocks-rocket",
    "invent-rocks.noob": "rocks-noob",
    "invent-rocks.opal": "rocks-opal",
    "invent-rocks": "rocks",
    "invent-rocket-pandas": "rocket_pandas",
    "invent-fabbrica-plugin-invent": "airflow-fabbrica-plugin-invent",
    "invent-fabbrica": "airflow-fabbrica",
    "invent-omega-ui": "omega-ui",
    "invent-future-visibility": "future-visibility",
}


def parse_requirements(filepath: Path) -> dict[str, str]:
    """Extract {package: version} for == pinned entries only."""
    versions = {}
    if not filepath.exists():
        return versions
    for line in filepath.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([\w\-\.]+)(?:\[[\w,]+\])?==([^\s]+)", line)
        if match:
            versions[match.group(1).lower()] = match.group(2)
    return versions


def parse_fabbrica_version(filepath: Path) -> str | None:
    """Extract rocket_pandas version from fabbrica.yaml."""
    if not filepath.exists():
        return None
    for line in filepath.read_text().splitlines():
        match = re.search(r"image_name:\s*rocketpandas:([^\s]+)", line)
        if match:
            return match.group(1)
    return None


def latest_tag(repo_dir: Path) -> str | None:
    """Return the latest semantic version tag in the repo."""
    result = subprocess.run(
        ["git", "tag", "--sort=-version:refname"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    tags = [t.strip() for t in result.stdout.splitlines() if t.strip()]
    return tags[0] if tags else None


def best_tag_for_constraint(repo_dir: Path, constraint: str) -> str | None:
    """Return the latest tag in repo_dir satisfying a PEP 440 constraint string.

    constraint examples: '>=1.15.0,<2.0.0'  '>=1.0'
    """
    from packaging.specifiers import SpecifierSet
    from packaging.version import Version, InvalidVersion

    spec = SpecifierSet(constraint)
    result = subprocess.run(
        ["git", "tag", "--sort=-version:refname"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    for raw in result.stdout.splitlines():
        tag = raw.strip()
        ver_str = tag.lstrip("v")
        try:
            if Version(ver_str) in spec:
                return tag
        except InvalidVersion:
            continue
    return None


def parse_setup_cfg_requires(setup_cfg: Path) -> dict[str, str]:
    """Extract {normalised-package-name: constraint} from install_requires in setup.cfg."""
    if not setup_cfg.exists():
        return {}
    cfg = configparser.ConfigParser()
    cfg.read(setup_cfg)
    raw = cfg.get("options", "install_requires", fallback="")
    requires = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # split on first >= <= != == ~= < >
        match = re.match(r"^([\w\-\.]+)((?:[><=!~][^;#\s]+)*)", line)
        if match:
            pkg = re.sub(r"[-_.]", "-", match.group(1).lower())
            constraint = match.group(2).strip()
            if constraint:
                requires[pkg] = constraint
    return requires


def has_uncommitted_changes(repo_dir: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def fetch_tags(repo_dir: Path) -> None:
    subprocess.run(
        ["git", "fetch", "--tags"],
        cwd=repo_dir,
        capture_output=True,
    )


def checkout(repo_dir: Path, version: str | None) -> None:
    if has_uncommitted_changes(repo_dir):
        print(f"  ! {repo_dir.name} → skipped (uncommitted changes)")
        return
    fetch_tags(repo_dir)
    if version:
        tag = f"v{version}"
    else:
        tag = latest_tag(repo_dir)
        if not tag:
            print(f"  ! {repo_dir.name} → no tags found, skipping")
            return
    result = subprocess.run(
        ["git", "checkout", tag],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        label = tag if version else f"{tag} (latest)"
        print(f"  ✓ {repo_dir.name} → {label}")
    else:
        print(f"  ✗ {repo_dir.name} → {tag} failed: {result.stderr.strip()}")


def main() -> None:
    client_dir = Path.cwd()
    print(f"Client: {client_dir.name}\n")

    versions: dict[str, str] = {}
    versions.update(parse_requirements(client_dir / "requirements-spark.txt"))
    versions.update(parse_requirements(client_dir / "requirements-airflow.txt"))

    rp_version = parse_fabbrica_version(client_dir / "dags" / "fabbrica.yaml")
    if rp_version:
        versions["invent-rocket-pandas"] = rp_version

    checked = set()
    for pkg, repo_name in PACKAGE_TO_REPO.items():
        if repo_name in checked:
            continue
        repo_dir = PRODUCTS_DIR / repo_name
        if not repo_dir.exists():
            continue
        version = versions.get(pkg.lower())
        checkout(repo_dir, version)
        checked.add(repo_name)

    # Sync invent-noob transitively: read the constraint declared by rocks-noob
    # and checkout the latest matching tag. rocks-noob must be synced first (above).
    noob_repo = PRODUCTS_DIR / "noob"
    rocks_noob_repo = PRODUCTS_DIR / "rocks-noob"
    if noob_repo.exists() and rocks_noob_repo.exists():
        transitive = parse_setup_cfg_requires(rocks_noob_repo / "setup.cfg")
        constraint = transitive.get("invent-noob")
        if constraint:
            fetch_tags(noob_repo)
            tag = best_tag_for_constraint(noob_repo, constraint)
            if tag:
                if has_uncommitted_changes(noob_repo):
                    print(f"  ! noob → skipped (uncommitted changes)")
                else:
                    result = subprocess.run(
                        ["git", "checkout", tag],
                        cwd=noob_repo,
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        print(f"  ✓ noob → {tag} (via rocks-noob constraint: {constraint})")
                    else:
                        print(f"  ✗ noob → {tag} failed: {result.stderr.strip()}")
            else:
                print(f"  ! noob → no tag satisfies rocks-noob constraint ({constraint})")


if __name__ == "__main__":
    main()
