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
-- Evita repetir os.execute(mkdir) a cada export — no Windows isso pisca uma janela cmd.
COMPANION.OUTPUT_DIR_READY = false
COMPANION.SUBDIR_READY = {}

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
    if COMPANION.OUTPUT_DIR_READY then
        return true
    end
    local ok = os.rename(COMPANION.OUTPUT_DIR, COMPANION.OUTPUT_DIR)
    if ok then
        COMPANION.OUTPUT_DIR_READY = true
        return true
    end
    os.execute('mkdir "' .. COMPANION.OUTPUT_DIR .. '" >nul 2>nul')
    if os.rename(COMPANION.OUTPUT_DIR, COMPANION.OUTPUT_DIR) then
        COMPANION.OUTPUT_DIR_READY = true
        return true
    end
    return false
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
    if COMPANION.SUBDIR_READY[path] then
        return true
    end
    local ok = os.rename(path, path)
    if ok then
        COMPANION.SUBDIR_READY[path] = true
        return true
    end
    os.execute('mkdir "' .. path .. '" >nul 2>nul')
    if os.rename(path, path) then
        COMPANION.SUBDIR_READY[path] = true
        return true
    end
    return false
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
    -- O histórico na DB usa o clube do gestor (career_users.clubteamid). GetUserTeamID() por vezes
    -- diverge (ex.: contexto/nacional); priorizar clubteamid para bater com teamid/offerteamid.
    local function resolve_user_club_team_id_for_transfers()
        local tid = 0
        if LE and LE.db and LE.db.GetTable then
            local ut = safe_call(nil, LE.db.GetTable, LE.db, "career_users")
            if ut then
                local r = ut:GetFirstRecord()
                if r and r > 0 then
                    tid = to_number(ut:GetRecordFieldValue(r, "clubteamid"), 0)
                end
            end
        end
        if tid <= 0 then
            tid = to_number(safe_call(0, GetUserTeamID), 0)
        end
        if tid <= 0 then
            tid = to_number(((payload.club or {}).team_id), 0)
        end
        return tid
    end
    local user_team_id = resolve_user_club_team_id_for_transfers()
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
    local items_world = {}
    local seen = {}
    local seen_world = {}
    local presigned_rows_scanned = 0
    local user_club_id_seen_in_presigned = false
    -- Inclui transferências a título gratuito / futuras obrigações já assinadas (não só fee > 0).
    local function row_counts_as_transfer(fee, is_loan_buy, complete_date, signed_date)
        if fee > 0 then
            return true
        end
        if is_loan_buy ~= 0 then
            return true
        end
        if complete_date > 0 or signed_date > 0 then
            return true
        end
        return false
    end
    if transfer_table then
        local rec = transfer_table:GetFirstRecord()
        while rec and rec > 0 do
            presigned_rows_scanned = presigned_rows_scanned + 1
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
            local is_loan_move = (is_loan_buy ~= 0) or (fee <= 0 and complete_date > 0)
            local include_transfer = row_counts_as_transfer(fee, is_loan_buy, complete_date, signed_date)
            -- Global: grátis sem datas preenchidas no LE ainda assim são movimentos válidos (origem ≠ destino).
            local include_world = include_transfer
            if not include_world and player_id > 0 and from_team_id > 0 and offer_team_id > 0 and from_team_id ~= offer_team_id then
                if fee <= 0 and offered_fee <= 0 and future_fee <= 0 and is_loan_buy == 0 then
                    include_world = true
                end
            end
            if user_team_id > 0 and (from_team_id == user_team_id or offer_team_id == user_team_id) then
                user_club_id_seen_in_presigned = true
            end
            -- Histórico global ("Todos os clubes"): qualquer movimento com origem/destino válidos.
            if
                include_world
                and from_team_id > 0
                and offer_team_id > 0
                and from_team_id ~= offer_team_id
                and player_id > 0
            then
                local key_w = tostring(player_id)
                    .. "|"
                    .. tostring(signed_date)
                    .. "|"
                    .. tostring(from_team_id)
                    .. "|"
                    .. tostring(offer_team_id)
                    .. "|"
                    .. tostring(fee)
                if not seen_world[key_w] then
                    seen_world[key_w] = true
                    items_world[#items_world + 1] = {
                        id = "w:" .. key_w,
                        player_id = player_id,
                        player_name = player_name(player_id),
                        amount = fee,
                        fee = fee,
                        scope = "world",
                        is_loan = is_loan_move,
                        is_loan_buy = is_loan_buy,
                        signed_date = signed_date,
                        completed_date = complete_date,
                        period = format_period_from_raw_date(signed_date) or format_period_from_raw_date(complete_date),
                        from_team_id = from_team_id,
                        from_team_name = team_name(from_team_id),
                        to_team_id = offer_team_id,
                        to_team_name = team_name(offer_team_id),
                    }
                end
            end
            -- Meu clube: alinhado ao save_parser (Python) — compra exige clube de origem válido e != teu.
            if user_team_id > 0 then
                local is_buy = offer_team_id == user_team_id and from_team_id > 0 and from_team_id ~= user_team_id
                local is_sell = from_team_id == user_team_id and offer_team_id > 0 and offer_team_id ~= user_team_id
                local include_club = (is_buy or is_sell) and include_transfer
                if include_club then
                    local key = tostring(player_id)
                        .. "|"
                        .. tostring(signed_date)
                        .. "|"
                        .. tostring(offer_team_id)
                        .. "|"
                        .. tostring(from_team_id)
                        .. "|"
                        .. tostring(fee)
                    if not seen[key] then
                        seen[key] = true
                        local to_team_id = offer_team_id
                        local source_team_id = is_buy and from_team_id or user_team_id
                        items[#items + 1] = {
                            id = key,
                            player_id = player_id,
                            player_name = player_name(player_id),
                            amount = fee,
                            fee = fee,
                            type = is_buy and "buy" or "sell",
                            direction = is_buy and "in" or "out",
                            scope = "club",
                            is_loan = is_loan_move,
                            is_loan_buy = is_loan_buy,
                            signed_date = signed_date,
                            completed_date = complete_date,
                            period = format_period_from_raw_date(signed_date) or format_period_from_raw_date(complete_date),
                            from_team_id = source_team_id,
                            from_team_name = team_name(source_team_id),
                            to_team_id = to_team_id,
                            to_team_name = team_name(to_team_id),
                        }
                    end
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
    table.sort(items_world, function(a, b)
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
        items_world = items_world,
        meta = {
            export_version = "2.2.3",
            exported_at_iso = os.date("!%Y-%m-%dT%H:%M:%SZ"),
            exported_at_ts = os.time(),
            game_date = ((payload.meta or {}).game_date) or { day = nil, month = nil, year = nil },
            save_uid = save_uid,
            script_name = "companion_export.lua",
            source = "live_editor",
            user_club_team_id = user_team_id,
            user_club_id_seen_in_le_presigned = user_club_id_seen_in_presigned
        },
        summary = {
            count = #items,
            world_count = #items_world,
            incoming_count = incoming_count,
            outgoing_count = outgoing_count,
            presigned_rows_scanned = presigned_rows_scanned,
            presigned_table_available = transfer_table ~= nil,
            le_presigned_has_user_club_rows = user_club_id_seen_in_presigned
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

local function seed_user_team_names_into_cache()
    local team_id = to_number(safe_call(0, GetUserTeamID), 0)
    if team_id <= 0 or not LE or not LE.db or not LE.db.GetTable then
        return
    end
    local contract_table = LE.db:GetTable("career_playercontract")
    if contract_table == nil then
        return
    end
    local rec = contract_table:GetFirstRecord()
    while rec and rec > 0 do
        local row_team = to_number(contract_table:GetRecordFieldValue(rec, "teamid"), 0)
        if row_team == team_id then
            local player_id = to_number(contract_table:GetRecordFieldValue(rec, "playerid"), 0)
            if player_id > 0 then
                local name = safe_call("", GetPlayerName, player_id)
                if type(name) == "string" then
                    name = name:gsub("^%s+", ""):gsub("%s+$", "")
                    if name ~= "" then
                        COMPANION.NAME_CACHE[player_id] = name
                    end
                end
            end
        end
        rec = contract_table:GetNextValidRecord()
    end
end

function GetUserTeamLiveDbPlayers()
    local function run()
        local team_id = to_number(safe_call(0, GetUserTeamID), 0)
        if team_id <= 0 or not LE or not LE.db or not LE.db.GetTable then
            return {}
        end
        local contract_table = LE.db:GetTable("career_playercontract")
        local players_table = LE.db:GetTable("players")
        if contract_table == nil or players_table == nil then
            return {}
        end
        local wanted = {}
        local cr = contract_table:GetFirstRecord()
        while cr and cr > 0 do
            local row_team = to_number(contract_table:GetRecordFieldValue(cr, "teamid"), 0)
            if row_team == team_id then
                local player_id = to_number(contract_table:GetRecordFieldValue(cr, "playerid"), 0)
                if player_id > 0 then
                    wanted[player_id] = true
                end
            end
            cr = contract_table:GetNextValidRecord()
        end
        local out = {}
        local need = 0
        for _ in pairs(wanted) do
            need = need + 1
        end
        if need <= 0 then
            return {}
        end
        local found = 0
        local pr = players_table:GetFirstRecord()
        local guard = 0
        while pr and pr > 0 do
            guard = guard + 1
            if guard > 200000 then
                break
            end
            if need > 0 and found >= need then
                break
            end
            local player_id = to_number(players_table:GetRecordFieldValue(pr, "playerid"), 0)
            if wanted[player_id] and out[tostring(player_id)] == nil then
                local ovr_raw = players_table:GetRecordFieldValue(pr, "overallrating")
                local ovr = nil
                if ovr_raw ~= nil then
                    ovr = to_number(ovr_raw, nil)
                end
                -- Tabela players no LE/FC26 não expõe age/form/fitness/sharpness com estes nomes (gera erro por registo).
                out[tostring(player_id)] = {
                    overallrating = ovr,
                    preferredposition1 = to_number(players_table:GetRecordFieldValue(pr, "preferredposition1"), nil),
                    potential = to_number(players_table:GetRecordFieldValue(pr, "potential"), nil)
                }
                found = found + 1
            end
            pr = players_table:GetNextValidRecord()
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

local function read_live_transfer_budget()
    if type(GetUserTransferBudget) == "function" then
        return to_number(safe_call(0, GetUserTransferBudget), 0)
    end
    if type(GetTransferBudget) == "function" then
        return to_number(safe_call(0, GetTransferBudget), 0)
    end
    return 0
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

local function discover_finance_functions(team_id)
    local function run()
        local out = {}
        local tid = to_number(team_id, 0)
        local function store_value(name, value)
            if type(value) == "number" or type(value) == "string" or type(value) == "boolean" then
                out[name] = value
            elseif type(value) == "table" then
                out[name] = value
            elseif value ~= nil then
                out[name] = tostring(value)
            end
        end
        if type(GetUserTransferBudget) == "function" then
            store_value("GetUserTransferBudget", safe_call(nil, GetUserTransferBudget))
        end
        if tid > 0 and type(GetCPUTransferBudget) == "function" then
            store_value("GetCPUTransferBudget", safe_call(nil, GetCPUTransferBudget, tid))
        end
        local no_arg_names = {
            "GetUserWageBudget",
            "GetWageBudget",
            "GetCPUWageBudget",
            "GetClubWorth",
            "GetClubValue",
            "GetProjectedClubWorth",
            "GetProjectedClubValue",
            "GetFinanceOverview",
            "GetFinanceData"
        }
        for _, name in ipairs(no_arg_names) do
            local fn = _G[name]
            if type(fn) == "function" then
                local value = safe_call(nil, fn)
                store_value(name, value)
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
            transfer_budget_live = normalize_budget_value(read_live_transfer_budget()),
            manager_pref = manager_pref,
            manager_info = manager_info,
            manager_history = manager_history,
            contract_summary = contract_summary,
            transfer_summary = transfer_summary,
            discovered_function_values = discover_finance_functions(team_id),
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
        local transfer_budget_live = normalize_budget_value(read_live_transfer_budget())
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
            live_db_players = GetUserTeamLiveDbPlayers(),
            finance_live = finance_live,
            player_stats = safe_call({}, GetUserTeamPlayerStats, team_id),
            competition_player_stats = safe_call({
                competitions = {},
                competitions_club = {},
                competitions_general = {},
                source = "lua"
            }, GetCompetitionPlayerStats, team_id)
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
        live_db_players = {},
        finance_live = {},
        competition_player_stats = {
            competitions = {},
            competitions_club = {},
            competitions_general = {},
            source = "lua"
        }
    }, run)
end

--- LE.db:GetRecordFieldValue com nome inexistente gera ERROR no log do Live Editor; tentar vários nomes com pcall (FC 25/26).
local function db_field_number(tbl, rec, candidate_names)
    for _, n in ipairs(candidate_names) do
        local ok, v = pcall(function() return tbl:GetRecordFieldValue(rec, n) end)
        if ok and v ~= nil then
            return to_number(v, 0)
        end
    end
    return 0
end

--- Nome curto tipo "C1014" ou placeholder: tentar nome oficial (DOC.MD: GetCompetitionNameByObjID).
local function looks_like_placeholder_comp_name(s)
    if type(s) ~= "string" then return true end
    s = s:gsub("^%s+", ""):gsub("%s+$", "")
    if s == "" then return true end
    if s:match("^C%d+$") then return true end
    if s:match("^c%d+$") then return true end
    if s:match("^Competição %d+$") then return true end
    return false
end

local function resolve_competition_display_name(cid, fallback_short)
    cid = to_number(cid, 0)
    if cid <= 0 then return "Competição ?" end
    local fb = ""
    if type(fallback_short) == "string" then
        fb = fallback_short:gsub("^%s+", ""):gsub("%s+$", "")
    end
    if type(GetCompetitionNameByObjID) == "function" then
        local ok, gn = pcall(GetCompetitionNameByObjID, cid)
        if ok and type(gn) == "string" then
            local g = gn:gsub("^%s+", ""):gsub("%s+$", "")
            if g ~= "" and not looks_like_placeholder_comp_name(g) then
                return g
            end
            if g ~= "" and looks_like_placeholder_comp_name(fb) then
                fb = g
            end
        end
    end
    if fb ~= "" and not looks_like_placeholder_comp_name(fb) then return fb end
    if fb ~= "" then return fb end
    return "Competição " .. tostring(cid)
end

local function merge_comp_name_from_stat(comp_names, cid, compname)
    if type(compname) ~= "string" then return end
    local cn = compname:gsub("^%s+", ""):gsub("%s+$", "")
    if cn == "" then return end
    if not looks_like_placeholder_comp_name(cn) then
        comp_names[cid] = cn
    elseif looks_like_placeholder_comp_name(comp_names[cid]) then
        comp_names[cid] = cn
    end
end

--- Clube: só o teu elenco. Geral: todos os jogadores que o jogo expõe em GetPlayersStats para essas competições.
--- Nomes: GetCompetitionNameByObjID + compname das stats quando melhor que compshortname.
function GetCompetitionPlayerStats(team_id)
    local function run()
        local out = {
            competitions = {},
            competitions_club = {},
            competitions_general = {},
            source = "lua",
            source_club = "lua",
            source_general = "lua"
        }
        if not LE or not LE.db then return out end
        team_id = to_number(team_id, 0)
        if team_id <= 0 then return out end

        local squad_ids = {}
        local ct = LE.db:GetTable("career_playercontract")
        if ct then
            local r = ct:GetFirstRecord()
            while r and r > 0 do
                if to_number(ct:GetRecordFieldValue(r, "teamid"), 0) == team_id then
                    local pid = to_number(ct:GetRecordFieldValue(r, "playerid"), 0)
                    if pid > 0 then squad_ids[pid] = true end
                end
                r = ct:GetNextValidRecord()
            end
        end

        local comp_names = {}
        local pt = LE.db:GetTable("career_competitionprogress")
        if pt then
            local r = pt:GetFirstRecord()
            while r and r > 0 do
                if to_number(pt:GetRecordFieldValue(r, "teamid"), 0) == team_id then
                    local cid = to_number(pt:GetRecordFieldValue(r, "compobjid"), 0)
                    if cid > 0 then
                        local sn = pt:GetRecordFieldValue(r, "compshortname")
                        if type(sn) == "string" then
                            sn = sn:gsub("^%s+", ""):gsub("%s+$", "")
                        else
                            sn = ""
                        end
                        if sn ~= "" then
                            comp_names[cid] = sn
                        elseif comp_names[cid] == nil then
                            comp_names[cid] = "Competição " .. tostring(cid)
                        end
                    end
                end
                r = pt:GetNextValidRecord()
            end
        end

        for cid, nm in pairs(comp_names) do
            comp_names[cid] = resolve_competition_display_name(cid, nm)
        end

        local by_club = {}
        local by_general = {}
        for cid, _ in pairs(comp_names) do
            by_club[cid] = {}
            by_general[cid] = {}
        end

        local pp_by_pid = {}
        local function ensure_pp_map()
            if next(pp_by_pid) ~= nil then return end
            local pl = LE.db:GetTable("players")
            if not pl then return end
            local r = pl:GetFirstRecord()
            while r and r > 0 do
                local p = db_field_number(pl, r, { "playerid" })
                local pp = db_field_number(pl, r, { "preferredposition1" })
                if p > 0 then pp_by_pid[p] = pp end
                r = pl:GetNextValidRecord()
            end
        end

        local function position_label_for_pid(pid)
            if type(GetPlayerPrimaryPositionName) ~= "function" then return "" end
            ensure_pp_map()
            local pp = pp_by_pid[pid]
            if pp == nil then return "" end
            local ok, lab = pcall(GetPlayerPrimaryPositionName, pp)
            if ok and type(lab) == "string" then return lab end
            return ""
        end

        local api_hits_club = 0
        local api_hits_gen = 0
        if type(GetPlayersStats) == "function" then
            local ok_api, all_stats = pcall(GetPlayersStats)
            if ok_api and type(all_stats) == "table" then
                for i = 1, #all_stats do
                    local stat = all_stats[i]
                    if type(stat) == "table" then
                        local cid = to_number(stat.compobjid, 0)
                        local pid = to_number(stat.playerid, 0)
                        local app = to_number(stat.app, 0)
                        if cid > 0 and pid > 0 and comp_names[cid] ~= nil and app > 0 then
                            merge_comp_name_from_stat(comp_names, cid, stat.compname)
                            local goals = to_number(stat.goals, 0)
                            local assists = to_number(stat.assists, 0)
                            local y = to_number(stat.yellow, 0) + to_number(stat.two_yellow, 0)
                            local red = to_number(stat.red, 0)
                            local cs = to_number(stat.clean_sheets, 0)
                            local avg_raw = to_number(stat.avg, 0)
                            local rating_10 = 0
                            if app > 1 then
                                rating_10 = (avg_raw / app) / 10
                            elseif app == 1 then
                                rating_10 = avg_raw / 10
                            end
                            local tid = to_number(stat.teamid, 0)
                            local row_club = {
                                playerid = pid,
                                goals = goals,
                                assists = assists,
                                appearances = app,
                                clean_sheets = cs,
                                yellow_cards = y,
                                red_cards = red,
                                avg_rating_raw = rating_10
                            }
                            local row_gen = {
                                playerid = pid,
                                teamid = tid,
                                team_name = safe_call("", GetTeamName, tid),
                                player_name = safe_call("", GetPlayerName, pid),
                                position = position_label_for_pid(pid),
                                goals = goals,
                                assists = assists,
                                appearances = app,
                                clean_sheets = cs,
                                yellow_cards = y,
                                red_cards = red,
                                avg_rating_raw = rating_10
                            }
                            by_general[cid][#by_general[cid] + 1] = row_gen
                            api_hits_gen = api_hits_gen + 1
                            if squad_ids[pid] then
                                by_club[cid][#by_club[cid] + 1] = row_club
                                api_hits_club = api_hits_club + 1
                            end
                        end
                    end
                end
            end
        end

        if api_hits_club == 0 then
            out.source_club = "lua_career_playerstats_table"
            local pst = LE.db:GetTable("career_playerstats")
            if pst then
                local r = pst:GetFirstRecord()
                while r and r > 0 do
                    local cid = db_field_number(pst, r, { "compobjid", "compobjId", "competitionid" })
                    local pid = db_field_number(pst, r, { "playerid" })
                    if cid > 0 and pid > 0 and squad_ids[pid] and comp_names[cid] then
                        local goals = db_field_number(pst, r, { "goals", "leaguegoals", "totalgoals" })
                        local assists = db_field_number(pst, r, { "assists", "leagueassists", "totalassists" })
                        local apps = db_field_number(pst, r, { "appearances", "gamesplayed", "leaguegames", "numgames" })
                        local cs = db_field_number(pst, r, { "cleansheets", "leaguecleansheets" })
                        local y = db_field_number(pst, r, { "yellows", "yellowcards", "yellowcard" })
                        local red = db_field_number(pst, r, { "reds", "redcards", "redcard" })
                        local rating = db_field_number(pst, r, { "avgmatchrating", "averagestat", "rating", "lastmatchrating", "avgrating" })
                        by_club[cid][#by_club[cid] + 1] = {
                            playerid = pid,
                            goals = goals,
                            assists = assists,
                            appearances = apps,
                            clean_sheets = cs,
                            yellow_cards = y,
                            red_cards = red,
                            avg_rating_raw = rating
                        }
                    end
                    r = pst:GetNextValidRecord()
                end
            end
        else
            out.source_club = "lua_get_players_stats"
        end

        if api_hits_gen > 0 then
            out.source_general = "lua_get_players_stats"
        else
            out.source_general = "lua_no_general_data"
        end

        for cid, nm in pairs(comp_names) do
            comp_names[cid] = resolve_competition_display_name(cid, nm)
        end

        local list_club = {}
        local list_gen = {}
        for cid, name in pairs(comp_names) do
            list_club[#list_club + 1] = {
                competition_id = cid,
                competition_name = name,
                players = by_club[cid] or {}
            }
            list_gen[#list_gen + 1] = {
                competition_id = cid,
                competition_name = name,
                players = by_general[cid] or {}
            }
        end
        table.sort(list_club, function(a, b) return tostring(a.competition_name) < tostring(b.competition_name) end)
        table.sort(list_gen, function(a, b) return tostring(a.competition_name) < tostring(b.competition_name) end)
        out.competitions = list_club
        out.competitions_club = list_club
        out.competitions_general = list_gen
        out.source = out.source_club
        return out
    end
    return safe_call({
        competitions = {},
        competitions_club = {},
        competitions_general = {},
        source = "lua"
    }, run)
end

function GetUserTeamPlayerStats(team_id)
    local function run()
        if not LE or not LE.db then return {} end
        local tpl = LE.db:GetTable("teamplayerlinks")
        if tpl == nil then return {} end
        team_id = to_number(team_id, 0)
        local out = {}
        local rec = tpl:GetFirstRecord()
        while rec and rec > 0 do
            local row_team = db_field_number(tpl, rec, { "teamid" })
            if row_team == team_id then
                local pid = db_field_number(tpl, rec, { "playerid" })
                if pid > 0 then
                    -- FC 26 teamplayerlinks (schema real): leaguegoals, leagueappearances, yellows, reds, form…
                    -- NÃO usar leagueassists/leaguecleansheets aqui — o Live Editor regista ERROR no log mesmo com pcall.
                    -- Assistências / jogos sem sofrer gols vêm de career_playerstats (GetCompetitionPlayerStats / aba Estatísticas).
                    out[#out + 1] = {
                        playerid     = pid,
                        goals        = db_field_number(tpl, rec, { "leaguegoals", "goals" }),
                        assists      = 0,
                        appearances  = db_field_number(tpl, rec, { "leagueappearances", "appearances", "gamesplayed", "numgames" }),
                        clean_sheets = 0,
                        yellow_cards = db_field_number(tpl, rec, { "yellows", "yellowcards" }),
                        red_cards    = db_field_number(tpl, rec, { "reds", "redcards" }),
                        form         = db_field_number(tpl, rec, { "form" }),
                    }
                end
            end
            rec = tpl:GetNextValidRecord()
        end
        return out
    end
    return safe_call({}, run)
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
        safe_call(nil, seed_user_team_names_into_cache)
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
