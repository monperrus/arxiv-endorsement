# ArXiv Endorsement Protocol

I receive many arXiv endorsement requests (and more due to Gen AI). I follow a structured protocol with three steps before endorsing. All three must pass before I can endorse.

## Why a Protocol?

ArXiv endorsements carry real scientific weight. An endorsement signals that the endorsed author is a legitimate researcher submitting work appropriate for a given subject area. a bad endorsement hurts arXiv, the scientific community, and ultimately the integrity of science.

At the same time, I want to be helpful to genuine researchers who lack an endorser. The protocol below is designed to be fast, transparent, and fair.

---

## Gate 1: Verified LinkedIn Profile

**What I need:** A link to your LinkedIn profile, and it must be verified (LinkedIn's identity verification badge).

**Why:** ArXiv endorsement requests can come from anyone. Without identity verification, there is no way to distinguish a genuine researcher from a fake account or a bot. A verified LinkedIn profile provides a basic but meaningful assurance that you are who you say you are. If you do not have a LinkedIn account or have not completed LinkedIn's identity verification, please do so before reaching out.

---

## Gate 2: The Paper

**What I need:** A complete draft of the paper you intend to submit, in PDF form.

**Why:** I cannot endorse a researcher in a vacuum. I need to skim the paper to assess whether it is a genuine scientific contribution appropriate for arXiv. Please send the full draft, not just an abstract or a title.

---

## Gate 3: Automated AI Peer Review

**What I need:** Nothing extra from you — I run this step myself.

**Why:** Reading every paper in depth is time-consuming. To ensure consistent and thorough assessment, I pass the paper through an automated AI peer review. This checks for basic scientific soundness, clarity, and appropriateness for the claimed subject area.

This is not a replacement for human peer review and does not guarantee the paper will be accepted at a journal or conference. It is a fast, reproducible filter to catch papers that are clearly not ready or not appropriate for arXiv.

---

## How to Request an Endorsement

**Submit a pull request to this repository** — do not send requests by email. All endorsement requests are handled publicly via pull requests for transparency: anyone can see what was submitted and what decision was made.

To submit a request, open a pull request that adds exactly one new `.txt` file under `requests/`.

Use this exact three-line format, with one field per line:

```text
LinkedIn: https://www.linkedin.com/in/your-profile
Paper: https://example.org/your-paper.pdf
Subject: cs.LG
```

Rules:

1. The file must contain exactly these three fields, in this order: `LinkedIn`, `Paper`, `Subject`.
2. Each field must appear exactly once, on a single line, as `Field: value`.
3. `LinkedIn` must be an `https://www.linkedin.com/in/...` or `https://www.linkedin.com/pub/...` profile URL.
4. `Paper` must be a public `https://` URL to the paper PDF or preprint page.
5. `Subject` must be a valid arXiv category ID such as `cs.LG`, `stat.ML`, or `math.OC`.
6. LinkedIn verification is still checked manually. The automated check only validates that the URL has the right shape.

You can find the current arXiv category taxonomy here:
https://arxiv.org/category_taxonomy

I will run the AI review on my end and post my decision as a comment on the pull request.
