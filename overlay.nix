final: prev:
prev.lib.optionalAttrs (prev.stdenv.hostPlatform.system == "x86_64-linux") {
  velocidrone = final.callPackage ./pkgs/velocidrone { };
}
