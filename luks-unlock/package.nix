{ lib, writeShellApplication, python3, openssh }:
let source = builtins.path { path = ./.; name = "luks-unlock-source";
  filter = path: type: builtins.elem (baseNameOf path) [ "unlock.py" "gui_bridge.py" ]; };
in writeShellApplication {
  name = "luks-unlock";
  runtimeInputs = [ python3 openssh ];
  text = ''
    exec python3 ${source}/unlock.py "$@"
  '';
  meta.mainProgram = "luks-unlock";
}
