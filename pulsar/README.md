# Pulsar

Native x86-64 Linux launchers for Steam's Space Engineers games, packaged from
the [Pulsar v2.4.3 release](https://github.com/SpaceGT/Pulsar/releases/tag/v2.4.3).
The package uses .NET 10 and patches the release's ELF executables and libraries
for NixOS. The source build requires game assemblies from a local installation
and Linux Steamworks binaries.

| Steam game | Pulsar variant | Installed command |
| --- | --- | --- |
| Space Engineers (244850) | Interim | `pulsar` |
| Space Engineers 2 (1133870) | Modern | `pulsar-se2` |

## NixOS

Once the subflake is published in nix-tools, add it to your flake inputs.

```nix
inputs.pulsar = {
  url = "github:Soziapath/nix-tools?dir=pulsar";
  inputs.nixpkgs.follows = "nixpkgs";
};
```

For an unpublished checkout, use `path:/absolute/path/to/nix-tools/pulsar` as
the input URL. Import the module where the enclosing flake's inputs are in scope.

```nix
{
  imports = [ inputs.pulsar.nixosModules.default ];
  programs.pulsar.enable = true;
}
```

The module installs both launchers using the host's Nixpkgs. Install the Linux
Steam client and enable graphics with a Vulkan-capable driver on the host. The
Pulsar launcher GUI uses X11 and works through XWayland on a Wayland desktop.

From a checkout of this subflake you can also build or try the package directly.

```sh
nix flake check path:.
nix build path:.#pulsar
nix run path:. -- -help
```

## Steam launch options

Install the game through the desktop Steam client. In its **Properties → General
→ Launch Options**, enter the line for your game.

**Space Engineers**

```text
/run/current-system/sw/bin/pulsar %command%
```

**Space Engineers 2**

```text
/run/current-system/sw/bin/pulsar-se2 %command%
```

Place the Pulsar command before `%command%`. Pulsar treats the original Steam
command as arguments for game discovery and starts the game in its own Linux
process. It can also find installations in Steam's `libraryfolders.vdf`
under `~/.steam/steam`, `~/.steam/root` or `~/.local/share/Steam`.

If discovery fails, pass the absolute game directory, including `Bin64` for
Space Engineers or `Game2` for Space Engineers 2. For example, with a Steam
library on a separate drive:

```text
/run/current-system/sw/bin/pulsar -bin64 "/mnt/games/SteamLibrary/steamapps/common/SpaceEngineers/Bin64" %command%
```

For Space Engineers 2 use `-game2 "/path/to/SpaceEngineers2/Game2"`. Both
commands can also be run from a terminal with Steam running.

## Updates and user data

The launchers pass `-noUpdate` to disable the Pulsar self-updater and `-useHome`
to keep Pulsar's settings, profiles, logs, plugin downloads and preloader cache
under `${XDG_CONFIG_HOME:-$HOME/.config}/Pulsar/Interim` or
`${XDG_CONFIG_HOME:-$HOME/.config}/Pulsar/Modern`. To migrate an existing
portable installation, copy its per-game data into the corresponding directory.

Pulsar downloads applicable compatibility plugins through its normal plugin
mechanism. Those plugins and the Steam-managed game files follow their own
updates, so game build compatibility depends on the corresponding
[Space Engineers 1](https://github.com/CometWorks/linux-compat) or
[Space Engineers 2](https://github.com/CometWorks/linux-compat2) compatibility
plugin. To update the packaged launcher after publication, update the
`pulsar` flake input and rebuild NixOS.
