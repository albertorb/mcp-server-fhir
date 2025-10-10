#!/usr/bin/env python3
"""Generate RSA keys and JWKS artefacts for Epic FHIR authentication."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence

PRIVATE_KEY_PATH = Path("private_key.pem")
PUBLIC_KEY_PATH = Path("public_key.pem")
CERTIFICATE_PATH = Path("certificate.pem")
JWKS_PATH = Path("jwks.json")
DOTENV_PATH = Path(".env")
DOTENV_TEMPLATE_PATH = Path(".env.example")
KID_VALUE = "epic-fhir-key-1"


class CommandError(RuntimeError):
    """Raised when an external command fails."""


def run_command(command: Sequence[str], description: str) -> None:
    """Run a shell command and raise an informative error when it fails."""
    print(f"{description}...")
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise SystemExit(f"Required command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or ""
        stdout = exc.stdout or ""
        details = "\n".join(filter(None, [stdout.strip(), stderr.strip()]))
        message = f"{description} failed with exit code {exc.returncode}"
        if details:
            message = f"{message}:\n{details}"
        raise SystemExit(message) from exc


def ask_overwrite(path: Path) -> bool:
    """Return True when the user confirms overwriting an existing file."""
    response = input(f"{path} already exists. Overwrite? [y/N]: ").strip().lower()
    return response == "y"


def generate_rsa_keys(force: bool) -> None:
    """Generate private key, public key, and certificate using OpenSSL."""
    if PRIVATE_KEY_PATH.exists() and not force:
        if not ask_overwrite(PRIVATE_KEY_PATH):
            print("Skipping key generation.")
            return

    run_command(["openssl", "genrsa", "-out", str(PRIVATE_KEY_PATH), "2048"], "Generating RSA private key")

    run_command(
        ["openssl", "rsa", "-in", str(PRIVATE_KEY_PATH), "-pubout", "-out", str(PUBLIC_KEY_PATH)],
        "Exporting public key",
    )

    run_command(
        [
            "openssl",
            "req",
            "-new",
            "-x509",
            "-key",
            str(PRIVATE_KEY_PATH),
            "-out",
            str(CERTIFICATE_PATH),
            "-days",
            "365",
            "-subj",
            "/CN=Epic FHIR MCP Server",
        ],
        "Creating X.509 certificate",
    )


def create_jwks() -> None:
    """Generate a JWKS file based on the previously created certificate."""
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: cryptography. Install it with 'pip install cryptography'."
        ) from exc

    if not CERTIFICATE_PATH.exists():
        raise SystemExit("certificate.pem was not found. Run key generation first.")

    cert_data = CERTIFICATE_PATH.read_bytes()
    cert = x509.load_pem_x509_certificate(cert_data, default_backend())
    public_key = cert.public_key()
    numbers = public_key.public_numbers()

    modulus = base64.urlsafe_b64encode(
        numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")
    ).decode().rstrip("=")
    exponent = base64.urlsafe_b64encode(
        numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")
    ).decode().rstrip("=")

    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS384",
        "n": modulus,
        "e": exponent,
        "kid": KID_VALUE,
    }

    JWKS_PATH.write_text(json.dumps({"keys": [jwk]}, indent=2) + "\n")
    print(f"Created {JWKS_PATH}.")


def create_env_file() -> None:
    """Copy .env.example to .env if the target file does not already exist."""
    if DOTENV_PATH.exists():
        print(".env already exists. Skipping environment file creation.")
        return

    if not DOTENV_TEMPLATE_PATH.exists():
        print(".env.example not found. Skipping environment file creation.")
        return

    DOTENV_PATH.write_text(DOTENV_TEMPLATE_PATH.read_text())
    print("Created .env from .env.example.")


def print_next_steps() -> None:
    """Display follow-up actions for the user."""
    print()
    print("Next steps:")
    print("1. Host jwks.json publicly (GitHub Gist or HTTPS endpoint).")
    print("2. Add the JWKS URL to your Epic backend systems app and validate it.")
    print("3. Wait up to 30 minutes for Epic to propagate configuration changes.")
    print("4. Update .env with your Epic client credentials.")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate RSA keys and JWKS artefacts.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing key files without prompting.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])

    print("Epic FHIR key generation utility\n")

    generate_rsa_keys(force=args.force)
    create_jwks()
    create_env_file()
    print_next_steps()

    print()
    print("Setup complete.")


if __name__ == "__main__":
    main()
