import json
import subprocess

from ..domain.models import KernelVersion, Revision
from ..domain.ports import FlakeSource, KernelInspector


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
