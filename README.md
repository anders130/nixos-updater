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

## Options

| Option     | Type   | Description                   |
| ---------- | ------ | ----------------------------- |
| `enable`   | bool   | Enable the service            |
| `flakeUrl` | string | Flake to watch for updates    |

## Development

```bash
nix develop
nix build
```

To test the UI without waiting for a real update:

```bash
echo "0000000000000000000000000000000000000000" > ~/.local/share/nixos-updater/applied-rev
NIXOS_UPDATER_FLAKE_URL="github:NixOS/nixpkgs/nixos-unstable" \
NIXOS_UPDATER_HOSTNAME="test" \
./result/bin/nixos-updater &
```
