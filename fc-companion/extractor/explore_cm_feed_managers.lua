--[[
  Exploração: ponteiros dos managers de CM relacionados com notícias, redes sociais,
  mailbox de eventos e story — para correr no Live Editor (FC 26) com o jogo em modo carreira.

  Uso: colar em Live Editor\lua\scripts\, executar com o save em CM carregado.
  Ideal: repetir com o ecrã do feed social aberto vs fechado e comparar logs.

  Dependências: imports oficiais do LE (helpers, enums, memory).
]]

require 'imports/career_mode/helpers'
require 'imports/career_mode/enums'
require 'imports/services/enums'

local function hex_byte(b)
    return string.format("%02X", b % 256)
end

--- Primeiros `max` bytes como hex (16 por linha), para inspeção manual.
local function dump_bytes(addr, max)
    max = max or 128
    if addr == nil or addr == 0 then
        return "(null)"
    end
    local ok, chunk = pcall(function()
        return MEMORY:ReadBytes(addr, max)
    end)
    if not ok or type(chunk) ~= "table" then
        return "(ReadBytes falhou)"
    end
    local lines = {}
    for i = 1, #chunk, 16 do
        local row = {}
        for j = 0, 15 do
            local idx = i + j
            if idx <= #chunk then
                row[#row + 1] = hex_byte(chunk[idx])
            end
        end
        lines[#lines + 1] = string.format("%04X  %s", i - 1, table.concat(row, " "))
    end
    return table.concat(lines, "\n")
end

local MANAGERS = {
    { "EmailManager", ENUM_FCEGameModesFCECareerModeEmailManager },
    { "EventsMailBox", ENUM_FCEGameModesFCECareerModeEventsMailBox },
    { "EventsManager", ENUM_FCEGameModesFCECareerModeEventsManager },
    { "FCECommsManager", ENUM_FCEGameModesFCECareerModeFCECommsManager },
    { "NewsManager", ENUM_FCEGameModesFCECareerModeNewsManager },
    { "StoryManager", ENUM_FCEGameModesFCECareerModeStoryManager },
    { "CareerStoryManager", ENUM_FCEGameModesFCECareerModeCareerStoryManager },
    { "TournamentStoryManager", ENUM_FCEGameModesFCECareerModeTournamentStoryManager },
    { "TalkToPressManager", ENUM_FCEGameModesFCECareerModeTalkToPressManager },
    { "SocialMediaManager", ENUM_FCEGameModesFCECareerModeSocialMediaManager },
}

local function log_block(title, body)
    if LOGGER and LOGGER.LogInfo then
        LOGGER:LogInfo("=== " .. title .. " ===\n" .. tostring(body))
    else
        print("=== " .. title .. " ===")
        print(tostring(body))
    end
end

local function try_list_db_tables(patterns)
    if LE == nil or LE.db == nil then
        log_block("LE.db", "LE.db indisponível")
        return
    end
    local ok, err = pcall(function()
        if LE.db.Load then
            LE.db:Load()
        end
    end)
    if not ok then
        log_block("LE.db:Load", tostring(err))
    end
    local tables = LE.db.tables
    if type(tables) ~= "table" then
        log_block("LE.db.tables", "tabela interna não exposta (versão diferente do LE)")
        return
    end
    local hits = {}
    for name, _ in pairs(tables) do
        local ln = string.lower(tostring(name))
        for _, p in ipairs(patterns) do
            if string.find(ln, p, 1, true) then
                hits[#hits + 1] = tostring(name)
                break
            end
        end
    end
    table.sort(hits)
    log_block(
        "Tabelas DB (filtro: news, social, story, mail, message, event, inbox, feed, notif)",
        #hits > 0 and table.concat(hits, "\n") or "(nenhum match — expande os padrões no script)"
    )
end

local function try_news_plugin()
    local ptr = GetPlugin(ENUM_djb2newsinterface_CLSS)
    log_block("GetPlugin(ENUM_djb2newsinterface_CLSS)", string.format("0x%X", tonumber(ptr) or 0))
end

--- Ponteiro plausível em espaço de utilizador Win64 (evita lixo).
local function plausible_ptr(p)
    p = tonumber(p) or 0
    return p > 0x10000 and p < 0x00007FFFFFFFFFFF
end

--- Lê qwords em `base+offsets` e faz dump curto de cada destino único (para achar vetores/listas de posts).
local function follow_qword_dumps(base, label, offsets, bytes_each)
    bytes_each = bytes_each or 96
    if not plausible_ptr(base) then
        return
    end
    local seen = {}
    for _, off in ipairs(offsets) do
        local child = MEMORY:ReadPointer(base + off)
        child = tonumber(child) or 0
        if plausible_ptr(child) and not seen[child] then
            seen[child] = true
            log_block(
                string.format("%s — follow %s+0x%X -> %s", label, label, off, string.format("0x%X", child)),
                dump_bytes(child, bytes_each)
            )
        end
    end
end

-- --- main ---
if not IsInCM() then
    log_block("CM", "IsInCM() == false — entra no modo carreira e recarrega o script.")
    return
end

try_news_plugin()

local social_ptr = 0

for _, row in ipairs(MANAGERS) do
    local label, tid = row[1], row[2]
    local ptr = GetManagerObjByTypeId(tid)
    local hex = string.format("0x%X", tonumber(ptr) or 0)
    log_block(string.format("%s (type_id=%d)", label, tid), hex)
    if ptr and ptr ~= 0 then
        log_block(string.format("%s — dump 128 bytes @ %s", label, hex), dump_bytes(ptr, 128))
        if tid == ENUM_FCEGameModesFCECareerModeSocialMediaManager then
            social_ptr = ptr
        end
    end
end

log_block(
    "Notas — managers a 0x0",
    "NewsManager(68), StoryManager(112), TournamentStoryManager(115) podem vir a null: lazy init, outro fluxo no FC 26, ou só instanciam noutro ecrã/fase. Volta a correr com: separador Notícias aberto, ou após simular um dia com headline."
)

-- Segundo nível: apontadores dentro do objeto (ajuda a localizar estruturas de feed).
if plausible_ptr(social_ptr) then
    follow_qword_dumps(
        social_ptr,
        "SocialMediaManager",
        { 0x10, 0x18, 0x20, 0x28, 0x30, 0x38, 0x40, 0x48, 0x50, 0x58, 0x60, 0x68, 0x70 },
        96
    )
end

try_list_db_tables({
    "news",
    "social",
    "story",
    "mail",
    "message",
    "event",
    "inbox",
    "feed",
    "notif",
    "press",
    "media",
    "journal",
})

log_block("Fim", "Compara duas execuções: hub CM vs ecrã rede social aberto.")
