# Modo Carreira: feed de notícias, redes sociais, mailbox e story (LE + memória + DB)

Este documento consolida **como o Live Editor expõe** os subsistemas do EA FC (FC 26) e **como avançar** para ler o feed “como no ecrã”, a caixa de eventos e a story engine. Não substitui reverse engineering: os **offsets dentro de cada `*Manager`** não vêm documentados no LE; o script `extractor/explore_cm_feed_managers.lua` serve para os fixar empiricamente.

---

## 1. Duas fontes de verdade

| Fonte | O que dá | Limitação |
|--------|-----------|-----------|
| **`LE.db` (T3DB)** | Tabelas do save em disco / metadados nomeados (`GetTable("career_*")`, `players`, `teams`, …) | Muitas UIs (feed social, fila de notícias “ao vivo”) podem existir **só em runtime** ou em tabelas com nomes opacos até listares o catálogo completo. |
| **Objetos C++ via `MEMORY` + `GetManagerObjByTypeId`** | Estado atual do modo carreira na RAM (filas, UI backing stores) | É preciso mapear **offsets por versão** do executável; `le_offsets.json` no LE é para outro propósito (assinaturas), não para estes managers. |

Para o companion, o fluxo típico é: **eventos** (`pre__CareerModeEvent`) + **IDs** (equipa, jogador, tipo de notícia) + **resolução de nomes** pela DB, e em paralelo **exploração de `SocialMediaManager` / `NewsManager`** para aproximar o texto que o jogo mostra.

---

## 2. Cadeia de ponteiros até aos “managers” do CM

Implementação em `lua/libs/v2/imports/career_mode/helpers.lua` (instalação do LE):

1. `GetPlugin(ENUM_djb2FeFceGMCommServiceInterface_CLSS)` → serviço de comunicação do modo carreira.
2. `MEMORY:ReadMultilevelPointer(comm_impl, {0x20, 0x10})` → array de entradas de managers.
3. Para o `type_id` N (`0x20 * N` a partir dessa base): verificar instância (`+0x10 == 1`, etc.).
4. `MEMORY:ReadMultilevelPointer(mode_manager, {0x18, 0x0})` → **ponteiro para o objeto manager** (o que queres inspecionar).

Função exposta: **`GetManagerObjByTypeId(type_id)`** — devolve endereço ou `0` se inexistente / não instanciado.

---

## 3. IDs relevantes (`career_mode/enums.lua`)

Subsistemas alinhados ao que pediste (nomes oficiais do enum LE):

| `type_id` | Constante | Papel provável no jogo |
|-----------|-----------|-------------------------|
| **38** | `FCECareerModeEmailManager` | E-mails / mensagens do CM (inbox de “correio”). |
| **41** | `FCECareerModeEventsMailBox` | Caixa de **eventos** (fila ligada a notificações / eventos de carreira). |
| **42** | `FCECareerModeEventsManager` | Orquestração/despacho de eventos de CM. |
| **43** | `FCECareerModeFCECommsManager` | Camada de comunicações (liga Email, UI e outros). |
| **68** | `FCECareerModeNewsManager` | Geração / gestão de **notícias** no CM (artigos, titulares, etc.). |
| **112** | `FCECareerModeStoryManager` | Motor de **story** genérico. |
| **113** | `FCECareerModeCareerStoryManager` | Arcos de história da carreira. |
| **115** | `FCECareerModeTournamentStoryManager` | Histórias ligadas a competições. |
| **117** | `FCECareerModeTalkToPressManager` | Coletivas / imprensa (relacionado com narrativa, não é o feed social completo). |
| **145** | `FCECareerModeSocialMediaManager` | **Rede social / feed** tipo o ecrã com post, likes e comentários. |

Outros úteis: `PersistentEventsManager` (70), `MainHubManager` (60), `FlowManager` (49).

---

## 4. Como o jogo “monta” o texto (modelo mental)

O ecrã do feed **não** precisa de guardar a frase completa em PT como único blob na RAM:

1. **Tipo de notícia / evento** — ex.: `ENUM_CM_EVENT_MSG_NEWS_WORTHY_TRANSFER_EVENT` (ver `career_mode/consts.lua` / `enums.lua`).
2. **Entidades** — IDs de `teamid`, `playerid`, e às vezes `journalist` / storyline.
3. **Templates de localização** — strings em `loc` + placeholders; o cliente monta “EXCLUSIVA: {Team} … {Player}”.
4. **Nomes** — resolvidos via tabelas `teams`, `players`, e tabelas de jornalistas / media se existirem na DB exportada.

Por isso o companion pode ficar **coerente com o jogo** mesmo antes de decodificar RAM: **mesmos IDs + mesmo tipo de evento + mesmas tabelas** → texto equivalente (ou via LLM com os mesmos factos).

---

## 5. Plugin `newsinterface` (serviço global)

Em `lua/libs/v2/imports/services/enums.lua`:

- `ENUM_djb2newsinterface_CLSS` / `INTERFACE`

Isto é um **serviço** do jogo (stack mais global que só CM). Pode ser uma segunda entrada para APIs de notícia; o LE não traz wrappers Lua prontos na pasta de scripts — vale experimentar `GetPlugin(ENUM_djb2newsinterface_CLSS)` e registar o endereço ao lado dos managers CM.

---

## 6. Tabelas no save (`LE.db`)

O vosso `save_parser` já usa várias `career_*`; **não** há hoje no parser uma tabela óbvia tipo `career_social_feed` — isso é normal.

Passos recomendados:

1. Com o jogo em **modo carreira** e save carregado, correr o script de exploração (ou um script que invoque `LE.db:Load()` e percorra `LE.db.tables`).
2. Filtrar nomes que contenham `news`, `social`, `story`, `mail`, `message`, `event`, `inbox`, `feed` (case insensitive).
3. Para cada candidata: `GetFirstRecord` / `GetRecordFieldValue` e ver colunas no meta do LE.

Assim descobris **o que é persistido** vs **só RAM**.

---

## 7. Próximos passos de engenharia (ordem sugerida)

1. Correr `explore_cm_feed_managers.lua` com o feed social **aberto no jogo** e com o CM **no hub** — comparar dumps quando a UI muda.
2. Fixar **um** offset estável (ex.: ponteiro para um `std::vector` de posts) dentro de `SocialMediaManager` — ferramenta típida: Cheat Engine + mesmo processo, ou repetir leituras no Lua.
3. Ligar `pre__CareerModeEvent` aos tipos `*NEWS*` para marcar “há novidade” e invalidar cache do companion.
4. Opcional: espelhar posts **reconstruídos** a partir de DB + eventos até a RAM estar mapeada.

---

## 8. Referência de código no repo

- `fc-companion/extractor/explore_cm_feed_managers.lua` — dump seguro de ponteiros + listagem de tabelas.
- `fc-companion/extractor/companion_export.lua` — exemplos de `GetPlugin` + `MEMORY` (`get_fce_data_manager`, standings, …).

Copia o `.lua` para a pasta de scripts do LE (`FCM 26\Live Editor\lua\scripts`) se quiseres executá-lo a partir da UI do editor.
