import json
import urllib.request
import urllib.error
import re
from typing import Optional, Tuple
from ui.constants import APP_VERSION, GITHUB_URL

def parse_version(version_str: str) -> Tuple[int, ...]:
    """
    Parses a version string like 'v1.2.3-alpha.4' into a comparable tuple.
    Returns (major, minor, patch, pre_release_type, pre_release_num).
    Pre-release types are mapped: alpha=1, beta=2, rc=3, final=4.
    """
    # Clean 'v' prefix and handle basic semantic versioning
    v = version_str.lstrip('v').lower()
    
    # Regex to capture major, minor, patch and optional pre-release info
    # Supports: 1.2.3, 1.2.3-alpha.1, 1.2.3-beta, 1.2.3-rc5, etc.
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:-?([a-zA-Z]+)(?:\.?(\d+))?)?$', v)
    
    if not match:
        # Fallback for non-standard versions: just extract all digit groups
        digits = re.findall(r'\d+', v)
        return tuple(map(int, digits)) + (4, 0)

    major, minor, patch, pre_type, pre_num = match.groups()
    
    pre_map = {
        'alpha': 1,
        'beta': 2,
        'rc': 3,
        None: 4
    }
    
    # Determine pre-release type value
    type_val = 4 # Default to final
    if pre_type:
        for key, val in pre_map.items():
            if key and pre_type.startswith(key):
                type_val = val
                break
    
    num_val = int(pre_num) if pre_num else 0
    
    return (int(major), int(minor), int(patch), type_val, num_val)

def check_for_updates() -> Tuple[bool, Optional[str]]:
    """
    Checks GitHub for a newer release.
    Returns (True, latest_version) if a newer version is available,
    (False, None) otherwise.
    """
    try:
        # Extract owner and repo from GITHUB_URL
        parts = GITHUB_URL.rstrip("/").split("/")
        if len(parts) < 5:
            return False, None
        
        owner = parts[-2]
        repo = parts[-1]
        
        # We check both 'latest' (stable) and the general releases list
        # to ensure we can detect updates even if we are on a pre-release.
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        
        req = urllib.request.Request(
            api_url, 
            headers={"User-Agent": "MiBudsClient-Updater"}
        )
        
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.getcode() == 200:
                releases = json.loads(response.read().decode())
                if not releases:
                    return False, None
                
                # Get the most recent release (GitHub API returns them sorted by date)
                latest_release = releases[0]
                latest_tag = latest_release.get("tag_name")
                
                if latest_tag:
                    local_v = parse_version(APP_VERSION)
                    latest_v = parse_version(latest_tag)
                    
                    if latest_v > local_v:
                        return True, latest_tag
                    
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, None
        print(f"HTTP Error checking for updates: {e}")
    except Exception as e:
        print(f"Error checking for updates: {e}")
        
    return False, None
