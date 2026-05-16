{
    description = "NixOS system updater tray application";

    inputs = {
        nixpkgs.url = "nixpkgs/nixos-unstable";
        flake-parts = {
            url = "github:hercules-ci/flake-parts";
            inputs.nixpkgs-lib.follows = "nixpkgs";
        };
        nix-lib = {
            url = "github:anders130/nix-lib";
            inputs.flake-parts.follows = "flake-parts";
        };
    };

    outputs = inputs:
        inputs.nix-lib.lib.mkFlakeFromTree {
            inherit inputs;
            root = ./.;
        };
}
