"""
Update Checker - Checks GitHub for new vconv releases
"""
import re
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com/repos/motaz-hefny/MoTekLab-vconv/releases/latest"


@dataclass
class UpdateInfo:
    available: bool
    latest_version: str
    current_version: str
    release_url: str
    release_notes: str = ""
    error: str = ""


def parse_version(tag: str) -> Tuple[int, ...]:
    """Parse a version tag like 'v9.2.0' into (9, 1, 0)."""
    tag = tag.lstrip('v')
    parts = []
    for p in tag.replace('-', '.').replace('_', '.').split('.'):
        try:
            parts.append(int(p))
            if len(parts) >= 3:  # Only keep major.minor.patch
                break  # Stop at pre-release suffix
        except ValueError:
            break
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(latest_tag: str, current_version: str) -> bool:
    """Compare two version strings. Returns True if latest > current."""
    try:
        latest = parse_version(latest_tag)
        current = parse_version(current_version)
        return latest > current
    except Exception as e:
        logger.warning(f"Version comparison failed: {e}")
        return False


def check_for_updates(current_version: str, cache_file: Optional[str] = None,
                      cache_ttl_hours: int = 24) -> UpdateInfo:
    """
    Check GitHub for a newer release.

    Args:
        current_version: Current app version (e.g. '9.2.0')
        cache_file: Path to cache file to avoid repeated API calls
        cache_ttl_hours: How long to use cached result

    Returns:
        UpdateInfo with update availability details
    """
    info = UpdateInfo(
        available=False,
        latest_version=current_version,
        current_version=current_version,
        release_url="",
        error=""
    )

    # Check cache first
    if cache_file:
        cached = _read_cache(cache_file, cache_ttl_hours)
        if cached:
            cached_latest = cached.get('latest_version', '')
            cached_url = cached.get('release_url', '')
            if is_newer(cached_latest, current_version):
                info.available = True
                info.latest_version = cached_latest
                info.release_url = cached_url
            return info

    try:
        req = urllib.request.Request(
            GITHUB_API,
            headers={
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'vconv-update-checker/9.2.0'
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        latest_tag = data.get('tag_name', '')
        release_url = data.get('html_url', '')
        body = data.get('body', '')

        if not latest_tag:
            info.error = "No tag_name in response"
            return info

        has_update = is_newer(latest_tag, current_version)
        info.available = has_update
        info.latest_version = latest_tag.lstrip('v')
        info.release_url = release_url
        info.release_notes = body[:500] if body else ""

        # Cache the result
        if cache_file:
            _write_cache(cache_file, {
                'latest_version': latest_tag.lstrip('v'),
                'release_url': release_url,
                'checked_at': datetime.now().isoformat()
            })

        if has_update:
            logger.info(f"Update available: {latest_tag} (current: v{current_version})")
        else:
            logger.debug(f"No update available (latest: {latest_tag})")

    except urllib.error.HTTPError as e:
        info.error = f"GitHub API error: {e.code}"
        logger.warning(f"Update check failed: {e.code}")
    except urllib.error.URLError as e:
        info.error = f"Network error: {e.reason}"
        logger.debug(f"Update check network error: {e.reason}")
    except (json.JSONDecodeError, KeyError) as e:
        info.error = f"Parse error: {e}"
        logger.warning(f"Update check parse error: {e}")
    except Exception as e:
        info.error = f"Error: {e}"
        logger.debug(f"Update check failed: {e}")

    return info


def _cache_path() -> str:
    """Get path to update check cache file."""
    cache_dir = Path.home() / ".config" / "vconv"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return str(cache_dir / "update_cache.json")


def _read_cache(cache_file: str, ttl_hours: int) -> Optional[dict]:
    """Read cached update check result if not expired."""
    try:
        path = Path(cache_file)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        checked_at = datetime.fromisoformat(data.get('checked_at', ''))
        if datetime.now() - checked_at < timedelta(hours=ttl_hours):
            return data
    except (json.JSONDecodeError, ValueError, OSError) as e:
        logger.debug(f"Cache read failed: {e}")
    return None


def _write_cache(cache_file: str, data: dict):
    """Write update check result to cache."""
    try:
        Path(cache_file).write_text(json.dumps(data, indent=2))
    except OSError as e:
        logger.debug(f"Cache write failed: {e}")