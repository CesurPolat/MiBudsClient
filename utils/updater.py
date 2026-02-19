import json
import urllib.request
import urllib.error
from typing import Optional, Tuple
from ui.constants import APP_VERSION, GITHUB_URL

def check_for_updates() -> Tuple[bool, Optional[str]]:
    """
    Checks GitHub for a newer release.
    Returns (True, latest_version) if a newer version is available,
    (False, None) otherwise.
    """
    try:
        # Extract owner and repo from GITHUB_URL
        # Expected: https://github.com/Owner/Repo
        parts = GITHUB_URL.rstrip("/").split("/")
        if len(parts) < 5:
            return False, None
        
        owner = parts[-2]
        repo = parts[-1]
        
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        
        req = urllib.request.Request(
            api_url, 
            headers={"User-Agent": "MiBudsClient-Updater"}
        )
        
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode())
                latest_tag = data.get("tag_name")
                
                if latest_tag and latest_tag != APP_VERSION:
                    # Clean tags (remove 'v' prefix if present)
                    v_local = APP_VERSION.lstrip('v').split('.')
                    v_latest = latest_tag.lstrip('v').split('.')
                    
                    try:
                        # Compare major.minor.patch
                        for i in range(min(len(v_local), len(v_latest))):
                            if int(v_latest[i]) > int(v_local[i]):
                                return True, latest_tag
                            elif int(v_latest[i]) < int(v_local[i]):
                                return False, None
                        
                        # If all parts equal, but latest has more parts (e.g. 1.0.1 vs 1.0)
                        if len(v_latest) > len(v_local):
                            return True, latest_tag
                            
                    except (ValueError, IndexError):
                        # Fallback to simple comparison if parsing fails
                        return latest_tag != APP_VERSION
                    
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # No releases found or repository not accessible
            return False, None
        print(f"HTTP Error checking for updates: {e}")
    except Exception as e:
        print(f"Error checking for updates: {e}")
        
    return False, None
