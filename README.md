# research-tools

Two small tools for research sessions, plus a SearXNG deployment for the NAS.

- `bin/websearch`: queries a SearXNG instance and prints the raw ranked results (title, URL, which engines returned it, date). A second search source next to whatever an AI assistant's built-in search returns, so the two can be compared.
- `bin/fetchpage`: fetches a page with headless Chromium and prints its text, HTML, links or a screenshot. For pages that are empty without JavaScript. It reports the HTTP status so blocks are visible.
- `searxng/`: Docker Compose and settings for a LAN-only SearXNG with the JSON API enabled.

## Setup on a session machine

```sh
cd /mnt/code/research-tools
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install   # Playwright 1.64.1, matches Chromium build 1248
export PATH="$PWD/bin:$PATH"
export SEARXNG_URL=http://10.0.0.16:8888          # default if unset
```

`websearch` is standard-library Python 3; nothing to install.

`fetchpage` expects Playwright's Chromium headless shell under `~/.cache/ms-playwright/chromium_headless_shell-*/`. On the claude-dev container the shell needs the Debian libraries staged under `~/.local/chrome-libs/root`; the script adds that directory to `LD_LIBRARY_PATH` automatically when it exists. Override the browser with `FETCHPAGE_CHROME=/path/to/chrome`.

## Usage

```sh
websearch milamend NSF certified            # 15 results from the NAS instance
websearch -c science -t year inositol PCOS  # science category, last year
websearch -s -n 5 '!pubmed myo-inositol'    # snippets; SearXNG bang syntax selects an engine
websearch --json query > results.json       # raw JSON, includes answers/infoboxes/suggestions
websearch --public query                    # public instance fallback (usually fails: most disable JSON)

websearch scholar inositol PCOS                        # Semantic Scholar, 15 results, relevance ranked
websearch scholar -y 2020- --type Review,MetaAnalysis -s inositol PCOS
websearch scholar --cited-by DOI:10.1002/jrsm.1378     # citation chaining: who cites this paper
websearch scholar --references PMID:31614060           # what this paper cites
websearch scholar --open-access --min-citations 50 query

fetchpage https://example.com/              # page text to stdout; status, URL, title to stderr
fetchpage --links URL                       # "text -> href" per link
fetchpage --html --selector main URL        # HTML of one element
fetchpage --screenshot out.png URL          # full-page PNG
fetchpage --wait networkidle --timeout 60000 URL
```

Exit codes for `fetchpage`: 0 on 2xx/3xx, 3 on 4xx/5xx or navigation failure, 2 if the browser cannot start.

### What fetchpage is not for

It renders JavaScript. It does not try to get past bot checks, captchas or paywalls, and its default user agent is Playwright's own, which identifies itself as HeadlessChrome. Sites that refuse automated clients (PitchBook, Forbes, OpenCorporates were the examples that prompted this tool) will still refuse it, and that refusal is the answer. In the claude-dev container the permission classifier also blocks fetches aimed at such sites. `--ua` exists for sites that legitimately need a specific string, not for impersonation.

### Academic search

`websearch scholar` uses the Semantic Scholar Academic Graph API (api.semanticscholar.org/graph/v1, spec read 2026-10-30). It replaces Google Scholar, which has no API and whose robots.txt disallows automated queries, so this repo does not scrape it. Paper IDs accept `DOI:`, `PMID:`, `ARXIV:`, `PMCID:` prefixes or a Semantic Scholar id. Each result prints the DOI link, up to three authors, venue, year, citation count, PubMed id and open-access PDF when present. Relevance search returns at most 1,000 results in pages of 100.

The unauthenticated quota is shared by everyone and returned 429 on most calls during testing, so the client retries three times with backoff and then tells you to get a key. Apply for a free key at https://www.semanticscholar.org/product/api#api-key-form and `export S2_API_KEY=...`; the client sends it as `x-api-key`.

## Deploying SearXNG on the NAS (TrueNAS)

The compose files follow the SearXNG container docs (docs.searxng.org, version 2026.10.30). The TrueNAS steps follow apps.truenas.com "Installing custom apps" (read 2026-10-30, page undated).

1. Generate a secret: `openssl rand -hex 32`.
2. On the NAS web UI: **Apps > Discover**, the three-dot menu, **Install via YAML**. Name it `searxng`.
3. Paste `searxng/truenas-compose.yml` with `REPLACE_ME` swapped for the secret. The config bind mount points at this repo's `searxng/config/` through the pool path `/mnt/main/code/research-tools/searxng/config`, so `settings.yml` is already in place. Create `searxng/data/` first (it is gitignored) or point that mount elsewhere.
4. Save. Then from any LAN machine:

```sh
curl 'http://10.0.0.16:8888/search?q=test&format=json' | head -c 300
websearch test
```

If the JSON call returns 403, `search.formats` in `settings.yml` is not being read; check the bind mount path.

With Docker Compose on a normal host instead: copy `searxng/.env.example` to `searxng/.env`, set the secret, `docker compose up -d` in `searxng/`.

Settings choices, all in `searxng/config/settings.yml`: JSON output on (off by default, returns 403 otherwise), limiter off because the instance is LAN-only and the limiter needs Valkey, `public_instance: false`, `image_proxy: false`, default language `en`, safe search off. `SEARXNG_SECRET` and `SEARXNG_BASE_URL` are read from the environment, which overrides `server.secret_key` and `server.base_url` in the file.

## Why this exists

An AI assistant's built-in web search returns a short list plus a model-written summary, and does not disclose the search provider or ranking. Running a second search engine you control makes the difference visible. The fetcher exists because, in a company due-diligence task on 2026-10-30, the losses came from pages the plain fetcher could not read, not from search.
