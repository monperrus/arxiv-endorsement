# Recommendations for Open Science Verifiability

This document explains how to organize your paper and your repository so that a reader — human or automated — can check every empirical claim you make. It is the reference for [Gate 4](README.md) (and Gate 5, `osaudit.toml`) of the endorsement protocol: *every empirical number in the paper must be present in a committed data file, or recomputable by a committed script*.

The rule of thumb: **a reader who wonders "where does 87.3% come from?" should reach the answer in one click, or one command.**

---

## 1. The paper

### 1.1 Link the repository from the paper, and prominently

Put the repository URL in the abstract or in a footnote on page 1, not only in a "Data availability" paragraph at the end. Use the full URL in the text so it survives printing:

> Our implementation and all experimental data are available at <https://github.com/user/project>.

### 1.2 Hyperlink every empirical number to its source

This is the single most valuable thing you can do. A number in a table is a claim; a hyperlinked number is evidence. In LaTeX, `\href` from the table cell, the figure caption, or the sentence to the exact file — GitHub permalinks to a pinned commit, not to `main`:

```latex
\usepackage[hidelinks]{hyperref}
\newcommand{\artifact}[2]{\href{https://github.com/user/project/blob/v1.0/#1}{#2}}

Our approach repairs \artifact{results/repair_summary.csv}{87.3\%} of the bugs.
```

Use a **tag or commit SHA** in the URL (`/blob/v1.0/...`), never `/blob/main/...`: `main` moves, and a link that pointed at the evidence when you submitted must still point at it years later.

Link at the granularity of the claim:

- a single number → the file containing it, ideally with a line anchor (`...#L42`)
- a table → the CSV or JSON the table was generated from
- a figure → the script that draws it, plus the data it reads

### 1.3 Say how each number was obtained

For every table and figure, one sentence stating the command that produces it:

> Table 3 is produced by `make table3` from `results/rq2_raw.jsonl`.

If a number is computed by hand or by a spreadsheet, it is not reproducible. Move it into a script.

### 1.4 Make the numbers in the text agree with the numbers in the data

Rounding is fine — `87.3` in the paper for `87.31204` in the CSV is expected and detectable. Two things are not fine and are routinely caught:

- **Sums that do not add up.** If you report per-category counts and a total, verify the total equals the sum.
- **Numbers that exist nowhere.** A value that appears only in the PDF, in no file and in no script output, is unverifiable. Every such number is a Gate 4 failure.

### 1.5 Archive the artifact and cite the DOI

A GitHub repository can be deleted or renamed. Deposit a snapshot on [Zenodo](https://zenodo.org/) (or Software Heritage) and cite the DOI in the paper alongside the repository URL. The repository is for working with the artifact; the DOI is for citing it.

---

## 2. The repository

### 2.1 A predictable layout

Names matter more than structure — a reviewer must be able to guess where things are:

```
README.md              what this is, how to reproduce, what each result file contains
LICENSE                an OSI-approved license (MIT, Apache-2.0, …)
requirements.txt       pinned dependencies (or pyproject.toml / environment.yml)
Makefile               one target per table and figure in the paper
data/                  inputs: the subjects, the benchmark, the raw measurements
  raw/                 untouched, as collected
scripts/               everything that transforms data into results
results/               committed outputs: one file per table/figure in the paper
  table3_repair_rates.csv
  figure2_latency.csv
paper/                 the LaTeX source, if you keep it here
```

### 2.2 Name result files after the paper

`results/table3_repair_rates.csv` is verifiable at a glance. `results/out2.csv` is not. Whenever a file backs a specific table, figure, or claimed number, say so in its name — and repeat the mapping in the README:

| Paper | Produced by | Data |
|---|---|---|
| Table 3 | `make table3` | `results/table3_repair_rates.csv` |
| Figure 2 | `scripts/plot_latency.py` | `results/figure2_latency.csv` |
| §5.2, "87.3%" | `make rq1` | `results/rq1_summary.json` |

### 2.3 Commit the results, not just the code

Code alone is not enough. A reviewer may not have your API keys, your cluster, your 40 hours of compute, or the version of the subject programs you used. **Commit the computed results as files**, in a text format (CSV, JSON, JSONL), so that every number can be found without running anything. Keep them small enough for git; if a raw log is enormous, commit the aggregate and archive the raw file on Zenodo with a link.

### 2.4 Make it runnable in one command

```bash
git clone https://github.com/user/project && cd project
pip install -r requirements.txt
make all          # regenerates everything under results/
```

State the expected runtime and hardware. If the full experiment takes days, provide a smoke target (`make demo`) that runs in minutes on a subset, and say which numbers it reproduces.

### 2.5 Pin everything that makes a run deterministic

Fixed random seeds, pinned dependency versions, pinned dataset version or commit, recorded model identifiers and parameters (for LLM experiments: model ID, temperature, the exact prompts, and the raw responses). Non-deterministic experiments should commit the raw outputs of the run reported in the paper, so the specific numbers in the paper remain checkable even if a re-run differs.

### 2.6 Aggregates need a script, not a claim

Derived figures — a total, an average, a speedup, "9 of the 22 measures" — must be computed by committed code from committed data. If the only place the aggregation exists is your terminal history, it is not reproducible. A ten-line script in `scripts/` is enough.

### 2.7 Documentation and license

The README states what the artifact is, how to install it, how to reproduce each result, and what each file under `results/` contains. Add a `LICENSE` file: without one, nobody may legally reuse the artifact, which defeats the point of publishing it.

---

## 3. Checklist before you submit

- [ ] The repository URL is in the paper, on page 1, as a full URL.
- [ ] Every table, figure, and headline number links to the file or script behind it, via a **pinned** commit or tag.
- [ ] Every empirical number in the paper appears in a committed file, or a committed script computes it.
- [ ] Reported totals and percentages are consistent with the committed per-item data.
- [ ] Result files are named after the tables and figures they back.
- [ ] The README maps each paper artifact to its command and its data file.
- [ ] `git clone` + one documented command regenerates `results/`.
- [ ] Seeds, versions, model IDs, and prompts are pinned and committed.
- [ ] `LICENSE` is present.
- [ ] A snapshot is archived with a DOI, cited in the paper.

---

## 4. Why this is worth your time

Reviewers, readers, and future you all ask the same question: *is this number real?* An artifact organized this way answers it in seconds, without you in the loop. It also makes your work easier to build on — which is how papers get cited.

Further reading: the [ACM Artifact Review and Badging](https://www.acm.org/publications/policies/artifact-review-and-badging-current) policy, and the [FAIR principles for research software](https://doi.org/10.15497/RDA00068).
