import yaml
import shutil
import time
from pathlib import Path

def merge_config():
    h = Path('/opt/data/custom-config.yaml')
    c = Path('/opt/data/config.yaml')
    if h.exists():
        try:
            hc = yaml.safe_load(h.read_text()) or {}
            cc = yaml.safe_load(c.read_text()) or {} if c.exists() else {}
            def merge(a, b):
                for k, v in b.items():
                    if isinstance(v, dict) and k in a and isinstance(a[k], dict):
                        merge(a[k], v)
                    else:
                        a[k] = v
            merge(cc, hc)
            c.write_text(yaml.safe_dump(cc))
            print("[Env-Sync] config.yaml merged successfully.", flush=True)
        except Exception as e:
            print(f"[Env-Sync] Error merging config.yaml: {e}", flush=True)

def main():
    # 1. Merge config at startup
    merge_config()
    
    # 2. Sync env at startup
    env_host = Path('/opt/data/custom-.env')
    env_container = Path('/opt/data/.env')
    
    if env_host.exists():
        try:
            shutil.copy2(env_host, env_container)
            print("[Env-Sync] Initialized .env from host.", flush=True)
        except Exception as e:
            print(f"[Env-Sync] Error initializing .env from host: {e}", flush=True)
            
    # 3. Start sync loop
    last_mtime_host = env_host.stat().st_mtime if env_host.exists() else 0
    last_mtime_container = env_container.stat().st_mtime if env_container.exists() else 0
    
    print("[Env-Sync] Starting background sync loop...", flush=True)
    while True:
        try:
            time.sleep(2)
            # Check host changes
            if env_host.exists():
                mtime_host = env_host.stat().st_mtime
                if mtime_host > last_mtime_host:
                    shutil.copy2(env_host, env_container)
                    last_mtime_host = mtime_host
                    last_mtime_container = env_container.stat().st_mtime if env_container.exists() else 0
                    print("[Env-Sync] .env updated in container from host changes.", flush=True)
                    continue
            # Check container changes
            if env_container.exists():
                mtime_container = env_container.stat().st_mtime
                if mtime_container > last_mtime_container:
                    shutil.copy2(env_container, env_host)
                    last_mtime_container = mtime_container
                    last_mtime_host = env_host.stat().st_mtime if env_host.exists() else 0
                    print("[Env-Sync] .env updated on host from container changes.", flush=True)
        except Exception as e:
            # Ignore and retry next iteration
            pass

if __name__ == '__main__':
    main()
