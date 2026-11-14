{
  description = "Interactive SSH helper for unlocking a LUKS-encrypted server";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      eachSystem = nixpkgs.lib.genAttrs systems;
    in {
      packages = eachSystem (system:
        let pkgs = nixpkgs.legacyPackages.${system}; in rec {
          default = tui;
          tui = pkgs.callPackage ./package.nix { };
          noctalia-plugin = pkgs.callPackage ./plugin.nix { };
          noctalia-source = pkgs.linkFarm "noctalia-luks-unlock-source" [
            { name = "luks-unlock"; path = noctalia-plugin; }
          ];
        });

      devShells = eachSystem (system: {
        default = let pkgs = nixpkgs.legacyPackages.${system}; in pkgs.mkShell {
          packages = [ pkgs.python3 pkgs.openssh pkgs.luau ];
        };
      });
    };
}
