local function configuredHost()
  local path = noctalia.getConfig("host_file")
  if path and path ~= "" then
    local value = noctalia.readFile(noctalia.expandPath(path))
    return value and string.match(value, "^%s*(%S+)%s*$") or ""
  end
  return noctalia.getConfig("host")
end

-- One watcher per plugin, shared by every bar and output.
local state = { status = "checking", checked = "Never", available = false }
local probing = false
local lastAvailable = false
local unavailableChecks = 0
local generation = 0

local function publish()
  state.host = configuredHost()
  state.port = noctalia.getConfig("port")
  noctalia.state.set("endpoint", state)
end

local function command(mode)
  return {
    noctalia.getConfig("command"), mode,
    "--port", tostring(noctalia.getConfig("port")),
    "--user", noctalia.getConfig("user"),
    "--identity", noctalia.expandPath(noctalia.getConfig("identity")),
    "--timeout", tostring(noctalia.getConfig("timeout")),
    "--", configuredHost(),
  }
end

local function probe()
  if probing then return end
  if configuredHost() == "" then
    state.status = "unavailable"
    state.error = "Set the SSH host in the plugin settings"
    publish()
    return
  end
  probing = true
  local revision = generation
  local argv = command("--check-unlock")
  table.insert(argv, 3, "--json")
  local started = noctalia.runAsync(argv, function(result)
    if revision ~= generation then return end
    probing = false
    state.checked = noctalia.formatTime("%H:%M:%S")
    local value = noctalia.json.decode(result.stdout)
    if result.timedOut or type(value) ~= "table" or type(value.available) ~= "boolean"
        or (result.exitCode ~= 0 and result.exitCode ~= 1) then
      state.status = "error"
      state.available = false
      state.error = result.timedOut and "Status check timed out" or "Status helper failed; check its command and settings"
      unavailableChecks = 0
    else
      state.available = value.available
      state.status = value.unlocking and "unlocking" or (value.available and "available" or "unavailable")
      state.error = nil
      if value.available and not value.unlocking and not lastAvailable and noctalia.getConfig("notify") then
        noctalia.notify("Proxmox unlock available", configuredHost() .. ":" .. tostring(noctalia.getConfig("port")) .. " — click the lock in the bar to unlock")
      end
      if value.available then
        lastAvailable = not value.unlocking or lastAvailable
        unavailableChecks = 0
      elseif value.unlocking then
        unavailableChecks = 0
      else
        unavailableChecks += 1
        if unavailableChecks >= 3 then lastAvailable = false end
      end
    end
    publish()
  end, (noctalia.getConfig("timeout") * 3 + 6) * 1000)
  if not started then
    probing = false
    state.status = "error"
    state.available = false
    state.error = "Could not start the status helper"
    publish()
  end
end

noctalia.state.watch("action", function(value)
  if type(value) ~= "table" then return end
  if value.name == "refresh" then probe() end
end)

function update()
  noctalia.setUpdateInterval(noctalia.getConfig("interval") * 1000)
  probe()
end

function onConfigChanged()
  generation += 1
  probing = false
  if state.host ~= configuredHost() or state.port ~= noctalia.getConfig("port") then
    lastAvailable = false
    unavailableChecks = 0
  end
  state = { status = "checking", checked = "Never", available = false }
  publish()
  update()
end

function onIpc(event)
  if event == "refresh" then probe() end
end

publish()
update()
