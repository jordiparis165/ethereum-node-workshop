"""SSH helpers; keep credentials local and accept the existing btc/.env file."""
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env" if (ROOT / ".env").exists() else ROOT.parent / "btc/.env"


def load_env(path):
    lines = [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    fields = {}
    for line in lines:
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key.strip()] = value.strip().strip('"').strip("'")
    if "VPS_HOST" in fields or "HOST" in fields:
        config = {"host": fields.get("VPS_HOST", fields.get("HOST", "")),
                  "user": fields.get("VPS_USER", fields.get("USER", "")),
                  "password": fields.get("VPS_PASSWORD", fields.get("PASSWORD", ""))}
    elif len(lines) >= 4:
        config = dict(zip(("host", "user", "password"), lines[1:4]))
    else:
        raise ValueError("Expected VPS_HOST, VPS_USER and VPS_PASSWORD in the local .env")
    if not all(config.values()):
        raise ValueError("Missing SSH connection fields in the local .env")
    return config


def connect(config):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=config["host"], username=config["user"], password=config["password"],
                   timeout=20, banner_timeout=20, auth_timeout=20)
    return client


def run_remote(client, command):
    stdin, stdout, stderr = client.exec_command(command, timeout=30)
    stdin.close()
    output = stdout.read().decode("utf-8", errors="replace")
    error = stderr.read().decode("utf-8", errors="replace")
    return stdout.channel.recv_exit_status(), output, error
