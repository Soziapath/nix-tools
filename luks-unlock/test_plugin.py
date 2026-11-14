"""Exercise actual Luau scripts against a small Noctalia API harness."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).parent


@unittest.skipUnless(shutil.which("luau"), "run with nix develop for Luau tests")
class PluginTests(unittest.TestCase):
    def test_panel_enables_ticks_and_displays_prompt(self):
        self.run_script("panel.luau", '''
local ticks=false
local env={}
local stream, response, tree
local config={host="host",port=2222,command="/helper",identity="/key",user="root",timeout=2}
noctalia={getenv=function(k) return env[k] end, getConfig=function(k) return config[k] end, expandPath=function(v) return v end,
  runStream=function(_,cb) stream=cb; return true end,
  log=function() end,
  json={encode=function() return "{}" end,decode=function(s)
    if s=="connection" then return {port=1234,token="token"} end
    return {status="password",message="Enter disk passphrase",attempt=1}
  end},
  http=function(options,cb) response=cb; return true end}
panel={setWantsSecondTicks=function(v) ticks=v end,render=function(t) tree=t end,close=function() end}
ui=setmetatable({}, {__index=function(_,kind) return function(props,children) return {kind=kind,props=props,children=children} end end})
''', '''
onOpen()
assert(ticks, "Panel polling must use setWantsSecondTicks")
stream("connection")
assert(response, "Bridge connection must trigger an immediate status request")
response({ok=true,body="password"})
local found=false
for _,child in ipairs(tree.children) do
  if child.kind=="input" then found=child.props.password and child.props.focus end
end
assert(found, "The actual disk prompt must produce a focused, masked input")
onClose()
assert(not ticks)
stream=nil
env.http_proxy="http://proxy.example.test:8080"
onOpen()
assert(not stream and not ticks, "Must fail closed when loopback could use a proxy")
env.NO_PROXY="localhost,127.0.0.1"
onOpen()
assert(stream and ticks, "An explicit loopback exclusion allows direct polling")
''')

    def run_script(self, name, setup, assertions):
        script = setup + "\n" + (ROOT / "noctalia-plugin" / name).read_text() + "\n" + assertions
        with tempfile.NamedTemporaryFile(mode="w", suffix=".luau") as file:
            file.write(script)
            file.flush()
            result = subprocess.run(["luau", file.name], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_watcher_transitions_notifications_and_detached_unlock(self):
        self.run_script("service.luau", '''
local values, watchers, calls = {}, {}, {}
local notifications = 0
local config = {command="/helper with spaces", host="proxmox.example.test", port=2222,
    user="root", identity="/key with spaces", timeout=2, interval=5, notify=true}
noctalia = {
    getConfig=function(key) return config[key] end,
    expandPath=function(path) return path end,
    setUpdateInterval=function(ms) assert(ms == 5000) end,
    formatTime=function() return "12:34:56" end,
    notify=function() notifications += 1 end,
    runAsync=function(argv, callback, timeout)
        table.insert(calls, {argv=argv, callback=callback, timeout=timeout})
        return true
    end,
    json={decode=function(value)
        if value == "bad" then return nil end
        return {available=value ~= "offline", unlocking=value == "unlocking"}
    end},
    state={set=function(key,value) values[key]=table.clone(value) end,
           watch=function(key,callback) watchers[key]=callback end},
}
local function complete(value, code)
    calls[#calls].callback({stdout=value, exitCode=code or 0, timedOut=false})
end
''', '''
assert(#calls == 1)
assert(calls[1].argv[1] == "/helper with spaces")
assert(calls[1].argv[2] == "--check-unlock")
assert(calls[1].argv[3] == "--json")
update() -- No overlapping probes.
assert(#calls == 1)
complete("offline", 1)
assert(values.endpoint.status == "unavailable" and notifications == 0)
update()
complete("online")
assert(values.endpoint.status == "available" and notifications == 1)
update()
complete("online")
assert(notifications == 1)
update()
complete("bad", 2)
update()
complete("online")
assert(notifications == 1, "Helper errors must not rearm the notification")
onConfigChanged()
complete("online")
assert(notifications == 1, "Reloading settings for the same host must not rearm the notification")
update()
complete("offline", 1)
update()
complete("online")
assert(notifications == 1, "One missed prompt must not rearm the notification")
update()
complete("unlocking")
assert(values.endpoint.status == "unlocking")
update()
complete("offline", 1)
assert(values.endpoint.status == "unavailable")
update()
local stale = calls[#calls].callback
onConfigChanged()
stale({stdout="online",exitCode=0})
assert(values.endpoint.status == "checking")
complete("bad", 2)
assert(values.endpoint.status == "error")
for _ = 1, 3 do
  update()
  complete("offline", 1)
end
update()
complete("online")
assert(notifications == 2, "A confirmed disappearance allows a new notification")
''')

    def test_bar_presentation_actions_and_optional_hiding(self):
        self.run_script("bar.luau", '''
local watcher, output, action
local config = {host="host", port=2222, show_label=true, hide_when_unavailable=false}
output = {}
noctalia = {
    getConfig=function(key) return config[key] end,
    setUpdateInterval=function() end,
    nowMs=function() return 1000 end,
    togglePanel=function(id) action={name=id} end,
    state={get=function() return {status="unavailable"} end,
        watch=function(_,callback) watcher=callback end,
        set=function(_,value) action=value end},
}
barWidget = {
    setVisible=function(value) output.visible=value end,
    setGlyph=function(value) output.glyph=value end,
    setGlyphColor=function(value) output.color=value end,
    setColor=function() end,
    setText=function(value) output.text=value end,
    setTooltip=function(value) output.tooltip=value end,
    isVertical=function() return false end,
    outputName=function() return "DP-1" end,
}
''', '''
assert(output.visible and output.text == "" and output.color == "on_surface_variant")
config.hide_when_unavailable=true
update()
assert(not output.visible)
watcher({status="available", host="host", port=2222, checked="12:34"})
assert(output.visible and output.text == "Unlock Proxmox" and output.color == "primary")
onClick()
assert(action.name == "soziapath/luks-unlock:unlock")
onRightClick()
assert(action.name == "refresh")
watcher({status="error", error="Helper failed"})
assert(output.visible and output.color == "error")
''')


if __name__ == "__main__":
    unittest.main()
