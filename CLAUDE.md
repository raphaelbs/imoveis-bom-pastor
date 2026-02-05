# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Full scrape + publish to docs/
python3 scraper/relatorio_imoveis.py --docs-dir docs

# Simulation only (no scraping)
python3 scraper/relatorio_imoveis.py --no-scrape --preco 500000 --aluguel 2000

# Export formats
python3 scraper/relatorio_imoveis.py --export json --docs-dir docs
python3 scraper/relatorio_imoveis.py --export csv --output relatorio.csv
python3 scraper/relatorio_imoveis.py --export texto

# Trigger GitHub Action manually
gh workflow run scrape.yml --repo raphaelbs/imoveis-bom-pastor
```

No dependencies beyond Python 3.12 stdlib. No tests.

## Architecture

**Scraper** (`scraper/relatorio_imoveis.py`) — single-file Python script with four concerns:

1. **Scrapers**: Four imobiliárias in Divinópolis/MG, each with its own function. Ala and Achei use the same platform (JSON POST API). Francisco and MGF use HTML regex parsing. All target Bom Pastor neighborhood.
2. **Financial simulation**: 30-year rent vs buy comparison using historical IPCA/Selic data (2010-2025) plus projected cycles (2026-2039). Three scenarios: buy with extra amortization, buy without, rent + invest.
3. **Report generation**: Text (ASCII tables), CSV, and JSON output formats.
4. **Docs publishing** (`--docs-dir`): Writes `docs/data/YYYY-MM-DD.json`, copies to `docs/latest.json`, appends to `docs/history.json`.

**Dashboard** (`docs/index.html`) — standalone SPA using Alpine.js + Tailwind via CDN. Reads `latest.json` for current view and `history.json` for date navigation. No build step — works opening locally as a file.

**GitHub Action** (`.github/workflows/scrape.yml`) — runs every Monday 08:00 UTC, executes scraper, auto-commits new data to `docs/`.

## Key data flow

```
GitHub Action → scraper/relatorio_imoveis.py --docs-dir docs
  → scrape 4 imobiliárias (aluguel + venda)
  → run 30-year simulation
  → write docs/data/YYYY-MM-DD.json
  → copy to docs/latest.json
  → update docs/history.json
  → Action commits + pushes docs/
```

## Scraper details

- Ala/Achei scrapers use `http_post()` to a `/imoveis/ajax/` endpoint with form-encoded params. Bairro codes: Ala uses `7,358`, Achei uses `12`.
- Francisco/MGF scrapers use `http_get()` + regex parsing. These are fragile and may break if the sites change HTML structure.
- ZAP Imóveis and VivaReal are NOT included — they use Cloudflare bot protection.
- SSL verification is disabled (`CERT_NONE`) to handle sites with bad certificates.
