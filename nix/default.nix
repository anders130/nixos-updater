{...}: {
    _module.args.pyproject = {
        build-system = {
            requires = ["hatchling"];
            build-backend = "hatchling.build";
        };
        project = {
            name = "nixos-updater";
            version = "0.1.0";
            requires-python = ">=3.11";
            dependencies = [];
            scripts."nixos-updater" = "nixos_updater.main:main";
        };
        tool.hatch.build.targets.wheel.packages = ["src/nixos_updater"];
    };
}
