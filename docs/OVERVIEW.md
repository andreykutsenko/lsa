# LSA — What It Does and Why It Matters

## The Problem

When a batch job fails in our legacy systems, developers spend a lot of time **before they can even start debugging**:

- "Which script actually failed?" — searching through hundreds of files
- "What does PPCS1037F mean?" — looking up cryptic error codes
- "Is this a code bug or a config issue?" — manually checking InfoTrac, Message Manager
- "Didn't we fix this before?" — asking colleagues, searching old tickets

**This context-gathering takes 30-70% of debugging time.**

## The Solution

LSA is a command-line tool that **automates context gathering**.

You give it a log file, and it returns:

1. **Which process failed** — with exact file paths to open
2. **What the error codes mean** — decoded from PDF documentation
3. **Is it code or config?** — detects external system issues (InfoTrac, API failures)
4. **Similar past issues** — from our debugging history with known fixes

## Before vs After

| Without LSA | With LSA |
|-------------|----------|
| Copy log into AI chat | Copy **structured context pack** into AI |
| AI guesses what PPCS1037F means | AI knows: "Document definition not found" |
| 5-15 back-and-forth clarifications | 1-3 focused questions |
| Same problem = debug from scratch | Same problem = "we fixed this in January" |

## How It Works (Simple Version)

```
1. ONCE: Index the production server snapshot
   $ lsa scan /path/to/snapshot

2. ONCE: Import error code definitions
   $ lsa import-codes /path/to/snapshot

3. ONCE: Import past debugging sessions
   $ lsa import-histories /path/to/snapshot

4. EACH TIME: Analyze a failing log
   $ lsa explain /path/to/snapshot --log failed_job.log

   → Outputs a "Context Pack" ready to paste into IDE/AI
```

## What You Get

When you run `lsa explain`, you get a single block of text containing:

- Most likely failing process (87% confidence)
- Execution chain: `bkfnds1 → script.sh → control.ctl → DOCDEF`
- Decoded error codes with explanations
- **External signals**: "This is a config issue, not a code bug"
- Top 3 hypotheses ranked by likelihood
- Similar past cases with known fixes
- List of files to open

This "Context Pack" is designed to be **pasted directly into Claude/Cursor/ChatGPT**.

## Business Value

| Benefit | Impact |
|---------|--------|
| Faster debugging | 30-70% less time on context gathering |
| Knowledge retention | Past solutions don't get lost |
| Better AI assistance | Structured context → accurate answers |
| Easier onboarding | New devs get context instantly |

## One-Liner for Executives

> LSA turns cryptic error logs into actionable debugging context, cutting investigation time and improving AI-assisted development.
