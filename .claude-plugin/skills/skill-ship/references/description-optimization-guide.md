---
type: quality
load_when: quality
priority: mandatory
estimated_lines: 285
---

# Description Optimization Guide

Comprehensive guide for optimizing skill descriptions to improve triggering accuracy. Extracted from skill-creator's `improve_description.py` script and prompt engineering patterns.

---

## Overview

The skill description is the **primary triggering mechanism** for Claude Code skills. When a user sends a query, Claude decides whether to invoke the skill based **solely** on the title and description. This guide explains how to write and optimize descriptions that trigger correctly.

---

## Key Principles

### 1. Avoid Overfitting

**Problem:** Adding ever-expanding lists of specific queries that the skill should or shouldn't trigger for.

**Why it's bad:**
- Overfits to specific test cases
- List may get very long and blow token budget
- Doesn't generalize to new queries

**Solution:** Generalize from failures to broader categories of user intent and situations.

### 2. Focus on User Intent

The skill description should focus on **what the user is trying to achieve**, not the implementation details of how the skill works.

**Bad:**
```
This skill uses pypdf to extract text from PDF files and processes them with regex.
```

**Good:**
```
This skill should be used when the user asks to "extract text from PDF", "get data from PDF documents", "parse PDF forms", or mentions PDF data extraction, text extraction, or form parsing.
```

### 3. Be "Pushy" to Combat Under-Triggering

Claude has a tendency to "under-trigger" skills — not using them when they'd be useful. To combat this, make descriptions a little bit "pushy."

**Before (too passive):**
```
How to build a simple fast dashboard to display internal Anthropic data.
```

**After (pushy):**
```
How to build a simple fast dashboard to display internal Anthropic data. Make sure to use this skill whenever the user mentions dashboards, data visualization, internal metrics, or wants to display any kind of company data, even if they don't explicitly ask for a 'dashboard.'
```

### 4. Keep It Concise

- Target **100-200 words** maximum
- Hard limit of **1024 characters** for the description field
- Every word must earn its place

---

## Description Quality Checklist

**Good Description:**
- [ ] Uses third person ("This skill should be used when...")
- [ ] Includes specific trigger phrases users would actually say
- [ ] Lists concrete scenarios (create X, configure Y)
- [ ] Focuses on user intent, not implementation
- [ ] Is distinctive and immediately recognizable
- [ ] Under 1024 characters

**Bad Description:**
- [ ] Uses second person ("Use this skill when you want...")
- [ ] Vague about when to trigger
- [ ] Lists implementation details instead of use cases
- [ ] Generic description that could apply to many skills
- [ ] Overly long list of specific queries

---

## Optimization Process

### Step 1: Gather Data

For each eval, track:
- **Failed to trigger**: Should have triggered but didn't
- **False triggers**: Triggered but shouldn't have
- **Trigger count**: How many times it triggered across N runs

### Step 2: Identify Patterns

Look for patterns in the failures:
- Are there categories of user intent being missed?
- Are there synonyms or variations not covered?
- Is the description too vague?

### Step 3: Generalize, Don't Overfit

**Example of overfitting:**
```
Add "extract names from PDF" to the description
```

**Example of generalizing:**
```
Add "data extraction from PDF documents including names, addresses, form fields, and tables"
```

### Step 4: Iterate with Multiple Approaches

When you're not making progress after repeated attempts, change things up:
- Try different sentence structures
- Try different wordings
- Mix up the style across iterations

You'll have multiple opportunities and can grab the highest-scoring one at the end.

---

## Prompt Template for Description Improvement

This is the actual prompt used by skill-creator's `improve_description.py` script:

```
You are optimizing a skill description for a Claude Code skill called "{skill_name}".

A "skill" is sort of like a prompt, but with progressive disclosure -- there's a title and description that Claude sees when deciding whether to use the skill, and then if it does use the skill, it reads the .md file which has lots more details and potentially links to other resources.

The description appears in Claude's "available_skills" list. When a user sends a query, Claude decides whether to invoke the skill based solely on the title and on this description. Your goal is to write a description that triggers for relevant queries, and doesn't trigger for irrelevant ones.

Based on the failures, write a new and improved description that is more likely to trigger correctly.

**What I DON'T want you to do** is produce an ever-expanding list of specific queries that this skill should or shouldn't trigger for. Instead, try to **generalize from the failures to broader categories of user intent** and situations where this skill would be useful or not useful.

The reason for this is twofold:
1. Avoid overfitting
2. The list might get loooong and it's injected into ALL queries and there might be a lot of skills, so we don't want to blow too much space on any given description.

Concretely, your description should not be more than about 100-200 words, even if that comes at the cost of accuracy.

**Tips that work well:**
- The skill should be phrased in the imperative -- "Use this skill for" rather than "this skill does"
- The skill description should focus on the user's intent, what they are trying to achieve, vs. the implementation details of how the skill works.
- The description competes with other skills for Claude's attention — make it distinctive and immediately recognizable.
- If you're getting lots of failures after repeated attempts, change things up. Try different sentence structures or wordings.

I'd encourage you to be creative and mix up the style in different iterations since you'll have multiple opportunities to try different approaches.
```

---

## Examples

### Example 1: PDF Processing Skill

**Iteration 1 (vague):**
```
This skill processes PDF files to extract data and fill forms.
```

**Problem:** Doesn't specify when to use, not distinctive.

**Iteration 2 (better):**
```
This skill should be used when the user asks to "extract text from PDF", "fill out PDF forms", "parse PDF data", or mentions PDF processing, form filling, or data extraction from documents.
```

**Still missing:** Too generic, could apply to many PDF tools.

**Iteration 3 (optimized):**
```
This skill should be used when the user asks to "extract data from PDF forms", "fill PDF forms automatically", "parse PDF form fields", "extract text and tables from PDF", or mentions PDF form processing, automated form filling, PDF data extraction, or working withfillable PDF documents. Focuses on PDF forms and structured data extraction with pypdf and regex-based field parsing.
```

### Example 2: Dashboard Building Skill

**Iteration 1 (passive):**
```
Create dashboards for data visualization.
```

**Problem:** Too brief, doesn't indicate when to use.

**Iteration 2 (better):**
```
This skill should be used when the user wants to create a dashboard or visualize data.
```

**Still missing:** Not specific enough, misses many trigger phrases.

**Iteration 3 (pushy and optimized):**
```
This skill should be used when the user asks to "create a dashboard", "build a data visualization", "make charts and graphs", "visualize metrics", "display analytics", or wants to show data in a visual format. Make sure to use this skill whenever the user mentions dashboards, data visualization, metrics display, charts, graphs, analytics, or wants to display any kind of data visually, even if they don't explicitly ask for a "dashboard."
```

---

## Common Pitfalls

### Pitfall 1: Listing Tool Names

**Bad:**
```
This skill uses pypdf, pdfplumber, and regex to process PDF files.
```

**Why bad:** Users don't care about tools; they care about what they can accomplish.

**Fix:** Focus on user intent:
```
This skill should be used when the user wants to extract data from PDF files or fill out PDF forms.
```

### Pitfall 2: Second Person

**Bad:**
```
Use this skill when you want to create a dashboard.
```

**Why bad:** Uses second person ("you"), not the required third-person format.

**Fix:**
```
This skill should be used when the user asks to "create a dashboard"...
```

### Pitfall 3: Too Generic

**Bad:**
```
This skill helps with data analysis.
```

**Why bad:** Could apply to dozens of skills; not distinctive.

**Fix:** Be specific:
```
This skill should be used when the user asks to "analyze data with Python", "perform statistical analysis", "create data visualizations", or mentions pandas data analysis, statistical computing, or data science workflows.
```

### Pitfall 4: Forgetting Edge Cases

**Bad:**
```
This skill should be used when the user wants to create a web form.
```

**Why bad:** Misses related queries like "build a contact form", "make a signup page", "add a form to my website".

**Fix:**
```
This skill should be used when the user asks to "create a web form", "build a contact form", "make a signup page", "add a form to my website", or mentions form creation, web forms, contact forms, or HTML form generation.
```

---

## Testing Your Description

### Manual Test

After writing a description, ask yourself:
1. **Would a user actually say these phrases?** (Realism check)
2. **Could this description be confused with another skill?** (Distinctiveness check)
3. **Does it cover the main use cases without being exhaustive?** (Coverage check)

### Automated Test

Use skill-creator's eval system to test triggering accuracy:

```bash
# Run triggering evals
python scripts/run_eval.py --skill-path /path/to/skill --evals-file evals/evals.json

# Check results
python scripts/improve_description.py --eval-results results.json --skill-path /path/to/skill --model claude-sonnet-4-20250514
```

---

## Additional Resources

- **`eval-complete-reference.md`** - Full evaluation system specification
- **skill-creator plugin** - Complete implementation with `improve_description.py` script
- **`skill-development` skill** - Progressive disclosure and writing style guidelines
