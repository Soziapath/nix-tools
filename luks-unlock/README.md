# LUKS Unlock

Unlock a remote Linux system that exposes `cryptroot-unlock` over initramfs
SSH. The terminal UI runs OpenSSH interactively. The Noctalia v5 plugin adds
a bar indicator and a masked passphrase field.

## Terminal UI

```sh
nix run 'github:Soziapath/nix-tools?dir=luks-unlock#tui' -- proxmox.example.test -p 2222 -i ~/.ssh/luks-unlock
```

From a local checkout, use `nix run path:.#tui -- proxmox.example.test`.
Provide a host or use `--host-file` to read it from a local file. The plugin
accepts the same file via its `host_file` setting. Port, identity and user default to `2222`,
`~/.ssh/luks-unlock` and `root`. The TUI waits for an SSH banner, then hands
the terminal to OpenSSH for verification and passphrase entry. Ctrl+C cancels.
`--check --json` probes once without a terminal or key. Exit 0 indicates an
SSH banner and exit 1 indicates that the endpoint is unavailable.

## Noctalia v5

The flake exposes `packages.<system>.noctalia-plugin` (a packaged plugin
directory) and `packages.<system>.noctalia-source` (a ready-to-use Noctalia
path source containing the plugin). The manifest points to the packaged helper
in the Nix store. Tested against Noctalia 5.1.0, using plugin API 24.

To collect this plugin alongside others, add this `flake.nix` to a separate
Git repository. The example uses the public tools repository.

```nix
{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.luks-unlock.url = "github:Soziapath/nix-tools?dir=luks-unlock";
  inputs.luks-unlock.inputs.nixpkgs.follows = "nixpkgs";

  outputs = { nixpkgs, luks-unlock, ... }: {
    packages = nixpkgs.lib.genAttrs [ "x86_64-linux" "aarch64-linux" ] (system: {
      default = nixpkgs.legacyPackages.${system}.linkFarm "noctalia-plugins" [
        {
          name = "luks-unlock";
          path = luks-unlock.packages.${system}.noctalia-plugin;
        }
        # Add other packaged plugin directories here.
      ];
    });
  };
}
```

Add the collector as `inputs.my-plugins.url = "github:OWNER/my-noctalia-plugins";`
in your NixOS flake. In the module that sets up Noctalia, merge these entries
into your existing settings. Pass `inputs` through your module arguments.

```nix
{ inputs, pkgs, ... }:
{
  programs.noctalia.settings = {
    plugins.source = [{
      name = "my-plugins";
      kind = "path";
      location = toString inputs.my-plugins.packages.${pkgs.stdenv.hostPlatform.system}.default;
      enabled = true;
    }];
    plugins.enabled = [ "soziapath/luks-unlock" ];

    bar.main.end = [ "luks-unlock" ];
    widget.luks-unlock.type = "soziapath/luks-unlock:bar";
    plugin_settings."soziapath/luks-unlock" = {
      host = "proxmox.example.test";
      port = 2222;
      identity = "~/.ssh/luks-unlock";
    };
  };
}
```

For a single-plugin setup, use this flake's `noctalia-source` package directly
as the path source. Both setups use Git for the flake input and a Nix store path
for Noctalia's plugin source. The bar widget is clickable once configured.
Right-click refreshes the probe.

## Passphrase handling

The panel waits for the remote `Please unlock disk …:` prompt before showing
the masked field. Its helper binds to loopback and authenticates each request
with a random per-session token. Passphrases travel in request bodies and then
to the SSH terminal. They are kept out of command arguments, logs and files.

The panel refuses to start when a proxy environment variable is set unless
`no_proxy` (or `NO_PROXY` when lowercase is unset or empty) contains the exact
comma-separated entry `127.0.0.1` or is `*`. Set that exclusion in **Noctalia's
launch environment** and restart it if needed. Requests disable redirects.
The panel requires a previously trusted SSH host key and an SSH identity usable
noninteractively. Load encrypted keys into your SSH agent first.

The Noctalia watcher verifies the trusted SSH host and looks for the disk
passphrase prompt before showing availability or notifying. It closes each
probe without sending input. A notification is rearmed after three consecutive
checks without a prompt. The TUI and plain `--check` still use an SSH banner
as their reachability check.

## Development

```sh
nix develop path:. -c python3 -m unittest -v
nix build path:.#tui path:.#noctalia-source
```

This directory is a standalone flake within nix-tools.
Keep machine-specific settings, SSH keys and passphrases in local configuration.
