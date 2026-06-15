# ⚡ ChargeGrid Intelligence — Sistema de Gerenciamento de Recarga

**Disciplina:** Data Structure and Algorithms 

## Integrantes
| NOME | RM |
| ---- | -- |
| LEONARDO SCOTTI TOBIAS | 573305 |
| NATAN SILVA DA COSTA | 573100 |
| ENZO SEIJI DELGADO TABUCHI | 573156 |
| LUCA ALMEIDA LUCARELI | 569061 |
| HENRIQUE ALMEIDA LUCARELI | 569183 |

---

## 📋 Descrição

O **ChargeGrid Intelligence** é um sistema de terminal em Python que simula a operação inteligente de um eletroposto com múltiplos pontos de carregamento simultâneos. O programa gerencia sessões de recarga, aplica controle dinâmico de potência (Power Management), calcula tarifas variáveis por horário, tipo de usuário e nível de demanda, e simula a comunicação com sistemas externos via protocolo OCPP 1.6 e leitura MODBUS.

---

## ▶️ Como executar

Requisito: Python 3.10+ (sem bibliotecas externas).

```bash
python chargegrid_sprint2.py
```

---

## 🗂️ Estrutura do código

```
chargegrid_sprint2.py
│
├── Constantes do sistema (tarifas, limiares, tipos de veículo/usuário)
├── pontos{}               → dicionário global com estado de cada ponto
├── historico_sessoes[]    → lista global de sessões encerradas
├── _prox_id_sessao[0]     → vetor contador mutável de IDs de sessão
│
├── demanda_atual_kw()        → soma potências de todos os pontos ativos
├── potencia_disponivel_kw()  → capacidade restante no transformador
├── pontos_livres()           → lista de pontos sem sessão ativa
├── pontos_ocupados()         → lista de pontos com sessão ativa
├── obter_sessao()            → retorna dados de um ponto específico
│
├── calcular_alocacao()       → aplica Power Management à potência solicitada
├── gerar_id_sessao()         → gera ID único no formato OCPP
├── iniciar_sessao()          → registra nova sessão e dispara OCPP
├── encerrar_sessao()         → finaliza sessão, processa e arquiva
│
├── detectar_horario()        → classifica hora em ponta/off-peak/normal
├── calcular_tarifa()         → tarifação dinâmica (3 fatores)
│
├── simular_recarga_silenciosa()  → simulação em lote (sem print)
├── simular_recarga_verbose()     → simulação com progresso no terminal
├── processar_sessao()            → orquestra simulação + cálculo financeiro
│
├── ocpp_boot_notification()   → BootNotification (CP → CS)
├── ocpp_start_transaction()   → Authorize + StartTransaction
├── ocpp_meter_values()        → MeterValues (telemetria periódica)
├── ocpp_stop_transaction()    → StopTransaction (encerramento)
├── modbus_leitura_medidor()   → leitura de registradores MODBUS
│
├── exibir_painel()                → status em tempo real do eletroposto
├── exibir_relatorio_sessao()      → relatório detalhado de sessão encerrada
├── exibir_relatorio_consolidado() → consolidado de todas as sessões
│
├── coletar_dados_sessao()     → coleta interativa de dados do usuário
├── cenario_multiplos_veiculos() → demonstração automática com 3 veículos
│
├── menu_iniciar_sessao()      → opção 1 do menu
├── menu_encerrar_sessao()     → opção 2 do menu
├── menu_relatorio_ativa()     → opção 4 do menu
│
└── main()                     → laço principal while True
```

---

## ⚙️ Lógica de decisão e controle

### Power Management (controle de demanda)
| Nível | Demanda total | Potência concedida |
|---|---|---|
| Normal | < 80% (< 35,2 kW) | 100% do solicitado |
| Alerta | 80–95% (35,2–41,8 kW) | 70% do solicitado |
| Crítico | > 95% (> 41,8 kW) | 50% do solicitado |

### Tarifação dinâmica
| Fator | Regra |
|---|---|
| Horário off-peak (0h–5h) | R$ 0,90/kWh |
| Horário normal | R$ 1,20/kWh |
| Horário de ponta (18h–20h) | R$ 1,85/kWh |
| Assinante | Desconto de 15% sobre o custo de energia |
| Frota Corporativa | Teto na tarifa off-peak, independente do horário |
| Alta demanda (> 80%) | Acréscimo de +10% (exceto Frota) |

### Status do eletroposto (exibir_painel)
| Demanda | Status exibido |
|---|---|
| < 80% da capacidade | NORMAL |
| 80–95% da capacidade | ALERTA |
| > 95% da capacidade | CRÍTICO |

---

## 🖥️ Demonstrações de saída

### Abertura do sistema
```
══════════════════════════════════════════════════════════════════
  ChargeGrid Intelligence v2.0 — FIAP Sprint 2
══════════════════════════════════════════════════════════════════

  Sistema de Gerenciamento Inteligente de Recarga de VEs.
  Controle simultâneo de múltiplos pontos com Power Management,
  tarifação dinâmica e simulação de protocolo OCPP 1.6 / MODBUS.
```

### Menu principal
```
──────────────────────────────────────────────────────────────
  MENU PRINCIPAL
──────────────────────────────────────────────────────────────
  [1] Iniciar nova sessão de recarga
  [2] Encerrar sessão ativa
  [3] Ver painel do eletroposto
  [4] Ver relatório de sessão ativa
  [5] Relatório consolidado (histórico)
  [6] Executar cenário automático (3 veículos)
  [7] Sair
```

### Opção 3 — Painel do eletroposto (com 3 sessões ativas)
```
══════════════════════════════════════════════════════════════════
  PAINEL DO ELETROPOSTO — ChargeGrid Intelligence
══════════════════════════════════════════════════════════════════

  Demanda total : 29.80 kW / 44.0 kW
  Disponível    : 14.20 kW
  Uso           : ████████████░░░░░░░░ 67.7%  [NORMAL]
  Pontos livres : [4]
  Pontos ativos : [1, 2, 3]
──────────────────────────────────────────────────────────────
  Sessões ativas
──────────────────────────────────────────────────────────────
  Ponto #1 │ CG-20250610-0001 │ Assinante          │ SUV Elétrico          │ 11.00 kW alocados
  Ponto #2 │ CG-20250610-0002 │ Visitante          │ Hatchback / Sedan     │  7.40 kW alocados
  Ponto #3 │ CG-20250610-0003 │ Frota Corporativa  │ Van / Utilitário       │ 11.00 kW alocados
```

### Opção 6 — Cenário automático (Power Management em ação)
```
──────────────────────────────────────────────────────────────
  Passo 2 — Início das Sessões
──────────────────────────────────────────────────────────────

  ✓ Ponto #1 — CG-20250610-0001
    Usuário  : Assinante
    Veículo  : SUV Elétrico
    Potência : 11.0 kW solicitados → 11.0 kW alocados  (capacidade normal)

  ✓ Ponto #2 — CG-20250610-0002
    Usuário  : Visitante
    Veículo  : Hatchback / Sedan
    Potência : 7.4 kW solicitados → 7.4 kW alocados  (capacidade normal)

  ✓ Ponto #3 — CG-20250610-0003
    Usuário  : Frota Corporativa
    Veículo  : Van / Utilitário
    Potência : 22.0 kW solicitados → 11.4 kW alocados  (redução preventiva >80% da capacidade)
```

### Simulação OCPP 1.6
```
  [OCPP] → CP→CS  2025-06-10T14:22:05Z
         action                : StartTransaction
         connectorId           : 1
         idTag                 : TAG-0001
         meterStart            : 0
         timestamp             : 2025-06-10T14:22:05Z
         transactionId         : CG-20250610-0001

  [OCPP] ← CS→CP  2025-06-10T14:22:05Z
         transactionId         : CG-20250610-0001
         idTagInfo.status      : Accepted
```

### Leitura MODBUS
```
  [MODBUS] Leitura — Registrador 0x1010  Ponto #1
           Tensão         : 220.0 V
           Corrente       : 50.0 A
           Potência Ativa : 11.00 kW
           Energia Acum.  : 2.750 kWh
           FP             : 0.97
```

### Relatório de sessão encerrada
```
══════════════════════════════════════════════════════════════════
  RELATÓRIO DE SESSÃO — CG-20250610-0001
══════════════════════════════════════════════════════════════════
  ID da Sessão     : CG-20250610-0001
  Ponto            : #1
  Tipo de Usuário  : Assinante
  Veículo          : SUV Elétrico
──────────────────────────────────────────────────────────────
  Período
──────────────────────────────────────────────────────────────
  Início           : 10/06/2025 19:00
  Fim              : 10/06/2025 22:22
  Duração          : 3h 22min
──────────────────────────────────────────────────────────────
  Cobrança
──────────────────────────────────────────────────────────────
  Custo de Energia : R$    57.02
  Desconto (15%)   : R$     8.55 –
  Taxa de Serviço  : R$     2.50
──────────────────────────────────────────────────────────────
  TOTAL A PAGAR    : R$    50.97
──────────────────────────────────────────────────────────────
  Impacto Estimado
──────────────────────────────────────────────────────────────
  CO₂ Evitado      : 10.81 kg
  Autonomia Ganha  : ~279 km
```

### Relatório consolidado
```
══════════════════════════════════════════════════════════════════
  RELATÓRIO CONSOLIDADO — ChargeGrid Intelligence
══════════════════════════════════════════════════════════════════

  ID Sessão              Ponto   Usuário              kWh       R$
──────────────────────────────────────────────────────────────
  CG-20250610-0001       #1      Assinante            46.410    50.97
  CG-20250610-0002       #2      Visitante            59.176    91.83
  CG-20250610-0003       #3      Frota Corporativa    79.092    73.73

  Sessões encerradas : 3
  Energia total      : 184.678 kWh
  Receita total      : R$ 216.53
  CO₂ evitado total  : 43.03 kg
  Autonomia gerada   : 1108 km
```

---

## 📐 Estruturas de dados utilizadas

| Estrutura | Uso no sistema |
|---|---|
| `dict` (pontos) | Estado de cada ponto de carregamento (sessão ativa ou None) |
| `list` (historico_sessoes) | Registro de todas as sessões encerradas |
| `list` (_prox_id_sessao) | Vetor de 1 elemento para contador mutável entre funções |
| `dict` (sessão) | Cada sessão armazena tipo, veículo, potência, tarifas e resultado |
| `OrderedDict` | Menus e tipos de usuário/veículo com ordem de inserção garantida |
| `while True` | Laço principal do menu — encerra só com opção 7 |
| `if / elif / else` | Condicionais de Power Management, tarifação e alertas |
| `for` | Percorre pontos e histórico para cálculo e exibição |
| `try / except` | Validação de entradas numéricas (ValueError) |
| `random` | Variação de ±5% na potência durante a simulação de recarga |
| `datetime / timedelta` | Cálculo de horário de início/fim e duração das sessões |

---

## 🎨 Diferenciais implementados

- **Power Management em três níveis** — redução automática de potência baseada na demanda total do transformador
- **Tarifação com três fatores independentes** — horário, tipo de usuário e nível de demanda combinados
- **Simulação OCPP 1.6 completa** — BootNotification, Authorize, StartTransaction, MeterValues e StopTransaction com estrutura de mensagens envio/recebimento
- **Leitura MODBUS simulada** — tensão, corrente, potência ativa, energia acumulada e fator de potência por registrador
- **Cenário automático** — demonstração passo a passo com 3 veículos simultâneos, evidenciando todos os módulos do sistema
- **Relatório de impacto ambiental** — CO₂ evitado (kg) e autonomia ganha (km) por sessão e consolidado
