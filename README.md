# nixos-updater

System tray app that notifies you when your NixOS flake has a new revision and lets you apply it with one click.

Built with PyQt6. Targets KDE Plasma but works on any desktop with an SNI-compatible tray.

## Usage

Add to your flake inputs:

```nix
nixos-updater = {
  url = "github:anders130/nixos-updater";
  inputs.nixpkgs.follows = "nixpkgs";
};
```

Apply the overlay so `pkgs.nixos-updater` is available:

```nix
nixpkgs.overlays = [inputs.nixos-updater.overlays.default];
```

Import the home-manager module and enable it:

```nix
imports = [inputs.nixos-updater.homeManagerModules.nixos-updater];

services.nixosUpdater = {
  enable = true;
  flakeUrl = "github:you/nixos-config";
};
```

Set the configuration revision in your NixOS configuration (where `self`
is your config flake) so the updater knows which revision is running:

```nix
system.configurationRevision = self.rev or self.dirtyRev or null;
```

## How updates are detected

The updater compares the flake's latest revision with
`nixos-version --configuration-revision`, i.e. the revision
`/run/current-system` was built from. This stays correct for hosts
deployed by other means (e.g. `nixos-rebuild --target-host`).

If the running revision is unknown (`system.configurationRevision` unset,
or a `-dirty` build), it falls back to the last revision applied through
the updater (`~/.local/share/nixos-updater/applied-rev`). If that is
missing too, an update is reported. A revision you chose to skip is not
offered again.

## Options

| Option     | Type   | Description                |
| ---------- | ------ | -------------------------- |
| `enable`   | bool   | Enable the service         |
| `flakeUrl` | string | Flake to watch for updates |

## Binary caches

nixos-updater runs `nixos-rebuild` directly, which inherits the Nix
daemon's configuration. Configure private caches in your NixOS config
and they will be used automatically during updates:

```nix
nix.settings = {
  substituters = ["https://you.cachix.org"];
  trusted-public-keys = ["you.cachix.org-1:abc123..."];
};
```

## Development

```bash
nix develop
nix build
PYTHONPATH=src python -m unittest discover -s tests
```

To test the UI without waiting for a real update:

```bash
NIXOS_UPDATER_FLAKE_URL="github:NixOS/nixpkgs/nixos-unstable" \
NIXOS_UPDATER_HOSTNAME="test" \
./result/bin/nixos-updater &
```
