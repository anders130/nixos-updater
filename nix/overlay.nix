{self, ...}: {
    flake.overlays.default = final: prev: {
        nixos-updater = self.packages.${prev.stdenv.hostPlatform.system}.nixos-updater;
    };
}
