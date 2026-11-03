# SPEC: a working second search engine (2 November 2026)

Approved by Gianni on 2 November 2026. First project run with the build workflow drafted in `_share/outbox/2026-11-02-build-workflow-draft.md` (light version, no Spec Kit). Size: medium.

## What and why

Research sessions have only the assistant's built-in web search, which returns a short list plus a model-written summary and does not say which engine it uses. The notebook asks for every web search to be run through a second engine as well, with the differences reported. The tools for that exist in this repo, but the SearXNG server they talk to was never installed, so today the second search fails. This project makes it work, and runs the comparison as an experiment to find out whether the second engine is worth keeping.

## Who uses it

Claude sessions on the claude-dev machine. Not Gianni directly from the phone (the search page exists but is out of scope).

## Done checks (each pass or fail)

1. A search from the claude-dev machine returns at least 10 results from at least 2 different search engines.
2. When an engine blocks the server, the output names it instead of silently returning fewer results.
3. When the server is down, the tool says so in one line within 5 seconds and names the fallback (the built-in search).
4. SearXNG runs on the claude-dev machine (Gianni's NAS runs TrueNAS CORE, which cannot host it; decided 2 November 2026). If it is not running, the search tool starts it by itself, so a machine restart needs nothing else.
5. Academic search reads the Semantic Scholar key from a private file, never prints it, and runs 10 searches in a row with no rate-limit errors, keeping to one request per second.
6. Comparing the two result lists is done by the tool: which links both searches found and which only one found.
7. **Experiment, for now:** every built-in search in a Claude session is automatically repeated on SearXNG and the comparison is logged (query, date, counts in common and unique to each, and the links), so the difference can be measured over real research tasks. It can be switched off with one setting.

## Out of scope

- Reading pages as clean text and filtering sources against the notebook's criteria automatically.
- Gianni using the search page from the phone.
- Deciding whether to keep the second engine for good: the experiment runs until Gianni and Claude decide to stop it, and that decision is made from the log.

## Decided

- The experiment has no end date: "The experiment runs until we want to stop. Maybe we find out that the search results are exactly the same, or that they are very different." (Gianni, 2 November 2026). The log must make either outcome visible.

## Setup steps for Gianni

`_share/outbox/research-tools/2026-11-02-phone-steps.md`: request the Semantic Scholar key and save it to `_share/inbox/research-tools/s2-key.txt`. Nothing on the NAS.
