-- Installed into the live Lua state only while OmniTiler is active.
-- Config reload discards this state; the controller reinstalls it after reload.
if not _G.__omnitiler_hotkeys then
  local state = { windows = {}, bindings = {} }
  _G.__omnitiler_hotkeys = state

  for _, entry in ipairs({
    { key = "LEFT", direction = "l", description = "Swap window to the left" },
    { key = "RIGHT", direction = "r", description = "Swap window to the right" },
  }) do
    local keys = "SUPER + SHIFT + " .. entry.key
    -- Replace the inspected Omarchy default, without duplicate handlers.
    hl.unbind(keys)
    local binding = hl.bind(keys, function()
      local window = hl.get_active_window()
      local workspace = window and window.workspace
      if window and workspace and window.fullscreen == 0
          and state.windows[window.stable_id] == workspace.id then
        hl.dispatch(hl.dsp.event("omnitiler:move," .. entry.direction .. ","
          .. window.address .. "," .. string.format("%x", window.stable_id)))
      else
        hl.dispatch(hl.dsp.window.swap({ direction = entry.direction }))
      end
    end, { description = entry.description })
    table.insert(state.bindings, { handle = binding, keys = keys,
      direction = entry.direction, description = entry.description })
  end

  function state.restore()
    state.windows = {}
    for _, entry in ipairs(state.bindings) do
      local ok, enabled = pcall(function() return entry.handle:is_enabled() end)
      if ok and enabled then
        hl.unbind(entry.keys)
        hl.bind(entry.keys, hl.dsp.window.swap({ direction = entry.direction }),
          { description = entry.description })
      end
    end
    _G.__omnitiler_hotkeys = nil
  end
end
