# research-tools

Small tools for research sessions on the claude-dev machine, plus a SearXNG search engine that runs there in Docker.

- `bin/websearch`: queries SearXNG and prints the raw ranked results (title, URL, which engines returned it, date), naming any engine that failed. A second search source next to an AI assistant's built-in search, so the two can be compared. Also: academic search (Semantic Scholar), `compare` for two result lists, and the controls for the server and the experiment.
- `bin/websearch-hook`: the experiment. A Claude Code hook that repeats every built-in web search on SearXNG and logs the comparison.
- `bin/fetchpage`: fetches a page with headless Chromium and prints its text, HTML, links or a screenshot. For pages that are empty without JavaScript. It reports the HTTP status so blocks are visible.
- `searxng/`: the Docker Compose file and settings for SearXNG on claude-dev, reachable from that machine only, JSON API enabled.
- `SPEC.md` and `PLAN.md`: what this was built to do (done checks 1 to 7) and how.

## Setup on claude-dev

```sh
cd /mnt/code/research-tools
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install   # Playwright 1.64.1, matches Chromium build 1248
export PATH="$PWD/bin:$PATH"
```

`websearch` is standard-library Python 3; nothing to install. It talks to `http://127.0.0.1:8888` unless `SEARXNG_URL` says otherwise.

`fetchpage` expects Playwright's Chromium headless shell under `~/.cache/ms-playwright/chromium_headless_shell-*/`. On claude-dev the shell needs the Debian libraries staged under `~/.local/chrome-libs/root`; the script adds that directory to `LD_LIBRARY_PATH` automatically when it exists. Override the browser with `FETCHPAGE_CHROME=/path/to/chrome`.

## Usage

```sh
websearch milamend NSF certified            # 15 results from the local SearXNG
websearch -c science -t year inositol PCOS  # science category, last year
websearch -s -n 5 '!pubmed myo-inositol'    # snippets; SearXNG bang syntax selects an engine
websearch --json query > results.json       # raw JSON (failed engines also named on stderr)
websearch --public query                    # public instance fallback (usually fails: most disable JSON)

websearch compare builtin.txt searx.json    # which links two lists share; one URL per line or JSON
websearch compare builtin.txt --query Q     # compare a saved list with a fresh SearXNG search
websearch compare a b --json --labels built-in,searxng

websearch server status                     # container state, answering or not, pinned image
websearch server start|stop                 # stop is temporary: the next search starts it again
websearch server update                     # move the pin to the newest SearXNG image; commit the change

websearch experiment status|on|off          # the built-in vs SearXNG experiment
websearch experiment report [--save]        # summary; --save also writes it to the outbox

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

When SearXNG cannot answer, `websearch` prints one line within 5 seconds that says why and names the built-in web search as the fallback, and exits non-zero.

`scholar`, `compare`, `server` and `experiment` are commands only when what follows fits them (a file for `compare`, an action for `server` and `experiment`), so `websearch compare postgres vs mysql` is an ordinary search. `websearch -- <query>` always searches.

### What fetchpage is not for

It renders JavaScript. It does not try to get past bot checks, captchas or paywalls, and its default user agent is Playwright's own, which identifies itself as HeadlessChrome. Sites that refuse automated clients (PitchBook, Forbes, OpenCorporates were the examples that prompted this tool) will still refuse it, and that refusal is the answer. On claude-dev the permission classifier also blocks fetches aimed at such sites. `--ua` exists for sites that legitimately need a specific string, not for impersonation.

## SearXNG on claude-dev

Installed 2026-11-02 following the SearXNG container docs (docs.searxng.org, "Installation container", which calls Docker "recommended for most users"). claude-dev has Debian's `docker.io` and `docker-compose` packages, the Docker service starts at boot, and the account is in the `docker` group.

- `searxng/docker-compose.yml`: the image is pinned to one exact build (tag and digest); `restart: unless-stopped` brings it back after a reboot; the port is published on `127.0.0.1:8888` only; the cache lives on claude-dev's own disk at `~/.local/share/research-tools/searxng-data/`.
- The server secret is in `~/.config/research-tools/searxng.env` (mode 600), generated once at install. Never commit it.
- `searxng/config/settings.yml`: JSON output on (off by default, returns 403 otherwise); limiter off, because only this machine can reach the server and the limiter needs Valkey; `public_instance: false`; `image_proxy: false`; default language `en`; safe search off.
- If the server is not answering, `websearch` runs `docker compose up -d` itself (under a lock, so two sessions do not race) and waits at most 5 seconds. A cold start that takes longer keeps going in the background, so the next search works.
- The container's log shows `chown: /etc/searxng: Operation not permitted` at start: the settings folder is on the NAS, which does not allow the change. SearXNG reads it fine. The `ahmia` and `torch` engines fail to load because they need Tor; harmless.
- Engines block servers that search too often. Only three engines give general web results by default (Brave, DuckDuckGo, Google CSE); during the build DuckDuckGo answered with a CAPTCHA after about a dozen searches and Brave suspended the server after about forty, leaving Google CSE alone. `websearch` names such engines on every search, and the experiment report counts them.

To start from nothing on another Debian machine: `sudo apt-get install docker.io docker-compose`, `sudo usermod -aG docker $USER`, create the secret file with `SEARXNG_SECRET=` followed by `openssl rand -hex 32` (mode 600), then `websearch server start`.

## The experiment: built-in search vs SearXNG

Started 2026-11-03 and runs until it is stopped: "Maybe we find out that the search results are exactly the same, or that they are very different." (Gianni, 2026-11-02.)

- The hook is wired in the notebook's `claude/settings.json` (`PostToolUse` on `WebSearch`, `async`), so it runs in every Claude Code session on claude-dev without slowing it.
- For each built-in search it runs the same query on SearXNG (applying the same `allowed_domains` and `blocked_domains`), then appends one JSON line to `experiment/log.jsonl` with both full lists, both timings, failed engines and the comparison numbers. If SearXNG is unavailable the line is still written, marked so.
- It writes SearXNG's full list to `experiment/searches/<date>-<time>-<id>.md` and gives the session a one-line note naming that file, so Claude can open it when the extra links matter.
- `experiment/` is not committed: research queries can be private.
- `websearch experiment off` pauses it (a one-word file, `~/.config/research-tools/experiment`; no file means on; off, false, 0, no and disabled all mean off).
- Privacy: while it runs, every built-in query from every session also goes to the engines SearXNG uses (Bing, Brave, DuckDuckGo, Google and others) and is written to `experiment/log.jsonl` on the NAS.

How the lists are compared (`websearch compare` and the hook use the same code):

- Links are tidied first, so trivial differences do not count: http or https, a leading `www.`, host case, default ports, a trailing slash, the part after `#`, percent-encoding, parameter order, and tracking parameters (`utm_*`, `gclid`, `fbclid`, `srsltid` and similar). Different pages on the same site stay different.
- Counts: in both, only in each.
- Overlap: shared links over all distinct links (0 to 1).
- Agreement at depth k: the share of the built-in list's k links that also appear in SearXNG's top k. The report's buckets use this: identical (1), mostly the same (0.5 or more), mostly different (below 0.5 with at least one link in common anywhere), nothing shared (no link in common anywhere).
- A search where SearXNG returned no results at all (every engine blocked or failed) is logged as `degraded` and, like an unavailable SearXNG, left out of the report's numbers and counted separately, so blocking cannot pass for disagreement.
- Rank-biased overlap (RBO), extrapolated form for lists of different lengths, with p = 0.9, which gives the top 10 ranks 86% of the weight. From W. Webber, A. Moffat and J. Zobel, "A Similarity Measure for Indefinite Rankings", ACM Transactions on Information Systems 28(4), November 2010 (equation 32; agreement is equation 3; p = 0.9 is the value the paper uses to compare search engines). Author's copy: http://codalism.com/research/papers/wmz10_tois.pdf

### Academic search

`websearch scholar` uses the Semantic Scholar Academic Graph API (api.semanticscholar.org/graph/v1, spec read 2026-10-30). It replaces Google Scholar, which has no API and whose robots.txt disallows automated queries, so this repo does not scrape it. Paper IDs accept `DOI:`, `PMID:`, `ARXIV:`, `PMCID:` prefixes or a Semantic Scholar id. Each result prints the DOI link, up to three authors, venue, year, citation count, PubMed id and open-access PDF when present. Relevance search returns at most 1,000 results in pages of 100.

- The key is read from `~/.config/research-tools/s2_api_key` (or `S2_API_KEY`), trimmed, and sent as `x-api-key`. It never appears in output, including error messages; a key file holding spaces or a second line is not used (one line says so), because the HTTP library's error for such a header would quote it. Without a key the tool says so in one line and searches without one.
- The key's terms allow 1 request per second, cumulative across all endpoints. The tool keeps every request at least 1.1 s after the previous one, across all sessions on the machine (a locked state file in `~/.local/state/research-tools/`), and stops at 200 requests per UTC day, the figure promised in the key application. Retries count toward both.
- Semantic Scholar refuses many requests (HTTP 429) whatever the spacing: on 2026-11-02 and 03, about half to seven in ten keyed requests, and nine in ten without a key. The tool retries up to 5 times after 2, 4, 8, 16 and 16 s plus a random extra, and prints one summary line. Some searches still fail; treat it as a tool for deliberate academic lookups, with SearXNG's `-c science` (Semantic Scholar, Europe PMC, arXiv, PubMed and others) as the first stop. Leave out `-t` there: engines that cannot filter by date drop out, and on 2026-11-03 a dated science search returned nothing.
- Terms: never share the key; credit "Semantic Scholar" in published material that uses its data; some data is CC BY-NC; keys unused for about 60 days may be removed.

## Tests

```sh
python3 -m unittest discover tests              # automated, offline: fake SearXNG and Semantic Scholar servers
RT_LIVE=1 python3 -m unittest tests.test_live -v   # live: real container and APIs (uses about 12 Semantic Scholar requests)
```

The live check that Docker restarts the container after a reboot needs sudo, so it is run by hand: `sudo systemctl restart docker`, then `websearch server status`.

## Why this exists

An AI assistant's built-in web search returns a short list plus a model-written summary, and does not disclose the search provider or ranking. Running a second search engine you control makes the difference visible. The fetcher exists because, in a company due-diligence task on 2026-10-30, the losses came from pages the plain fetcher could not read, not from search.
