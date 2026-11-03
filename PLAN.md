# Plan: the second search engine (research-tools), stage 3

Written 2 November 2026 for Gianni's approval. Briefs answered the same day (see "Decided" below). Builds what `research-tools/SPEC.md` (approved 2 November) asks for. Nothing in this plan has been built yet. Stage 4 (the build) starts only after you approve this, in a fresh session, as the build workflow draft says.

## Decided (Gianni, 2 November 2026)

- Brief 1: "Run docker". SearXNG runs in Docker with Compose (option A).
- Brief 2: "Claude should see the B, and then C if needed by a link." After each built-in search, the session gets the one-line note, and the note carries a link to a file holding SearXNG's full list, which Claude opens only when it needs it.
- Brief 3: "Go ahead with the deletion." Delete `searxng/truenas-compose.yml` and `searxng/.env.example` (option C).

## In one paragraph

SearXNG runs on claude-dev in a Docker container, SearXNG's main recommended method, using the Compose file already in the repo. Docker brings it back after a restart, and the search tool also starts it by itself if it is not running. Semantic Scholar searches read the key from its private file and are spaced a little over one second apart, even when two sessions search at once, with your 200-a-day promise enforced. A new `websearch compare` command shows which links two result lists share. Finally, a hook (a small program Claude Code runs automatically after each built-in search) repeats every built-in search on SearXNG and writes both lists and their overlap to a log, which a `websearch experiment report` command summarises. One command turns the experiment off.

## What I checked for this plan (2 November)

- claude-dev is a full virtual machine (KVM) running Debian 13.7, with systemd (Debian's service manager) in charge, Python 3.13.5, git, and internet access to GitHub and PyPI (the Python package site). [VERIFIED: `systemd-detect-virt`, `/etc/debian_version`, `curl`]
- Admin rights work with the password you gave on 2 November. [VERIFIED: `sudo` this session] Debian offers Docker 26.1.5 with docker-compose 2.26.1, and Podman 5.4.2 with podman-compose 1.3.0. [VERIFIED: `apt-cache policy`]
- For option C only: SearXNG's dependencies all have ready-made Linux packages for Python 3.13, so nothing needs compiling: lxml 6.1.3, msgspec 0.22.0, curl_cffi 0.17.0, and the Granian web server 2.8.7. [VERIFIED: PyPI file lists]
- SearXNG's current source is commit `cccbc9e158` (2 November 2026, 17:38 UTC). Option C would pin that commit; options A and B pin the matching image instead. [VERIFIED: GitHub API]
- About 3.5 GB of memory and 23 GB of disk are free. [VERIFIED: `free`, `df`]
- What Claude Code hands a hook after a built-in search: the documented inputs are `query`, `allowed_domains`, `blocked_domains` and `mode`. The result's shape is not documented. [VERIFIED: hooks reference, code.claude.com/docs/en/hooks.md, saved copy read this session] In your saved transcripts, each built-in search result holds the query, a list of links (title and URL), a text summary, `durationSeconds` and `searchCount`. Across 73 past searches it returned 7 to 20 links, median 10. [VERIFIED: my count over `~/.claude/projects/*/*.jsonl`] That the hook receives the same object is [INFERRED]; the first test in slice 6 checks it.
- A hook can run in the background (`"async": true`) so the session never waits for it. Anything it prints reaches Claude only on the next turn. [VERIFIED: hooks reference, "Run hooks in the background"]

## Choices made in this plan (with options)

### How SearXNG is installed and run

How I found the options: SearXNG's own docs (the container, step-by-step and Granian installation pages, read this session, undated, generated from the current source) and the facts above.

| Option | What it is | Trade-offs |
| --- | --- | --- |
| **A. Docker with Compose** | Install Docker from Debian, then run SearXNG's official image from the repo's existing `searxng/docker-compose.yml`, adapted for claude-dev. | The docs call Docker "recommended for most users" and Compose "the recommended way". [VERIFIED: docs.searxng.org "Installation container"] Docker restarts the container at boot by itself (`restart: unless-stopped`, already in the file). The Docker service runs all the time. For the tool to start the container without a password, your account joins the `docker` group, which amounts to admin rights for anything running as you, Claude sessions included. [INFERRED; I have not read Docker's own page on this today] Undo: remove the package and the group. |
| B. Podman, without admin rights | The same image, run by Podman as your own account, with no background service and no admin-level group. | Safer, but starting at boot needs "lingering" (letting your account run services while logged out) and a per-user service, neither set up here. [VERIFIED: `loginctl` says your account is not lingering; the previous session found no per-user service manager] The docs note "some considerations" for this mode. More pieces to get right. |
| C. Install in the home folder, no container | Download the source, make a private Python environment, run with Granian (SearXNG's newer web server). | Works without Docker, but the docs say Granian is "only officially supported in the Installation container", and pip has to be added by hand. [VERIFIED: Granian page] Restart at boot would need a hand-made service. |
| D. A public SearXNG server | No install. | Most public servers turn off the machine-readable output the tool needs. [STATED: README, "Usage"] |

**Recommendation: A**, see brief 1. What changes for claude-dev:
- The container listens only at `127.0.0.1:8888`, meaning this machine and nothing else, since only Claude sessions here use it (SPEC, "Who uses it").
- The image is pinned to the exact version current at install, instead of `latest`, so the install is repeatable.
- The settings file stays in the repo (`searxng/config/settings.yml`). The cache folder moves to claude-dev's own disk, `~/.local/share/research-tools/searxng-data/`, so the NAS holds no container data.
- A one-time server secret is generated at install and kept in `~/.config/research-tools/searxng.env`, readable only by your account.
- No Valkey (a database SearXNG's own Compose template adds for its bot limiter). The limiter is off, because only this machine can reach the server. [VERIFIED: `settings.yml` sets `limiter: false`]

### How "starts by itself" and "says so within 5 seconds" fit together

Done check 3 wants a one-line message within 5 seconds when the server is down; check 4 wants the tool to start it. Docker normally keeps the server running, so this is the backup path. A cold start may take longer than 5 seconds, so the tool waits at most 5 seconds. If the server is not ready by then, it prints one line ("SearXNG is starting, not ready yet; use the built-in search for now") and leaves the server starting in the background, so the next search works. If the server cannot start at all (for example Docker itself is down), the line says why and how to see the container's log. A lock file stops two sessions from starting two servers at once. [INFERRED: my reading of checks 3 and 4 together; tell me if you meant something else]

### The Semantic Scholar promises

The approval note asks for at most 1 request per second, "cumulative across all endpoints", and asks us to stay below that. [STATED: your pasted note] The tool keeps:
- **Spacing:** a small shared file recording the time of the last request, locked while in use, so every request waits until 1.1 seconds have passed, even across separate sessions.
- **Daily cap:** the same file counts requests per day; at 200 the tool refuses with one line. Your application promised 200 a day. [STATED: handoff section 3]
- **Backoff:** a rate-limit refusal (an HTTP 429 error) is retried with growing waits, as today. Retries count toward the spacing and the cap.
- **Limits on what is asked:** at most 100 results per call (already the case, `bin/websearch:110`) and only the listed fields. [VERIFIED for the 100 cap]
- **The key:** read from `~/.config/research-tools/s2_api_key`, with stray spaces and line endings trimmed, and sent as `x-api-key` (already the case, `bin/websearch:46-48`). It never appears in output or error messages. If the file is missing, the tool says so in one line and searches without a key, as it does today.

### The experiment's log

- **Where:** `/mnt/code/research-tools/experiment/log.jsonl`, on the NAS so it survives anything happening to claude-dev, and excluded from git because research queries can be private. One line per search, in JSON (a plain-text format both programs and people can read).
- **The full list for Claude (brief 2):** each search also gets a small readable file, `/mnt/code/research-tools/experiment/searches/<date>-<time>-<id>.md`, with SearXNG's full list and the comparison. The one-line note to the session names that file.
- **What each line holds:** date and time, session, the query and any domain filters, both result lists in order (title, URL, and for SearXNG which engines found it), each side's timing, SearXNG engines that failed, and the comparison numbers below. If SearXNG was unavailable, the line still gets written, marked so, rather than the search being dropped (the notebook's "keep every stage's metrics" rule).
- **The comparison numbers:**
  - links in common, only in the built-in list, only in SearXNG's
  - the overlap as a share (0 means nothing shared, 1 means identical sets)
  - overlap among the top 10 of each
  - **rank-biased overlap**, a 0-to-1 score that also counts whether the shared links sit near the top. It is from Webber, Moffat and Zobel, "A Similarity Measure for Indefinite Rankings", which uses comparing search engines as its example. [VERIFIED: title, authors and abstract, author's copy at codalism.com/research/papers/wmz10_tois.pdf, read this session; STATED from memory: published in ACM Transactions on Information Systems, 2010]
- **Matching links fairly:** before comparing, links are tidied so trivial differences do not count as different: http and https, a leading "www.", a trailing slash, the part after `#`, and tracking tags such as `utm_source`. If the built-in search was limited to certain sites, SearXNG's list gets the same limit before comparing.
- **The report:** `websearch experiment report` prints:
  - how many searches are logged
  - how they spread across "identical", "mostly the same", "mostly different" and "nothing shared"
  - the median overlap
  - what share of built-in links SearXNG also found, and the reverse
  - which engines fail most often

  With `--save` it writes the same report to your outbox as a dated file you can open on your phone. Both outcomes you mentioned ("exactly the same" or "very different") show up directly in that spread.

### The off switch

`websearch experiment off` (and `on`, `status`). It writes a one-word setting in `~/.config/research-tools/experiment`. When it is off, the hook exits at once and logs nothing. You can ask any session to run it.

## Decisions for you

Ordered hardest to undo first.

### Brief 1: Docker, Podman, or no container?

1. **Question:** should SearXNG run in Docker (A), in Podman without admin rights (B), or without a container (C)?
2. **Why now:** slice 1 installs it, and installing system software is the hardest step here to undo. If you do not decide, nothing gets installed.
3. **Background:** a container is a sealed box holding a program and everything it needs, so it runs the same anywhere. SearXNG publishes an official one. You have given me admin rights, so either container tool can be installed.
4. **Options:** the table above. In short:
   - **A. Docker:** the docs' main path, comes back after a restart by itself; the cost is the `docker` group, which gives anything running as you, Claude included, admin-level control of the machine without a password. [INFERRED]
   - **B. Podman:** no admin-level group; needs extra start-at-boot setup that has not worked on this machine before. [VERIFIED for the missing setup]
   - **C. No container:** the setup we planned before you gave admin rights; least official. [VERIFIED for the Granian note]
5. **Recommendation: A.** Simplest to keep working, and it follows the docs. Claude sessions on claude-dev can already use the admin password you gave, so the `docker` group gives them little they cannot already do. [INFERRED] I'd change my mind if you plan to stop giving sessions the admin password; then B.
6. **How I found the options:** SearXNG's installation pages, Debian's package list and checks on claude-dev, all this session.
7. **What to reply:** "1A", "1B" or "1C".

### Brief 2: should Claude see the SearXNG results after each built-in search?

1. **Question:** after the hook repeats a search, should it tell the session what SearXNG found, or only log it?
2. **Why now:** it shapes slice 6. If you do not decide, I build option B.
3. **Background:** the hook runs in the background, and anything it reports reaches Claude on the next turn. The spec's done check 7 asks only for the log. The spec's "What and why" also recalls the notebook's wish for every search to go through a second engine "with the differences reported".
4. **Options:**
   - **A. Log only.** Claude never sees it. The cleanest measurement, because the experiment does not change how sessions research. Costs nothing per search. Easy to change later. [INFERRED]
   - **B. Log, plus a one-line note** to Claude, for example "SearXNG found 6 links the built-in search did not; `websearch compare --last` shows them". About 150 characters per search. Claude gets the second engine's extra finds without running a second search by hand. Easy to change later. [INFERRED]
   - **C. Log, plus the full SearXNG list** handed to Claude. Up to about 2,000 characters per search, which adds up over a long research session. [INFERRED]
5. **Recommendation: B.** It delivers what the second engine is for at almost no cost. I'd switch to A if you want the experiment to measure the engines without them affecting each other.
6. **How I found the options:** the hooks reference (what a background hook can send back) and the spec.
7. **What to reply:** "2A", "2B" or "2C".

### Brief 3: may I remove the NAS install files?

1. **Question:** may I delete `searxng/truenas-compose.yml`, the setup file for TrueNAS SCALE's app screen?
2. **Why now:** the README fix in slice 7 rewrites the setup section and the Compose file changes in slice 1. If you do not decide, I keep the file and the README marks it as not for your NAS.
3. **Background:** that file only works on TrueNAS SCALE, and your NAS runs CORE. `searxng/docker-compose.yml` becomes the claude-dev setup, so it stays either way. `.env.example` is replaced by the generated secret file.
4. **Options:**
   - **A. Delete the TrueNAS file only.** Removes the one file that misleads; it stays in git history. [VERIFIED: committed in `42132d3`]
   - **B. Keep everything.** The README explains which files apply.
   - **C. Delete the TrueNAS file and `.env.example`.** Leaves only what claude-dev uses. Also kept in git history.
5. **Recommendation: C.** The SCALE steps have caused this mix-up twice ("This discrepancy keeps popping up"), and `.env.example` would describe a setup we no longer use.
6. **How I found the options:** the repo's file list and the handoff.
7. **What to reply:** "3A", "3B" or "3C".

### Notice, not a decision yet: the hook's setting lives in the notebook

The hook has to be listed in `~/.claude/settings.json` to run in every session, and that file is a copy of `notebook/claude/settings.json`. The alternative, a per-project settings file, would miss sessions started in other folders. [VERIFIED: settings docs, code.claude.com/docs/en/settings.md, saved copy] So slice 6 includes a notebook change. I will print the exact lines and wait for your approval at that point.

## Change list

| File | Change |
| --- | --- |
| `bin/websearch` | Default server becomes `http://127.0.0.1:8888`. Starts the container when the server is not answering. Names failed engines on every search. New commands: `compare`, `experiment on/off/status/report`, `server status/start/stop/update`. Semantic Scholar: key from the private file, spacing, daily cap. |
| `bin/websearch-hook` (new) | The experiment hook: reads what Claude Code hands it, runs the SearXNG search, writes the log line and the per-search file, and sends the one-line note naming that file. |
| `searxng/docker-compose.yml` | Adapted for claude-dev: only `127.0.0.1:8888`, pinned image, cache on the local disk, secret from `~/.config/research-tools/searxng.env`. |
| `searxng/config/settings.yml` | Comments updated for claude-dev. |
| claude-dev system (outside git) | Install `docker.io` and `docker-compose` from Debian; add your account to the `docker` group; turn on the Docker service at boot. |
| `tests/` (new) | Automated tests, standard Python only, run with `python3 -m unittest discover tests`. |
| `README.md` | Setup section rewritten for claude-dev; NAS steps removed; the experiment and its switch described. |
| `.gitignore` | Add `experiment/`. |
| `searxng/truenas-compose.yml`, `searxng/.env.example` | Deleted per brief 3. |
| `SPEC.md`, `PLAN.md` | Committed (this plan copied into the repo once approved). |
| `notebook/claude/settings.json`, then the copy at `~/.claude/settings.json` | Add the hook. Separate approval. |

Work happens on a branch, `searxng-on-claude-dev`, merged to `main` at the end on your yes, then pushed on your yes.

## Test list (plain English)

One or more per done check, then what must keep working. "Automated" tests run without the internet; "live" ones use the real server or real APIs, and their output is shown to you in stage 5.

**Check 1, at least 10 results from at least 2 engines**
- Live: a general query returns 10 or more results, and the results name at least 2 different engines.

**Check 2, a blocking engine is named**
- Automated: given a server reply that lists failed engines, the output prints a line naming each one and its reason (for example "google (CAPTCHA)").
- Automated: given a reply with no failures, that line is absent.
- Live: whatever engines fail during the stage 5 searches are named.

**Check 3, server down: one line within 5 seconds, naming the fallback**
- Automated: when the server cannot be reached and cannot be started, the tool prints exactly one line naming the built-in search as the fallback, and exits with an error, in under 5 seconds.
- Automated: when the server is still starting after 5 seconds, the tool prints the "starting, not ready yet" line and leaves the start running.

**Check 4, runs on claude-dev and starts by itself**
- Live: with the server stopped, a search starts it and returns results.
- Live: two searches started together produce one server, not two.
- Live: after the container is stopped, the next search brings it back with nothing else done.
- Live: after Docker itself restarts (standing in for a machine restart), the container is running again without any search.

**Check 5, Semantic Scholar: private key, never printed, 10 in a row, one per second or less**
- Live: 10 searches in a row all succeed with no rate-limit refusals, and the recorded request times are at least 1.1 seconds apart.
- Automated: two processes asking at the same moment are still spaced 1.1 seconds apart.
- Automated: the 201st request in a day is refused with one line and is never sent.
- Automated: the key never appears in any output, including error messages for a refused key and for network failures. The test compares inside the program and prints only pass or fail.
- Automated: a missing key file gives one line and a search without the key.

**Check 6, comparing two result lists**
- Automated: two lists give the right shared, built-in-only and SearXNG-only links.
- Automated: links that differ only by http/https, "www.", trailing slash, `#` part or tracking tags count as the same.
- Automated: different pages on the same site count as different.

**Check 7, the logged experiment with an off switch**
- Live, first: one real built-in search with the hook installed, to confirm what Claude Code hands the hook. If the shape differs from the transcripts, I stop and adjust the plan with you.
- Automated: a recorded hook input produces one log line with every field listed above, plus the per-search file.
- Automated: with the experiment off, the hook exits at once and logs nothing.
- Automated: with SearXNG unavailable, a line is still logged, marked unavailable.
- Automated: a built-in search limited to certain sites applies the same limit to SearXNG's list before comparing.
- Automated: the report counts and buckets a small sample log correctly, including "identical" and "nothing shared".
- Automated: the hook's note to the session is one line, under 300 characters, and names a per-search file that exists and holds SearXNG's full list.
- Live: after a few real built-in searches, the log has one line per search and the report prints.

**Must keep working**
- `websearch scholar` search, `--cited-by` and `--references` return results.
- `websearch --json`, `-c science`, `-t`, `-s` behave as before; `SEARXNG_URL` still overrides the server address.
- `fetchpage` is untouched.
- The notebook's hook tests still pass, 28 of 28 (`notebook/claude/tests/test_hooks.py`).

## Order of slices

Each slice: write its tests and watch them fail, build until they and all earlier tests pass, show the command and its output, commit on the branch.

1. **Install SearXNG** (per brief 1): install Docker, adapt the Compose file, generate the secret, pin the image, start it. Ends with check 1 passing by hand.
2. **Start by itself and the down message** (checks 3 and 4), plus the new default address.
3. **Name failed engines** (check 2).
4. **Semantic Scholar key, spacing and daily cap** (check 5).
5. **`websearch compare`** (check 6), including the link tidying.
6. **The experiment** (check 7): the hook, the log, the switch, the report, and the notebook settings change (separate approval).
7. **README, .gitignore, file removal per brief 2, commit SPEC and PLAN.**

Then stage 5 (I run every done check live and show you the output) and stage 6 (a review by Sonnet at xhigh against the spec, then an Opus check of each finding).

## Cost estimate

- This session so far, including the key handling and the guard change: $2.54 by `/home/gianni/model-tests/round5/cost.py` (57 calls), which prices cache writes at the 5-minute rate; about $3 counting 1-hour cache writes.
- Build, slices 1 to 7, in the main conversation on Opus at medium: about $5 to $8. Slices 1 and 6 are the largest.
- Stage 5, seeing it working: about $1.
- Stage 6 review: Sonnet at xhigh about $1 to $2, then the Opus check about $1.
- **Total from here: about $8 to $12**, under the $15 line. No Fable, no workflows. If slice 1 runs into trouble (for example Docker inside this virtual machine), I stop and report rather than spend past $15.

## Risks I know about

- Search engines may block or show CAPTCHAs to claude-dev's address once the experiment sends every built-in search through them. Check 2 makes that visible, and the report counts it.
- SearXNG engines break as sites change. The pinned image makes the install repeatable, but it will need an update now and then; `websearch server update` pulls a newer image and records which one.
- The Docker service uses some memory all the time; about 3.5 GB is free today. I will measure what Docker and SearXNG use in slice 1. [VERIFIED for the free memory]
- If the NAS is down, the hook cannot run (it lives on the NAS share). Claude Code treats a failed background hook as a non-blocking error, so the session carries on. [VERIFIED: hooks reference, "Timeouts" and "Run hooks in the background"]

## Changes during the build (stage 4, 2 and 3 November 2026)

- Approved by Gianni on 2 November ("Yes" to the restatement of goal, state and next step).
- Slice 2 also added `websearch server status/start/stop/update` from the change list. A stopped container came back in 1.7 s, so the "starting, not ready yet" line is rarely seen.
- Check 5: Semantic Scholar refused about half of keyed requests (seven in ten the next day) whatever the spacing, and nine in ten without a key. Gianni chose patient retries (option A: 5 retries, 2, 4, 8, 16, 16 s plus jitter, one summary line) and then: "Ignore check 5. If they are having issues, there's probably nothing we can do about it." Spacing, cap and key handling are built and tested offline; the live check stays failed for outside reasons.
- The report's buckets use agreement at depth k (Webber et al. 2010, equation 3, k = the built-in list's length) instead of plain overlap, because plain overlap cannot reach 1 when SearXNG returns 30 to 40 links against the built-in's 7 to 20. Every log line keeps both full lists, so other measures can be computed later.
- The experiment switch defaults to on when its file is missing, because installing the hook is the opt-in.
- The notebook change (hook in `claude/settings.json`, line in `claude/README.md`) was approved by Gianni on 3 November ("Approve"), commit `5bdc440` in the notebook. The first live built-in search confirmed the hook receives the same result shape as the transcripts, and that the hook takes effect without restarting the session.
