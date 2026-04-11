"""Três respostas modelo por tema × tom × audiência — coerentes com a pauta (sem repetir adversário/placar fora de contexto)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

PRESS_THEMES = frozenset({"match", "form", "player", "market", "board", "medical", "locker_room", "season"})

THEME_LABEL_PT: Dict[str, str] = {
    "match": "PARTIDA E RESULTADO RECENTE",
    "form": "FORMA E SEQUENCIA DE RESULTADOS",
    "player": "DESEMPENHO INDIVIDUAL E ESCALAÇÃO",
    "market": "MERCADO, JANELA E RUMORES",
    "board": "DIRETORIA E COBRANÇA INSTITUCIONAL",
    "medical": "PARTE FISICA, LESOES E MINUTOS",
    "locker_room": "VESTIÁRIO E CLIMA INTERNO",
    "season": "TABELA, CALENDÁRIO E OBJETIVOS",
}


def normalize_topic(topic_type: Optional[str]) -> str:
    t = (topic_type or "").strip().lower()
    return t if t in PRESS_THEMES else "season"


def question_hook(question: str, club: str, opp: str, topic: str) -> str:
    q = (question or "").strip()
    low = q.lower()
    if topic == "market":
        return "Sobre mercado, janela e o barulho em volta do elenco, "
    if topic == "medical":
        return "Sobre físico, gestão de minutos e critério do departamento médico, "
    if topic == "board":
        return "Sobre alinhamento com a diretoria e expectativa institucional, "
    if topic == "locker_room":
        return "Sobre ambiente interno e clima de grupo, "
    if topic == "player":
        return "Sobre papéis individuais, minutos e hierarquia técnica, "
    if topic == "season":
        return "Sobre o que a temporada e a classificação exigem de nós, "
    if topic == "form":
        return "Sobre a sequência recente de resultados e o que ela mostra, "
    if topic == "match":
        if " x " in low or " contra " in low:
            return "Sobre o confronto e o contexto desse jogo, "
        return "Sobre o último jogo e a leitura que fazemos dele, "
    if len(q) < 12:
        return f"Olhando para o {club} neste momento, "
    if " x " in low or " contra " in low or "tabela" in low:
        return "Sobre a pauta que vocês trouxeram, "
    return "Sobre o que foi perguntado, "


def _t(style: str, aud: str, bank: Dict[tuple, List[str]]) -> List[str]:
    key = (style, aud)
    if key in bank:
        return bank[key]
    if (style, "staff") in bank:
        return bank[(style, "staff")]
    return bank.get(("analytical", "staff"), [
        "Eu respondo com foco no processo e no que controlamos no dia a dia.",
        "Minha prioridade é clareza técnica e coerência com o elenco.",
        "O trabalho no CT é o que sustenta qualquer mensagem pública.",
    ])


def options_for_topic(
    topic: str,
    style_l: str,
    aud: str,
    ctx: Dict[str, Any],
    open_ref: str,
    club: str,
    stakes: str,
    comp_next: str,
    opp: str,
    last_frag: str,
    last_score: str,
    rank: Optional[int],
    pts: Optional[int],
    tcomp: str,
    inj: int,
    fatigue: Optional[float],
) -> List[str]:
    o, c = open_ref, club
    comp = comp_next
    sc = last_score
    opp_n = opp or "o adversário"
    tbl = ""
    if rank is not None and pts is not None and tcomp:
        tbl = f"na {tcomp}, estamos na {rank}ª colocação com {pts} pontos"
    med_note = ""
    if inj > 0:
        med_note = f"com {inj} desfalque(s) no radar do DM"
    elif fatigue is not None and float(fatigue) >= 55:
        med_note = "com desgaste acumulado que monitoramos de perto"
    else:
        med_note = "com recuperação e cargas bem desenhadas"

    if topic == "market":
        bank: Dict[tuple, List[str]] = {
            ("aggressive", "board"): [
                f"{o}eu não alimento novela: mercado é assunto fechado com diretoria e com critério técnico — o dia a dia do {c} é treino e competição.",
                f"{o}especulação não escala time. Quem está aqui tem meu foco total; o resto é ruído que não entra no vestiário.",
                f"{o}janela existe, mas quem manda no elenco sou eu. Decisão séria não se faz por manchete.",
            ],
            ("aggressive", "players"): [
                f"{o}eu quero cabeça no lugar: quem veste a camisa precisa ignorar rumor e trabalhar. Confiança se ganha em campo, não em portal.",
                f"{o}cobrança minha é interna — mercado não define titular. Mostra no treino quem quer jogar.",
                f"{o}barulho externo não pode virar distração. Fechamos o grupo no que importa: próximo treino e próximo jogo.",
            ],
            ("aggressive", "staff"): [
                f"{o}eu corto especulação na origem: pauta de mercado não muda nosso planejamento microciclo a microciclo.",
                f"{o}rumor não substitui vídeo-borradura nem relatório médico. A comissão segue o plano com rigor.",
                f"{o}o foco do {c} é esporte: contratação e saída, quando houver, serão comunicadas no tempo certo — não agora em tom de novela.",
            ],
            ("calm", "board"): [
                f"{o}eu separo bem rumor de decisão. Com a diretoria alinhamos o que for estratégico; publicamente protejo o elenco.",
                f"{o}a janela gera perguntas, mas minha mensagem para o grupo é estabilidade: trabalho, foco e respeito a quem está aqui.",
                f"{o}entendo o interesse da imprensa, porém o {c} precisa de serenidade — mercado não pode roubar a energia da {comp}.",
            ],
            ("calm", "players"): [
                f"{o}eu converso com quem precisa, mas não vou expor nome em coletiva. O elenco sabe: confiança vem de postura diária.",
                f"{o}mercado faz parte do futebol, não do nosso estado emocional no CT. Mantemos rotina e critério.",
                f"{o}quem está no plantel tem prioridade; o resto é gestão interna — sem drama público.",
            ],
            ("calm", "staff"): [
                f"{o}eu e minha comissão filtramos o ruído: o planejamento segue centrado em quem está disponível e na {comp}.",
                f"{o}rumores não alteram cargas nem vídeo do dia. O processo é o mesmo: análise, saúde do grupo, decisão técnica.",
                f"{o}a reta decisiva pede cabeça fria — janela não pode virar tema único de conversa no vestiário.",
            ],
            ("motivational", "board"): [
                f"{o}eu acredito no elenco que temos hoje: orgulho, trabalho e ambição responsável — mercado não apaga isso.",
                f"{o}a torcida pode confiar: nosso combustível é grupo fechado e foco na {comp}, não em especulação.",
                f"{o}onde há trabalho forte há caminho — e é isso que vendo no dia a dia, independente do barulho de fora.",
            ],
            ("motivational", "players"): [
                f"{o}eu confio em vocês que estão aqui — provamos juntos que resultado vem de entrega, não de notícia.",
                f"{o}mantenham a cabeça no que controlamos: treino, união e vontade. O resto a gente resolve nos bastidores.",
                f"{o}o {c} é feito de gente que abraça a camisa; isso é o que importa para a torcida ver em campo.",
            ],
            ("motivational", "staff"): [
                f"{o}nós seguimos confiantes no processo: mercado é ciclo, mas identidade e trabalho diário são o que sustentam o {c}.",
                f"{o}a energia correta é olhar para frente com o grupo atual — com foco e confiança na {comp}.",
                f"{o}eu acredito no caminho: cada treino bem feito responde melhor à torcida do que qualquer rumor.",
            ],
            ("analytical", "board"): [
                f"{o}eu trato mercado como variável de gestão, não como tema de coletiva diária: critério, timing e encaixe técnico valem mais que barulho.",
                f"{o}decisões passam por análise de elenco, financeiro e desempenho — não por narrativa de janela.",
                f"{o}o que posso garantir é processo: transparência interna com a diretoria e mensagem estável para o grupo.",
            ],
            ("analytical", "players"): [
                f"{o}eu avalio nome por treino e jogo; rumor não entra na planilha. Hierarquia é campo + critério.",
                f"{o}separo informação de especulação: o elenco recebe o que é factual — o resto não ajuda performance.",
                f"{o}minutos e funções seguem leitura técnica; mercado não muda isso da noite para o dia.",
            ],
            ("analytical", "staff"): [
                f"{o}nossa análise segue microciclos, disponibilidade e adversário — não feed de transferência.",
                f"{o}eu priorizo dados de desempenho e saúde do grupo; janela entra só quando há decisão madura.",
                f"{o}o planejamento tático e físico permanece; rumor externo não vira variável no nosso modelo.",
            ],
        }
        return _t(style_l, aud, bank)

    if topic == "match":
        sc_bit = f" O último placar ({sc}) entra na nossa leitura técnica." if sc else ""
        opp_bit = f" Contra {opp_n} o desafio é outro — respeito, mas o nosso padrão tem que aparecer." if opp else ""
        bank = {
            ("aggressive", "board"): [
                f"{o}eu quero resultado e postura {stakes}o {c} não pode relaxar após o que mostrou em campo.{sc_bit}",
                f"{o}cobrança é máxima: o último jogo ditou o tom e a sequência exige consistência.{sc_bit}",
                f"{o}o que importa agora é manter intensidade — vitória boa não dá folga para o próximo compromisso.{sc_bit}",
            ],
            ("aggressive", "players"): [
                f"{o}eu quero ver o mesmo foco de jogo no treino: nada de achismo — execução e competição por vaga.{sc_bit}",
                f"{o}o grupo precisa provar que o último resultado não foi acaso.{sc_bit}",
                f"{o}cada posição é disputada; quem cair na complacência perde minutos.",
            ],
            ("aggressive", "staff"): [
                f"{o}a comissão não dá brecha: análise do rival, recuperação e clareza tática — tudo no mais alto nível.{opp_bit or sc_bit}",
                f"{o}eu exijo detalhe: o próximo jogo começa no vídeo de hoje.{sc_bit}",
                f"{o}padrão ofensivo e defensivo precisam subir — o último jogo mostrou onde ajustar.{sc_bit}",
            ],
            ("calm", "board"): [
                f"{o}eu leio o último jogo com equilíbrio: pontos fortes para manter e arestas para lapidar.{sc_bit}",
                f"{o}tranquilidade não é moleza — é método para não perder o que funcionou.{sc_bit}",
                f"{o}vamos seguir o plano sem euforia exagerada: futebol pede consistência.{sc_bit}",
            ],
            ("calm", "players"): [
                f"{o}eu valorizo o que fizeram, mas o foco já é o próximo passo — cabeça disciplinada.{sc_bit}",
                f"{o}confiança sim, relaxamento não. O elenco sabe da minha cobrança construtiva.{sc_bit}",
                f"{o}celebrar rápido e voltar ao trabalho: é assim que time grande age.{sc_bit}",
            ],
            ("calm", "staff"): [
                f"{o}fechamos a leitura do jogo com calma: cargas e ideia tática alinhadas ao que vem.{opp_bit or sc_bit}",
                f"{o}o processo continua organizado — cada área sabe o que ajustar após o último resultado.{sc_bit}",
                f"{o}eu prefiro clareza a volume: menos ruído, mais precisão no treino.{sc_bit}",
            ],
            ("motivational", "board"): [
                f"{o}eu acredito no que esse grupo mostrou — trabalho e confiança nos levam adiante.{sc_bit}",
                f"{o}a torcida pode se orgulhar da entrega; nosso desafio é manter essa chama.{sc_bit}",
                f"{o}vitória fortalece o vestiário — e nós vamos usar isso com responsabilidade.{sc_bit}",
            ],
            ("motivational", "players"): [
                f"{o}eu confio em vocês: o que fizemos em campo veio de união — vamos repetir a dose de compromisso.{sc_bit}",
                f"{o}essa energia positiva é nosso combustível para a sequência.{sc_bit}",
                f"{o}juntos somos mais fortes — e o próximo desafio já nos espera.{sc_bit}",
            ],
            ("motivational", "staff"): [
                f"{o}a comissão está alinhada e confiante no trabalho — seguimos com foco e orgulho no {c}.{opp_bit or sc_bit}",
                f"{o}eu acredito no processo: cada detalhe do último jogo nos dá base para crescer.{sc_bit}",
                f"{o}vamos com humildade e ambição — duas coisas que não se contradizem.{sc_bit}",
            ],
            ("analytical", "board"): [
                f"{o}eu separo o que foi sustentável taticamente do que foi momento — métrica e vídeo mostram o caminho.{sc_bit}",
                f"{o}a leitura técnica aponta ajustes pontuais sem reinventar o time do dia para a noite.{sc_bit}",
                f"{o}performance ofensiva e transição merecem destaque; agora é repetir padrão com mais consistência.{sc_bit}",
            ],
            ("analytical", "players"): [
                f"{o}minutos e papéis seguem o que o campo provou — critério, não impulso.{sc_bit}",
                f"{o}eu olho indicadores de esforço e decisão: quem entregou continuidade ganha confiança.{sc_bit}",
                f"{o}a escalação reflete treino e necessidade do modelo — não narrativa.{sc_bit}",
            ],
            ("analytical", "staff"): [
                f"{o}estruturamos o microciclo com base no último desempenho e no próximo cenário.{opp_bit or sc_bit}",
                f"{o}vídeo, dados e saúde do grupo definem o plano — sem achismo.{sc_bit}",
                f"{o}o foco é repetir o que funcionou e corrigir o que custou chances.{sc_bit}",
            ],
        }
        return _t(style_l, aud, bank)

    if topic == "form":
        bank = {
            ("aggressive", "board"): [
                f"{o}eu não vendo ilusão: sequência boa exige mais exigência, não menos — o {c} precisa subir o nível na {comp}.",
                f"{o}tendência só vira realidade com trabalho diário — cobrança continua alta.",
                f"{o}resultados recentes autorizam confiança, não conforto.",
            ],
            ("aggressive", "players"): [
                f"{o}eu quero fome de jogo — quem achar que já provou tudo vai perder espaço.",
                f"{o}a forma vem de treino e de mentalidade; nada está garantido.",
                f"{o}cada jogo é novo exame — passado não joga por você.",
            ],
            ("aggressive", "staff"): [
                f"{o}a comissão eleva o padrão: boa fase é janela para corrigir detalhes antes que virem problema.",
                f"{o}eu exijo evolução tática mesmo quando o resultado ajuda — isso separa time grande.",
                f"{o}vamos apertar o que já funciona para não estagnar.",
            ],
            ("calm", "board"): [
                f"{o}eu leio a sequência com cautela otimista: há sinais claros, mas a {comp} pune vacilo.",
                f"{o}mantemos os pés no chão: tendência positiva precisa de gestão emocional.",
                f"{o}o grupo entende que regularidade é o próximo degrau.",
            ],
            ("calm", "players"): [
                f"{o}eu confio na trajetória, mas peço humildade — futebol muda rápido.",
                f"{o}celebramos o que foi feito e já corrigimos o que falta.",
                f"{o}o foco é repetir padrão, não buscar herói solitário.",
            ],
            ("calm", "staff"): [
                f"{o}ajustamos cargas e ideias para sustentar a forma sem esgotar o elenco.",
                f"{o}a leitura interna é de crescimento gradual — sem euforia nem pessimismo.",
                f"{o}fechamos cada semana olhando dados e sensação do grupo.",
            ],
            ("motivational", "board"): [
                f"{o}eu acredito que estamos no caminho certo — trabalho e união aparecem nos números e no olhar do time.",
                f"{o}a confiança do {c} cresce quando o processo é sério — e é isso que vendo.",
                f"{o}quero levar essa energia para a torcida com responsabilidade e ambição.",
            ],
            ("motivational", "players"): [
                f"{o}vocês estão de parabéns pelo momento — agora é manter o foco e a fome.",
                f"{o}eu confio no grupo: seguimos juntos com orgulho e humildade.",
                f"{o}cada vitória ou empate construtivo nos aproxima do que queremos.",
            ],
            ("motivational", "staff"): [
                f"{o}a comissão sente o grupo confiante — vamos alimentar isso com trabalho bem feito.",
                f"{o}eu acredito no que estamos construindo; a sequência mostra identidade.",
                f"{o}confiança vem de preparação — e nós preparamos bem.",
            ],
            ("analytical", "board"): [
                f"{o}eu separo tendência de certeza: os dados mostram evolução, mas o calendário ainda vai testar o elenco.",
                f"{o}olho xG, consistência defensiva e minutos — forma é pacote, não um jogo isolado.",
                f"{o}a leitura é positiva com ressalvas táticas que já estamos tratando.",
            ],
            ("analytical", "players"): [
                f"{o}minutos seguem performance e necessidade do modelo — boa fase não trava rotação se o time precisa fresco.",
                f"{o}eu avalio sustentabilidade: ritmo, lesão e opção tática.",
                f"{o}cada posição tem indicadores claros — critério acima de narrativa.",
            ],
            ("analytical", "staff"): [
                f"{o}estruturamos a semana para manter indicadores físicos e táticos alinhados.",
                f"{o}a forma reflete processo — microciclos e vídeo sustentam o que vem em campo.",
                f"{o}eu priorizo previsibilidade de desempenho, não só resultado pontual.",
            ],
        }
        return _t(style_l, aud, bank)

    if topic == "player":
        bank = {
            ("aggressive", "board"): [
                f"{o}eu não exponho jogador para aplaudir ou crucificar em público — decisão é técnica e interna.",
                f"{o}cobrança existe, mas respeito ao atleta: quem não entrega no padrão sente no time.",
                f"{o}hierarquia é campo; narrativa externa não manda no meu grupo.",
            ],
            ("aggressive", "players"): [
                f"{o}eu sou claro: titularidade se conquista todo dia — ninguém tem vaga eterna.",
                f"{o}quem quiser minutos que domine o treino e o jogo — simples assim.",
                f"{o}eu cobro liderança dentro de campo, não entrevista bonita.",
            ],
            ("aggressive", "staff"): [
                f"{o}a comissão trabalha perfil e função — nome não entra na equação antes do mérito.",
                f"{o}eu exijo leitura fria: estatística, esforço e comportamento.",
                f"{o}ajuste tático pode mudar papel de qualquer um — preparação decide.",
            ],
            ("calm", "board"): [
                f"{o}eu converso com o grupo e protejo o elenco; caso a caso fica no CT.",
                f"{o}minha função é dar critério estável — nem hype nem linchamento público.",
                f"{o}o {c} precisa de serenidade para desenvolver jogadores com responsabilidade.",
            ],
            ("calm", "players"): [
                f"{o}eu confio no trabalho individual, mas o coletivo manda — função importa tanto quanto talento.",
                f"{o}cada um sabe o que precisa melhorar; meu papel é orientar com clareza.",
                f"{o}eu valorizo quem aceita o papel do time acima do holofote.",
            ],
            ("calm", "staff"): [
                f"{o}definimos papéis com calma: vídeo, dados e conversa direta com o atleta.",
                f"{o}eu evito polarizar nome na imprensa — isso atrapalha evolução.",
                f"{o}o plano é técnico: minutos e posição seguem necessidade do modelo.",
            ],
            ("motivational", "board"): [
                f"{o}eu acredito no potencial do elenco — desenvolvimento é processo e exige paciência responsável.",
                f"{o}quem trabalha forte encontra espaço; eu sou o primeiro a valorizar isso.",
                f"{o}o {c} cresce quando cada jogador se sente parte do projeto.",
            ],
            ("motivational", "players"): [
                f"{o}eu confio em vocês — mostrem personalidade e respeito ao grupo que a hierarquia se acerta.",
                f"{o}cada um tem chance de brilhar dentro do coletivo — é assim que ganhamos.",
                f"{o}orgulho da camisa e trabalho diário abrem portas.",
            ],
            ("motivational", "staff"): [
                f"{o}a comissão está junto do elenco para elevar individualidades sem quebrar o time.",
                f"{o}eu acredito que com método cada jogador pode dar um passo a mais.",
                f"{o}motivação vem de clareza de função e de confiança mútua.",
            ],
            ("analytical", "board"): [
                f"{o}eu separo exposição midiática de gestão esportiva — decisões são técnicas e documentadas internamente.",
                f"{o}leio desempenho por métricas de impacto, não por opinião solta.",
                f"{o}o modelo tático define quem encaixa melhor em cada momento da {comp}.",
            ],
            ("analytical", "players"): [
                f"{o}minutos respondem a necessidade do jogo e a cargas — não a pressão de rede social.",
                f"{o}eu avalio consistência, não lampejo — time grande precisa de regularidade.",
                f"{o}cada posição tem checklist técnico; quem cumpre ganha confiança.",
            ],
            ("analytical", "staff"): [
                f"{o}estruturamos individual com vídeo e dados, sempre ligado ao coletivo.",
                f"{o}eu priorizo encaixe tático e disponibilidade física na escolha de nomes.",
                f"{o}a leitura é objetiva: função, adversário e momento da temporada.",
            ],
        }
        return _t(style_l, aud, bank)

    if topic == "board":
        bank = {
            ("aggressive", "board"): [
                f"{o}eu assumo a pressão {stakes}resultado é o termômetro e eu não fujo disso.",
                f"{o}a cobrança da diretoria é legítima — minha resposta é trabalho e entrega imediata.",
                f"{o}eu não prometo discurso bonito; prometo organização e competência para reagir.",
            ],
            ("aggressive", "players"): [
                f"{o}o clube espera mais — e eu cobro isso de cada atleta, todo dia.",
                f"{o}instituição acima de conforto individual: quem não estiver alinhado sente.",
                f"{o}eu quero grupo que entenda o tamanho da responsabilidade.",
            ],
            ("aggressive", "staff"): [
                f"{o}a comissão responde junto: padrão alto e zero desculpa esportiva.",
                f"{o}eu e meus auxiliares assumimos o plano — execução tem que subir.",
                f"{o}cada área precisa entregar mais para o {c} reagir com resultado e clareza.",
            ],
            ("calm", "board"): [
                f"{o}eu prefiro diálogo claro com a diretoria: alinhamento de expectativa e transparência no que controlamos.",
                f"{o}pressão faz parte — minha postura é calma para decidir melhor.",
                f"{o}o {c} precisa de estabilidade de mensagem e de método.",
            ],
            ("calm", "players"): [
                f"{o}eu protejo o elenco, mas todos sabem o que a instituição espera.",
                f"{o}confiança e cobrança caminham juntas — sem drama, com critério.",
                f"{o}o grupo está informado do cenário e focado no trabalho.",
            ],
            ("calm", "staff"): [
                f"{o}fechamos o planejamento com serenidade: menos ruído, mais execução.",
                f"{o}a relação com a diretoria passa por fatos e plano — é assim que eu conduzo.",
                f"{o}eu e a comissão entregamos relatório claro do que precisa mudar.",
            ],
            ("motivational", "board"): [
                f"{o}eu acredito no projeto e quero que a diretoria veja o mesmo orgulho de trabalho que eu vejo no CT.",
                f"{o}juntos podemos reagir — união institucional é fundamental.",
                f"{o}o {c} tem gente competente; agora é converter trabalho em resultado estável.",
            ],
            ("motivational", "players"): [
                f"{o}eu confio no grupo para responder à expectativa do clube com garra.",
                f"{o}vamos mostrar que merecemos a confiança com entrega em campo.",
                f"{o}a torcida e a diretoria querem o mesmo que nós: vitória com identidade.",
            ],
            ("motivational", "staff"): [
                f"{o}a comissão está motivada a dar resposta com trabalho intenso e alinhado.",
                f"{o}eu acredito que com método e união revertemos qualquer pressão.",
                f"{o}o caminho é esporte sério — e nós vivemos isso 24 horas.",
            ],
            ("analytical", "board"): [
                f"{o}eu separo gestão de resultado: entrego indicadores, plano de curto prazo e leitura de risco {stakes}",
                f"{o}transparência com a diretoria é base de critério técnico, não de promessa vazia.",
                f"{o}o que proponho é processo mensurável — evolução em campo e em números.",
            ],
            ("analytical", "players"): [
                f"{o}eu traduzo cobrança institucional em metas claras para o elenco.",
                f"{o}cada jogador sabe o que o clube espera em desempenho e postura.",
                f"{o}a mensagem interna é objetiva: foco, trabalho e responsabilidade.",
            ],
            ("analytical", "staff"): [
                f"{o}a comissão documenta ajustes e presta contas do plano com clareza.",
                f"{o}eu priorizo decisões baseadas em dado e em saúde do elenco.",
                f"{o}o alinhamento com a diretoria passa por relatório e execução semanal.",
            ],
        }
        return _t(style_l, aud, bank)

    if topic == "medical":
        bank = {
            ("aggressive", "board"): [
                f"{o}eu não negocio saúde do atleta — disponibilidade manda na escalação e ponto final.",
                f"{o}o DM tem autonomia técnica; eu cobro agilidade, mas não pressa irresponsável.",
                f"{o}quem não está bem não entra — o {c} precisa de jogador inteiro.",
            ],
            ("aggressive", "players"): [
                f"{o}eu quero honestidade no corpo: sinal de dor tem que vir cedo, não no aquecimento.",
                f"{o}disponibilidade é profissionalismo — cuidar de si é ajudar o time.",
                f"{o}ninguém ganha minuto lesionado; recuperação é parte do trabalho.",
            ],
            ("aggressive", "staff"): [
                f"{o}a comissão ajusta carga sem piedade quando o dado pede — performance exige corpo pronto.",
                f"{o}eu exijo comunicação médica clara todo dia — sem surpresa.",
                f"{o}prevenção e recuperação são prioridade máxima.",
            ],
            ("calm", "board"): [
                f"{o}eu gerencio elenco com critério médico {med_note}; decisão esportiva respeita o corpo.",
                f"{o}transparência com a diretoria sobre risco de lesão é inegociável.",
                f"{o}o calendário é puxado, mas eu não sacrifico atleta por uma escalação.",
            ],
            ("calm", "players"): [
                f"{o}eu confio no DM e peço que vocês confiem no processo de recuperação.",
                f"{o}rodízio e minutos existem para proteger o grupo na sequência.",
                f"{o}cada um tem papel na prevenção: sono, nutrição e honestidade no treino.",
            ],
            ("calm", "staff"): [
                f"{o}fechamos microciclo olhando fadiga e histórico — método evita improviso.",
                f"{o}a integração médica-tática é diária; é assim que protegemos o {c}.",
                f"{o}eu prefiro um jogador a menos no banco do que um a mais no departamento.",
            ],
            ("motivational", "board"): [
                f"{o}eu acredito que com gestão certa o elenco aguenta a maratona — confiança no trabalho de prevenção.",
                f"{o}o grupo está comprometido com recuperação; isso nos dá fôlego.",
                f"{o}vamos chegar inteiro nos momentos decisivos.",
            ],
            ("motivational", "players"): [
                f"{o}eu confio em vocês para se cuidarem — time forte é time disponível.",
                f"{o}cada treino bem recuperado é passo para vencer no fim de semana.",
                f"{o}juntos equilibramos esforço e saúde.",
            ],
            ("motivational", "staff"): [
                f"{o}a comissão está unida para manter o grupo fresco e confiante fisicamente.",
                f"{o}eu acredito no trabalho do DM e na disciplina do elenco.",
                f"{o}energia no campo começa no cuidado no CT.",
            ],
            ("analytical", "board"): [
                f"{o}eu separo risco de retorno: decisões seguem protocolo e leitura de carga {med_note}.",
                f"{o}os números de desgaste orientam rodízio — não opinião solta.",
                f"{o}minha função é equilibrar calendário e performance com segurança.",
            ],
            ("analytical", "players"): [
                f"{o}minutos e titularidade refletem disponibilidade e necessidade tática.",
                f"{o}eu uso dados de esforço para proteger e para exigir no momento certo.",
                f"{o}a escalação honra quem está apto e o modelo do jogo.",
            ],
            ("analytical", "staff"): [
                f"{o}estruturamos treino com monitoramento — integração médica e tática é padrão.",
                f"{o}eu priorizo previsibilidade física para o modelo de jogo funcionar.",
                f"{o}cada sessão tem objetivo claro de carga e recuperação.",
            ],
        }
        return _t(style_l, aud, bank)

    if topic == "locker_room":
        bank = {
            ("aggressive", "board"): [
                f"{o}internamente eu cobro lealdade ao grupo — problema se resolve porta fechada, não na imprensa.",
                f"{o}o {c} precisa de vestiário forte; divergência vira trabalho ou vira banco.",
                f"{o}eu não tolero fissura pública — união ou ajuste imediato.",
            ],
            ("aggressive", "players"): [
                f"{o}eu quero respeito mútuo no dia a dia — cabeça no time, não no ego.",
                f"{o}quem atrapalhar o ambiente sente na hora — padrão comportamental é lei.",
                f"{o}liderança se prova dentro do grupo, não em entrevista.",
            ],
            ("aggressive", "staff"): [
                f"{o}a comissão observa sinais cedo e age — clima ruim vira plano de correção.",
                f"{o}eu exijo comunicação direta com jogadores — sem ruído.",
                f"{o}vestiário ganha com disciplina e exemplo.",
            ],
            ("calm", "board"): [
                f"{o}eu cuido do ambiente com diálogo e limites claros — estabilidade é prioridade.",
                f"{o}protejo o elenco, mas cobro maturidade coletiva.",
                f"{o}o {c} precisa de segurança emocional para performar.",
            ],
            ("calm", "players"): [
                f"{o}eu confio no núcleo do grupo e peço que resolvam conflitos com respeito.",
                f"{o}cada um é responsável pelo clima — começa no treino.",
                f"{o}união não é discurso vazio; é postura diária.",
            ],
            ("calm", "staff"): [
                f"{o}monitoramos clima com a mesma seriedade que vídeo tático.",
                f"{o}eu e os auxiliares conversamos com líderes do grupo para manter o eixo.",
                f"{o}prefiro antecipar problema do que apagar incêndio.",
            ],
            ("motivational", "board"): [
                f"{o}eu acredito no caráter desse elenco — juntos saímos de qualquer turbulência.",
                f"{o}o vestiário é nossa fortaleza; vamos fortalecer laços com trabalho.",
                f"{o}confiança e humildade constroem time grande.",
            ],
            ("motivational", "players"): [
                f"{o}eu confio em vocês para segurarem o grupo com maturidade e garra.",
                f"{o}juntos somos mais fortes — isso não é clichê, é método.",
                f"{o}o {c} precisa sentir orgulho de vestir a camisa juntos.",
            ],
            ("motivational", "staff"): [
                f"{o}a comissão reforça valores de grupo todo dia — ambiente positivo com disciplina.",
                f"{o}eu acredito que liderança compartilhada fortalece o vestiário.",
                f"{o}trabalho sério cria respeito mútuo.",
            ],
            ("analytical", "board"): [
                f"{o}eu separo fato de ruído: avalio clima com líderes e comissão, com critério.",
                f"{o}gestão de grupo passa por rotina, regras e conversas programadas.",
                f"{o}o {c} precisa de previsibilidade de comportamento.",
            ],
            ("analytical", "players"): [
                f"{o}papéis de liderança são definidos com clareza — menos improviso, mais responsabilidade.",
                f"{o}eu uso conversa individual e coletiva com método.",
                f"{o}o vestiário responde quando as regras são claras e justas.",
            ],
            ("analytical", "staff"): [
                f"{o}mapeamos sinais de tensão e agimos com plano — sem achismo.",
                f"{o}a integração psico-técnica faz parte do nosso modelo.",
                f"{o}eu priorizo ambiente profissional: respeito, horário e padrão.",
            ],
        }
        return _t(style_l, aud, bank)

    # season (default complex)
    tbl_ref = f" Estamos {tbl} — isso molda nossas decisões." if tbl else ""
    bank = {
        ("aggressive", "board"): [
            f"{o}eu não aceito acomodação: a {comp} exige pontos e postura de time grande.{tbl_ref}",
            f"{o}objetivo é claro — subir ou consolidar posição com trabalho agressivo e inteligente.{tbl_ref}",
            f"{o}o calendário não espera; eu cobro resposta imediata do elenco.",
        ],
        ("aggressive", "players"): [
            f"{o}cada jogo da reta pesa — quem não estiver mentalizado para guerra fica de fora.{tbl_ref}",
            f"{o}eu quero sede de classificação e de título, dentro do realismo do elenco.",
            f"{o}a temporada cobra regularidade — entrega total.",
        ],
        ("aggressive", "staff"): [
            f"{o}a comissão planeja a maratona com exigência máxima — sem desperdício de sessão.{tbl_ref}",
            f"{o}eu quero cada detalhe alinhado aos objetivos da temporada.",
            f"{o}pressão boa é a que nos coloca onde queremos na tabela.",
        ],
        ("calm", "board"): [
            f"{o}eu leio a temporada com pé no chão: objetivos existem, mas o caminho é jogo a jogo.{tbl_ref}",
            f"{o}gestão de elenco e expectativa precisa ser madura — falo isso com a diretoria também.",
            f"{o}o {c} evolui quando mantém clareza de propósito.",
        ],
        ("calm", "players"): [
            f"{o}foco no próximo desafio — tabela é consequência de trabalho bem feito.{tbl_ref}",
            f"{o}eu confio no processo; vocês confiem no método.",
            f"{o}regularidade emocional nos ajuda na reta decisiva.",
        ],
        ("calm", "staff"): [
            f"{o}organizamos a sequência com serenidade: calendário, viagens e recuperação.{tbl_ref}",
            f"{o}a leitura da temporada é conjunta — comissão alinhada ao objetivo.",
            f"{o}menos pressa, mais precisão nas escolhas.",
        ],
        ("motivational", "board"): [
            f"{o}eu acredito no que podemos conquistar — trabalho e união nos colocam na briga.{tbl_ref}",
            f"{o}a torcida merece ver um time que nunca desiste da temporada.",
            f"{o}o {c} tem tudo para reagir e sonhar com o que é possível.",
        ],
        ("motivational", "players"): [
            f"{o}vamos juntos buscar cada ponto — confiança e garra definem nossa reta.{tbl_ref}",
            f"{o}eu confio em vocês para escrever uma história forte na {comp}.",
            f"{o}cada treino nos aproxima do que queremos na tabela.",
        ],
        ("motivational", "staff"): [
            f"{o}a comissão está motivada a levar o grupo ao limite do potencial.{tbl_ref}",
            f"{o}eu acredito no projeto esportivo para fechar a temporada com orgulho.",
            f"{o}trabalho diário é nossa moeda para subir na classificação.",
        ],
        ("analytical", "board"): [
            f"{o}eu separo cenário real de desejo: nossas metas seguem o que os números e o elenco permitem.{tbl_ref}",
            f"{o}a leitura da tabela orienta prioridades táticas e de minutos.",
            f"{o}objetivo é claro em indicadores: pontos, desempenho e saúde do grupo.",
        ],
        ("analytical", "players"): [
            f"{o}cada jogo é unidade de análise — constância nos coloca onde queremos.{tbl_ref}",
            f"{o}eu uso dados e calendário para distribuir esforço na temporada.",
            f"{o}a classificação reflete processo; vamos fortalecer o processo.",
        ],
        ("analytical", "staff"): [
            f"{o}planejamento de temporada integra tabela, desgaste e adversários.{tbl_ref}",
            f"{o}eu priorizo decisões sustentáveis — não só resultado pontual.",
            f"{o}o modelo do {c} precisa funcionar por muitas rodadas seguidas.",
        ],
    }
    return _t(style_l, aud, bank)
