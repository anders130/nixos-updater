import json
import os
import subprocess

from ..domain.models import KernelVersion, Revision
from ..domain.ports import FlakeSource, KernelInspector, SystemDiffer


def _cache_env_args() -> list[str]:
    args = []
    for entry in os.environ.get("NIXOS_UPDATER_CACHES", "").split(";"):
        parts = entry.split("|", 1)
        if len(parts) == 2 and parts[0].strip():
            args += ["--substituters", parts[0].strip(), "--trusted-public-keys", parts[1].strip()]
    return args


class NixFlakeSource(FlakeSource):
    def __init__(self, flake_url: str) -> None:
        self._url = flake_url

    def fetch_revision(self) -> Revision | None:
        try:
            result = subprocess.run(
                ["nix", "flake", "metadata", "--refresh", "--json", self._url],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                rev = json.loads(result.stdout).get("revision")
                if rev:
                    return Revision(rev)
        except Exception:
            pass
        return None


class NixKernelInspector(KernelInspector):
    def __init__(self, flake_url: str, hostname: str) -> None:
        self._url = flake_url
        self._hostname = hostname

    def running_version(self) -> KernelVersion | None:
        try:
            result = subprocess.run(["uname", "-r"], capture_output=True, text=True)
            if result.returncode == 0:
                # e.g. "6.6.30-zen1-1-zen" → "6.6.30"
                return KernelVersion(result.stdout.strip().split("-")[0])
        except Exception:
            pass
        return None

    def upstream_version(self) -> KernelVersion | None:
        try:
            attr = (
                f"{self._url}#nixosConfigurations.{self._hostname}"
                ".config.boot.kernelPackages.kernel.version"
            )
            result = subprocess.run(
                ["nix", "eval", "--raw", attr],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                return KernelVersion(result.stdout.strip())
        except Exception:
            pass
        return None


class NixSystemDiffer(SystemDiffer):
    def __init__(self, flake_url: str, hostname: str) -> None:
        self._url = flake_url
        self._hostname = hostname

    def diff(self) -> str | None:
        try:
            attr = f"{self._url}#nixosConfigurations.{self._hostname}.config.system.build.toplevel"
            build = subprocess.run(
                ["nix", "build", "--no-link", "--print-out-paths", attr]
                + _cache_env_args(),
                capture_output=True,
                text=True,
                timeout=600,
            )
            if build.returncode != 0:
                return None
            new_path = build.stdout.strip().splitlines()[-1]
            diff = subprocess.run(
                ["nix", "store", "diff-closures", "/run/current-system", new_path],
                capture_output=True,
                text=True,
                timeout=60,
            )
            return diff.stdout if diff.returncode == 0 else None
        except Exception:
            return None
