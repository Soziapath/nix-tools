{ callPackage, runCommand }:
let
  cli = callPackage ./package.nix { };
in runCommand "noctalia-luks-unlock" { } ''
  mkdir -p "$out"
  cp -r ${./noctalia-plugin}/. "$out/"
  chmod -R u+w "$out"
  substituteInPlace "$out/plugin.toml" \
    --replace-fail '@LUKS_UNLOCK@' '${cli}/bin/luks-unlock'
''
