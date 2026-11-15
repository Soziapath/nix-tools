{
  description = "Pulsar native Linux launcher for Space Engineers";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs =
    { nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      pulsar = pkgs.callPackage ./package.nix { };
    in
    {
      packages.${system} = {
        default = pulsar;
        inherit pulsar;
      };
      checks.${system} = { inherit pulsar; };
      formatter.${system} = pkgs.nixfmt;

      nixosModules.default =
        {
          config,
          lib,
          pkgs,
          ...
        }:
        {
          options.programs.pulsar.enable = lib.mkEnableOption "the Pulsar launcher for Space Engineers";

          config = lib.mkIf config.programs.pulsar.enable {
            environment.systemPackages = [ (pkgs.callPackage ./package.nix { }) ];
          };
        };
    };
}
