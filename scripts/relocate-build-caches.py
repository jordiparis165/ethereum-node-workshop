"""Preserve inactive build caches on /data to recover hot-volume headroom."""
import hashlib
import argparse
import json
import os
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path

DESTINATION = Path('/data/ethereum-build-cache')
SOURCES = (Path('/home/adm-mesifi/.cache/go-build'), Path('/home/adm-mesifi/go/pkg/mod'))


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        while chunk := handle.read(4 * 1024**2):
            value.update(chunk)
    return value.hexdigest()


def relocate(source, target):
    if source.is_symlink():
        if source.resolve() != target.resolve():
            raise RuntimeError('Existing cache symlink has an unexpected destination')
        return {'source': str(source), 'target': str(target), 'already_relocated': True}
    if not source.is_dir():
        raise RuntimeError('Cache source is not a directory')
    if target.exists():
        raise RuntimeError('Destination occupied; inspect before retrying')
    entries = list(source.rglob('*'))
    size = sum(p.stat().st_size for p in entries if p.is_file() and not p.is_symlink())
    if shutil.disk_usage(target.parent).free < size + 40 * 1024**3:
        raise RuntimeError('Insufficient destination reserve')
    snapshot = {str(p.relative_to(source)): (p.lstat().st_size, p.lstat().st_mtime_ns) for p in entries}
    shutil.copytree(source, target, symlinks=True, copy_function=shutil.copy2)
    for path in entries:
        other = target / path.relative_to(source)
        if path.is_symlink():
            if os.readlink(path) != os.readlink(other):
                raise RuntimeError('Symlink mismatch')
        elif path.is_file() and digest(path) != digest(other):
            raise RuntimeError('Cache copy checksum mismatch')
    current = {str(p.relative_to(source)): (p.lstat().st_size, p.lstat().st_mtime_ns) for p in source.rglob('*')}
    if current != snapshot:
        raise RuntimeError('Cache changed during verification; original retained')
    for path in [source, *entries]:
        info = path.lstat()
        os.lchown(target / path.relative_to(source), info.st_uid, info.st_gid)
    owner = source.stat()
    backup = source.with_name(source.name + '.verified-cache-move')
    if backup.exists() or backup.is_symlink():
        raise RuntimeError('Backup path occupied')
    source.rename(backup)
    try:
        source.symlink_to(target, target_is_directory=True)
        os.lchown(source, owner.st_uid, owner.st_gid)
    except Exception:
        if source.is_symlink():
            source.unlink()
        backup.rename(source)
        raise
    # Only discard the redundant source copy after SHA-256 validation and cutover.
    def make_writable(function, path, exc):
        os.chmod(path, stat.S_IRWXU)
        function(path)
    shutil.rmtree(backup, onerror=make_writable)
    return {'source': str(source), 'target': str(target), 'verified_bytes': size,
            'all_regular_files_sha256_verified': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--include-module-cache', action='store_true')
    options = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('Run as root to preserve cache ownership')
    DESTINATION.mkdir(exist_ok=True)
    results = []
    pairs = list(zip(SOURCES, ('go-build', 'go-mod')))
    for source, name in (pairs if options.include_module_cache else pairs[:1]):
        result = relocate(source, DESTINATION / name)
        results.append(result)
        print(json.dumps(result), flush=True)
    report = {'observed_at': datetime.now(timezone.utc).isoformat(), 'results': results,
              'root_free_bytes': shutil.disk_usage('/').free}
    (DESTINATION / 'relocation-status.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
