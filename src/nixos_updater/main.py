import os
import sys
from pathlib import Path

from .application.services import (
    ChangelogService,
    KernelCheckService,
    UpdateCheckService,
)
from .infrastructure.file_store import FileRevisionStore
from .infrastructure.nix_cli import NixFlakeSource, NixKernelInspector, NixSystemDiffer
from .presentation.tray import NixOSUpdaterApp


def main() -> None:
    flake_url = os.environ.get("NIXOS_UPDATER_FLAKE_URL", "")
    hostname = os.environ.get("NIXOS_UPDATER_HOSTNAME", "")

    if not flake_url:
        print("Error: NIXOS_UPDATER_FLAKE_URL is not set", file=sys.stderr)
        sys.exit(1)
    if not hostname:
        print("Error: NIXOS_UPDATER_HOSTNAME is not set", file=sys.stderr)
        sys.exit(1)

    data_dir = Path.home() / ".local" / "share" / "nixos-updater"
    store = FileRevisionStore(data_dir)
    source = NixFlakeSource(flake_url)
    inspector = NixKernelInspector(flake_url, hostname)
    differ = NixSystemDiffer(flake_url, hostname)

    update_service = UpdateCheckService(store, source)
    kernel_service = KernelCheckService(inspector)
    changelog_service = ChangelogService(differ)

    app = NixOSUpdaterApp(
        sys.argv, flake_url, update_service, kernel_service, changelog_service
    )
    sys.exit(app.exec())
