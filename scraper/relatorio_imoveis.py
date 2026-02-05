#!/usr/bin/env python3
"""
Relatório Comparativo: Aluguel vs Compra — Bom Pastor, Divinópolis/MG
Scraping de imobiliárias + simulação financeira com ciclos econômicos.

Uso:
    python3 relatorio_imoveis.py
    python3 relatorio_imoveis.py --preco 600000 --aluguel 2500 --entrada 0.3 --juros 0.10
    python3 relatorio_imoveis.py --amortizacao 0.5
    python3 relatorio_imoveis.py --export csv
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.parse
import urllib.error
import ssl

# ─────────────────────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────────────────────

@dataclass
class Imovel:
    area: float  # m²
    quartos: int
    banheiros: int
    vagas: int
    preco: float  # R$
    tipo: str  # "aluguel" ou "venda"
    fonte: str
    bairro: str = "Bom Pastor"
    endereco: str = ""

    @property
    def preco_m2(self) -> float:
        return self.preco / self.area if self.area > 0 else 0

    def to_dict(self) -> dict:
        return {
            "area": self.area,
            "quartos": self.quartos,
            "banheiros": self.banheiros,
            "vagas": self.vagas,
            "preco": self.preco,
            "preco_m2": round(self.preco_m2, 2),
            "tipo": self.tipo,
            "fonte": self.fonte,
            "bairro": self.bairro,
            "endereco": self.endereco,
        }


# ─────────────────────────────────────────────────────────────
# HTTP Helper
# ─────────────────────────────────────────────────────────────

def http_get(url: str, timeout: int = 15) -> Optional[str]:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [ERRO] GET {url}: {e}")
        return None


def http_post(url: str, data: dict, timeout: int = 15) -> Optional[dict]:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=encoded, method="POST", headers={
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        print(f"  [ERRO] POST {url}: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# Scrapers
# ─────────────────────────────────────────────────────────────

def scrape_ala_imoveis(finalidade: str, bairro_codigos: str = "7,358") -> list[Imovel]:
    """Ala Imóveis — API JSON via POST /imoveis/ajax/"""
    print(f"  Ala Imóveis ({finalidade})...")
    data = {
        "imovel[finalidade]": finalidade,
        "imovel[codigosbairros]": bairro_codigos,
        "imovel[numeroquartos]": "0",
        "imovel[numerovagas]": "0",
        "imovel[numerobanhos]": "0",
        "imovel[numerosuite]": "0",
        "imovel[valorde]": "0",
        "imovel[valorate]": "0",
        "imovel[areade]": "0",
        "imovel[areaate]": "0",
        "imovel[numeropagina]": "1",
        "imovel[numeroregistros]": "50",
        "imovel[ordenacao]": "valordesc",
        "imovel[codigocondominio]": "0",
        "imovel[opcaoimovel]": "4",
        "imovel[destaque]": "0",
        "imovel[pagina]": "1",
        "imovel[codigocidade]": "0",
        "imovel[codigoregiao]": "0",
    }
    resp = http_post("https://www.alaimoveis.com.br/imoveis/ajax/", data)
    if not resp or "lista" not in resp:
        return []

    imoveis = []
    for item in resp["lista"]:
        if "Casa" not in item.get("tipo", ""):
            continue
        preco_str = item.get("valor", "0")
        preco = float(re.sub(r"[^\d,]", "", preco_str).replace(",", "."))
        area_str = item.get("areaprincipal", "0")
        area = float(area_str.replace(",", ".")) if area_str else 0
        imoveis.append(Imovel(
            area=area,
            quartos=int(item.get("numeroquartos", 0)),
            banheiros=int(item.get("numerobanhos", 0)),
            vagas=int(item.get("numerovagas", 0)),
            preco=preco,
            tipo=finalidade,
            fonte="Ala Imóveis",
            endereco=item.get("endereco", ""),
        ))
    print(f"    → {len(imoveis)} casas encontradas")
    return imoveis


def scrape_achei_imobiliaria(finalidade: str, bairro_codigo: str = "12") -> list[Imovel]:
    """Achei Imobiliária — mesma API da Ala (mesma plataforma)"""
    print(f"  Achei Imobiliária ({finalidade})...")
    data = {
        "imovel[finalidade]": finalidade,
        "imovel[codigosbairros]": bairro_codigo,
        "imovel[numeroquartos]": "0",
        "imovel[numerovagas]": "0",
        "imovel[numerobanhos]": "0",
        "imovel[numerosuite]": "0",
        "imovel[valorde]": "0",
        "imovel[valorate]": "0",
        "imovel[areade]": "0",
        "imovel[areaate]": "0",
        "imovel[numeropagina]": "1",
        "imovel[numeroregistros]": "50",
        "imovel[ordenacao]": "valordesc",
        "imovel[codigocondominio]": "0",
        "imovel[opcaoimovel]": "4",
        "imovel[destaque]": "0",
        "imovel[pagina]": "1",
        "imovel[codigocidade]": "0",
        "imovel[codigoregiao]": "0",
    }
    resp = http_post("https://www.acheiimobiliaria.com/imoveis/ajax/", data)
    if not resp or "lista" not in resp:
        return []

    imoveis = []
    for item in resp["lista"]:
        if "Casa" not in item.get("tipo", ""):
            continue
        preco_str = item.get("valor", "0")
        preco = float(re.sub(r"[^\d,]", "", preco_str).replace(",", "."))
        area_str = item.get("areaprincipal", "0")
        area = float(area_str.replace(",", ".")) if area_str else 0
        imoveis.append(Imovel(
            area=area,
            quartos=int(item.get("numeroquartos", 0)),
            banheiros=int(item.get("numerobanhos", 0)),
            vagas=int(item.get("numerovagas", 0)),
            preco=preco,
            tipo=finalidade,
            fonte="Achei Imobiliária",
            endereco=item.get("endereco", ""),
        ))
    print(f"    → {len(imoveis)} casas encontradas")
    return imoveis


def scrape_francisco_imoveis(finalidade: str) -> list[Imovel]:
    """Francisco Imóveis — scraping HTML direto"""
    tipo_url = "comprar" if finalidade == "venda" else "alugar"
    url = f"https://franciscoimoveis.com.br/imoveis/{tipo_url}/casa/divinopolis/bom-pastor/1/"
    print(f"  Francisco Imóveis ({finalidade})...")
    html = http_get(url)
    if not html:
        return []

    imoveis = []
    # Parse listing cards from HTML
    # Pattern: data with area, quartos, vagas, preco
    cards = re.findall(
        r'class="[^"]*card[^"]*".*?</(?:div|article|li)>',
        html, re.DOTALL | re.IGNORECASE
    )

    # Alternative: extract structured data from the page
    # Look for JSON-LD or listing patterns
    area_matches = re.findall(r'"area"\s*:\s*"?([\d.,]+)"?\s*', html)
    quartos_matches = re.findall(r'"quartos"\s*:\s*"?(\d+)"?\s*', html)
    vagas_matches = re.findall(r'"vagas"\s*:\s*"?(\d+)"?\s*', html)
    preco_matches = re.findall(r'"valor"\s*:\s*"?([\d.,]+)"?\s*', html)

    # Try another pattern: look for the listing data in the HTML
    listings = re.findall(
        r'(?:area|tamanho)[^\d]*([\d.,]+)\s*m'
        r'.*?(\d+)\s*(?:quartos?|dorm)'
        r'.*?(\d+)\s*vagas?'
        r'.*?R\$\s*([\d.,]+)',
        html, re.DOTALL | re.IGNORECASE
    )

    if not listings:
        # Try simpler pattern
        prices = re.findall(r'R\$\s*([\d.]+[.,]\d{2,3}(?:\.\d{3})*)', html)
        areas = re.findall(r'([\d.,]+)\s*m[²2]', html)
        quartos = re.findall(r'(\d+)\s*(?:quartos?|dorm)', html, re.IGNORECASE)
        vagas = re.findall(r'(\d+)\s*vagas?', html, re.IGNORECASE)

        # Match by position (approximate)
        n = min(len(prices), len(areas))
        for i in range(n):
            try:
                area = float(areas[i].replace(".", "").replace(",", "."))
                preco = float(prices[i].replace(".", "").replace(",", "."))
                q = int(quartos[i]) if i < len(quartos) else 0
                v = int(vagas[i]) if i < len(vagas) else 0
                if area > 0 and preco > 0:
                    imoveis.append(Imovel(
                        area=area, quartos=q, banheiros=0, vagas=v,
                        preco=preco, tipo=finalidade, fonte="Francisco Imóveis",
                    ))
            except (ValueError, IndexError):
                continue

    print(f"    → {len(imoveis)} casas encontradas")
    return imoveis


def scrape_mgf_imoveis(finalidade: str) -> list[Imovel]:
    """MGF Imóveis — scraping HTML"""
    url = f"https://www.mgfimoveis.com.br/{finalidade}/casa/mg-divinopolis-bom-pastor"
    print(f"  MGF Imóveis ({finalidade})...")
    html = http_get(url)
    if not html:
        return []

    imoveis = []
    # Extract listing blocks
    blocks = re.split(r'class="[^"]*card[^"]*"', html)

    # Simple pattern: find all R$ values and area values
    prices = re.findall(r'R\$\s*([\d.]+)', html)
    areas_raw = re.findall(r'(\d+)\s*m[²2]', html)
    quartos_raw = re.findall(r'(\d+)\s*quarto', html, re.IGNORECASE)
    banheiros_raw = re.findall(r'(\d+)\s*banheir', html, re.IGNORECASE)
    vagas_raw = re.findall(r'(\d+)\s*vaga', html, re.IGNORECASE)

    n = min(len(prices), max(len(areas_raw), 1))
    for i in range(n):
        try:
            preco = float(prices[i].replace(".", ""))
            area = float(areas_raw[i]) if i < len(areas_raw) else 0
            q = int(quartos_raw[i]) if i < len(quartos_raw) else 0
            b = int(banheiros_raw[i]) if i < len(banheiros_raw) else 0
            v = int(vagas_raw[i]) if i < len(vagas_raw) else 0
            # Filter reasonable values
            if finalidade == "aluguel" and 500 < preco < 20000:
                imoveis.append(Imovel(area=area, quartos=q, banheiros=b, vagas=v,
                                      preco=preco, tipo=finalidade, fonte="MGF Imóveis"))
            elif finalidade == "venda" and preco > 50000:
                imoveis.append(Imovel(area=area, quartos=q, banheiros=b, vagas=v,
                                      preco=preco, tipo=finalidade, fonte="MGF Imóveis"))
        except (ValueError, IndexError):
            continue

    print(f"    → {len(imoveis)} casas encontradas")
    return imoveis


# ─────────────────────────────────────────────────────────────
# Scrape All
# ─────────────────────────────────────────────────────────────

def scrape_todos() -> list[Imovel]:
    """Scrape all sources for both aluguel and venda."""
    print("\n🔍 Coletando dados de imobiliárias...\n")
    todos = []

    for finalidade in ["aluguel", "venda"]:
        todos += scrape_ala_imoveis(finalidade)
        todos += scrape_achei_imobiliaria(finalidade)
        todos += scrape_francisco_imoveis(finalidade)
        todos += scrape_mgf_imoveis(finalidade)

    print(f"\n✅ Total coletado: {len(todos)} imóveis")
    print(f"   Aluguel: {len([i for i in todos if i.tipo == 'aluguel'])}")
    print(f"   Venda:   {len([i for i in todos if i.tipo == 'venda'])}")
    return todos


# ─────────────────────────────────────────────────────────────
# Financial Simulation
# ─────────────────────────────────────────────────────────────

# Ciclos econômicos baseados no padrão histórico brasileiro (2010-2025)
CICLOS_DEFAULT = [
    {"nome": "Aperto (atual)",    "anos": 4, "selic": 14.0, "ipca": 4.5},
    {"nome": "Afrouxamento",      "anos": 5, "selic": 9.0,  "ipca": 5.5},
    {"nome": "Juros baixos",      "anos": 3, "selic": 5.0,  "ipca": 6.5},
    {"nome": "Choque inflação",   "anos": 5, "selic": 13.0, "ipca": 8.0},
    {"nome": "Estabilização",     "anos": 5, "selic": 10.5, "ipca": 5.0},
    {"nome": "Novo afrouxamento", "anos": 4, "selic": 7.0,  "ipca": 5.5},
    {"nome": "Novo aperto",       "anos": 4, "selic": 12.0, "ipca": 4.5},
]

# Dados históricos reais (para simulação híbrida)
HISTORICO = [
    (2010, 5.91, 9.8),  (2011, 6.50, 11.6), (2012, 5.84, 8.5),
    (2013, 5.91, 8.2),  (2014, 6.41, 10.9), (2015, 10.67, 13.3),
    (2016, 6.29, 14.0), (2017, 2.95, 10.0), (2018, 3.75, 6.4),
    (2019, 4.31, 5.9),  (2020, 4.52, 2.8),  (2021, 10.06, 4.4),
    (2022, 5.78, 12.4), (2023, 4.62, 13.0), (2024, 4.83, 10.9),
    (2025, 4.26, 14.3),
]

PROJECAO = [
    (2026, 4.5, 15.0), (2027, 4.5, 13.0), (2028, 5.0, 10.5),
    (2029, 5.5, 9.0),  (2030, 6.0, 7.5),  (2031, 6.5, 5.5),
    (2032, 7.0, 4.0),  (2033, 8.0, 6.0),  (2034, 7.0, 10.0),
    (2035, 5.5, 13.0), (2036, 4.5, 12.0), (2037, 4.0, 10.0),
    (2038, 4.5, 9.0),  (2039, 5.0, 8.0),
]


def simular(preco: float, aluguel_ini: float, entrada_pct: float,
            taxa_financ: float, amort_extra_pct: float) -> dict:
    """
    Simula 30 anos de compra (com e sem amortização) vs aluguel.
    Usa dados históricos 2010-2025 + projeção cíclica 2026-2039.
    """
    entrada = preco * entrada_pct
    financiado = preco * (1 - entrada_pct)
    tx_m = taxa_financ / 12
    prazo = 360
    parcela = financiado * (tx_m * (1 + tx_m) ** prazo) / ((1 + tx_m) ** prazo - 1)
    amort_extra = parcela * amort_extra_pct
    orcamento = parcela + amort_extra

    dados = HISTORICO + PROJECAO

    # ── Cenário 1: Comprar COM amortização extra ──
    saldo_com = financiado
    patrim_comprador = 0.0
    total_juros_com = 0.0
    total_pago_com = entrada
    meses_quitou = 0

    # ── Cenário 2: Comprar SEM amortização ──
    saldo_sem = financiado
    total_juros_sem = 0.0

    # ── Cenário 3: Alugar + investir ──
    patrim_inquilino = entrada
    aluguel = aluguel_ini
    total_aluguel = 0.0

    imovel_val = preco
    crossover = None
    historico_anual = []

    for idx, (year, ipca, selic) in enumerate(dados):
        ano = idx + 1
        selic_m = (1 + selic / 100) ** (1 / 12) - 1

        for m in range(12):
            # Comprador COM amortização
            if saldo_com > 0:
                juros = saldo_com * tx_m
                amort_normal = parcela - juros
                total_juros_com += juros
                saldo_com -= (amort_normal + amort_extra)
                total_pago_com += parcela + amort_extra
                if saldo_com <= 0:
                    saldo_com = 0
                    meses_quitou = (ano - 1) * 12 + m + 1
            else:
                patrim_comprador = patrim_comprador * (1 + selic_m) + orcamento

            # Comprador SEM amortização
            if saldo_sem > 0:
                juros_sem = saldo_sem * tx_m
                total_juros_sem += juros_sem
                saldo_sem -= (parcela - juros_sem)

            # Inquilino
            investimento = orcamento - aluguel
            patrim_inquilino = patrim_inquilino * (1 + selic_m) + investimento
            total_aluguel += aluguel

        aluguel *= (1 + ipca / 100)
        imovel_val *= (1 + ipca / 100)

        if crossover is None and aluguel > parcela:
            crossover = ano

        historico_anual.append({
            "ano": ano, "year": year, "ipca": ipca, "selic": selic,
            "aluguel": round(aluguel, 2),
            "saldo_com": round(max(saldo_com, 0), 2),
            "saldo_sem": round(max(saldo_sem, 0), 2),
            "patrim_comprador": round(patrim_comprador, 2),
            "patrim_inquilino": round(patrim_inquilino, 2),
            "imovel_val": round(imovel_val, 2),
        })

    avg_selic = sum(d[2] for d in dados) / 30
    avg_ipca = sum(d[1] for d in dados) / 30

    return {
        "parametros": {
            "preco_imovel": preco,
            "entrada_pct": entrada_pct,
            "entrada_valor": entrada,
            "financiado": financiado,
            "taxa_financ": taxa_financ,
            "parcela": round(parcela, 2),
            "amort_extra_pct": amort_extra_pct,
            "amort_extra_valor": round(amort_extra, 2),
            "orcamento_mensal": round(orcamento, 2),
            "aluguel_inicial": aluguel_ini,
        },
        "medias": {
            "selic_media": round(avg_selic, 2),
            "ipca_medio": round(avg_ipca, 2),
            "juros_real_medio": round(avg_selic - avg_ipca, 2),
        },
        "resultado": {
            "meses_quitou": meses_quitou,
            "anos_quitou": round(meses_quitou / 12, 1),
            "juros_com_amort": round(total_juros_com, 2),
            "juros_sem_amort": round(total_juros_sem, 2),
            "economia_juros": round(total_juros_sem - total_juros_com, 2),
            "crossover_ano": crossover,
            "aluguel_final": round(aluguel, 2),
            "parcela_fixa": round(parcela, 2),
            "imovel_valorizado": round(imovel_val, 2),
            "patrim_comprador_invest": round(patrim_comprador, 2),
            "patrim_comprador_total": round(imovel_val + patrim_comprador, 2),
            "patrim_inquilino": round(patrim_inquilino, 2),
            "total_pago_aluguel": round(total_aluguel, 2),
            "total_pago_compra": round(total_pago_com, 2),
        },
        "ranking": sorted([
            {"cenario": "Comprar SEM amortizar", "patrimonio": round(imovel_val, 2)},
            {"cenario": "Comprar COM amortizar", "patrimonio": round(imovel_val + patrim_comprador, 2)},
            {"cenario": "Alugar + investir", "patrimonio": round(patrim_inquilino, 2)},
        ], key=lambda x: -x["patrimonio"]),
        "historico_anual": historico_anual,
    }


# ─────────────────────────────────────────────────────────────
# Report Generation
# ─────────────────────────────────────────────────────────────

def gerar_relatorio_texto(imoveis: list[Imovel], sim: dict) -> str:
    """Gera relatório em texto formatado."""
    lines = []
    w = lines.append
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    w(f"{'='*75}")
    w(f"RELATÓRIO COMPARATIVO: ALUGUEL vs COMPRA — BOM PASTOR, DIVINÓPOLIS/MG")
    w(f"Gerado em: {now}")
    w(f"{'='*75}")

    # ── Dados do mercado ──
    venda = [i for i in imoveis if i.tipo == "venda" and i.area >= 100 and i.vagas >= 1]
    aluguel = [i for i in imoveis if i.tipo == "aluguel"]

    w(f"\n📊 DADOS DO MERCADO (casas Bom Pastor)")
    w(f"\n── VENDA ({len(venda)} imóveis, filtro: ≥100m², com garagem) ──")
    w(f"{'Área':>7} | {'Q':>2} | {'B':>2} | {'V':>2} | {'Preço':>14} | {'R$/m²':>9} | {'Fonte':<20}")
    w(f"{'─'*7}-+-{'─'*2}-+-{'─'*2}-+-{'─'*2}-+-{'─'*14}-+-{'─'*9}-+-{'─'*20}")
    for i in sorted(venda, key=lambda x: x.preco):
        w(f"{i.area:>6.0f}m²| {i.quartos:>2} | {i.banheiros:>2} | {i.vagas:>2} | R$ {i.preco:>11,.0f} | R$ {i.preco_m2:>6,.0f} | {i.fonte:<20}")

    if venda:
        precos_v = [i.preco for i in venda]
        w(f"\n  Mediana venda: R$ {sorted(precos_v)[len(precos_v)//2]:,.0f}")
        w(f"  Faixa: R$ {min(precos_v):,.0f} — R$ {max(precos_v):,.0f}")

    w(f"\n── ALUGUEL ({len(aluguel)} imóveis) ──")
    w(f"{'Área':>7} | {'Q':>2} | {'B':>2} | {'V':>2} | {'Aluguel/mês':>14} | {'Fonte':<20}")
    w(f"{'─'*7}-+-{'─'*2}-+-{'─'*2}-+-{'─'*2}-+-{'─'*14}-+-{'─'*20}")
    for i in sorted(aluguel, key=lambda x: x.preco):
        w(f"{i.area:>6.0f}m²| {i.quartos:>2} | {i.banheiros:>2} | {i.vagas:>2} | R$ {i.preco:>11,.0f} | {i.fonte:<20}")

    if aluguel:
        precos_a = [i.preco for i in aluguel]
        w(f"\n  Mediana aluguel: R$ {sorted(precos_a)[len(precos_a)//2]:,.0f}/mês")

    # ── Simulação financeira ──
    p = sim["parametros"]
    r = sim["resultado"]
    m = sim["medias"]

    w(f"\n{'='*75}")
    w(f"💰 SIMULAÇÃO FINANCEIRA (30 ANOS COM CICLOS ECONÔMICOS)")
    w(f"{'='*75}")
    w(f"\n  Imóvel: R$ {p['preco_imovel']:,.0f} | Entrada {p['entrada_pct']*100:.0f}%: R$ {p['entrada_valor']:,.0f}")
    w(f"  Financiamento: R$ {p['financiado']:,.0f} a {p['taxa_financ']*100:.0f}% a.a.")
    w(f"  Parcela: R$ {p['parcela']:,.0f}/mês | Amortização extra: R$ {p['amort_extra_valor']:,.0f}/mês")
    w(f"  Orçamento mensal: R$ {p['orcamento_mensal']:,.0f} (igual para todos os cenários)")
    w(f"  Aluguel inicial: R$ {p['aluguel_inicial']:,.0f}/mês")
    w(f"\n  Médias projetadas: Selic {m['selic_media']:.1f}% | IPCA {m['ipca_medio']:.1f}% | Juros real {m['juros_real_medio']:.1f}%")

    w(f"\n── EVOLUÇÃO ANO A ANO ──")
    w(f"{'Ano':>4} | {'IPCA':>5} | {'Selic':>5} | {'Aluguel':>9} | {'Parcela':>9} | {'Saldo fin.':>11} | {'Patrim.Inq.':>13}")
    w(f"{'─'*4}-+-{'─'*5}-+-{'─'*5}-+-{'─'*9}-+-{'─'*9}-+-{'─'*11}-+-{'─'*13}")
    for h in sim["historico_anual"]:
        if h["ano"] in [1, 3, 5, 8, 10, 12, 15, 20, 25, 30]:
            sd = f"R$ {h['saldo_com']:>8,.0f}" if h["saldo_com"] > 0 else "  QUITADO"
            w(f"{h['ano']:>4} | {h['ipca']:>4.1f}% | {h['selic']:>4.1f}% | R$ {h['aluguel']:>6,.0f} | R$ {p['parcela']:>6,.0f} | {sd:>11} | R$ {h['patrim_inquilino']:>10,.0f}")

    w(f"\n── RESULTADO FINAL ──")
    w(f"  Financiamento quitado em: {r['anos_quitou']:.1f} anos ({r['meses_quitou']} meses)")
    w(f"  Economia de juros com amortização: R$ {r['economia_juros']:,.0f}")
    w(f"  Aluguel ultrapassa parcela no: Ano {r['crossover_ano']}")
    w(f"  Aluguel final: R$ {r['aluguel_final']:,.0f}/mês vs Parcela: R$ {r['parcela_fixa']:,.0f}/mês")

    w(f"\n{'='*75}")
    w(f"🏆 RANKING PATRIMONIAL (30 ANOS)")
    w(f"{'='*75}")
    for i, item in enumerate(sim["ranking"]):
        w(f"  {i+1}º {item['cenario']:<30} R$ {item['patrimonio']:>12,.0f}")

    vencedor = sim["ranking"][0]
    segundo = sim["ranking"][1]
    ratio = vencedor["patrimonio"] / segundo["patrimonio"]
    w(f"\n  {vencedor['cenario']} vence por {ratio:.1f}x")

    return "\n".join(lines)


def gerar_csv(imoveis: list[Imovel], sim: dict) -> str:
    """Gera dados em CSV."""
    lines = ["tipo,area_m2,quartos,banheiros,vagas,preco,preco_m2,fonte,bairro"]
    for i in imoveis:
        lines.append(f"{i.tipo},{i.area},{i.quartos},{i.banheiros},{i.vagas},{i.preco},{i.preco_m2:.2f},{i.fonte},{i.bairro}")

    lines.append("")
    lines.append("ano,year,ipca,selic,aluguel,saldo_financ,patrim_comprador,patrim_inquilino,imovel_valor")
    for h in sim["historico_anual"]:
        lines.append(f"{h['ano']},{h['year']},{h['ipca']},{h['selic']},{h['aluguel']},{h['saldo_com']},{h['patrim_comprador']},{h['patrim_inquilino']},{h['imovel_val']}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def publish_to_docs(data: dict, docs_dir: str) -> str:
    """Save JSON to docs/data/YYYY-MM-DD.json, copy to latest.json, update history.json."""
    docs = Path(docs_dir)
    data_dir = docs / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    data_file = data_dir / f"{today}.json"
    latest_file = docs / "latest.json"
    history_file = docs / "history.json"

    # Write dated file
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    data_file.write_text(json_str, encoding="utf-8")
    print(f"  Salvo: {data_file}")

    # Copy to latest.json
    latest_file.write_text(json_str, encoding="utf-8")
    print(f"  Atualizado: {latest_file}")

    # Update history.json
    history = []
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            history = []

    # Remove existing entry for today (re-run)
    history = [h for h in history if h.get("date") != today]
    history.insert(0, {"date": today, "file": f"data/{today}.json"})
    history_file.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Atualizado: {history_file}")

    return str(data_file)


def main():
    parser = argparse.ArgumentParser(description="Relatório Aluguel vs Compra — Bom Pastor, Divinópolis/MG")
    parser.add_argument("--preco", type=float, default=500000, help="Preço do imóvel (default: 500000)")
    parser.add_argument("--aluguel", type=float, default=2000, help="Aluguel mensal inicial (default: 2000)")
    parser.add_argument("--entrada", type=float, default=0.30, help="Percentual de entrada (default: 0.30)")
    parser.add_argument("--juros", type=float, default=0.10, help="Taxa de financiamento anual (default: 0.10)")
    parser.add_argument("--amortizacao", type=float, default=0.5, help="Amortização extra como fração da parcela (default: 0.5)")
    parser.add_argument("--export", choices=["texto", "csv", "json"], default="texto", help="Formato de saída")
    parser.add_argument("--no-scrape", action="store_true", help="Pular scraping (usar só simulação)")
    parser.add_argument("--output", type=str, default=None, help="Arquivo de saída (default: stdout)")
    parser.add_argument("--docs-dir", type=str, default=None,
                        help="Publish JSON to docs/ directory (e.g. ../docs). Creates data/YYYY-MM-DD.json, latest.json, history.json")
    args = parser.parse_args()

    # Scraping
    if args.no_scrape:
        imoveis = []
        print("Scraping pulado (--no-scrape)")
    else:
        imoveis = scrape_todos()

    # Simulação
    print("\nExecutando simulacao financeira...\n")
    sim = simular(
        preco=args.preco,
        aluguel_ini=args.aluguel,
        entrada_pct=args.entrada,
        taxa_financ=args.juros,
        amort_extra_pct=args.amortizacao,
    )

    # Build full data payload
    full_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "generated_at": datetime.now().isoformat(),
        "imoveis": [i.to_dict() for i in imoveis],
        "simulacao": sim,
        "resumo": {
            "total_imoveis": len(imoveis),
            "total_venda": len([i for i in imoveis if i.tipo == "venda"]),
            "total_aluguel": len([i for i in imoveis if i.tipo == "aluguel"]),
            "fontes": list(set(i.fonte for i in imoveis)),
        },
    }

    # Publish to docs/ if requested
    if args.docs_dir:
        print("\nPublicando em docs/...")
        publish_to_docs(full_data, args.docs_dir)

    # Output
    if args.export == "json":
        output = json.dumps(full_data, indent=2, ensure_ascii=False)
    elif args.export == "csv":
        output = gerar_csv(imoveis, sim)
    else:
        output = gerar_relatorio_texto(imoveis, sim)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\nRelatorio salvo em: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
