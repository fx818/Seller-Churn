# Skills Share Readiness Review

Checked against the current Agent Skills spec on May 16, 2026.

Short answer: `C:\Users\Imart\Desktop\Hackathon\skills` is not ready to share as a clean Agent Skills package yet, and the per-skill `SKILL.md` files are not all spec-ready as-is.

## Findings

### High

16 of the 17 actual skill directories use `metadata` as a nested schema container, not a flat string-to-string map.

Representative examples:

- [bl-card/SKILL.md](./bl-card/SKILL.md)
- [winback-priority/SKILL.md](./winback-priority/SKILL.md)

The published spec defines `metadata` as string keys to string values. Your `inputs`, `outputs`, lists, and nested objects are outside that contract, so a strict validator or client can reject or mis-handle them.

### Medium

[seller-churn-assessment/SKILL.md](./seller-churn-assessment/SKILL.md) hardcodes a repo-root path:

```bash
python skills/seller-churn-assessment/scripts/run_pipeline.py <glid>
```

The spec's file-reference guidance expects skill-root-relative references like `scripts/run_pipeline.py`. This file is the closest to spec structurally, but it is still coupled to this repo layout and to custom host tools like `run_pipeline` and `read_skill_reference`.

### Medium

The folder mixes real Agent Skills directories with legacy top-level markdown definitions.

[README.md](./README.md) says each `.md` file in the directory is a machine-parseable skill definition, and these files still use the older one-file format:

- [build_library.md](./build_library.md)
- [score_seller.md](./score_seller.md)
- [pipeline.md](./pipeline.md)

A compliant Agent Skills client scans subdirectories containing `SKILL.md`, so these top-level files will be ignored and the README is misleading for external sharing.

### Low

The package contains many `__pycache__` directories and `.pyc` files. That is not a spec violation, but it is not publish-ready packaging.

## Open Questions / Assumptions

- I treated the 17 subdirectories under `skills\` as the publishable skills.
- There is no top-level `C:\Users\Imart\Desktop\Hackathon\skills\SKILL.md`.
- I did not run `skills-ref validate` because `skills-ref` is not installed locally.
- I found no `license:` fields in the skill `SKILL.md` files. That is optional in the spec, but for sharing you should decide on reuse terms.

## Verdict

The basic structure is partly good:

- the 17 skill directories have valid hyphenated names
- their `name` fields match the directory names
- descriptions are non-empty
- all `SKILL.md` files are under 500 lines

The main blocker is the frontmatter design. If you want these to be shareable Agent Skills, move the rich `inputs` / `outputs` schemas out of `metadata` and into the body or `references/`, or flatten `metadata` to string values only.

The folder itself also needs cleanup before sharing:

- remove caches
- separate or remove the legacy top-level `.md` files
- update the README to describe the current subdirectory-based layout

## Sources

- Agent Skills specification: https://agentskills.io/specification
- Adding skills support / discovery conventions: https://agentskills.io/client-implementation/adding-skills-support
