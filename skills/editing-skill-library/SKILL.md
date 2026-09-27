---
name: editing-skill-library
description: Route editing requests to the library's atomic and workflow Skills, using the agent's available editor tools or the optional local runtime with explicit result handoff.
---

# Editing Skill Library gateway

Read [the registry](../../registry/skills.json) and [semantic router](../../registry/router.md) to choose an atomic or workflow Skill. Read its entry and the [capability handoff contract](../../contracts/capability-handoff.md). Use the running agent's available editor tool, MCP, CLI or local media tool if it can perform the declared action and return evidence for the result. A missing local runtime dependency does not make an equivalent editor capability unavailable.

The bundled `list_skills`, `diagnose_installation` and `run_operation` MCP tools are optional local execution aids. When choosing `run_operation`, satisfy its work directory and exact local request contract; `diagnose_installation` reports only that local implementation's dependencies. No DeepSeek key, generation model, or specific editor is required to load or route the general Skills. Keep complex judgment in the workflow, and read back any changed project before claiming adoption or delivery.
