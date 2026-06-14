"""
==================================================================
        ChargeGrid Intelligence — Sistema de Gerenciamento
                       Sprint 2 — FIAP
==================================================================
"""

import random
from datetime import datetime, timedelta
from collections import OrderedDict
import pandas as pd

CAPACIDADE_TOTAL_KW    = 44.0
NUM_PONTOS             = 4
POTENCIA_MAX_PONTO_KW  = 22.0
POTENCIA_MIN_KW        = 3.7

TARIFA_PADRAO_KWH      = 1.20
TARIFA_PONTA_KWH       = 1.85
TARIFA_OFF_PEAK_KWH    = 0.90
TAXA_SERVICO           = 2.50

DESCONTO_ASSINANTE     = 0.15
ACRESCIMO_ALTA_DEMANDA = 0.10

LIMIAR_REDUCAO_KW      = CAPACIDADE_TOTAL_KW * 0.80
LIMIAR_CRITICO_KW      = CAPACIDADE_TOTAL_KW * 0.95

TIPOS_USUARIO = OrderedDict([
    ("1", "Visitante"),
    ("2", "Assinante"),
    ("3", "Frota Corporativa"),
])

TIPOS_VEICULO = OrderedDict([
    ("1", {"nome": "Hatchback / Sedan",  "bateria_kwh": 40,  "potencia_max": 7.4}),
    ("2", {"nome": "SUV Elétrico",        "bateria_kwh": 77,  "potencia_max": 11.0}),
    ("3", {"nome": "Van / Utilitário",    "bateria_kwh": 90,  "potencia_max": 22.0}),
    ("4", {"nome": "Moto Elétrica",       "bateria_kwh": 5,   "potencia_max": 3.7}),
])


pontos: dict = {i: None for i in range(1, NUM_PONTOS + 1)}

_prox_id_sessao: list = [1]

historico_sessoes: list = []


def demanda_atual_kw() -> float:
    return sum(
        s["potencia_alocada_kw"]
        for s in pontos.values()
        if s is not None
    )


def potencia_disponivel_kw() -> float:
    return max(0.0, CAPACIDADE_TOTAL_KW - demanda_atual_kw())


def pontos_livres() -> list:
    return [p for p, s in pontos.items() if s is None]


def pontos_ocupados() -> list:
    return [p for p, s in pontos.items() if s is not None]


def obter_sessao(ponto: int) -> dict | None:
    return pontos.get(ponto)


def calcular_alocacao(potencia_solicitada_kw: float) -> tuple:
    demanda = demanda_atual_kw()
    if demanda >= LIMIAR_CRITICO_KW:
        fator  = 0.50
        motivo = "restrição crítica (>95% da capacidade)"
    elif demanda >= LIMIAR_REDUCAO_KW:
        fator  = 0.70
        motivo = "redução preventiva (>80% da capacidade)"
    else:
        fator  = 1.00
        motivo = "capacidade normal"

    alocado = min(potencia_solicitada_kw * fator, potencia_disponivel_kw())
    alocado = max(POTENCIA_MIN_KW, alocado) if alocado >= POTENCIA_MIN_KW else 0.0
    return alocado, fator, motivo


def gerar_id_sessao() -> str:
    id_num = _prox_id_sessao[0]
    _prox_id_sessao[0] += 1
    return f"CG-{datetime.now().strftime('%Y%m%d')}-{id_num:04d}"


def iniciar_sessao(ponto: int, dados: dict) -> str:
    potencia_solicitada        = dados["potencia_kw"]
    alocada, fator, motivo     = calcular_alocacao(potencia_solicitada)
    id_sessao                  = gerar_id_sessao()

    hora      = dados["hora_inicio"]
    dt_inicio = datetime.now().replace(hour=hora, minute=0, second=0, microsecond=0)

    pontos[ponto] = {
        "id_sessao":            id_sessao,
        "ponto":                ponto,
        "tipo_usuario":         dados["tipo_usuario"],
        "veiculo":              dados["veiculo"],
        "carga_inicial":        dados["carga_inicial"],
        "carga_alvo":           dados["carga_alvo"],
        "potencia_solicitada":  potencia_solicitada,
        "potencia_alocada_kw":  alocada,
        "fator_reducao":        fator,
        "motivo_reducao":       motivo,
        "hora_inicio":          hora,
        "dt_inicio":            dt_inicio,
        "demanda_no_inicio_kw": dados.get("demanda_no_inicio_kw", 0.0),
        "status":               "Carregando",
    }

    ocpp_start_transaction(id_sessao, ponto, dados)
    return id_sessao


def encerrar_sessao(ponto: int) -> dict | None:
    sessao = pontos.get(ponto)
    if not sessao:
        return None

    resultado       = processar_sessao(sessao)
    sessao["resultado"] = resultado
    sessao["status"]    = "Encerrada"

    ocpp_stop_transaction(sessao, resultado)

    historico_sessoes.append({**sessao})
    pontos[ponto] = None
    return resultado


def detectar_horario(hora: int) -> str:
    if 18 <= hora <= 20:
        return "ponta"
    elif 0 <= hora <= 5:
        return "off-peak"
    return "normal"


def calcular_tarifa(hora: int, tipo_usuario: str, demanda_kw: float) -> tuple:
    periodo = detectar_horario(hora)
    base    = {
        "ponta":    TARIFA_PONTA_KWH,
        "off-peak": TARIFA_OFF_PEAK_KWH,
        "normal":   TARIFA_PADRAO_KWH,
    }[periodo]

    if tipo_usuario == "Frota Corporativa":
        tarifa        = min(base, TARIFA_OFF_PEAK_KWH)
        desconto_label = "Tarifa negociada (teto off-peak)"
    else:
        tarifa        = base
        desconto_label = ""

    acrescimo = 0.0
    if demanda_kw > LIMIAR_REDUCAO_KW and tipo_usuario != "Frota Corporativa":
        acrescimo = tarifa * ACRESCIMO_ALTA_DEMANDA
        tarifa   += acrescimo

    return tarifa, periodo, desconto_label, acrescimo


#  SIMULAÇÃO FÍSICA DA RECARGA
def simular_recarga_silenciosa(
    potencia_kw: float,
    carga_inicial: float,
    carga_alvo: float,
    capacidade_bateria: float,
) -> tuple:
    energia_necessaria = (carga_alvo - carga_inicial) / 100 * capacidade_bateria
    energia_carregada  = 0.0
    minuto             = 0
    registros          = []

    while energia_carregada < energia_necessaria:
        variacao       = random.uniform(-0.05, 0.05)
        potencia_atual = max(
            POTENCIA_MIN_KW,
            min(potencia_kw * (1 + variacao), POTENCIA_MAX_PONTO_KW)
        )
        energia_ciclo     = min(potencia_atual / 60, energia_necessaria - energia_carregada)
        energia_carregada += energia_ciclo
        soc_atual          = carga_inicial + (energia_carregada / capacidade_bateria) * 100
        minuto            += 1
        registros.append({
            "minuto":     minuto,
            "potencia_kw": round(potencia_atual, 2),
            "energia_kwh": round(energia_ciclo, 4),
            "soc":         round(soc_atual, 1),
        })

    return registros, energia_carregada


def simular_recarga_verbose(
    potencia_kw: float,
    carga_inicial: float,
    carga_alvo: float,
    capacidade_bateria: float,
) -> tuple:
    energia_necessaria = (carga_alvo - carga_inicial) / 100 * capacidade_bateria
    energia_carregada  = 0.0
    minuto             = 0
    registros          = []

    print()
    subcabecalho("Simulação em progresso...")
    print(f"  Energia a carregar: {energia_necessaria:.2f} kWh")
    print()

    while energia_carregada < energia_necessaria:
        variacao       = random.uniform(-0.05, 0.05)
        potencia_atual = max(
            POTENCIA_MIN_KW,
            min(potencia_kw * (1 + variacao), POTENCIA_MAX_PONTO_KW)
        )
        energia_ciclo     = min(potencia_atual / 60, energia_necessaria - energia_carregada)
        energia_carregada += energia_ciclo
        soc_atual          = carga_inicial + (energia_carregada / capacidade_bateria) * 100
        minuto            += 1
        registros.append({
            "minuto":     minuto,
            "potencia_kw": round(potencia_atual, 2),
            "energia_kwh": round(energia_ciclo, 4),
            "soc":         round(soc_atual, 1),
        })
        if minuto % 5 == 0 or energia_carregada >= energia_necessaria:
            barra = int(soc_atual / 5)
            print(
                f"  t={minuto:>4}min │ {potencia_atual:>5.2f} kW │ "
                f"SOC: {'█' * barra:<20} {soc_atual:>5.1f}%"
            )

    return registros, energia_carregada


#  FINANCEIRO DA SESSÃO
def processar_sessao(sessao: dict, verbose: bool = False) -> dict:
    veiculo      = sessao["veiculo"]
    tipo_usuario = sessao["tipo_usuario"]
    hora_inicio  = sessao["hora_inicio"]
    potencia     = sessao["potencia_alocada_kw"]

    fn_simular = simular_recarga_verbose if verbose else simular_recarga_silenciosa
    registros, energia_total = fn_simular(
        potencia_kw        = potencia,
        carga_inicial      = sessao["carga_inicial"],
        carga_alvo         = sessao["carga_alvo"],
        capacidade_bateria = veiculo["bateria_kwh"],
    )

    duracao_min    = len(registros)
    dt_inicio      = sessao["dt_inicio"]
    dt_fim         = dt_inicio + timedelta(minutes=duracao_min)
    potencia_media = sum(r["potencia_kw"] for r in registros) / len(registros)

    demanda_contexto = sessao.get("demanda_no_inicio_kw", 0.0)
    tarifa_kwh, periodo, desconto_label, acrescimo = calcular_tarifa(
        hora_inicio, tipo_usuario, demanda_contexto
    )

    custo_energia = energia_total * tarifa_kwh
    desconto      = custo_energia * DESCONTO_ASSINANTE if tipo_usuario == "Assinante" else 0.0
    total         = custo_energia - desconto + TAXA_SERVICO

    co2_evitado   = energia_total * 0.233
    km_estimado   = energia_total * 6

    return {
        "registros":      registros,
        "energia_total":  round(energia_total, 3),
        "duracao_min":    duracao_min,
        "dt_inicio":      dt_inicio,
        "dt_fim":         dt_fim,
        "tarifa_kwh":     tarifa_kwh,
        "periodo":        periodo,
        "acrescimo_kwh":  round(acrescimo, 3),
        "desconto_label": desconto_label,
        "custo_energia":  round(custo_energia, 2),
        "desconto":       round(desconto, 2),
        "taxa_servico":   TAXA_SERVICO,
        "total":          round(total, 2),
        "potencia_media": round(potencia_media, 2),
        "co2_evitado":    round(co2_evitado, 2),
        "km_estimado":    round(km_estimado, 0),
    }

def _ocpp_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _ocpp_log(direcao: str, mensagem: dict):
    seta = "→ CP→CS" if direcao == "envio" else "← CS→CP"
    print(f"\n  [OCPP] {seta}  {_ocpp_timestamp()}")
    for k, v in mensagem.items():
        print(f"         {k:<22}: {v}")


def ocpp_boot_notification(ponto: int):
    _ocpp_log("envio", {
        "action":           "BootNotification",
        "chargePointModel": "ChargeGrid-P22AC",
        "chargePointVendor":"ChargeGrid Intelligence",
        "connectorId":      ponto,
        "firmwareVersion":  "v2.1.4",
    })
    _ocpp_log("recebimento", {
        "status":      "Accepted",
        "currentTime": _ocpp_timestamp(),
        "interval":    30,
    })


def ocpp_start_transaction(id_sessao: str, ponto: int, dados: dict):
    _ocpp_log("envio", {
        "action": "Authorize",
        "idTag":  f"TAG-{id_sessao[-4:]}",
    })
    _ocpp_log("recebimento", {
        "idTagInfo.status": "Accepted",
    })
    _ocpp_log("envio", {
        "action":        "StartTransaction",
        "connectorId":   ponto,
        "idTag":         f"TAG-{id_sessao[-4:]}",
        "meterStart":    0,
        "timestamp":     _ocpp_timestamp(),
        "transactionId": id_sessao,
    })
    _ocpp_log("recebimento", {
        "transactionId":    id_sessao,
        "idTagInfo.status": "Accepted",
    })


def ocpp_meter_values(id_sessao: str, ponto: int, soc: float,
                      energia_kwh: float, potencia_kw: float):
    _ocpp_log("envio", {
        "action":        "MeterValues",
        "connectorId":   ponto,
        "transactionId": id_sessao,
        "SoC [%]":       f"{soc:.1f}",
        "Energy.Active.Import.Register [kWh]": f"{energia_kwh:.3f}",
        "Power.Active.Import [kW]":            f"{potencia_kw:.2f}",
        "timestamp":     _ocpp_timestamp(),
    })


def ocpp_stop_transaction(sessao: dict, resultado: dict):
    _ocpp_log("envio", {
        "action":          "StopTransaction",
        "transactionId":   sessao["id_sessao"],
        "meterStop [kWh]": f"{resultado['energia_total']:.3f}",
        "timestamp":       _ocpp_timestamp(),
        "reason":          "Local",
    })
    _ocpp_log("recebimento", {
        "idTagInfo.status": "Accepted",
    })


def modbus_leitura_medidor(ponto: int, potencia_kw: float, energia_kwh: float):
    registrador = 0x1000 + ponto * 0x10
    print(f"\n  [MODBUS] Leitura — Registrador 0x{registrador:04X}  Ponto #{ponto}")
    print(f"           Tensão         : 220.0 V")
    print(f"           Corrente       : {(potencia_kw * 1000 / 220):.1f} A")
    print(f"           Potência Ativa : {potencia_kw:.2f} kW")
    print(f"           Energia Acum.  : {energia_kwh:.3f} kWh")
    print(f"           FP             : 0.97")


def linha(char="-", largura=62):
    print(char * largura)


def cabecalho(titulo: str):
    linha("=")
    print(f"  {titulo}")
    linha("=")


def subcabecalho(titulo: str):
    linha("-")
    print(f"  {titulo}")
    linha("-")


def entrada_inteira(prompt: str, minimo: int, maximo: int) -> int:
    while True:
        try:
            valor = int(input(prompt))
            if minimo <= valor <= maximo:
                return valor
            print(f"     Digite um número entre {minimo} e {maximo}.")
        except ValueError:
            print("     Entrada inválida. Digite apenas números inteiros.")


def entrada_float(prompt: str, minimo: float, maximo: float) -> float:
    while True:
        try:
            valor = float(input(prompt))
            if minimo <= valor <= maximo:
                return valor
            print(f"     Digite um valor entre {minimo:.1f} e {maximo:.1f}.")
        except ValueError:
            print("     Entrada inválida. Use ponto como separador decimal.")


def escolher_opcao(prompt: str, opcoes: dict) -> str:
    for k, v in opcoes.items():
        print(f"    [{k}] {v}")
    while True:
        escolha = input(prompt).strip()
        if escolha in opcoes:
            return escolha
        print(f"     Opção inválida. Escolha entre: {', '.join(opcoes.keys())}.")


def exibir_painel():
    cabecalho("PAINEL DO ELETROPOSTO — ChargeGrid Intelligence")
    demanda  = demanda_atual_kw()
    uso_pct  = demanda / CAPACIDADE_TOTAL_KW * 100
    barra    = int(uso_pct / 5)
    cor      = (
        "CRÍTICO" if demanda >= LIMIAR_CRITICO_KW else
        "ALERTA"  if demanda >= LIMIAR_REDUCAO_KW else
        "NORMAL"
    )

    print(f"\n  Demanda total : {demanda:.2f} kW / {CAPACIDADE_TOTAL_KW:.1f} kW")
    print(f"  Disponível    : {potencia_disponivel_kw():.2f} kW")
    print(f"  Uso           : {'█' * barra:<20} {uso_pct:.1f}%  [{cor}]")
    print(f"  Pontos livres : {pontos_livres()}")
    print(f"  Pontos ativos : {pontos_ocupados()}")

    if pontos_ocupados():
        subcabecalho("Sessões ativas")
        for ponto in pontos_ocupados():
            s = obter_sessao(ponto)
            print(
                f"  Ponto #{ponto} │ {s['id_sessao']} │ {s['tipo_usuario']:<18} │ "
                f"{s['veiculo']['nome']:<20} │ {s['potencia_alocada_kw']:.2f} kW alocados"
            )
    print()


def exibir_relatorio_sessao(sessao: dict, resultado: dict):
    cabecalho(f"RELATÓRIO DE SESSÃO — {sessao['id_sessao']}")

    subcabecalho("Identificação")
    print(f"  ID da Sessão     : {sessao['id_sessao']}")
    print(f"  Ponto            : #{sessao['ponto']}")
    print(f"  Tipo de Usuário  : {sessao['tipo_usuario']}")
    print(f"  Veículo          : {sessao['veiculo']['nome']}")
    print(f"  Capacidade       : {sessao['veiculo']['bateria_kwh']} kWh")

    subcabecalho("Período")
    print(f"  Início           : {resultado['dt_inicio'].strftime('%d/%m/%Y %H:%M')}")
    print(f"  Fim              : {resultado['dt_fim'].strftime('%d/%m/%Y %H:%M')}")
    h, m = divmod(resultado["duracao_min"], 60)
    print(f"  Duração          : {h}h {m:02d}min")

    subcabecalho("Power Management")
    print(f"  Potência solicitada : {sessao['potencia_solicitada']:.2f} kW")
    print(
        f"  Potência alocada    : {sessao['potencia_alocada_kw']:.2f} kW "
        f"({sessao['fator_reducao']*100:.0f}%)"
    )
    print(f"  Motivo              : {sessao['motivo_reducao']}")

    subcabecalho("Energia")
    print(f"  SOC Inicial      : {sessao['carga_inicial']:.1f}%")
    print(f"  SOC Final        : {sessao['carga_alvo']:.1f}%")
    print(f"  Energia Total    : {resultado['energia_total']:.3f} kWh")
    print(f"  Potência Média   : {resultado['potencia_media']:.2f} kW")

    subcabecalho("Tarifação Dinâmica")
    periodo_label = {
        "ponta":    "Horário de Ponta (18h–20h)",
        "off-peak": "Fora de Ponta / Madrugada (0h–5h)",
        "normal":   "Horário Normal",
    }[resultado["periodo"]]
    print(f"  Período          : {periodo_label}")
    print(f"  Tarifa aplicada  : R$ {resultado['tarifa_kwh']:.4f}/kWh")
    if resultado["acrescimo_kwh"] > 0:
        print(f"  Acréscimo demanda: +R$ {resultado['acrescimo_kwh']:.4f}/kWh (+10%)")
    if resultado["desconto_label"]:
        print(f"  Regra especial   : {resultado['desconto_label']}")

    subcabecalho("Cobrança")
    print(f"  Custo de Energia : R$ {resultado['custo_energia']:>8.2f}")
    if resultado["desconto"] > 0:
        print(f"  Desconto (15%)   : R$ {resultado['desconto']:>8.2f} –")
    print(f"  Taxa de Serviço  : R$ {resultado['taxa_servico']:>8.2f}")
    linha("-")
    print(f"  TOTAL A PAGAR    : R$ {resultado['total']:>8.2f}")

    subcabecalho("Impacto Estimado")
    print(f"  CO₂ Evitado      : {resultado['co2_evitado']:.2f} kg")
    print(f"  Autonomia Ganha  : ~{resultado['km_estimado']:.0f} km")

    linha("=")
    print("  Sessão encerrada com sucesso. Protocolo OCPP 1.6 registrado.")
    linha("=")
    print()


def exibir_relatorio_consolidado():
    if not historico_sessoes:
        print("\n  Nenhuma sessão encerrada até o momento.\n")
        return

    cabecalho("RELATÓRIO CONSOLIDADO — ChargeGrid Intelligence")
    total_energia = 0.0
    total_receita = 0.0
    total_co2     = 0.0
    total_km      = 0.0

    print(f"\n  {'ID Sessão':<22} {'Ponto':<7} {'Usuário':<20} {'kWh':>7} {'R$':>8}")
    linha()

    for s in historico_sessoes:
        r = s.get("resultado", {})
        if not r:
            continue
        print(
            f"  {s['id_sessao']:<22} #{s['ponto']:<6} {s['tipo_usuario']:<20} "
            f"{r['energia_total']:>7.3f} {r['total']:>8.2f}"
        )
        total_energia += r["energia_total"]
        total_receita += r["total"]
        total_co2     += r["co2_evitado"]
        total_km      += r["km_estimado"]

    linha()
    print(f"\n  Sessões encerradas : {len(historico_sessoes)}")
    print(f"  Energia total      : {total_energia:.3f} kWh")
    print(f"  Receita total      : R$ {total_receita:.2f}")
    print(f"  CO₂ evitado total  : {total_co2:.2f} kg")
    print(f"  Autonomia gerada   : {total_km:.0f} km")
    linha("=")
    print()



def exportar_relatorio_excel():
    if not historico_sessoes:
        print("\n  Nenhuma sessão encerrada para exportar.\n")
        return

    dados = []

    for sessao in historico_sessoes:
        resultado = sessao.get("resultado")

        if not resultado:
            continue

        dados.append({
            "ID Sessão": sessao["id_sessao"],
            "Ponto": sessao["ponto"],
            "Usuário": sessao["tipo_usuario"],
            "Veículo": sessao["veiculo"]["nome"],
            "SOC Inicial (%)": sessao["carga_inicial"],
            "SOC Final (%)": sessao["carga_alvo"],
            "Potência Solicitada (kW)": sessao["potencia_solicitada"],
            "Potência Alocada (kW)": sessao["potencia_alocada_kw"],
            "Energia Consumida (kWh)": resultado["energia_total"],
            "Duração (min)": resultado["duracao_min"],
            "Tarifa (R$/kWh)": resultado["tarifa_kwh"],
            "Valor Total (R$)": resultado["total"],
            "CO2 Evitado (kg)": resultado["co2_evitado"],
            "Autonomia Gerada (km)": resultado["km_estimado"],
            "Início": resultado["dt_inicio"].strftime("%d/%m/%Y %H:%M"),
            "Fim": resultado["dt_fim"].strftime("%d/%m/%Y %H:%M")
        })

    df = pd.DataFrame(dados)

    nome_arquivo = f"relatorio_chargegrid_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    df.to_excel(nome_arquivo, index=False)

    print(f"\n  Relatório exportado com sucesso!")
    print(f"  Arquivo: {nome_arquivo}\n")


def coletar_dados_sessao() -> dict | None:
    livres = pontos_livres()
    if not livres:
        print("\n     Todos os pontos estão ocupados. Encerre uma sessão primeiro.\n")
        return None

    print(f"\n  Pontos disponíveis: {livres}")
    ponto = entrada_inteira(
        f"  Selecione o ponto de carregamento [{livres[0]}–{livres[-1]}]: ",
        min(livres), max(livres),
    )
    if ponto not in livres:
        print(f"\n     Ponto #{ponto} está ocupado.\n")
        return None

    print("\n  Tipo de usuário:")
    chave_usuario = escolher_opcao("\n  Escolha [1/2/3]: ", TIPOS_USUARIO)
    tipo_usuario  = TIPOS_USUARIO[chave_usuario]

    print("\n  Tipo de veículo:")
    chave_veiculo = escolher_opcao(
        "\n  Escolha [1/2/3/4]: ",
        {k: f"{v['nome']} (bat.: {v['bateria_kwh']} kWh)" for k, v in TIPOS_VEICULO.items()},
    )
    veiculo = TIPOS_VEICULO[chave_veiculo]

    print()
    carga_inicial = entrada_float("  SOC atual          [%] [0–99]: ", 0, 99)
    carga_alvo    = entrada_float(
        f"  SOC desejado       [%] [{carga_inicial+1:.0f}–100]: ",
        carga_inicial + 1, 100,
    )
    pot_max     = veiculo["potencia_max"]
    potencia_kw = entrada_float(
        f"  Potência desejada [kW] [{POTENCIA_MIN_KW}–{pot_max}]: ",
        POTENCIA_MIN_KW, pot_max,
    )
    hora_inicio = entrada_inteira("  Hora de início     [h] [0–23]: ", 0, 23)

    return {
        "ponto":               ponto,
        "tipo_usuario":        tipo_usuario,
        "veiculo":             veiculo,
        "carga_inicial":       carga_inicial,
        "carga_alvo":          carga_alvo,
        "potencia_kw":         potencia_kw,
        "hora_inicio":         hora_inicio,
        "demanda_no_inicio_kw": demanda_atual_kw(),
    }

def cenario_multiplos_veiculos():
    cabecalho("CENÁRIO AUTOMÁTICO — 3 Veículos Simultâneos")
    print("""
  Este cenário demonstra:
    • Conexão de 3 veículos em pontos distintos
    • Redução automática de potência por Power Management
    • Tarifação dinâmica (ponta / alta demanda)
    • Telemetria OCPP e leitura MODBUS
    • Encerramento sequencial com relatório consolidado
""")
    input("  Pressione ENTER para iniciar o cenário...")

    veiculos_cenario = [
        {
            "ponto": 1, "tipo_usuario": "Assinante",
            "veiculo": TIPOS_VEICULO["2"],
            "carga_inicial": 20, "carga_alvo": 80,
            "potencia_kw": 11.0, "hora_inicio": 19,
        },
        {
            "ponto": 2, "tipo_usuario": "Visitante",
            "veiculo": TIPOS_VEICULO["1"],
            "carga_inicial": 10, "carga_alvo": 90,
            "potencia_kw": 7.4, "hora_inicio": 19,
        },
        {
            "ponto": 3, "tipo_usuario": "Frota Corporativa",
            "veiculo": TIPOS_VEICULO["3"],
            "carga_inicial": 30, "carga_alvo": 95,
            "potencia_kw": 22.0, "hora_inicio": 19,
        },
    ]

    subcabecalho("Passo 1 — Boot dos Carregadores")
    for v in veiculos_cenario:
        ocpp_boot_notification(v["ponto"])

    input("\n  Pressione ENTER para conectar os veículos...")

    subcabecalho("Passo 2 — Início das Sessões")
    for v in veiculos_cenario:
        v["demanda_no_inicio_kw"] = demanda_atual_kw()
        id_sessao = iniciar_sessao(v["ponto"], v)
        s         = obter_sessao(v["ponto"])
        print(f"\n    Ponto #{v['ponto']} — {id_sessao}")
        print(f"    Usuário  : {v['tipo_usuario']}")
        print(f"    Veículo  : {v['veiculo']['nome']}")
        print(
            f"    Potência : {v['potencia_kw']:.1f} kW solicitados → "
            f"{s['potencia_alocada_kw']:.1f} kW alocados  ({s['motivo_reducao']})"
        )

    exibir_painel()
    input("  Pressione ENTER para simular telemetria MODBUS...")

    subcabecalho("Passo 3 — Telemetria Periódica (MeterValues + MODBUS)")
    for ponto in pontos_ocupados():
        s    = obter_sessao(ponto)
        pot  = s["potencia_alocada_kw"]
        kwh  = pot * 0.25
        soc  = s["carga_inicial"] + 5
        ocpp_meter_values(s["id_sessao"], ponto, soc, kwh, pot)
        modbus_leitura_medidor(ponto, pot, kwh)

    input("\n  Pressione ENTER para encerrar as sessões e gerar relatórios...")

    subcabecalho("Passo 4 — Encerramento das Sessões")
    for v in veiculos_cenario:
        snapshot  = {**obter_sessao(v["ponto"])}
        resultado = encerrar_sessao(v["ponto"])
        exibir_relatorio_sessao(snapshot, resultado)

    exibir_relatorio_consolidado()


def menu_iniciar_sessao():
    dados = coletar_dados_sessao()
    if not dados:
        return
    ponto     = dados["ponto"]
    id_sessao = iniciar_sessao(ponto, dados)
    s         = obter_sessao(ponto)
    print(f"\n    Sessão {id_sessao} iniciada no Ponto #{ponto}")
    print(f"    Potência alocada : {s['potencia_alocada_kw']:.2f} kW")
    print(f"    Motivo           : {s['motivo_reducao']}\n")


def menu_encerrar_sessao():
    ocupados = pontos_ocupados()
    if not ocupados:
        print("\n  Nenhum ponto ativo para encerrar.\n")
        return
    print(f"\n  Pontos com sessão ativa: {ocupados}")
    ponto = entrada_inteira(
        f"  Selecione o ponto a encerrar [{ocupados[0]}–{ocupados[-1]}]: ",
        min(ocupados), max(ocupados),
    )
    if ponto not in ocupados:
        print(f"\n     Ponto #{ponto} não possui sessão ativa.\n")
        return
    print(f"\n  Processando sessão do Ponto #{ponto}...")
    snapshot  = {**obter_sessao(ponto)}
    resultado = encerrar_sessao(ponto)
    exibir_relatorio_sessao(snapshot, resultado)


def menu_relatorio_ativa():
    ocupados = pontos_ocupados()
    if not ocupados:
        print("\n  Nenhum ponto ativo.\n")
        return
    print(f"\n  Pontos ativos: {ocupados}")
    ponto = entrada_inteira(
        f"  Selecione o ponto [{ocupados[0]}–{ocupados[-1]}]: ",
        min(ocupados), max(ocupados),
    )
    if ponto not in ocupados:
        print(f"\n     Ponto #{ponto} não possui sessão ativa.\n")
        return
    s = obter_sessao(ponto)
    subcabecalho(f"Sessão ativa — Ponto #{ponto}")
    print(f"  ID Sessão  : {s['id_sessao']}")
    print(f"  Usuário    : {s['tipo_usuario']}")
    print(f"  Veículo    : {s['veiculo']['nome']}")
    print(f"  SOC Alvo   : {s['carga_inicial']}% → {s['carga_alvo']}%")
    print(f"  Potência   : {s['potencia_alocada_kw']:.2f} kW ({s['motivo_reducao']})")
    print()


MENU_PRINCIPAL = OrderedDict([
    ("1", "Iniciar nova sessão de recarga"),
    ("2", "Encerrar sessão ativa"),
    ("3", "Ver painel do eletroposto"),
    ("4", "Ver relatório de sessão ativa"),
    ("5", "Relatório consolidado (histórico)"),
    ("6", "Executar cenário automático (3 veículos)"),
    ("7", "Exportar relatório Excel"),
    ("8", "Sair"),
])

ACOES_MENU = {
    "1": menu_iniciar_sessao,
    "2": menu_encerrar_sessao,
    "3": exibir_painel,
    "4": menu_relatorio_ativa,
    "5": exibir_relatorio_consolidado,
    "6": cenario_multiplos_veiculos,
    "7": exportar_relatorio_excel,
}


def main():
    print()
    cabecalho("ChargeGrid Intelligence v2.0 — FIAP Sprint 2")
    print("""
  Sistema de Gerenciamento Inteligente de Recarga de VEs.
  Controle simultâneo de múltiplos pontos com Power Management,
  tarifação dinâmica e simulação de protocolo OCPP 1.6 / MODBUS.
""")

    while True:
        subcabecalho("MENU PRINCIPAL")
        for k, v in MENU_PRINCIPAL.items():
            print(f"  [{k}] {v}")
        opcao = input("\n  Escolha uma opção: ").strip()

        if opcao == "8":
            print("\n  Encerrando ChargeGrid Intelligence. Até logo!\n")
            break
        elif opcao in ACOES_MENU:
            ACOES_MENU[opcao]()
        else:
            print("\n     Opção inválida. Escolha entre 1 e 8.\n")


if __name__ == "__main__":
    main()
