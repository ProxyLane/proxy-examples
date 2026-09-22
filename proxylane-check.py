#!/usr/bin/env python3
"""Run bounded, local HTTP(S) and SOCKS5 proxy checks with curl."""

import argparse
import csv
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote_to_bytes, urlsplit


MAX_PROXIES = 100
MAX_FILE_BYTES = 64 * 1024
MAX_URL_LENGTH = 2048
MAX_BODY_BYTES = 64 * 1024
FIELDS = ("proxy_index", "status", "http_status", "proxy_connect_status", "connect_ms", "total_ms", "bytes", "body_match")
WRITE_OUT = "%{http_code}\t%{http_connect}\t%{time_connect}\t%{time_total}"


class InputError(Exception):
    pass


def validate_url(value, schemes, kind):
    if not value or len(value) > MAX_URL_LENGTH or any(ord(char) < 33 or ord(char) > 126 or char in {'"', "\\"} for char in value):
        raise InputError(f"invalid {kind} URL")
    if re.search(r"%(?![0-9a-fA-F]{2})", value):
        raise InputError(f"invalid {kind} URL")
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in schemes or not parsed.hostname:
            raise InputError(f"invalid {kind} URL")
        port = parsed.port
        if (kind == "proxy" and port is None) or (port is not None and not 1 <= port <= 65535):
            raise InputError(f"invalid {kind} URL")
        if kind == "proxy":
            if parsed.path not in ("", "/") or parsed.query or parsed.fragment or "%" in parsed.hostname:
                raise InputError("invalid proxy URL")
            userinfo = parsed.netloc.rsplit("@", 1)[0] if "@" in parsed.netloc else ""
            if any(byte < 32 or byte == 127 for byte in unquote_to_bytes(userinfo)):
                raise InputError("invalid proxy URL")
        elif parsed.username is not None or parsed.password is not None or parsed.fragment or parsed.netloc.endswith(":"):
            raise InputError("invalid target URL")
    except (ValueError, UnicodeError) as error:
        raise InputError(f"invalid {kind} URL") from error
    return value


def load_proxies(proxy_file):
    env_proxy = os.environ.get("PROXY_URL")
    if bool(proxy_file) == bool(env_proxy):
        raise InputError("provide exactly one of PROXY_URL or --proxy-file")
    if env_proxy:
        return [validate_url(env_proxy, {"http", "https", "socks5", "socks5h"}, "proxy")]

    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(proxy_file, flags)
        with os.fdopen(descriptor, "rb") as source:
            details = os.fstat(source.fileno())
            if not stat.S_ISREG(details.st_mode) or details.st_mode & 0o077:
                raise InputError("proxy file must be a private regular file (chmod 600)")
            raw = source.read(MAX_FILE_BYTES + 1)
    except (OSError, ValueError) as error:
        raise InputError("cannot read private proxy file") from error
    if len(raw) > MAX_FILE_BYTES:
        raise InputError("proxy file exceeds 64 KiB")
    if any(byte < 32 and byte not in (10, 13) for byte in raw) or b"\r" in raw.replace(b"\r\n", b""):
        raise InputError("proxy file contains control characters")
    try:
        lines = [line for line in raw.decode("ascii").splitlines() if line]
    except UnicodeError as error:
        raise InputError("proxy file must contain ASCII URLs") from error
    if not 1 <= len(lines) <= MAX_PROXIES:
        raise InputError("provide 1 to 100 proxy URLs")
    return [validate_url(line, {"http", "https", "socks5", "socks5h"}, "proxy") for line in lines]


def curl_config(proxy_url, target_url):
    # Inputs are printable ASCII without quotes, backslashes or line breaks.
    return f'proxy = "{proxy_url}"\nurl = "{target_url}"\n'


def require_curl():
    try:
        completed = subprocess.run(["curl", "--version"], capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise InputError("curl 8.4 or newer is required") from error
    version = re.match(r"curl (\d+)\.(\d+)\.(\d+)", completed.stdout)
    if completed.returncode or not version or tuple(map(int, version.groups())) < (8, 4, 0):
        raise InputError("curl 8.4 or newer is required for the response body limit")


def classify(return_code, http_status, proxy_connect_status, body_match):
    if proxy_connect_status == 407 or http_status == 407:
        return "proxy_auth_required"
    if return_code == 28:
        return "timeout"
    if return_code == 63:
        return "body_limit"
    if return_code in (35, 51, 58, 60, 77, 83):
        return "tls_error"
    if return_code in (5, 6, 7):
        return "connect_failed"
    if return_code:
        return "transfer_failed"
    if not 200 <= http_status < 300:
        return f"http_{http_status}" if http_status else "transfer_failed"
    return "ok" if body_match is not False else "body_mismatch"


def check_proxy(index, proxy_url, target_url, expected_body, connect_timeout, timeout):
    with tempfile.TemporaryDirectory(prefix="proxylane-check-") as temporary_dir:
        body_path = Path(temporary_dir) / "response"
        command = [
            "curl", "--disable", "--silent", "--globoff", "--noproxy", "",
            "--proto", "=http,https", "--connect-timeout", str(connect_timeout),
            "--max-time", str(timeout), "--max-filesize", str(MAX_BODY_BYTES),
            "--output", str(body_path), "--write-out", WRITE_OUT, "--config", "-",
        ]
        child_env = {key: value for key, value in os.environ.items() if key.upper() not in {
            "PROXY_URL", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"
        }}
        try:
            completed = subprocess.run(
                command, input=curl_config(proxy_url, target_url), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=timeout + 2, env=child_env, check=False,
            )
        except subprocess.TimeoutExpired:
            return dict(proxy_index=index, status="timeout", http_status=None, proxy_connect_status=None,
                        connect_ms=None, total_ms=None, bytes=0, body_match=None)
        except OSError as error:
            raise InputError("curl is unavailable") from error

        try:
            code, proxy_connect, connect, total = completed.stdout.strip().split("\t")
            http_status = int(code)
            proxy_connect_status = int(proxy_connect)
            connect_ms = round(float(connect) * 1000, 1)
            total_ms = round(float(total) * 1000, 1)
        except (ValueError, TypeError):
            http_status = proxy_connect_status = connect_ms = total_ms = None
        if body_path.exists():
            with body_path.open("rb") as response:
                body = response.read(MAX_BODY_BYTES + 1)
        else:
            body = b""
        if len(body) > MAX_BODY_BYTES:
            return dict(proxy_index=index, status="body_limit", http_status=http_status or None,
                        proxy_connect_status=proxy_connect_status or None, connect_ms=connect_ms,
                        total_ms=total_ms, bytes=len(body), body_match=None)
        byte_count = len(body)
        body_match = expected_body.encode("utf-8") in body if expected_body is not None and completed.returncode == 0 else None
        status = classify(completed.returncode, http_status or 0, proxy_connect_status or 0, body_match)
        return dict(proxy_index=index, status=status, http_status=http_status or None,
                    proxy_connect_status=proxy_connect_status or None, connect_ms=connect_ms,
                    total_ms=total_ms, bytes=byte_count, body_match=body_match)


def main():
    parser = argparse.ArgumentParser(description="Check your own proxies locally; credentials never appear in results")
    parser.add_argument("--proxy-file", help="private file with one proxy URL per line (maximum 100)")
    parser.add_argument("--target", default="https://example.com", help="HTTP(S) URL to request")
    parser.add_argument("--expect-body", help="UTF-8 text that must appear in the response")
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--connect-timeout", type=int, default=5, help="connect timeout in seconds (1-30)")
    parser.add_argument("--timeout", type=int, default=15, help="total timeout in seconds (1-60)")
    args = parser.parse_args()
    try:
        if not 1 <= args.connect_timeout <= 30 or not 1 <= args.timeout <= 60 or args.connect_timeout > args.timeout:
            raise InputError("timeouts must be 1-30 and 1-60 seconds, with connect <= total")
        if args.expect_body is not None and len(args.expect_body.encode("utf-8")) > 1024:
            raise InputError("expected body text exceeds 1 KiB")
        target = validate_url(args.target, {"http", "https"}, "target")
        proxies = load_proxies(args.proxy_file)
        require_curl()
        results = [check_proxy(index, proxy, target, args.expect_body, args.connect_timeout, args.timeout)
                   for index, proxy in enumerate(proxies, 1)]
    except InputError as error:
        print(f"proxy checker: {error}", file=sys.stderr)
        return 2
    if args.format == "csv":
        writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(results)
    else:
        json.dump({"results": results}, sys.stdout, separators=(",", ":"))
        sys.stdout.write("\n")
    return 0 if all(result["status"] == "ok" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
