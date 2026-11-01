"""Create a bounded emergency swap reserve, refusing to overwrite unknown files."""
import os
import shutil
import stat
import subprocess
from pathlib import Path

SWAP = Path('/var/lib/erigon_swap')
SIZE = 4 * 1024**3


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Run as root')
    if SWAP.is_symlink():
        raise RuntimeError('Refusing a symlink swap target')
    if SWAP.exists():
        info = SWAP.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size != SIZE:
            raise RuntimeError('Existing target has unexpected type or size')
        kind = subprocess.check_output(
            ['blkid', '-p', '-s', 'TYPE', '-o', 'value', str(SWAP)], text=True
        ).strip()
        if kind != 'swap':
            raise RuntimeError('Existing file is not initialized swap; refusing to overwrite')
    else:
        if shutil.disk_usage(SWAP.parent).free < SIZE + 18 * 1024**3:
            raise RuntimeError('Insufficient space for swap plus 18 GiB disk reserve')
        fd = os.open(SWAP, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        subprocess.run(['fallocate', '-l', str(SIZE), str(SWAP)], check=True)
        subprocess.run(['mkswap', str(SWAP)], check=True)
    SWAP.chmod(0o600)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', '--now', 'var-lib-erigon_swap.swap'], check=True)
    subprocess.run(['swapon', '--show', '--bytes'], check=True)


if __name__ == '__main__':
    main()
