"""Deploy an authenticated TLS proxy without restarting Erigon."""
import json
import secrets
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import vps_ssh as watch_sync


def main():
    config = watch_sync.load_env(watch_sync.ENV_PATH)
    access_file = ROOT / "rpc-access.secret"
    if access_file.exists():
        access = json.loads(access_file.read_text(encoding="utf-8"))
    else:
        access = {"host": config["host"], "port": 9443,
                  "user": "etudiant", "password": secrets.token_urlsafe(32)}
        access_file.write_text(json.dumps(access, indent=2), encoding="utf-8")
    client = watch_sync.connect(config)
    try:
        stdin, stdout, stderr = client.exec_command("openssl passwd -6 -stdin", timeout=20)
        stdin.write(access["password"] + "\n")
        stdin.flush()
        stdin.channel.shutdown_write()
        hashed = stdout.read().decode().strip()
        if stdout.channel.recv_exit_status() or not hashed.startswith("$6$"):
            raise RuntimeError("Could not hash RPC password")
        with client.open_sftp() as sftp:
            sftp.put(str(ROOT / "configs/ethereum-rpc.nginx.conf"), "/tmp/ethereum-rpc.nginx.conf")
            with sftp.open("/tmp/ethereum-rpc.htpasswd", "w") as handle:
                handle.write(access["user"] + ":" + hashed + "\n")
            sftp.chmod("/tmp/ethereum-rpc.htpasswd", 0o600)
        subject = shlex.quote("/CN=" + access["host"])
        alternative = shlex.quote("subjectAltName=DNS:" + access["host"])
        command = f"""set -e
sudo -n install -d -m 750 -o root -g www-data /etc/nginx/ethereum-rpc
sudo -n install -m 640 -o root -g www-data /tmp/ethereum-rpc.htpasswd /etc/nginx/ethereum-rpc/htpasswd
if ! sudo -n test -s /etc/nginx/ethereum-rpc/tls.key; then
 sudo -n openssl req -x509 -newkey rsa:2048 -nodes -days 7 -keyout /etc/nginx/ethereum-rpc/tls.key -out /etc/nginx/ethereum-rpc/tls.crt -subj {subject} -addext {alternative} 2>/dev/null
 sudo -n chmod 600 /etc/nginx/ethereum-rpc/tls.key
fi
sudo -n install -m 644 /tmp/ethereum-rpc.nginx.conf /etc/nginx/conf.d/ethereum-rpc.conf
sudo -n nginx -t
sudo -n systemctl enable nginx
sudo -n systemctl reload-or-restart nginx
sudo -n cat /etc/nginx/ethereum-rpc/tls.crt
"""
        code, output, error = watch_sync.run_remote(client, command)
        if code:
            raise RuntimeError(error)
        start = output.index("-----BEGIN CERTIFICATE-----")
        (ROOT / "configs/rpc-tls.crt").write_text(output[start:], encoding="ascii")
        print("TLS RPC proxy deployed; credentials in rpc-access.secret (excluded from git).")
        print("Public certificate saved to configs/rpc-tls.crt; trust it explicitly for testing.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
