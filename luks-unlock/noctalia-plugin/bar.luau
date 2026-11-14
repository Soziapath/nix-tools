local snapshot = noctalia.state.get("endpoint") or { status = "checking", checked = "Never" }
local sequence = 0
local labels = {
  checking = "Checking…",
  available = "Unlock Proxmox",
  unavailable = "Unlock endpoint unavailable",
  unlocking = "Unlocking…",
  error = "Unlock check failed",
}

local function render()
  local status = snapshot.status
  local active = status == "available" or status == "unlocking"
  local color = status == "error" and "error" or (active and "primary" or "on_surface_variant")
  barWidget.setVisible(not noctalia.getConfig("hide_when_unavailable") or status ~= "unavailable")
  barWidget.setGlyph(status == "error" and "alert-circle" or (status == "unlocking" and "terminal" or "lock"))
  barWidget.setGlyphColor(color)
  barWidget.setColor(color)
  local label = (active or status == "error") and labels[status] or ""
  barWidget.setText(noctalia.getConfig("show_label") and not barWidget.isVertical() and label or "")
  barWidget.setTooltip({
    { key = "Proxmox", value = labels[status] or "Unknown" },
    { key = "Endpoint", value = (snapshot.host or noctalia.getConfig("host")) .. ":" .. tostring(snapshot.port or noctalia.getConfig("port")) },
    { key = "Last check", value = snapshot.checked or "Never" },
    { key = "Action", value = status == "available" and "Click to unlock · right-click to refresh" or (snapshot.error or "Right-click to refresh") },
  })
end

local function request(name)
  sequence += 1
  noctalia.state.set("action", { name = name, sequence = sequence, time = noctalia.nowMs(), output = barWidget.outputName() })
end

noctalia.state.watch("endpoint", function(value)
  if type(value) == "table" then snapshot = value end
  render()
end)

function update()
  noctalia.setUpdateInterval(5000)
  render()
end

function onClick()
  noctalia.togglePanel("soziapath/luks-unlock:unlock")
end

function onRightClick()
  request("refresh")
end

render()
