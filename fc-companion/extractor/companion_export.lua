require 'imports/career_mode/helpers'
MEMORY = require 'imports/core/memory'
require 'imports/other/helpers'
require 'imports/services/enums'

local COMPANION = {}
COMPANION.EVENTS = {}
COMPANION.MAX_EVENTS = 250
COMPANION.EXPORT_INTERVAL_SECONDS = 10
COMPANION.OUTPUT_DIR = ((os.getenv("USERPROFILE") or "C:\\Users\\Default") .. "\\Desktop\\fc_companion")
COMPANION.STATE_LUA_TMP = COMPANION.OUTPUT_DIR .. "\\state_lua.tmp"
COMPANION.STATE_LUA_JSON = COMPANION.OUTPUT_DIR .. "\\state_lua.json"
COMPANION.UNRESOLVED_IDS_JSON = COMPANION.OUTPUT_DIR .. "\\unresolved_player_ids.json"
COMPANION.LAST_EXPORT_TS = 0
COMPANION.IS_EXPORTING = false
COMPANION.NAME_CACHE = {}
COMPANION.NAME_RESOLVE_INTERVAL_SECONDS = 10
COMPANION.NAME_RESOLVE_BATCH_SIZE = 12
COMPANION.LAST_NAME_RESOLVE_TS = 0

local function log_info(msg)
    if LOGGER and LOGGER.LogInfo then
        LOGGER:LogInfo(msg)
        return
    end
    print(msg)
end

local function log_error(msg)
    if LOGGER and LOGGER.LogError then
        LOGGER:LogError(msg)
        return
    end
    print("[ERROR] " .. tostring(msg))
end

local function safe_call(default_value, fn, ...)
    if type(fn) ~= "function" then
        return default_value
    end
    local ok, result = pcall(fn, ...)
    if ok then
        return result
    end
    log_error(result)
    return default_value
end

local function to_bool(v)
    return v == true or v == 1
end

local function to_number(v, default_value)
    local n = tonumber(v)
    if n == nil then
        return default_value
    end
    return n
end

-- Serializer JSON puro para manter o script independente de bibliotecas externas.
local function json_escape(value)
    local s = tostring(value or "")
    s = s:gsub("\\", "\\\\")
    s = s:gsub("\"", "\\\"")
    s = s:gsub("\n", "\\n")
    s = s:gsub("\r", "\\r")
    s = s:gsub("\t", "\\t")
    return s
end

local function is_array(tbl)
    if type(tbl) ~= "table" then
        return false
    end
    local max_index = 0
    local count = 0
    for k, _ in pairs(tbl) do
        if type(k) ~= "number" or k <= 0 or k % 1 ~= 0 then
            return false
        end
        if k > max_index then
            max_index = k
        end
        count = count + 1
    end
    if count == 0 then
        return true
    end
    return max_index == count
end

local function serialize_json(value)
    local t = type(value)
    if t == "nil" then
        return "null"
    end
    if t == "boolean" then
        return value and "true" or "false"
    end
    if t == "number" then
        return tostring(value)
    end
    if t == "string" then
        return "\"" .. json_escape(value) .. "\""
    end
    if t ~= "table" then
        return "\"" .. json_escape(tostring(value)) .. "\""
    end
    if is_array(value) then
        local out = {}
        for i = 1, #value do
            out[#out + 1] = serialize_json(value[i])
        end
        return "[" .. table.concat(out, ",") .. "]"
    end
    local out = {}
    for k, v in pairs(value) do
        out[#out + 1] = "\"" .. json_escape(k) .. "\":" .. serialize_json(v)
    end
    table.sort(out)
    return "{" .. table.concat(out, ",") .. "}"
end

local function normalize_save_uid(raw_uid)
    local uid = tostring(raw_uid or "unknown_save")
    uid = uid:gsub("^%s+", ""):gsub("%s+$", "")
    uid = uid:gsub("[\\/:*?\"<>|]", "_")
    if uid == "" then
        uid = "unknown_save"
    end
    return uid
end

-- Escrita atômica para evitar leitura de arquivo incompleto pelo backend.
local function ensure_output_dir()
    local ok = os.rename(COMPANION.OUTPUT_DIR, COMPANION.OUTPUT_DIR)
    if ok then
        return true
    end
    local _, _, code = os.execute('mkdir "' .. COMPANION.OUTPUT_DIR .. '" >nul 2>nul')
    return code == 0
end

local function write_state_lua_atomic(payload)
    local file, err = io.open(COMPANION.STATE_LUA_TMP, "w")
    if not file then
        log_error("Falha ao abrir state_lua.tmp: " .. tostring(err))
        return false
    end
    file:write(serialize_json(payload))
    file:close()
    os.remove(COMPANION.STATE_LUA_JSON)
    local renamed, rename_err = os.rename(COMPANION.STATE_LUA_TMP, COMPANION.STATE_LUA_JSON)
    if not renamed then
        log_error("Falha ao renomear para state_lua.json: " .. tostring(rename_err))
        return false
    end
    return true
end

local function ensure_dir(path)
    local ok = os.rename(path, path)
    if ok then
        return true
    end
    local _, _, code = os.execute('mkdir "' .. path .. '" >nul 2>nul')
    return code == 0
end

local function write_json_atomic(path, payload)
    local tmp = path .. ".tmp"
    local file, err = io.open(tmp, "w")
    if not file then
        log_error("Falha ao abrir arquivo temporário: " .. tostring(err))
        return false
    end
    file:write(serialize_json(payload))
    file:close()
    os.remove(path)
    local renamed, rename_err = os.rename(tmp, path)
    if not renamed then
        log_error("Falha ao concluir escrita atômica: " .. tostring(rename_err))
        return false
    end
    return true
end

local function format_period_from_raw_date(raw)
    local n = to_number(raw, 0)
    if n <= 0 then
        return nil
    end
    local year = math.floor(n / 10000)
    local month = math.floor((n % 10000) / 100)
    if year <= 0 or month <= 0 or month > 12 then
        return nil
    end
    return string.format("%04d-%02d", year, month)
end

local function write_transfer_history_json(payload)
    local save_uid = normalize_save_uid(((payload.meta or {}).save_uid) or "unknown_save")
    local save_dir = COMPANION.OUTPUT_DIR .. "\\" .. save_uid
    if not ensure_dir(save_dir) then
        log_error("Falha ao preparar diretório do save para transfer_history.")
        return false
    end
    local transfer_table = nil
    if LE and LE.db and LE.db.GetTable then
        transfer_table = safe_call(nil, LE.db.GetTable, LE.db, "career_presignedcontract")
    end
    local user_team_id = to_number(((payload.club or {}).team_id), 0)
    local team_name_cache = {}
    local function team_name(team_id)
        local key = tostring(to_number(team_id, 0))
        if team_name_cache[key] ~= nil then
            return team_name_cache[key]
        end
        local value = safe_call("Unknown", GetTeamName, to_number(team_id, 0))
        team_name_cache[key] = value
        return value
    end
    local function player_name(player_id)
        local pid = to_number(player_id, 0)
        if pid <= 0 then
            return "Jogador"
        end
        if COMPANION.NAME_CACHE[pid] then
            return COMPANION.NAME_CACHE[pid]
        end
        local value = safe_call("Jogador", GetPlayerName, pid)
        if type(value) == "string" and value ~= "" then
            COMPANION.NAME_CACHE[pid] = value
            return value
        end
        return "Jogador"
    end
    local items = {}
    local seen = {}
    if transfer_table and user_team_id > 0 then
        local rec = transfer_table:GetFirstRecord()
        while rec and rec > 0 do
            local offer_team_id = to_number(transfer_table:GetRecordFieldValue(rec, "offerteamid"), 0)
            local from_team_id = to_number(transfer_table:GetRecordFieldValue(rec, "teamid"), 0)
            local player_id = to_number(transfer_table:GetRecordFieldValue(rec, "playerid"), 0)
            local signed_date = to_number(transfer_table:GetRecordFieldValue(rec, "signeddate"), 0)
            local complete_date = to_number(transfer_table:GetRecordFieldValue(rec, "completedate"), 0)
            local offered_fee = to_number(transfer_table:GetRecordFieldValue(rec, "offeredfee"), 0)
            local future_fee = to_number(transfer_table:GetRecordFieldValue(rec, "future_fee"), 0)
            local is_loan_buy = to_number(transfer_table:GetRecordFieldValue(rec, "isloanbuy"), 0)
            local fee = offered_fee
            if fee <= 0 and future_fee > 0 then
                fee = future_fee
            end
            local is_buy = offer_team_id == user_team_id
            local is_sell = from_team_id == user_team_id and offer_team_id > 0 and offer_team_id ~= user_team_id
            if fee > 0 and (is_buy or is_sell) then
                local key = tostring(player_id) .. "|" .. tostring(signed_date) .. "|" .. tostring(offer_team_id) .. "|" .. tostring(from_team_id) .. "|" .. tostring(fee)
                if not seen[key] then
                    seen[key] = true
                    local to_team_id = is_buy and offer_team_id or offer_team_id
                    local source_team_id = is_buy and from_team_id or user_team_id
                    items[#items + 1] = {
                        id = key,
                        player_id = player_id,
                        player_name = player_name(player_id),
                        amount = fee,
                        fee = fee,
                        type = is_buy and "buy" or "sell",
                        direction = is_buy and "in" or "out",
                        is_loan_buy = is_loan_buy,
                        signed_date = signed_date,
                        completed_date = complete_date,
                        period = format_period_from_raw_date(signed_date) or format_period_from_raw_date(complete_date),
                        from_team_id = source_team_id,
                        from_team_name = team_name(source_team_id),
                        to_team_id = to_team_id,
                        to_team_name = team_name(to_team_id)
                    }
                end
            end
            rec = transfer_table:GetNextValidRecord()
        end
    end
    table.sort(items, function(a, b)
        local da = to_number(a.signed_date, 0)
        local db = to_number(b.signed_date, 0)
        if da == db then
            return tostring(a.id) < tostring(b.id)
        end
        return da < db
    end)
    local incoming_count = 0
    local outgoing_count = 0
    for _, item in ipairs(items) do
        if tostring(item.type) == "buy" then
            incoming_count = incoming_count + 1
        elseif tostring(item.type) == "sell" then
            outgoing_count = outgoing_count + 1
        end
    end
    local transfer_payload = {
        items = items,
        meta = {
            export_version = "2.1.0",
            exported_at_iso = os.date("!%Y-%m-%dT%H:%M:%SZ"),
            exported_at_ts = os.time(),
            game_date = ((payload.meta or {}).game_date) or { day = nil, month = nil, year = nil },
            save_uid = save_uid,
            script_name = "companion_export.lua",
            source = "live_editor"
        },
        summary = {
            count = #items,
            incoming_count = incoming_count,
            outgoing_count = outgoing_count
        }
    }
    local output_path = save_dir .. "\\transfer_history.json"
    return write_json_atomic(output_path, transfer_payload)
end

local function read_text_file(path)
    local f = io.open(path, "r")
    if not f then
        return nil
    end
    local content = f:read("*a")
    f:close()
    return content
end

local function parse_numeric_json_array(text)
    if type(text) ~= "string" or text == "" then
        return {}
    end
    local out = {}
    local seen = {}
    for raw in string.gmatch(text, "-?%d+") do
        local pid = tonumber(raw)
        if pid ~= nil and pid > 0 and not seen[pid] then
            seen[pid] = true
            out[#out + 1] = pid
        end
    end
    return out
end

local function resolve_missing_names_batch()
    local now = os.time()
    if now - COMPANION.LAST_NAME_RESOLVE_TS < COMPANION.NAME_RESOLVE_INTERVAL_SECONDS then
        return
    end
    local unresolved_text = read_text_file(COMPANION.UNRESOLVED_IDS_JSON)
    local ids = parse_numeric_json_array(unresolved_text)
    if #ids == 0 then
        COMPANION.LAST_NAME_RESOLVE_TS = now
        return
    end
    local resolved_now = 0
    for _, pid in ipairs(ids) do
        if resolved_now >= COMPANION.NAME_RESOLVE_BATCH_SIZE then
            break
        end
        if not COMPANION.NAME_CACHE[pid] then
            local name = safe_call("", GetPlayerName, pid)
            if type(name) == "string" then
                name = name:gsub("^%s+", ""):gsub("%s+$", "")
                if name ~= "" then
                    COMPANION.NAME_CACHE[pid] = name
                    resolved_now = resolved_now + 1
                end
            end
        end
    end
    COMPANION.LAST_NAME_RESOLVE_TS = now
end

local function build_name_resolution_payload()
    local count = 0
    for _, _ in pairs(COMPANION.NAME_CACHE) do
        count = count + 1
    end
    return {
        resolved = COMPANION.NAME_CACHE,
        resolved_count = count,
        updated_at = os.time()
    }
end

-- Cadeia de ponteiros oficial para acessar dados de fixtures/standings sem DB table scans.
local function get_fce_data_manager()
    local IFCEInterface = GetPlugin(ENUM_djb2IFCEInterface_CLSS)
    if IFCEInterface == nil or IFCEInterface == 0 then
        return nil
    end
    local FCEDataManager = MEMORY:ReadMultilevelPointer(IFCEInterface, {0x18, 0x10, 0x08, 0x00})
    return FCEDataManager
end

local function read_standings_raw()
    local function run()
        local FCEDataManager = get_fce_data_manager()
        if FCEDataManager == nil or FCEDataManager == 0 then
            return {}
        end
        local StandingsDataList = MEMORY:ReadPointer(FCEDataManager + 0x88)
        if StandingsDataList == nil or StandingsDataList == 0 then
            return {}
        end
        local mBegin = MEMORY:ReadPointer(StandingsDataList + 0x28)
        local max_items_count = MEMORY:ReadInt(StandingsDataList + 0x1C) - 1
        if mBegin == nil or mBegin == 0 or max_items_count < 0 then
            return {}
        end
        local itemSize = 0x18
        local out = {}
        for i = 0, max_items_count do
            local mCurrent = mBegin + (i * itemSize)
            local is_used = to_bool(MEMORY:ReadBool(mCurrent + 0x16))
            if is_used then
                out[#out + 1] = {
                    mId = MEMORY:ReadShort(mCurrent + 0x00),
                    mCompObjId = MEMORY:ReadShort(mCurrent + 0x02),
                    mTeamId = MEMORY:ReadInt(mCurrent + 0x04),
                    mTeamIndex = MEMORY:ReadChar(mCurrent + 0x08),
                    mHomeWins = MEMORY:ReadChar(mCurrent + 0x09),
                    mHomeDraws = MEMORY:ReadChar(mCurrent + 0x0A),
                    mHomeLosses = MEMORY:ReadChar(mCurrent + 0x0B),
                    mHomeGoalsFor = MEMORY:ReadChar(mCurrent + 0x0C),
                    mHomeGoalsAgainst = MEMORY:ReadChar(mCurrent + 0x0D),
                    mAwayWins = MEMORY:ReadChar(mCurrent + 0x0E),
                    mAwayDraws = MEMORY:ReadChar(mCurrent + 0x0F),
                    mAwayLosses = MEMORY:ReadChar(mCurrent + 0x10),
                    mAwayGoalsFor = MEMORY:ReadChar(mCurrent + 0x11),
                    mAwayGoalsAgainst = MEMORY:ReadChar(mCurrent + 0x12),
                    mPoints = MEMORY:ReadShort(mCurrent + 0x14)
                }
            end
        end
        return out
    end
    return safe_call({}, run)
end

function GetAllStandings()
    local function run()
        local raw = read_standings_raw()
        local out = {}
        for _, row in ipairs(raw) do
            local home_wins = to_number(row.mHomeWins, 0)
            local home_draws = to_number(row.mHomeDraws, 0)
            local home_losses = to_number(row.mHomeLosses, 0)
            local home_gf = to_number(row.mHomeGoalsFor, 0)
            local home_ga = to_number(row.mHomeGoalsAgainst, 0)
            local away_wins = to_number(row.mAwayWins, 0)
            local away_draws = to_number(row.mAwayDraws, 0)
            local away_losses = to_number(row.mAwayLosses, 0)
            local away_gf = to_number(row.mAwayGoalsFor, 0)
            local away_ga = to_number(row.mAwayGoalsAgainst, 0)
            local team_id = to_number(row.mTeamId, 0)
            out[#out + 1] = {
                standing_id = to_number(row.mId, 0),
                competition_id = to_number(row.mCompObjId, 0),
                team_id = team_id,
                team_name = safe_call("Unknown", GetTeamName, team_id),
                home = {
                    wins = home_wins,
                    draws = home_draws,
                    losses = home_losses,
                    goals_for = home_gf,
                    goals_against = home_ga
                },
                away = {
                    wins = away_wins,
                    draws = away_draws,
                    losses = away_losses,
                    goals_for = away_gf,
                    goals_against = away_ga
                },
                total = {
                    wins = home_wins + away_wins,
                    draws = home_draws + away_draws,
                    losses = home_losses + away_losses,
                    goals_for = home_gf + away_gf,
                    goals_against = home_ga + away_ga,
                    points = to_number(row.mPoints, 0)
                }
            }
        end
        return out
    end
    return safe_call({}, run)
end

local function build_standing_indexes()
    local raw = read_standings_raw()
    local by_id = {}
    local by_index = {}
    for _, row in ipairs(raw) do
        by_id[to_number(row.mId, -1)] = row
        by_index[to_number(row.mTeamIndex, -1)] = row
    end
    return by_id, by_index
end

function GetAllFixtures()
    local function run()
        local FCEDataManager = get_fce_data_manager()
        if FCEDataManager == nil or FCEDataManager == 0 then
            return {}
        end
        local FixtureDataList = MEMORY:ReadPointer(FCEDataManager + 0x60)
        if FixtureDataList == nil or FixtureDataList == 0 then
            return {}
        end
        local mBegin = MEMORY:ReadPointer(FixtureDataList + 0x28)
        local max_items_count = MEMORY:ReadInt(FixtureDataList + 0x1C) - 1
        if mBegin == nil or mBegin == 0 or max_items_count < 0 then
            return {}
        end
        local standings_by_id, standings_by_index = build_standing_indexes()
        local itemSize = 0x18
        local out = {}
        for i = 0, max_items_count do
            local mCurrent = mBegin + (i * itemSize)
            local is_used = to_bool(MEMORY:ReadBool(mCurrent + 0x14))
            if is_used then
                local mDate = MEMORY:ReadInt(mCurrent + 0x00)
                local mTime = MEMORY:ReadShort(mCurrent + 0x04)
                local mId = MEMORY:ReadShort(mCurrent + 0x06)
                local mCompObjId = MEMORY:ReadShort(mCurrent + 0x08)
                local mHomeStandingId = MEMORY:ReadShort(mCurrent + 0x0A)
                local mAwayStandingId = MEMORY:ReadShort(mCurrent + 0x0C)
                local mHomeScore = MEMORY:ReadChar(mCurrent + 0x0F)
                local mAwayScore = MEMORY:ReadChar(mCurrent + 0x11)
                local mHomePenalties = MEMORY:ReadChar(mCurrent + 0x10)
                local mAwayPenalties = MEMORY:ReadChar(mCurrent + 0x12)
                local mGameCompletion = to_bool(MEMORY:ReadBool(mCurrent + 0x13))
                local home_standing = standings_by_id[mHomeStandingId] or standings_by_index[mHomeStandingId] or {}
                local away_standing = standings_by_id[mAwayStandingId] or standings_by_index[mAwayStandingId] or {}
                local home_team_id = to_number(home_standing.mTeamId, 0)
                local away_team_id = to_number(away_standing.mTeamId, 0)
                out[#out + 1] = {
                    id = to_number(mId, 0),
                    competition_id = to_number(mCompObjId, 0),
                    home_team_id = home_team_id,
                    away_team_id = away_team_id,
                    home_team_name = safe_call("Unknown", GetTeamName, home_team_id),
                    away_team_name = safe_call("Unknown", GetTeamName, away_team_id),
                    home_score = mGameCompletion and to_number(mHomeScore, 0) or nil,
                    away_score = mGameCompletion and to_number(mAwayScore, 0) or nil,
                    home_penalties = mGameCompletion and to_number(mHomePenalties, 0) or nil,
                    away_penalties = mGameCompletion and to_number(mAwayPenalties, 0) or nil,
                    is_completed = mGameCompletion,
                    date_raw = to_number(mDate, 0),
                    time_raw = to_number(mTime, 0)
                }
            end
        end
        return out
    end
    return safe_call({}, run)
end

local function read_live_role_map_from_status_manager()
    local function run()
        local out = {}
        local player_status_mgr = safe_call(0, GetManagerObjByTypeId, ENUM_FCEGameModesFCECareerModePlayerStatusManager)
        if player_status_mgr == nil or player_status_mgr == 0 then
            return out
        end
        local vec_begin = MEMORY:ReadPointer(player_status_mgr + 0x18)
        local vec_end = MEMORY:ReadPointer(player_status_mgr + 0x20)
        if vec_begin == nil or vec_begin == 0 or vec_end == nil or vec_end == 0 or vec_end <= vec_begin then
            return out
        end
        local item_size = 0x8
        local max_steps = math.floor((vec_end - vec_begin) / item_size)
        if max_steps < 0 then
            return out
        end
        if max_steps > 20000 then
            max_steps = 20000
        end
        local current_addr = vec_begin
        for _ = 1, max_steps do
            if current_addr >= vec_end then
                break
            end
            local player_id = to_number(MEMORY:ReadInt(current_addr + 0x0), 0)
            local role_id = to_number(MEMORY:ReadInt(current_addr + 0x4), -1)
            if player_id > 0 and role_id >= 0 then
                out[player_id] = role_id
            end
            current_addr = current_addr + item_size
        end
        return out
    end
    return safe_call({}, run)
end

function GetUserTeamLiveRoles()
    local function run()
        local team_id = to_number(safe_call(0, GetUserTeamID), 0)
        if team_id <= 0 then
            return {}
        end
        local live_map = read_live_role_map_from_status_manager()
        local contract_table = LE.db:GetTable("career_playercontract")
        local current_record = contract_table:GetFirstRecord()
        local out = {}
        while current_record > 0 do
            local row_team_id = to_number(contract_table:GetRecordFieldValue(current_record, "teamid"), 0)
            if row_team_id == team_id then
                local player_id = to_number(contract_table:GetRecordFieldValue(current_record, "playerid"), 0)
                if player_id > 0 then
                    local contract_role = to_number(contract_table:GetRecordFieldValue(current_record, "playerrole"), -1)
                    local role = contract_role
                    local source = "career_playercontract"
                    if live_map[player_id] ~= nil then
                        role = to_number(live_map[player_id], contract_role)
                        source = "lua_player_status_manager"
                    end
                    out[player_id] = {
                        playerrole = role,
                        source = source,
                        contract_status = to_number(contract_table:GetRecordFieldValue(current_record, "contract_status"), 0)
                    }
                end
            end
            current_record = contract_table:GetNextValidRecord()
        end
        return out
    end
    return safe_call({}, run)
end

local function append_event(event_id)
    COMPANION.EVENTS[#COMPANION.EVENTS + 1] = {
        event_id = to_number(event_id, 0),
        timestamp = os.time()
    }
    if #COMPANION.EVENTS > COMPANION.MAX_EVENTS then
        table.remove(COMPANION.EVENTS, 1)
    end
end

local function normalize_budget_value(raw_value)
    local value = to_number(raw_value, 0)
    if value > 0 and value < 1000 then
        return value * 1000000
    end
    return value
end

local function read_manager_pref_finance()
    local function run()
        local pref_table = LE.db:GetTable("career_managerpref")
        if pref_table == nil then
            return {}
        end
        local rec = pref_table:GetFirstRecord()
        if rec == nil or rec <= 0 then
            return {}
        end
        return {
            transferbudget = normalize_budget_value(pref_table:GetRecordFieldValue(rec, "transferbudget")),
            wagebudget = normalize_budget_value(pref_table:GetRecordFieldValue(rec, "wagebudget")),
            startofseasontransferbudget = normalize_budget_value(pref_table:GetRecordFieldValue(rec, "startofseasontransferbudget")),
            startofseasonwagebudget = normalize_budget_value(pref_table:GetRecordFieldValue(rec, "startofseasonwagebudget"))
        }
    end
    return safe_call({}, run)
end

local function read_manager_info_finance()
    local function run()
        local info_table = LE.db:GetTable("career_managerinfo")
        if info_table == nil then
            return {}
        end
        local rec = info_table:GetFirstRecord()
        if rec == nil or rec <= 0 then
            return {}
        end
        return {
            totalearnings = to_number(info_table:GetRecordFieldValue(rec, "totalearnings"), 0),
            wage = to_number(info_table:GetRecordFieldValue(rec, "wage"), 0),
            clubteamid = to_number(info_table:GetRecordFieldValue(rec, "clubteamid"), 0)
        }
    end
    return safe_call({}, run)
end

local function read_manager_history_finance()
    local function run()
        local history_table = LE.db:GetTable("career_managerhistory")
        if history_table == nil then
            return {}
        end
        local rec = history_table:GetFirstRecord()
        if rec == nil or rec <= 0 then
            return {}
        end
        return {
            bigbuyamount = normalize_budget_value(history_table:GetRecordFieldValue(rec, "bigbuyamount")),
            bigsellamount = normalize_budget_value(history_table:GetRecordFieldValue(rec, "bigsellamount")),
            bigbuyplayername = tostring(history_table:GetRecordFieldValue(rec, "bigbuyplayername") or ""),
            bigsellplayername = tostring(history_table:GetRecordFieldValue(rec, "bigsellplayername") or ""),
            leagueobjective = to_number(history_table:GetRecordFieldValue(rec, "leagueobjective"), 0),
            leaguetrophies = to_number(history_table:GetRecordFieldValue(rec, "leaguetrophies"), 0)
        }
    end
    return safe_call({}, run)
end

local function summarize_contract_finance(user_team_id)
    local function run()
        local contract_table = LE.db:GetTable("career_playercontract")
        if contract_table == nil or user_team_id <= 0 then
            return {
                players_count = 0,
                athletes_weekly_wages = 0,
                signon_bonus_total = 0,
                performance_bonus_projection = 0
            }
        end
        local players_count = 0
        local athletes_weekly_wages = 0
        local signon_bonus_total = 0
        local performance_bonus_projection = 0
        local rec = contract_table:GetFirstRecord()
        while rec and rec > 0 do
            local team_id = to_number(contract_table:GetRecordFieldValue(rec, "teamid"), 0)
            if team_id == user_team_id then
                players_count = players_count + 1
                local wage = to_number(contract_table:GetRecordFieldValue(rec, "wage"), 0)
                local signon_bonus = to_number(contract_table:GetRecordFieldValue(rec, "signon_bonus"), 0)
                local perf_value = to_number(contract_table:GetRecordFieldValue(rec, "performancebonusvalue"), 0)
                local perf_count = to_number(contract_table:GetRecordFieldValue(rec, "performancebonuscount"), 0)
                athletes_weekly_wages = athletes_weekly_wages + wage
                signon_bonus_total = signon_bonus_total + signon_bonus
                if perf_value > 0 and perf_count > 0 then
                    performance_bonus_projection = performance_bonus_projection + (perf_value * perf_count)
                end
            end
            rec = contract_table:GetNextValidRecord()
        end
        return {
            players_count = players_count,
            athletes_weekly_wages = athletes_weekly_wages,
            signon_bonus_total = signon_bonus_total,
            performance_bonus_projection = performance_bonus_projection
        }
    end
    return safe_call({
        players_count = 0,
        athletes_weekly_wages = 0,
        signon_bonus_total = 0,
        performance_bonus_projection = 0
    }, run)
end

local function summarize_presigned_finance(user_team_id)
    local function run()
        local transfer_table = LE.db:GetTable("career_presignedcontract")
        if transfer_table == nil or user_team_id <= 0 then
            return {
                buys_count = 0,
                sells_count = 0,
                buys_total = 0,
                sells_total = 0
            }
        end
        local buys_count = 0
        local sells_count = 0
        local buys_total = 0
        local sells_total = 0
        local rec = transfer_table:GetFirstRecord()
        while rec and rec > 0 do
            local offer_team_id = to_number(transfer_table:GetRecordFieldValue(rec, "offerteamid"), 0)
            local from_team_id = to_number(transfer_table:GetRecordFieldValue(rec, "teamid"), 0)
            local offered_fee = to_number(transfer_table:GetRecordFieldValue(rec, "offeredfee"), 0)
            local future_fee = to_number(transfer_table:GetRecordFieldValue(rec, "future_fee"), 0)
            local fee = offered_fee
            if fee <= 0 and future_fee > 0 then
                fee = future_fee
            end
            if fee > 0 then
                if offer_team_id == user_team_id and from_team_id > 0 and from_team_id ~= user_team_id then
                    buys_count = buys_count + 1
                    buys_total = buys_total + fee
                elseif from_team_id == user_team_id and offer_team_id > 0 and offer_team_id ~= user_team_id then
                    sells_count = sells_count + 1
                    sells_total = sells_total + fee
                end
            end
            rec = transfer_table:GetNextValidRecord()
        end
        return {
            buys_count = buys_count,
            sells_count = sells_count,
            buys_total = buys_total,
            sells_total = sells_total
        }
    end
    return safe_call({
        buys_count = 0,
        sells_count = 0,
        buys_total = 0,
        sells_total = 0
    }, run)
end

local function sample_manager_numeric_offsets(ptr, max_bytes, limit)
    local out = {}
    if ptr == nil or ptr <= 0 then
        return out
    end
    local seen = {}
    local count = 0
    local max_scan = to_number(max_bytes, 0x300)
    local max_results = to_number(limit, 60)
    local off = 0
    while off <= max_scan and count < max_results do
        local value = to_number(safe_call(0, MEMORY.ReadInt, MEMORY, ptr + off), 0)
        if value > 1000 and value < 2000000000 and not seen[value] then
            seen[value] = true
            out[#out + 1] = { offset = off, value = value }
            count = count + 1
        end
        off = off + 4
    end
    return out
end

local function discover_finance_functions()
    local function run()
        local names = {
            "GetTransferBudget",
            "GetUserTransferBudget",
            "GetCPUTransferBudget",
            "GetWageBudget",
            "GetUserWageBudget",
            "GetCPUWageBudget",
            "GetClubWorth",
            "GetClubValue",
            "GetProjectedClubWorth",
            "GetProjectedClubValue",
            "GetFinanceOverview",
            "GetFinanceData"
        }
        local out = {}
        for _, name in ipairs(names) do
            local fn = _G[name]
            if type(fn) == "function" then
                local value = safe_call(nil, fn)
                if type(value) == "number" or type(value) == "string" or type(value) == "boolean" then
                    out[name] = value
                elseif type(value) == "table" then
                    out[name] = value
                else
                    out[name] = "callable"
                end
            end
        end
        return out
    end
    return safe_call({}, run)
end

local function read_finance_live_snapshot(team_id)
    local function run()
        local manager_pref = read_manager_pref_finance()
        local manager_info = read_manager_info_finance()
        local manager_history = read_manager_history_finance()
        local contract_summary = summarize_contract_finance(team_id)
        local transfer_summary = summarize_presigned_finance(team_id)
        local budget_manager_ptr = to_number(safe_call(0, GetManagerObjByTypeId, ENUM_FCEGameModesFCECareerModeBudgetManager), 0)
        local finance_manager_ptr = to_number(safe_call(0, GetManagerObjByTypeId, ENUM_FCEGameModesFCECareerModeFinanceManager), 0)
        local tcm_finance_manager_ptr = to_number(safe_call(0, GetManagerObjByTypeId, ENUM_FCEGameModesFCECareerModeTcmFinanceManager), 0)
        return {
            transfer_budget_live = normalize_budget_value(to_number(safe_call(0, GetTransferBudget), 0)),
            manager_pref = manager_pref,
            manager_info = manager_info,
            manager_history = manager_history,
            contract_summary = contract_summary,
            transfer_summary = transfer_summary,
            discovered_function_values = discover_finance_functions(),
            manager_memory_samples = {
                budget_manager = {
                    ptr = budget_manager_ptr,
                    values = sample_manager_numeric_offsets(budget_manager_ptr, 0x300, 80)
                },
                finance_manager = {
                    ptr = finance_manager_ptr,
                    values = sample_manager_numeric_offsets(finance_manager_ptr, 0x300, 80)
                },
                tcm_finance_manager = {
                    ptr = tcm_finance_manager_ptr,
                    values = sample_manager_numeric_offsets(tcm_finance_manager_ptr, 0x300, 80)
                }
            }
        }
    end
    return safe_call({}, run)
end

function BuildStatePartial()
    local function run()
        local game_date = safe_call({ day = nil, month = nil, year = nil }, GetCurrentDate)
        local save_uid = normalize_save_uid(safe_call("unknown_save", GetSaveUID))
        local team_id = to_number(safe_call(0, GetUserTeamID), 0)
        local manager_pref = read_manager_pref_finance()
        local finance_live = read_finance_live_snapshot(team_id)
        local transfer_budget_live = normalize_budget_value(to_number(safe_call(0, GetTransferBudget), 0))
        local transfer_budget = transfer_budget_live
        if transfer_budget <= 0 then
            transfer_budget = to_number(manager_pref.transferbudget, 0)
        end
        if transfer_budget <= 0 then
            transfer_budget = to_number(manager_pref.startofseasontransferbudget, 0)
        end
        local wage_budget = to_number(manager_pref.wagebudget, 0)
        if wage_budget <= 0 then
            wage_budget = to_number(manager_pref.startofseasonwagebudget, 0)
        end
        return {
            meta = {
                timestamp = os.time(),
                save_uid = save_uid,
                game_date = {
                    day = game_date and game_date.day or nil,
                    month = game_date and game_date.month or nil,
                    year = game_date and game_date.year or nil
                },
                is_in_career_mode = true,
                source = "lua_memory"
            },
            club = {
                team_id = team_id,
                team_name = safe_call("Unknown", GetTeamName, team_id),
                transfer_budget = transfer_budget,
                wage_budget = wage_budget
            },
            fixtures = GetAllFixtures(),
            standings = GetAllStandings(),
            events_raw = COMPANION.EVENTS,
            name_resolution = build_name_resolution_payload(),
            live_player_roles = GetUserTeamLiveRoles(),
            finance_live = finance_live
        }
    end
    return safe_call({
        meta = {
            timestamp = os.time(),
            save_uid = "unknown_save",
            game_date = { day = nil, month = nil, year = nil },
            is_in_career_mode = false,
            source = "lua_memory"
        },
        club = { team_id = 0, team_name = "Unknown", transfer_budget = 0, wage_budget = 0 },
        fixtures = {},
        standings = {},
        events_raw = {},
        name_resolution = { resolved = {}, resolved_count = 0, updated_at = os.time() },
        live_player_roles = {},
        finance_live = {}
    }, run)
end

local function export_once()
    local function run()
        if not IsInCM() then
            log_info("FC Companion: IsInCM() == false. Aguardando modo carreira.")
            return
        end
        if not ensure_output_dir() then
            log_error("FC Companion: não foi possível criar/acessar diretório de saída.")
            return
        end
        safe_call(nil, resolve_missing_names_batch)
        local payload = BuildStatePartial()
        local wrote_state = write_state_lua_atomic(payload)
        local wrote_transfer = write_transfer_history_json(payload)
        if wrote_state then
            COMPANION.LAST_EXPORT_TS = os.time()
            log_info("FC Companion: state_lua.json atualizado.")
        end
        if wrote_transfer then
            log_info("FC Companion: transfer_history.json atualizado.")
        end
    end
    local ok, err = pcall(run)
    if not ok then
        log_error("FC Companion: erro no export_once: " .. tostring(err))
    end
end

local function maybe_export()
    if COMPANION.IS_EXPORTING then
        return
    end
    local now = os.time()
    if now - COMPANION.LAST_EXPORT_TS < COMPANION.EXPORT_INTERVAL_SECONDS then
        return
    end
    COMPANION.IS_EXPORTING = true
    local ok, err = pcall(export_once)
    COMPANION.IS_EXPORTING = false
    if not ok then
        log_error("FC Companion: erro no maybe_export: " .. tostring(err))
    end
end

local function on_career_mode_event(event_id)
    safe_call(nil, append_event, event_id)
    safe_call(nil, maybe_export)
end

local function start_periodic_export()
    local started = false
    if type(RegisterFunction) == "function" then
        local ok1 = pcall(RegisterFunction, maybe_export, 10000)
        if ok1 then
            started = true
        else
            local ok2 = pcall(RegisterFunction, "FCCompanionTick", maybe_export, 10000)
            if ok2 then
                started = true
            end
        end
    end
    if not started then
        log_info("FC Companion: timer indisponível. Export por eventos ativo.")
    end
end

local function start_companion()
    COMPANION.LAST_EXPORT_TS = 0
    safe_call(nil, AddEventHandler, "pre__CareerModeEvent", on_career_mode_event)
    safe_call(nil, start_periodic_export)
    safe_call(nil, maybe_export)
    log_info("FC Companion: exportador híbrido iniciado.")
end

safe_call(nil, start_companion)
