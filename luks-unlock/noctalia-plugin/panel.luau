local function configuredHost()
  local path = noctalia.getConfig("host_file")
  if path and path ~= "" then
    local value = noctalia.readFile(noctalia.expandPath(path))
    return value and string.match(value, "^%s*(%S+)%s*$") or ""
  end
  return noctalia.getConfig("host")
end

local connection = nil
local current = {status="connecting", message="Connecting to Proxmox…", attempt=0}
local secret = ""
local opened = false
local polling = false
local revision = 0
local render

-- Noctalia's HTTP client inherits libcurl's proxy configuration. Require an
-- explicit loopback exclusion whenever a proxy could apply to this request.
local function loopbackIsDirect()
  for _, name in ipairs({"http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY"}) do
    if (noctalia.getenv(name) or "") ~= "" then
      local bypass = noctalia.getenv("no_proxy")
      if not bypass or bypass == "" then bypass = noctalia.getenv("NO_PROXY") or "" end
      if bypass == "*" then return true end
      for entry in string.gmatch(bypass, "[^,]+") do
        if entry == "127.0.0.1" then return true end
      end
      return false
    end
  end
  return true
end

local function request(path, value, callback)
  if not connection then return end
  if not loopbackIsDirect() then return end
  local options = {url="http://127.0.0.1:" .. tostring(connection.port) .. path,
    follow_redirects=false,
    headers={"Authorization: Bearer " .. connection.token}}
  if value then
    options.method="POST"
    options.body=noctalia.json.encode(value)
    table.insert(options.headers,"Content-Type: application/json")
  end
  noctalia.http(options, callback or function() end)
end

local function submit()
  if current.status ~= "password" or secret == "" then return end
  local value = secret
  secret = ""
  current.status="working"
  current.message="Unlocking the disk…"
  render() -- Destroy the input, including its retained native text.
  local active = revision
  request("/password", {password=value}, function(result)
    if active ~= revision or not opened then return end
    if not result.ok or result.status ~= 200 then
      current={status="error",message="Could not submit the passphrase. Close and try again.",attempt=0}
      render()
    end
  end)
  value = nil
end

render = function()
  local children = {
    ui.row({gap=12, align="center"}, {
      ui.glyph({name=current.status == "success" and "circle-check" or "lock", size=30, color="primary"}),
      ui.column({gap=4}, {
        ui.label({text="Unlock Proxmox", fontSize=21, fontWeight="bold"}),
        ui.label({text=configuredHost() .. ":" .. tostring(noctalia.getConfig("port")), color="on_surface_variant"}),
      }),
    }),
    ui.separator({}),
    ui.label({text=current.message, maxWidth=410, maxLines=4, color=current.status == "error" and "error" or "on_surface"}),
  }
  if current.status == "password" then
    table.insert(children, ui.input({key="passphrase-" .. tostring(current.attempt), password=true, focus=true,
      placeholder=current.attempt > 1 and "Try your disk passphrase again" or "Disk passphrase",
      onChange=function(value) secret=value end,
      onSubmit=function(value) secret=value; submit() end}))
    table.insert(children, ui.button({text="Unlock disk", glyph="key", variant="primary", onClick=submit}))
  elseif current.status == "connecting" or current.status == "working" then
    table.insert(children, ui.label({text="Waiting for the SSH session…", color="on_surface_variant"}))
  end
  table.insert(children, ui.button({text=(current.status == "success" or current.status == "error") and "Close" or "Cancel", variant="ghost", onClick=function() panel.close() end}))
  panel.render(ui.column({padding=24,gap=18}, children))
end

function onOpen()
  opened=true
  revision += 1
  local active=revision
  connection=nil
  current={status="connecting",message="Connecting to Proxmox…",attempt=0}
  secret=""
  if configuredHost() == "" or not loopbackIsDirect() then
    current={status="error", attempt=0, message=configuredHost() == ""
      and "Set the SSH host in the plugin settings."
      or "Add 127.0.0.1 to Noctalia’s no_proxy environment and restart Noctalia."}
    render()
    return
  end
  local function quote(value) return "'" .. string.gsub(value,"'","'\\''") .. "'" end
  local argv={noctalia.getConfig("command"),"--gui","--port",tostring(noctalia.getConfig("port")),
    "--identity",noctalia.expandPath(noctalia.getConfig("identity")),"--user",noctalia.getConfig("user"),
    "--timeout",tostring(noctalia.getConfig("timeout")),"--",configuredHost()}
  for i,value in ipairs(argv) do argv[i]=quote(value) end
  local started=noctalia.runStream(table.concat(argv," "),function(line)
    local data=noctalia.json.decode(line)
    if type(data) ~= "table" then return end
    if type(data.port) == "number" and data.port % 1 == 0 and data.port >= 1 and data.port <= 65535
        and type(data.token) == "string" and string.match(data.token, "^[%w_-]+$") then
      connection=data
      if active ~= revision or not opened then request("/cancel",{}); connection=nil end
      if opened and active == revision then update() end
    elseif data.error and active == revision then
      current={status="error",message=data.error,attempt=0}; render()
    end
  end)
  if not started then current={status="error",message="Unable to start the unlock session.",attempt=0} end
  panel.setWantsSecondTicks(true)
  render()
end

function update()
  if not opened or not connection or polling then return end
  polling=true
  local active=revision
  request("/state",nil,function(result)
    polling=false
    if not opened or active ~= revision then return end
    local data=noctalia.json.decode(result.body or "")
    if result.ok and type(data)=="table" and data.status then
      if data.status ~= current.status or data.attempt ~= current.attempt then
        noctalia.log("LUKS panel status: " .. data.status)
        current=data; secret=""; render()
      end
    else
      current={status="error",message="The unlock session ended. Close and try again.",attempt=0}; render()
    end
  end)
end

function onClose()
  panel.setWantsSecondTicks(false)
  opened=false
  revision += 1
  secret=""
  request("/cancel",{})
  connection=nil
  polling=false
  current={status="connecting",message="",attempt=0}
  render()
end
