{
  description = "Personal Nix packages and tools";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs =
    { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        overlays = [ self.overlays.default ];
        config.allowUnfreePredicate = pkg: nixpkgs.lib.getName pkg == "steam-unwrapped";
      };
      packages = {
        inherit (pkgs) velocidrone;
      };
    in
    {
      overlays.default = import ./overlay.nix;
      packages.${system} = packages;
      apps.${system} = nixpkgs.lib.mapAttrs (_: package: {
        type = "app";
        program = nixpkgs.lib.getExe package;
        meta.description = package.meta.description;
      }) (nixpkgs.lib.filterAttrs (_: package: package.meta ? mainProgram) packages);
      checks.${system} = packages;
      formatter.${system} = pkgs.nixfmt;
    };
}
