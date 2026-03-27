# 🧠 FC Companion: Football Logic Engine Manifesto

## 1. Filosofia do Motor (Híbrido)
O Motor de Regras é o cérebro. A LLM (Gemini) é a voz.
- **O Motor (Python):** Analisa matemática, tabela, moral, histórico e decide O QUE está acontecendo e QUAL a gravidade. Gera 80% do conteúdo via templates rápidos.
- **A LLM (Gemini):** Só é chamada para os 20% de momentos épicos (crises, finais, polêmicas, entrevistas). O Motor alimenta a LLM com um contexto absurdamente rico para que ela não alucine.

## 2. O Contexto do Futebol (O que o motor precisa calcular)

### A. Termômetro de Pressão (0 a 100)
A pressão sobre o treinador não vem só de derrotas, mas do contexto:
- **Expectativa vs Realidade:** Time grande em 10º gera Pressão 80. Time pequeno em 10º gera Pressão 20.
- **Sequência (Momentum):** 3 derrotas seguidas = Crise. 5 vitórias = "Oba-oba" / Salto alto.
- **O Peso do Rival:** Perder pro lanterna é ruim. Perder pro maior rival em casa multiplica a pressão por 2.

### B. O Ecossistema da Tabela (Não olhe só para o seu time)
O motor deve varrer a tabela (`standings`) para criar narrativas periféricas:
- **A Secada:** Se o seu time é o 2º colocado, e o 1º colocado perdeu na rodada, o motor gera o evento: "Oportunidade de Ouro" (Aumenta a pressão para vencer o próximo jogo).
- **Ameaça Fantasma:** O time que vem logo atrás ganhou 4 seguidas? Evento: "Respiração no cangote".
- **O Limbo:** Faltam 5 rodadas, o time está no meio da tabela, sem chance de título ou rebaixamento. Evento: "Fim de feira" (Jogadores perdem moral mais rápido, diretoria já cobra a próxima temporada).

### C. Dinâmica de Vestiário (Egos e Hierarquia)
- **O Craque Intocável:** Overall alto + Salário alto. Se for pro banco, a moral despenca o dobro e vaza pra imprensa.
- **A Joia da Base:** Idade < 19 + Potencial alto. Se jogar bem, gera evento de "Assédio Europeu".
- **A Panela:** Se 3 jogadores do mesmo país/idioma estão com moral baixa, gera evento "Racha no vestiário".
- **A Lei do Ex:** O motor deve cruzar o adversário atual com o histórico dos seus jogadores. Se um jogador seu vai enfrentar o ex-clube, gera narrativa específica.

### D. A Diretoria (A Mão Invisível)
- **Mão de Vaca:** Orçamento alto, mas não libera contratação.
- **Impaciente:** Demite na primeira oscilação.
- O motor deve monitorar o `transfer_budget`. Se cair drasticamente sem contratação, gera evento "Diretoria corta gastos".

## 3. Matriz de Decisão: Template vs LLM

O motor classifica cada evento com uma `Severidade` (1 a 10).

| Severidade | Situação | Ação do Motor |
| :--- | :--- | :--- |
| **1 a 4** | Vitória normal, lesão leve, contratação de reserva, empate fora. | **TEMPLATE OFFLINE.** Ex: "O [TIME] venceu o [RIVAL] por 2x0 em um jogo morno." |
| **5 a 7** | Clássico, lesão do craque, 3 vitórias seguidas, contratação cara. | **TEMPLATE ENRIQUECIDO.** Usa variáveis complexas, cita histórico. |
| **8 a 10** | Risco de demissão, Final de Copa, Briga pública, Coletiva pós-goleada. | **CHAMA A LLM.** O motor monta um JSON de contexto e envia pro Gemini criar um texto dramático e imersivo. |

## 4. Estrutura do Contexto para a LLM
Quando o motor decide chamar a LLM, ele NUNCA manda um prompt vazio. Ele manda o "Dossiê":
```json
{
  "cenario": "Coletiva pós-derrota no clássico",
  "pressao_atual": 85,
  "fase_time": "3 jogos sem vencer",
  "posicao_tabela": "Caiu de 2º para 4º",
  "clima_vestiario": "Tenso (Capitão com moral baixa)",
  "diretriz_llm": "Aja como repórteres agressivos. O treinador está na corda bamba. Faça perguntas sobre a falha tática e a queda de rendimento do capitão."
}
```
