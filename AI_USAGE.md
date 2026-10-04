# AI Use Disclosure

AI tools used:
- ChatGPT
- OpenAI Codex / Terra

Used for:
- brainstorming and project research
- architecture discussion
- reviewing edge cases
- implementation assistance
- debugging assistance
- test-case suggestions
- adversarial failure hunting and edge-case analysis
- release hardening
- documentation assistance

Not used for:
- runtime scheduling decisions
- generating recovery plans at runtime
- determining whether runtime assignments are valid

Runtime:
ClassShift's recovery engine is deterministic and uses an exact optimization algorithm rather than an LLM.

The final implementation should be reviewed and tested by the project author before submission.
