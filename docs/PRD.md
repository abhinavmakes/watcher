# Watcher — Product Requirements Document

## Overview

Watcher is a real-time tech intelligence dashboard that clusters articles from multiple sources, scores their momentum, and lets users explore and query what's happening across AI/ML, startups, and the developer ecosystem.

## Problem statement

People who work in tech stay informed through newsletters, Twitter, and Hacker News. Each has a fundamental limitation:

Newsletters are curated by someone else, delivered on their schedule (usually daily), and can't be queried. If the topic you care about wasn't in today's edition, you missed it.

Twitter/X is real-time but overwhelmingly noisy. Signal is buried under opinions, threads, engagement bait, and algorithmic promotion. Finding what's genuinely gaining traction requires constant scrolling.

Hacker News is community-curated and high quality but single-source. A story might be trending on HN while the actual details live in a GitHub release, a blog post, and a funding announcement that HN didn't surface.

No existing tool combines real-time ingestion from multiple sources, AI-powered clustering of related coverage, momentum scoring, editorial-quality synthesis, and the ability to ask follow-up questions grounded in actual source material.

## Target user

AI engineers, software developers, and technical founders who need to stay current on the tech ecosystem. Specifically people who currently spend 30-60 minutes daily across newsletters, HN, and Twitter trying to answer: "what's happening that I should know about?"

## Core user stories

### Anonymous visitor (no login)

**As a visitor, I can see what's trending in tech right now.**
I land on the dashboard and see cluster cards sorted by momentum. Each card shows a title, a 2-3 sentence synthesis, article count, recency, domain tags, and a sparkline showing momentum direction. I can scan 8-10 clusters in under a minute and know what matters today.

**As a visitor, I can filter clusters by domain.**
I click domain pills (AI agents, Funding, Dev tools, Open source, etc.) to narrow the dashboard to topics I care about. Cards animate in/out smoothly.

**As a visitor, I can read the full analysis of any cluster.**
I click a cluster card and see the complete synthesis (summary + "so what"), the list of all source articles that formed the cluster, and when the cluster was first detected. I can click through to any original source.

### Authenticated user (GitHub OAuth)

**As an authenticated user, I can set my interests.**
I go to Settings and select domains I care about. On the dashboard, clusters matching my interests get a "Match" badge and are weighted higher in sort order. I still see all clusters — nothing is hidden.

**As an authenticated user, I can ask questions about a cluster.**
On the cluster detail page, I use the chat panel to ask follow-up questions. "What specifically changed?" "How does this compare to the previous version?" Answers are grounded in the actual articles in the cluster via RAG, with inline citations showing which source backs each claim.

**As an authenticated user, I can bring my own LLM for chat.**
I go to Settings, pick my provider (OpenAI, Anthropic, or Google), paste my API key, and select a model from the dropdown. My key is encrypted and stored securely. Chat responses use my key — Watcher pays nothing for my queries.

## Feature specifications

### F1: Dashboard (public)

**Cluster cards**
- Title: AI-generated, max 2 lines
- Synthesis: 2-3 sentence summary, truncated with ellipsis on card
- Single-source items: labeled "Single-source signal" when only one article backs the card
- Momentum badge: sparkline (5 bars) + numeric score (0-100)
  - Hot (70+): green accent, left border highlight
  - Warm (40-69): amber accent
  - Cool (<40): gray, fading
- Footer: article count, time since first seen, domain tags
- Authenticated users: purple "Match" badge on relevant clusters
- Click navigates to cluster detail page

**Stats row**
- Active clusters (count + delta today)
- Articles ingested (count + delta per 6h)
- Sources tracked (count)
- Last pipeline run (time ago + frequency)

**Domain filter pills**
- Horizontal scrollable row
- Options: All, AI agents, Funding rounds, Dev tools, Open source, Infra, LLMs, Startups
- Single-select, "All" is default
- Client-side filter with animated transitions

**Time separators**
- Groups clusters into: "Trending now", "Earlier today", "Yesterday"
- Based on cluster first_seen_at

**Live updates**
- Dashboard subscribes to SSE endpoint
- When pipeline completes, client refetches cluster data
- New clusters animate in from top
- Stats re-count to new values

**Search**
- Text input at top of dashboard
- Client-side filter: matches against cluster title, synthesis, and domain tags
- MVP scope: no full-text backend search

### F2: Cluster detail page (public read, auth for chat)

**Synthesis section**
- Full synthesis text (not truncated)
- Labeled "AI synthesis" with icon
- Includes both summary and "so what" editorial take

**Source articles list**
- Each article: source icon, title, source name, time
- Sorted by recency
- Click opens original article URL in new tab

**Chat panel (auth required)**
- Message thread: user messages right-aligned, AI responses left-aligned
- AI responses include inline citation tags referencing source articles
- Streaming: tokens appear progressively via SSE
- If not authenticated: "Sign in to ask questions" prompt
- If authenticated but no BYOK key: "Add your API key in Settings" link
- Input: text field + send button
- Footer: "Powered by your API key. Responses grounded in cluster articles."

### F3: Settings page (auth required)

**Interests**
- Multi-select tag interface
- Available domains match dashboard filter pills
- Saved to Supabase user_preferences table

**API keys**
- Table showing connected providers
- Each row: provider name, model name, masked key (sk-...xxxx), delete button
- "Add key" form: provider dropdown (OpenAI, Anthropic, Google) → API key input → model dropdown (curated list per provider) → Save
- Custom model text input below dropdown for unlisted models
- One key per provider maximum

**Curated model lists**

OpenAI: gpt-4.1, gpt-4.1-mini, gpt-4o, gpt-4o-mini
Anthropic: claude-sonnet-4-6, claude-haiku-4-5
Google: gemini-2.5-flash, gemini-2.5-pro

Plus "Custom model" text input for each provider.

### F4: Authentication

- GitHub OAuth via Supabase Auth
- Single "Sign in with GitHub" button in top bar
- No email/password, no other OAuth providers in MVP
- On sign-in: create user_preferences row with empty interests
- Session managed by Supabase client SDK (cookie-based)

## Data sources

| Source | API | Update frequency | Data type | Free |
|--------|-----|-----------------|-----------|------|
| Hacker News | Firebase API | Real-time | Community submissions | Yes |
| RSS feeds | feedparser | Per feed (1-6h) | Blog posts, newsletters | Yes |
| Dev.to | REST | Every 30 min | Developer articles with markdown body | Yes |
| GitHub trending | Scrape | Daily | Repositories | Yes (no official API) |
| Product Hunt | GraphQL | Daily | Product launches | Yes |

Build order is intentionally staged. HN, RSS, and Dev.to are the core MVP
sources because they provide the strongest article text for embedding and
RAG. GitHub Trending and Product Hunt are added after the core pipeline and
clustering evaluation work; both are best-effort connectors whose failure
must not block the pipeline.

**Curated RSS feeds (initial set):**
The Pragmatic Engineer, Simon Willison's Weblog, Lenny's Newsletter, TechCrunch AI, The Information, a16z blog, OpenAI blog, Anthropic research, Google AI blog, Hugging Face blog, LangChain blog, FastAPI blog, Python Weekly, AI News (by Jack Clark)

This list is stored as configuration, not code. New feeds can be added without code changes.

## Non-functional requirements

**Performance**
- Dashboard initial load: < 2 seconds
- Cluster detail load: < 1 second
- Chat first token: < 3 seconds (depends on user's LLM provider)
- Pipeline completion: < 15 minutes per run

**Security**
- BYOK API keys encrypted at rest (AES-256-GCM)
- Row-Level Security on all user-specific tables
- No API keys in logs, error messages, or frontend responses
- HTTPS everywhere

**Reliability**
- Pipeline failures don't affect dashboard availability
- Individual connector failures don't block the pipeline (skip and continue)
- SSE auto-reconnects on disconnect

**Cost**
- Infrastructure: ~$5/month (Railway hobby + Vercel free + Supabase free)
- LLM pipeline: $0 on Google AI Studio free tier (dev/launch)
- LLM pipeline: ~$2-10/month on paid tier at scale
- BYOK chat: $0 to Watcher (user pays their own provider)

## What is NOT in MVP

- Email digests or scheduled notifications
- User-managed RSS feed additions
- Historical momentum trend charts
- Team or organization features
- Mobile native app
- Landing page or marketing site (dashboard is the landing page)
- Dark/light theme toggle (uses system preference only)
- Full-text search backend
- OpenRouter as a BYOK provider option
- Onboarding wizard or tutorial

## Success metrics

- A hiring manager can understand the project in 30 seconds from the README
- The dashboard loads with real data and feels alive
- A user can go from landing page to reading a cluster synthesis in 0 clicks
- A user can go from sign-in to asking a RAG-powered question in under 2 minutes
- The architecture document can sustain a 30-minute technical interview discussion
