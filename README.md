# nix-tools

Personal Nix packages and launchers. The flake starts with VelociDrone on
x86-64 Linux.

## VelociDrone

From a checkout, install the desktop entry in your user profile or run it once.

```sh
nix profile add .#velocidrone
nix run .#velocidrone
```

Open **VelociDrone** from the application menu. Sign in to your VelociDrone
account and download the Linux launcher ZIP, then select it with **Choose ZIP**.
The wrapper imports the archive into the local Nix store. The official launcher
downloads and updates the simulator in the writable directory
`${XDG_DATA_HOME:-$HOME/.local/share}/velocidrone/game`. The game requires a
VelociDrone account and license.

To reuse an existing installation, or set up a previously downloaded ZIP from a
terminal, use one of these commands.

```sh
nix run .#velocidrone -- --use-existing /path/to/Velocidrone
nix run .#velocidrone -- --setup-zip /path/to/production-launcher-debian.zip
```

## Use in a NixOS configuration

Add the flake as an input. In a NixOS module, use its package from the flake's
pinned Nixpkgs.

```nix
{ pkgs, ... }:
{
  environment.systemPackages = [
    inputs.nix-tools.packages.${pkgs.stdenv.hostPlatform.system}.velocidrone
  ];
}
```

Here `inputs` refers to the enclosing configuration flake's inputs, passed into
scope when defining its modules. The flake also exports `overlays.default` to
build against your own Nixpkgs. If you use the overlay, allow
`steam-unwrapped` in your Nixpkgs unfree predicate for VelociDrone's Steam runtime.

## Add a package

1. Put a package expression and any local source files under `pkgs/<name>/`.
2. Register it with `callPackage` in `overlay.nix`, then export it in `flake.nix`.
3. Set `meta.mainProgram` to expose its executable through `nix run`.
4. Run `nix flake check` before committing.

## LUKS Unlock

The [LUKS Unlock subflake](luks-unlock/) packages a terminal UI and a Noctalia v5 plugin.

```sh
nix run 'github:Soziapath/nix-tools?dir=luks-unlock#tui' -- proxmox.example.test
```

## Pulsar

The [Pulsar subflake](pulsar/) packages the native Linux launchers for Space
Engineers 1 and 2 and exports a NixOS module. See its README for Steam launch
options.
