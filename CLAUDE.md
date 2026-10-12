# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

This is a monorepo of standalone, independently-runnable example agents built on the [AgentMail](https://agentmail.to) API (email inboxes for AI agents), most paired with the Anthropic Claude API. There is **no shared build system, no root `package.json`/`pyproject.toml`, no CI, and no test suite** — each subfolder is self-contained with its own dependencies, `.env.example`, and README. Don't assume tooling (linters, test runners, CI) exists unless you find it inside a specific example's folder.

Every template folder is also meant to be pulled out standalone via `npx degit agentmail-to/agentmail-examples/<name> my-app`, which is why each one carries its own `LICENSE`, `.gitignore`, and README rather than relying on the repo root.

## Folder categories (see README.md for the full index)

1. **Getting Started** (`langchain-terminal`, `openai-terminal`) — terminal chat agents wired to AgentMail tools. Single `main.py`, `pyproject.toml` + `uv.lock`.
2. **Advanced** (`email-agent`, `sales-agent`, `dinner-agent`, `github-maintainer-agent`) — single-file autonomous agents, mostly `uv`-managed.
3. **Templates** (`scheduling-agent`, `inbox-zero`, `note-taker`, `approval-inbox`, `gtm-agent`, `sales-signal-router`, `negotiation-agent`, `support-agent`, `docs-assistant`, `invoice-processor`, `x402-payment-agent`, `newsletter-digest`, `dinner-reservation`, `browser-signup-agent`) — production-shaped, each with **matching Python and TypeScript implementations** under `<template>/python/` and `<template>/typescript/`. Logic is mirrored file-for-file (e.g. `agent.py` ↔ `agent.ts`, `prompt.py` ↔ `prompt.ts`); if you change behavior in one language, port the same change to the other.
4. **Template Agents** (`agentmail-*` prefixed dirs, e.g. `agentmail-scheduling-agent`) — these are near-duplicates of the corresponding unprefixed template dirs above (same `python`/`typescript` split, same code), kept around as the `degit` pull targets referenced in the README's "Template Agents" table. **When fixing a bug or updating a template, check whether the matching `agentmail-*` directory needs the identical change** — the two currently drift out of sync only in minor ways (e.g. `typescript/package-lock.json` presence).
5. **Single-language agent examples** (`collections-agent`, `cold-email-researcher`, `contract-redline-agent`, `hiring-screener-agent`, `legal-intake-agent`, `podcast-booking-agent`, `receipt-parser-agent`, `recruiter-coordinator`) — simpler, one implementation only, under `src/main.py`, usually seeded from a CSV/JSON data file (e.g. `invoices.csv`, `prospects.csv`) and shipped with a `CROSSPOST.md` (marketing copy, not documentation to maintain). Not all of these use Claude — e.g. `collections-agent` calls `OpenAI` directly. Check imports before assuming the LLM provider.

## Running an example

- **pip-based Python** (most templates' `python/` subfolder, and single-language examples): `cd <dir>/python && pip install -r requirements.txt && cp .env.example .env` (fill in keys) `&& python agent.py` (or `main.py`).
- **uv-based Python** (`email-agent`, `sales-agent`, `dinner-agent`, `langchain-terminal`, `openai-terminal` — identifiable by `pyproject.toml` + `uv.lock` at the folder root instead of `requirements.txt`): `uv run main.py`.
- **TypeScript** (`<template>/typescript/`): `npm install && cp .env.example .env` (fill in keys) `&& npm start` (runs via `tsx`); `npm run dev` for watch mode; `npm run build` to typecheck/compile via `tsc`.
- Every example needs `AGENTMAIL_API_KEY` (from console.agentmail.to) and `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY` for the few OpenAI-based ones) at minimum — check the specific `.env.example` for template-specific vars (e.g. `USER_EMAIL`, scheduling windows, `POLL_INTERVAL_SECONDS`).
- There is no lint/format/test command to run — verify changes by actually running the agent against a real AgentMail inbox.

## Environment variables

Every example loads secrets from a local, gitignored `.env` via `dotenv`/`python-dotenv`. There's no single `.env.example` to point to for the whole repo — `email-agent`, `sales-agent`, `dinner-agent`, and `github-maintainer-agent` don't ship a `.env.example` at all; their README documents the `.env` contents inline instead. These recur across most examples:

- `AGENTMAIL_API_KEY` — from console.agentmail.to. Required by every example.
- `ANTHROPIC_API_KEY` + `ANTHROPIC_MODEL` — required by the **Templates** category (and their `agentmail-*` duplicates); each pins its own default model.
- `OPENAI_API_KEY` — required by **Getting Started**, **Advanced**, and every **single-language agent example** — all of these are OpenAI-based (`openai`, `langchain_openai`, or the `agents`/OpenAI Agents SDK), not Claude-based. Check imports before assuming the LLM provider; Templates are the Claude-based ones, not the exception.
- `POLL_INTERVAL_SECONDS` — polling cadence (default ~10s) for polling-based examples (Templates + single-language examples).
- `USER_EMAIL` / `USER_NAME` — the human the agent represents; most templates cc this address on outgoing replies.
- `INBOX_USERNAME`, `WEBHOOK_DOMAIN`, `NGROK_AUTHTOKEN` — only in the four **Advanced** examples, which run a local Flask server behind an ngrok tunnel and register a real AgentMail webhook instead of polling.
- Everything else (`TIMEZONE`, `COMPANY_NAME`, `SLACK_WEBHOOK_*`, `AUTO_APPROVE_LIMIT`, `CDP_API_KEY`/`WALLET_ADDRESS`, scheduling windows, etc.) is template-specific business configuration — read the specific `.env.example` (or README, for the four exceptions above) rather than guessing.

## Core architecture pattern

Nearly every template and advanced example follows the same shape, split across a handful of files:

1. **Inbox bootstrap** — `get_or_create_inbox()` creates an AgentMail inbox (`agentmail.inboxes.create`) on first run and persists its ID to a local, gitignored state file (`.agent_state.json`) so subsequent runs reuse the same address instead of creating a new one each time.
2. **Polling loop** — the main loop calls `agentmail.inboxes.messages.list(inbox_id, labels=["unread"])` every `POLL_INTERVAL_SECONDS` (default ~10s). This is deliberate: templates favor zero-infra polling (runs from a laptop, no public URL/ngrok needed) over webhooks. Each README's "Beyond the template" section documents the webhook upgrade path (`client.webhooks.create(...)`, `event_types=["message.received"]`), but **no example in this repo actually implements a webhook receiver** — don't assume one exists.
3. **Thread → LLM messages** — for each new message, the full thread is fetched (`agentmail.inboxes.threads.get`) and converted into Anthropic-shaped `messages` (helper typically named `thread_to_messages`): role is inferred by comparing the sender's address to `inbox.email`, the list is trimmed so it starts on a `user` turn, and consecutive same-role turns are collapsed (both are hard Anthropic API requirements).
4. **Model call** — `claude.messages.create(...)` with a `system` prompt built by a dedicated `build_system_prompt()` (kept in `prompt.py`/`prompt.ts`, separate from the agent loop) and, where the agent needs to trigger a side effect (e.g. `confirm_meeting`, generating a `.ics` invite), an Anthropic tool schema defined as a module-level constant near the top of the agent file.
5. **Reply + mark read** — reply in-thread via `agentmail.inboxes.messages.reply(inbox_id, message_id, text=..., cc=..., attachments=...)`, then mark the source message read by removing the `unread` label (`agentmail.inboxes.messages.update(..., remove_labels=["unread"])`). Sender-address checks guard against the agent replying to its own outgoing mail.
6. Runtime, per-run artifacts (state files, CSV/JSON logs the agent writes, `.wallet`, notes) are gitignored at the repo root in the top-level `.gitignore` — check there before assuming a data file should be committed.

When working on a template, read `agent.{py,ts}` alongside `prompt.{py,ts}` (and any domain helper like `calendar_invite.py`/`deal.py`) together — the polling/threading plumbing lives in the former, the agent's actual instructions and negotiation/business logic in the latter.
