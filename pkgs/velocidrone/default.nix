{
  coreutils,
  findutils,
  nix,
  steam-run,
  unzip,
  util-linux,
  xdg-user-dirs,
  xdg-utils,
  zenity,
  writeShellApplication,
  makeDesktopItem,
  symlinkJoin,
}:

let
  launcher = writeShellApplication {
    name = "velocidrone";
    runtimeInputs = [
      coreutils
      findutils
      nix
      steam-run
      unzip
      util-linux
      xdg-user-dirs
      xdg-utils
      zenity
    ];
    text = builtins.readFile ./velocidrone.sh;
  };

  desktopItem = makeDesktopItem {
    name = "velocidrone";
    desktopName = "VelociDrone";
    comment = "FPV drone simulator";
    exec = "${launcher}/bin/velocidrone";
    icon = "applications-games";
    categories = [
      "Game"
      "Simulation"
    ];
    terminal = false;
  };
in
symlinkJoin {
  name = "velocidrone";
  paths = [
    launcher
    desktopItem
  ];
  meta = {
    description = "Set up or launch VelociDrone";
    homepage = "https://velocidrone.com/";
    mainProgram = "velocidrone";
    platforms = [ "x86_64-linux" ];
  };
}
