"""Stage immutable state files on the faster existing volume, then switch cleanly."""
import hashlib
import json
import os
import pwd
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA = Path("/data/erigon")
HOT = Path("/var/lib/erigon-hot")
DOMAIN = DATA / "snapshots/domain"
SLOW_DOMAIN = DATA / "snapshots/domain.slow-backup"
CHAIN = DATA / "chaindata"
SLOW_CHAIN = DATA / "chaindata.slow-backup"
OVERRIDE = Path("/run/systemd/system/erigon.service.d/zz-hot-storage-stop.conf")
GIB = 1024**3
CHUNK = 16 * 1024**2
OWNER = pwd.getpwnam("adm-mesifi")
manifest = {}
copied = 0
total = 0
last_update = 0.0


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def status(phase, **details):
    value = {"observed_at": datetime.now(timezone.utc).isoformat(), "phase": phase,
             "copied_bytes": copied, "total_bytes": total, **details}
    atomic_json(HOT / "migration-status.json", value)
    print(json.dumps(value), flush=True)


def systemctl(*args):
    return subprocess.run(["systemctl", *args], check=True)


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            result.update(chunk)
    return result.hexdigest()


def copy_verified(source, target):
    global copied, last_update
    source, target = Path(source), Path(target)
    before = source.stat()
    key = str(source)
    old = manifest.get(key)
    if (old and target.is_file() and old["size"] == before.st_size
            and old["mtime_ns"] == before.st_mtime_ns and digest(target) == old["sha256"]):
        copied += before.st_size
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    os.chown(target.parent, OWNER.pw_uid, OWNER.pw_gid)
    temporary = target.with_name("." + target.name + ".partial")
    hashed = hashlib.sha256()
    with source.open("rb") as origin, temporary.open("wb") as destination:
        os.posix_fadvise(origin.fileno(), 0, 0, os.POSIX_FADV_SEQUENTIAL)
        while chunk := origin.read(CHUNK):
            destination.write(chunk)
            hashed.update(chunk)
            copied += len(chunk)
            if time.monotonic() - last_update >= 30:
                status("copying", current_file=source.name)
                last_update = time.monotonic()
        destination.flush()
        os.fsync(destination.fileno())
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"Source changed during copy: {source}")
    checksum = hashed.hexdigest()
    if digest(temporary) != checksum:
        raise RuntimeError(f"Copy checksum mismatch: {source}")
    shutil.copystat(source, temporary)
    os.chown(temporary, OWNER.pw_uid, OWNER.pw_gid)
    temporary.replace(target)
    manifest[key] = {"size": before.st_size, "mtime_ns": before.st_mtime_ns, "sha256": checksum}
    atomic_json(HOT / "verified-copies.json", manifest)


def kept_slow(path):
    return "-commitment." in path.name and path.suffix == ".kv"


def domain_files():
    files = list(DOMAIN.iterdir())
    if any(not file.is_file() or file.is_symlink() for file in files):
        raise RuntimeError("Unexpected non-regular snapshot entry; refusing to switch")
    return files


def copy_domain():
    files = domain_files()
    for source in sorted(files, key=lambda item: item.stat().st_size):
        if not kept_slow(source):
            copy_verified(source, HOT / "domain" / source.name)
    return files


def main():
    global total, manifest
    if DOMAIN.is_symlink() or CHAIN.is_symlink() or SLOW_DOMAIN.exists() or SLOW_CHAIN.exists():
        raise RuntimeError("Storage already switched or backup paths occupied; inspect before retrying")
    if DOMAIN.resolve() != (DATA / "snapshots/domain").absolute():
        raise RuntimeError("Unexpected snapshot path")
    HOT.mkdir(mode=0o755, exist_ok=True)
    os.chown(HOT, OWNER.pw_uid, OWNER.pw_gid)
    files = domain_files()
    total = sum(file.stat().st_size for file in files if not kept_slow(file))
    chain_size = sum(file.stat().st_size for file in CHAIN.rglob("*") if file.is_file())
    if shutil.disk_usage(HOT).free < total + chain_size + 30 * GIB:
        raise RuntimeError("Insufficient fast-volume space with 30 GiB reserve")
    saved = HOT / "verified-copies.json"
    if saved.exists():
        manifest = json.loads(saved.read_text())
    (HOT / "domain").mkdir(exist_ok=True)
    os.chown(HOT / "domain", OWNER.pw_uid, OWNER.pw_gid)
    domain_size = total
    total += chain_size
    status("preparing", fast_domain_bytes=domain_size, chain_bytes=chain_size)
    status("stopping_cleanly")
    # Allow the current transaction to close without a forced systemd kill.
    OVERRIDE.parent.mkdir(parents=True, exist_ok=True)
    OVERRIDE.write_text("[Service]\nTimeoutStopSec=infinity\n", encoding="ascii")
    systemctl("daemon-reload")
    subprocess.run(["systemctl", "stop", "ethereum-index-cache.service"], check=False)
    switched = []
    started = False
    try:
        systemctl("stop", "erigon.service")
        if subprocess.check_output(["systemctl", "show", "erigon", "-p", "MainPID", "--value"], text=True).strip() != "0":
            raise RuntimeError("Erigon still running; refusing to copy the mutable database")
        current = copy_domain()
        names = {file.name for file in current}
        for path in (HOT / "domain").iterdir():
            if path.name not in names and str(DOMAIN / path.name) in manifest:
                path.unlink()
        for source in current:
            if kept_slow(source):
                (HOT / "domain" / source.name).symlink_to(SLOW_DOMAIN / source.name)
        status("copying_stopped_database")
        if (HOT / "chaindata").exists():
            raise RuntimeError("Fast chaindata already exists; refusing to overwrite")
        shutil.copytree(CHAIN, HOT / "chaindata", copy_function=copy_verified)
        for directory, _, _ in os.walk(HOT / "chaindata"):
            os.chown(directory, OWNER.pw_uid, OWNER.pw_gid)
        if shutil.disk_usage(HOT).free < 25 * GIB:
            raise RuntimeError("Fast volume reserve too small after copying")
        for source, backup, target in ((DOMAIN, SLOW_DOMAIN, HOT / "domain"),
                                       (CHAIN, SLOW_CHAIN, HOT / "chaindata")):
            source.rename(backup)
            switched.append((source, backup))
            source.symlink_to(target, target_is_directory=True)
        status("starting_on_fast_storage")
        systemctl("start", "erigon.service")
        started = True
        subprocess.run(["systemctl", "start", "ethereum-index-cache.service"], check=False)
        status("activated", note="Originals preserved; monitor RPC for verified progress and final sync")
    except Exception:
        if not started:
            for source, backup in reversed(switched):
                if source.is_symlink():
                    source.unlink()
                if not source.exists():
                    backup.rename(source)
            subprocess.run(["systemctl", "start", "erigon.service"], check=False)
        raise
    finally:
        OVERRIDE.unlink(missing_ok=True)
        systemctl("daemon-reload")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        if HOT.exists():
            status("failed", error=f"{type(exc).__name__}: {exc}")
        raise
