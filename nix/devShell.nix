{pyproject, ...}: {
    perSystem = {
        pkgs,
        self',
        ...
    }: let
        devDeps = with pkgs; [black isort];
    in {
        devShells.default = pkgs.mkShell {
            inputsFrom = [self'.packages.nixos-updater];
            buildInputs = devDeps;
            shellHook = ''
                install -m644 ${pkgs.writers.writeTOML "pyproject.toml" pyproject} pyproject.toml
                install -m644 ${pkgs.writers.writeText "__init__.py" "__version__ = \"${pyproject.project.version}\""} src/nixos_updater/__init__.py
            '';
        };

        formatter = pkgs.writeShellApplication {
            name = "format";
            runtimeInputs = devDeps;
            text = ''
                black src/
                isort src/ --profile black
            '';
        };
    };
}
