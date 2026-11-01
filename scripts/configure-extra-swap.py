"""Add a second bounded swap file without stopping Erigon."""
import os
import shutil
import stat
import subprocess
from pathlib import Path


SWAP = Path('/var/lib/erigon_swap_extra')
UNIT = 'var-lib-erigon_swap_extra.swap'
SIZE = 4 * 1024**3
RESERVE = 20 * 1024**3


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
        if shutil.disk_usage(SWAP.parent).free < SIZE + RESERVE:
            raise RuntimeError('Insufficient space for swap plus 20 GiB disk reserve')
        fd = os.open(SWAP, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        subprocess.run(['fallocate', '-l', str(SIZE), str(SWAP)], check=True)
        subprocess.run(['mkswap', str(SWAP)], check=True)
    SWAP.chmod(0o600)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', '--now', UNIT], check=True)
    active = subprocess.check_output(['systemctl', 'is-active', UNIT], text=True).strip()
    if active != 'active':
        raise RuntimeError(f'{UNIT} is not active')
    print(subprocess.check_output(['swapon', '--show', '--bytes'], text=True))


if __name__ == '__main__':
    main()
