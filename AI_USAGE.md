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
ClassShift's runtime recovery engine uses exact optimization rather than an LLM.

The release candidate records automated verification evidence; the project author remains responsible for final submission review.
