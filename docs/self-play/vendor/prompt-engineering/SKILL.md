---
name: prompt-engineering
description: >-
  The Lexideck prompt-engineering protocol: structural clarity and manifold
  alignment over "magic words." Use whenever authoring a prompt, template,
  agent instruction, system prompt, or output schema and precision matters:
  semantic tagging, hierarchical markers, structured placeholders,
  collections, and attention management, plus the best-practice loop.
  Triggers include "write a prompt", "improve this prompt", "prompt template",
  "agent instructions", "system prompt", "output schema". For the
  contamination-free structural-example technique this protocol's master
  template relies on, see the hypershot-protocol skill.
---

# Prompt Engineering: structural clarity and manifold alignment

> Core axiom: effective prompting is not about "magic words" but about **structural clarity** and **manifold alignment**.

You are shaping how a model generates — a prompt, template, agent instruction, or output schema. The toolkit is the *how*; the best practices keep it honest.

## The toolkit

### A. Semantic tagging (the container)
Wrap distinct information blocks in XML-style tags to prevent context bleeding.
- `<context>`: environmental or historical state.
- `<task>`: the core objective.
- `<constraints>`: the non-negotiable logic bounds.
- `<output_instructions>`: the target format (JSON / MD / table).

### B. Hierarchical markers (the skeleton)
Use explicit outlining to define topological depth.
- `# Main Topic` / `## Sub-Topic` / `- Structural Detail`.
- Match marker style to the content's natural hierarchy: numbered lists for sequential processes, bullets for parallel items, nested headers for domain decomposition.

### C. Structured placeholders (the manifest)
Use placeholders to build reusable, parameterized prompts. Four types:
- `${...}` for user-provided inputs.
- `{...}` for objects or function-like components.
- `[...]` for lists or arrays.
- `(...)` for options or decisions.

### D. Collections (the data layer)
When presenting multiple data points to a model, structure them as collections:
- Simple lists for enumeration.
- Key-value pairs for attribute sets.
- Nested objects for multi-property items.
- Tables for comparison and batch processing.

### E. Attention management (the priority signal)
Direct the model's attention to what matters most.
- Use formatting (bold, caps, markers like `*** CRITICAL ***`) for emphasis.
- Order strategically: place the most important instructions where the model attends most strongly, the beginning and end of the prompt.
- Group related constraints into attention zones so they reinforce each other.
- Prioritize explicitly: "If any constraint conflicts, prioritize X over Y."

## The master template (a hypershot)

This template is itself a hypershot: a structural frame with free variables, not filled-in examples. See the hypershot-protocol skill for the full technique.

```xml
<request type="Structural_Synthesis">

  <context>
    Intelligence: [Agent Name]
    Substrate: [Platform/Environment]
  </context>

  <instruction>
    Act as [Role].
    1. Parse the [Data_Collection].
    2. Apply {Methodology}.
    3. Generate high-fidelity output.
  </instruction>

  <constraints>
    *** CRITICAL ***
    - [Non-negotiable constraint 1]
    - [Non-negotiable constraint 2]
    - [Format/style requirement]
  </constraints>

  <output_instructions>
    Format: [Target format]
    Audience: [Intended reader]
    Length: [Constraint]
  </output_instructions>

</request>
```

## Best practices

1. **Topological mapping.** Map the informatic distance between the prompt's starting state and the desired output before you generate — understand the shape of the problem before proposing a shape for the solution.
2. **Phase alignment.** Match tone, register, and technical depth to the context. A prompt for a 12-year-old and a prompt for a domain expert should differ in more than vocabulary.
3. **Decoherence prevention.** Turn ambiguity into stable, unambiguous instruction. Every vague term is a fork where the model guesses instead of follows.
4. **Positive instruction framing.** Tell the model what TO DO, not what to avoid. "Use plain language accessible to non-specialists" beats "Don't use jargon"; negation tokens can be dropped during processing, inverting meaning.
5. **Iterative refinement (the learning loop).** Treat every prompt as a draft. Evaluate the output, find where the model diverged from intent, tighten the prompt at the point of divergence, and repeat.
6. **Uncontaminated context.** A prompt for another agent carries exactly what that agent cannot derive cold and needs in order to look. What you expect it to find is content placed where it will be attended to, so the agent hands it back and no report separates that from a finding — most of all when the expectation is true; the probe that produced it carries the same content in method's clothes. One question sorts them: *does this let the agent look, or does it tell the agent what looking will turn up?* A held expectation goes to the collaborator instead of into the prompt (your repository's `AMBIENT.md` ask-the-collaborator rule — rule 5 in Recursus, 21(a) in Trellis; `spark-steering` § *Ask first — the un-tool*, manual-invoke only).

## Lineage

Derived from the Lexideck Prompt Engineering Curriculum, "Talking to AIs Effectively," a nine-part series by Matthew Murphy (Part 1 golden rules through Part 9 best practices; covering tags, hierarchical markers, placeholders, collections, and attention management). This skill is the Part 9 capstone compressed into an operational protocol; it is the deployed artifact, not the educational version. Full curriculum on Patreon (patreon.com/c/LexideckTechnologies); source doc `Lexideck_Prompt_Engineering_Curriculum.v2.md`.
