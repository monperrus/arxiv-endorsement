# ArXiv Endorsement Protocol

I receive many arXiv endorsement requests (and more due to Gen AI). I follow a structured protocol with five steps before endorsing. All five must pass before I can endorse.

## Why a Protocol?

ArXiv endorsements carry real scientific weight. An endorsement signals that the endorsed author is a legitimate researcher submitting work appropriate for a given subject area. a bad endorsement hurts arXiv, the scientific community, and ultimately the integrity of science.

At the same time, I want to be helpful to genuine researchers who lack an endorser. The protocol below is designed to be fast, transparent, and fair.

---

## Gate 1: Verified LinkedIn Profile

**What I need:** A link to your LinkedIn profile, and it must be verified (LinkedIn's identity verification badge).

**Why:** ArXiv endorsement requests can come from anyone. Without identity verification, there is no way to distinguish a genuine researcher from a fake account or a bot. A verified LinkedIn profile provides a basic but meaningful assurance that you are who you say you are. If you do not have a LinkedIn account or have not completed LinkedIn's identity verification, please do so before reaching out.

---

## Gate 2: The Paper

**What I need:** A complete draft of the paper you intend to submit, in PDF form, plus a link to a public GitHub repository with the code and data behind it.

**Why:** I cannot endorse a researcher in a vacuum. I need to skim the paper to assess whether it is a genuine scientific contribution appropriate for arXiv. Please send the full draft, not just an abstract or a title. An open science repository lets anyone verify and reproduce the work — it is mandatory, not optional. See [Recommendations for Open Science Verifiability](recommendation-open-science.md) for how to prepare both.

---

## Gate 3: Automated AI Peer Review

**What I need:** Nothing extra from you — I run this step myself.

**Why:** Reading every paper in depth is time-consuming. To ensure consistent and thorough assessment, I pass the paper through an automated AI peer review. This checks for basic scientific soundness, clarity, and appropriateness for the claimed subject area.

This is not a replacement for human peer review and does not guarantee the paper will be accepted at a journal or conference. It is a fast, reproducible filter to catch papers that are clearly not ready or not appropriate for arXiv.

---

## Gate 4: Repository ↔ Paper Correspondence

**What I need:** Nothing extra from you beyond the `Repo` link — I run this step myself.

**Why:** A repository link is worthless if the repository is unrelated to the paper, or if the paper's numbers cannot be found anywhere in it. So I check both:

1. **Correspondence.** The repository must be the one behind the paper — same system, same experiments — not an empty placeholder or an unrelated project.
2. **Traceability of every empirical number.** Every empirical fact in the paper (accuracies, runtimes, counts of bugs/subjects/repositories, p-values, table and figure values) must be either **present in a committed data file** or **recomputable by a committed script**. The repository is cloned, every claimed number is grepped for deterministically, and the result is reviewed against the file tree, the README and the scripts. At least 80% of the paper's empirical numbers must be backed this way.

If your paper reports a number that lives nowhere but in the PDF, commit the data file it came from or the script that produces it.

**Read this before submitting:** [Recommendations for Open Science Verifiability](recommendation-open-science.md) — how to organize the paper (hyperlink every number to the file behind it) and the repository (name result files after your tables, commit the results, one command to regenerate them) so this gate passes.

---

## Gate 5: `osaudit.toml`

**What I need:** The open science repository must contain an `osaudit.toml` at its root, and [osaudit](https://github.com/ASSERT-KTH/osaudit) must verify it (exit status 0, static checks). I run this step myself, on requests filed after this gate was introduced (already-analyzed requests are not re-checked against it).

**Why:** `osaudit` mechanically traces every number, quote and result of the paper to the evidence behind it. Conventions: <https://github.com/ASSERT-KTH/assert-research-agent/blob/main/CONVENTIONS.md>. Run `osaudit` in your repository before submitting.

---

## How to Request an Endorsement

**Submit a pull request to this repository** — do not send requests by email. All endorsement requests are handled publicly via pull requests for transparency: anyone can see what was submitted and what decision was made.

To submit a request, open a pull request that adds exactly one new `.txt` file under `requests/`.

Use this exact five-line format, with one field per line:

```text
LinkedIn: https://www.linkedin.com/in/your-profile
Paper: https://example.org/your-paper.pdf
Repo: https://github.com/your-username/your-paper-repo
Subject: cs.LG
EndorsementCode: A1B2C3
```

Rules:

1. The file must contain exactly these five fields, in this order: `LinkedIn`, `Paper`, `Repo`, `Subject`, `EndorsementCode`.
2. Each field must appear exactly once, on a single line, as `Field: value`.
3. `LinkedIn` must be an `https://www.linkedin.com/in/...` or `https://www.linkedin.com/pub/...` profile URL.
4. `Paper` must be a public `https://` URL to the paper PDF or preprint page.
5. `Repo` must be a public `https://github.com/...` URL to an open science repository (owner/repo) hosting the code and data behind the paper.
6. `Subject` must be a valid arXiv category ID such as `cs.LG`, `stat.ML`, or `math.OC`.
7. `EndorsementCode` must be the six-character alphanumeric code generated by arXiv for the endorsement request.
8. LinkedIn verification is still checked manually. The automated check only validates that the URL has the right shape.

You can find the current arXiv category taxonomy here:
https://arxiv.org/category_taxonomy

arXiv describes the endorsement code here:
https://info.arxiv.org/help/endorsement.html

I will run the AI review on my end and post my decision as a comment on the pull request.
