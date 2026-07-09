-- dualsub: measures how long each subtitle track is actively shown while playing,
-- so we can compute a "comprehension" score (time on source ÷ total sub time).
local out = os.getenv("DUALSUB_PROGRESS_OUT")
local episode = os.getenv("DUALSUB_EPISODE") or "unknown"

local acc = {}        -- sid -> accumulated seconds
local last_t = nil
local cur_sid = nil
local paused = false
local visible = true

local function tick()
    local t = mp.get_time()
    if last_t and cur_sid and not paused and visible then
        acc[cur_sid] = (acc[cur_sid] or 0) + (t - last_t)
    end
    last_t = t
end

mp.observe_property("sid", "number", function(_, v) tick(); cur_sid = v end)
mp.observe_property("pause", "bool", function(_, v) tick(); paused = v end)
mp.observe_property("sub-visibility", "bool", function(_, v) tick(); visible = v end)
mp.add_periodic_timer(1.0, tick)

mp.register_event("shutdown", function()
    tick()
    local src = acc[1] or 0
    local tgt = acc[2] or 0
    if out then
        local f = io.open(out, "w")
        if f then
            f:write(string.format('{"episode":"%s","src_seconds":%.1f,"tgt_seconds":%.1f}',
                episode, src, tgt))
            f:close()
        end
    end
end)
