{
  lib,
  stdenv,
  fetchurl,
  autoPatchelfHook,
  makeWrapper,
  coreutils,
  dotnetCorePackages,
  alsa-lib,
  fontconfig,
  libglvnd,
  libice,
  pulseaudio,
  libsm,
  libx11,
  libxext,
  libxkbcommon,
  openal,
  opus,
  pipewire,
  vulkan-loader,
  wayland,
}:

let
  # Avalonia, Steam and the compatibility plugins load these at runtime.
  runtimeLibraries = [
    alsa-lib
    fontconfig
    libglvnd
    libice
    pulseaudio
    libsm
    libx11
    libxext
    libxkbcommon
    openal
    opus
    pipewire
    stdenv.cc.cc.lib
    vulkan-loader
    wayland
  ];
in
stdenv.mkDerivation (finalAttrs: {
  pname = "pulsar";
  version = "2.4.3";

  src = fetchurl {
    url = "https://github.com/SpaceGT/Pulsar/releases/download/v${finalAttrs.version}/pulsar-v${finalAttrs.version}-linux-x64.tar.gz";
    hash = "sha256-g8cD1gbzgaKP5tdACIrT42jP9DjbjX5I1WFC/NAsYc8=";
  };
  sourceRoot = ".";

  nativeBuildInputs = [
    autoPatchelfHook
    makeWrapper
  ];
  buildInputs = [
    fontconfig
    stdenv.cc.cc.lib
  ];

  installPhase = ''
    runHook preInstall

    payload="$out/libexec/pulsar"
    mkdir -p "$payload" "$out/bin"
    cp -r Interim.* Modern.* Libraries "$payload/"
    install -Dm644 LICENSE "$out/share/doc/pulsar/LICENSE"

    wrapLauncher() {
      local variant="$1" command="$2"
      makeWrapper "$payload/$variant.bin" "$out/bin/$command" \
        --set DOTNET_ROOT_X64 "${dotnetCorePackages.runtime_10_0}/share/dotnet" \
        --prefix LD_LIBRARY_PATH : "${lib.makeLibraryPath runtimeLibraries}:/run/opengl-driver/lib" \
        --run 'case ''${XDG_CONFIG_HOME:-} in /*) ;; *) export XDG_CONFIG_HOME="$HOME/.config";; esac' \
        --run '${coreutils}/bin/mkdir -p -- "$XDG_CONFIG_HOME/Pulsar/'"$variant"'" || exit 1' \
        --add-flags '-noUpdate -useHome'
    }

    wrapLauncher Interim pulsar
    wrapLauncher Modern pulsar-se2

    runHook postInstall
  '';

  doInstallCheck = true;
  installCheckPhase = ''
    runHook preInstallCheck

    export XDG_CONFIG_HOME="$TMPDIR/pulsar-config"
    test "$("$out/bin/pulsar" -version)" = "Pulsar v${finalAttrs.version}"
    test "$("$out/bin/pulsar-se2" -version)" = "Pulsar v${finalAttrs.version}"
    test -d "$XDG_CONFIG_HOME/Pulsar/Interim"
    test -d "$XDG_CONFIG_HOME/Pulsar/Modern"

    DOTNET_ROOT_X64="${dotnetCorePackages.runtime_10_0}/share/dotnet" \
      "$out/libexec/pulsar/Libraries/Compiler/Compiler.bin" </dev/null

    runHook postInstallCheck
  '';

  meta = {
    description = "Native Linux launcher and plugin loader for Space Engineers 1 and 2";
    homepage = "https://github.com/SpaceGT/Pulsar";
    license = lib.licenses.mit;
    mainProgram = "pulsar";
    platforms = [ "x86_64-linux" ];
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
})
