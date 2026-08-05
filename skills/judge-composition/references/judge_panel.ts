/**
 * Four-judge panel: role definitions, verdict/manifest schemas, the
 * judge registry, per-role context assembly (structural blindness),
 * and engine-side panel composition.
 *
 * Normative specification:
 *   docs/product/epistemic-support/RECONCILIATION.md §2–§3 (the
 *   completed role definitions and the adopted composition design;
 *   ratification OPEN — see that record's §7), over
 *   docs/product/epistemic-support/FOUR_JUDGE_DESIGN.md §3–§6 and
 *   docs/architecture/EPISTEMIC_SUPPORT.md §3.
 *
 * Deliberately pure: no database, queue, network, or clock access.
 * Sole callers today: the zero-paid panel drill
 * (`npm run test:judge-panel`) and its unit pins. Production
 * reachability (a `support_sweep` job) is a separately gated feature.
 *
 * STRUCTURAL INVARIANT (AB-9, drill-pinned): this module — the
 * composition path — imports nothing from `judge_audit.ts`. The audit
 * role's verdicts have no route to any opinion: a J4-role verdict in
 * the composition input is a typed refusal, and a J4 finding reaches
 * a judge only as a contest of the judge capability, mediated outside
 * this module.
 */

import { z } from 'zod';
import {
  computeSupportOpinion,
  type SupportEvent,
  type SupportOpinion,
  type SupportParams,
} from './support';

// ---------------------------------------------------------------------------
// Roles (RECONCILIATION §2 — the completed definitions as data)
// ---------------------------------------------------------------------------

export type PanelRole = 'J1_GROUNDING' | 'J2_COHERENCE' | 'J3_CORROBORATION' | 'J4_AUDIT';
export type ClaimMode = 'fact' | 'inference' | 'prediction' | 'value' | 'belief' | 'experience';

export interface RoleDefinition {
  role: PanelRole;
  /** Claim modes the role may judge (S10 layer-3 applicability). Empty = judges judges, never claims. */
  claimModes: readonly ClaimMode[];
  /** Sparse qualified-parameter selection, `registry.parameter/aspect` (RECONCILIATION §1). */
  qualifiedParameters: readonly string[];
  /** Closed drawback taxonomy: class -> the qualified parameter it restricts. */
  taxonomy: Readonly<Record<string, string>>;
  /** Declared context allowlist — blindness made mechanical (COMPOSABLE_RUBRICS §2.1). */
  inputs: { required: readonly string[]; optional: readonly string[] };
  /** R-29 hard-gate material: assumptions the judged case must not negate. */
  requiredAssumptions: readonly string[];
}

export const ROLE_DEFINITIONS: Readonly<Record<PanelRole, RoleDefinition>> = {
  J1_GROUNDING: {
    role: 'J1_GROUNDING',
    claimModes: ['fact', 'inference'],
    qualifiedParameters: ['logical.evidence_quality/cited', 'logical.falsification/cited'],
    taxonomy: {
      unsupported_citation: 'logical.evidence_quality/cited',
      overclaimed_evidence: 'logical.evidence_quality/cited',
      contradicted_by_cited_bytes: 'logical.falsification/cited',
    },
    inputs: { required: ['claim', 'citedBytes'], optional: [] },
    requiredAssumptions: ['cited_bytes_available'],
  },
  J2_COHERENCE: {
    role: 'J2_COHERENCE',
    claimModes: ['fact', 'inference', 'prediction', 'belief'],
    qualifiedParameters: [
      'logical.consistency/internal',
      'logical.consistency/history',
      'logical.constraint_satisfaction/kind',
    ],
    taxonomy: {
      self_contradictory: 'logical.consistency/internal',
      history_inconsistent: 'logical.consistency/history',
      kind_incoherent: 'logical.constraint_satisfaction/kind',
    },
    inputs: { required: ['claim', 'history'], optional: ['claimKind'] },
    requiredAssumptions: ['history_available'],
  },
  J3_CORROBORATION: {
    role: 'J3_CORROBORATION',
    claimModes: ['fact', 'inference', 'prediction'],
    qualifiedParameters: [
      'logical.induction/world',
      'logical.falsification/independent',
      'logical.source_dependence/independent',
      'sensorial.observation_quality/independent',
    ],
    taxonomy: {
      uncorroborated: 'logical.induction/world',
      authority_contradicted: 'logical.falsification/independent',
      corroboration_ambiguous: 'sensorial.observation_quality/independent',
    },
    // citedBytes deliberately absent: the anti-circularity blindness.
    inputs: { required: ['claim', 'independentEvidence'], optional: ['authorityWeights'] },
    requiredAssumptions: ['independent_evidence_pool_available'],
  },
  J4_AUDIT: {
    role: 'J4_AUDIT',
    claimModes: [],
    qualifiedParameters: [
      'logical.hidden_assumptions/audit',
      'logical.goodharting/audit',
      'logical.coverage/audit',
      'logical.abduction/audit',
      'logical.counterfactuals/audit',
    ],
    taxonomy: {
      rubric_gamed: 'logical.goodharting/audit',
      convention_blind: 'logical.coverage/audit',
      systematic_drift: 'logical.abduction/audit',
    },
    // beliefOpinion / compositionState deliberately absent: the live
    // gating path is J4's structural blindness.
    inputs: { required: ['sampledTriples', 'taskContract'], optional: [] },
    requiredAssumptions: ['stored_verdict_evidence_pairs_available'],
  },
};

/** The roles whose verdicts may reach the support opinion. J4 is structurally excluded. */
export const COMPOSITION_ROLES: readonly PanelRole[] = [
  'J1_GROUNDING',
  'J2_COHERENCE',
  'J3_CORROBORATION',
];

/** `registry.parameter` half of a qualified parameter (registry-level kinship, RECONCILIATION §1). */
export function registryEntry(qualifiedParameter: string): string {
  const slash = qualifiedParameter.indexOf('/');
  return slash < 0 ? qualifiedParameter : qualifiedParameter.slice(0, slash);
}

// ---------------------------------------------------------------------------
// Verdict schema (JUDGE_CONTRACT_TEMPLATE §1 as amended: abstainReason)
// ---------------------------------------------------------------------------

const PANEL_ROLES = ['J1_GROUNDING', 'J2_COHERENCE', 'J3_CORROBORATION', 'J4_AUDIT'] as const;

const verdictBase = z.object({
  judgeId: z.string().min(1),
  role: z.enum(PANEL_ROLES),
  beliefId: z.string().min(1),
  verdict: z.enum(['drawback', 'clean', 'abstain']),
  drawback: z.string().min(1).nullable(),
  abstainReason: z.enum(['jurisdiction', 'evidence']).optional(),
  atMs: z.number().finite(),
  weight: z.number().finite().nonnegative(),
});

export type JudgeVerdict = z.infer<typeof verdictBase>;

export class JudgeVerdictSchemaError extends Error {}

/** Boundary validation: closed taxonomies; abstains carry a reason; unknown class refused. */
export function parseJudgeVerdict(raw: unknown): JudgeVerdict {
  const parsed = verdictBase.safeParse(raw);
  if (!parsed.success) {
    throw new JudgeVerdictSchemaError(`Verdict record malformed: ${parsed.error.issues[0]?.message}.`);
  }
  const v = parsed.data;
  if (v.verdict === 'drawback') {
    if (v.drawback === null) {
      throw new JudgeVerdictSchemaError(`Verdict ${v.judgeId}/${v.beliefId}: drawback verdict requires a drawback class.`);
    }
    const taxonomy = ROLE_DEFINITIONS[v.role].taxonomy;
    if (!(v.drawback in taxonomy)) {
      throw new JudgeVerdictSchemaError(
        `Verdict ${v.judgeId}/${v.beliefId}: unknown drawback class "${v.drawback}" for role ${v.role} (closed taxonomy).`
      );
    }
  } else if (v.drawback !== null) {
    throw new JudgeVerdictSchemaError(`Verdict ${v.judgeId}/${v.beliefId}: ${v.verdict} verdict must carry drawback null.`);
  }
  if (v.verdict === 'abstain' && v.abstainReason === undefined) {
    throw new JudgeVerdictSchemaError(
      `Verdict ${v.judgeId}/${v.beliefId}: abstain requires abstainReason (jurisdiction | evidence).`
    );
  }
  if (v.verdict !== 'abstain' && v.abstainReason !== undefined) {
    throw new JudgeVerdictSchemaError(`Verdict ${v.judgeId}/${v.beliefId}: abstainReason is abstain-only.`);
  }
  return v;
}

// ---------------------------------------------------------------------------
// Judge manifests and the registry (capability mold; R-27 model coupling)
// ---------------------------------------------------------------------------

const SHA256_HEX = /^[0-9a-f]{64}$/;

const manifestSchema = z.object({
  judgeId: z.string().min(1),
  role: z.enum(PANEL_ROLES),
  rubricSha: z.string().regex(SHA256_HEX, 'rubricSha must be 64 lowercase hex chars'),
  anchorSetSha: z.string().regex(SHA256_HEX, 'anchorSetSha must be 64 lowercase hex chars'),
  taxonomyVersion: z.string().min(1),
  // R-27: adaptations are model-coupled; a model migration must be able
  // to contest the judge. The field is REQUIRED (drill-pinned).
  targetModelIdentity: z.string().min(1),
});

export type JudgeManifest = z.infer<typeof manifestSchema>;

export class JudgeManifestError extends Error {}

export function parseJudgeManifest(raw: unknown): JudgeManifest {
  const parsed = manifestSchema.safeParse(raw);
  if (!parsed.success) {
    const issue = parsed.error.issues[0];
    const path = issue?.path.join('.') || 'manifest';
    throw new JudgeManifestError(`Judge manifest refused at "${path}": ${issue?.message}.`);
  }
  return parsed.data;
}

export interface ContestRecord {
  finding: string;
  reason: string;
  contestedAtMs: number;
  /** A re-registration marks the record superseded; it is never deleted. */
  superseded: boolean;
}

export interface RegisteredJudge {
  manifest: JudgeManifest;
  contested: boolean;
  history: readonly ContestRecord[];
  reRegisteredAtMs: number | null;
}

export type JudgeRegistry = ReadonlyMap<string, RegisteredJudge>;

export class JudgeRegistryError extends Error {}

export function emptyRegistry(): JudgeRegistry {
  return new Map();
}

export function registerJudge(registry: JudgeRegistry, rawManifest: unknown): JudgeRegistry {
  const manifest = parseJudgeManifest(rawManifest);
  if (registry.has(manifest.judgeId)) {
    throw new JudgeRegistryError(`Judge "${manifest.judgeId}" is already registered; editing is a new registration under a new id.`);
  }
  const next = new Map(registry);
  next.set(manifest.judgeId, { manifest, contested: false, history: [], reRegisteredAtMs: null });
  return next;
}

/** Applied by the sweep (or, in drills, the scripted mediator) — never by this module's composition path. */
export function contestJudge(
  registry: JudgeRegistry,
  judgeId: string,
  contest: { finding: string; reason: string; contestedAtMs: number }
): JudgeRegistry {
  const entry = registry.get(judgeId);
  if (!entry) throw new JudgeRegistryError(`Cannot contest unknown judge "${judgeId}".`);
  const next = new Map(registry);
  next.set(judgeId, {
    ...entry,
    contested: true,
    history: [...entry.history, { ...contest, superseded: false }],
  });
  return next;
}

/**
 * The human recovery analog (register_modules.ts recovery transition):
 * recovery follows re-review, never precedes it. The superseded contest
 * record survives in the history.
 */
export function reRegisterJudge(
  registry: JudgeRegistry,
  judgeId: string,
  review: { reviewedBy: string; atMs: number }
): JudgeRegistry {
  const entry = registry.get(judgeId);
  if (!entry) throw new JudgeRegistryError(`Cannot re-register unknown judge "${judgeId}".`);
  if (!entry.contested) throw new JudgeRegistryError(`Judge "${judgeId}" is not contested; nothing to recover.`);
  if (typeof review.reviewedBy !== 'string' || review.reviewedBy.length === 0) {
    throw new JudgeRegistryError(`Re-registration of "${judgeId}" requires a named human reviewer.`);
  }
  const next = new Map(registry);
  next.set(judgeId, {
    ...entry,
    contested: false,
    reRegisteredAtMs: review.atMs,
    history: entry.history.map((h) => ({ ...h, superseded: true })),
  });
  return next;
}

// ---------------------------------------------------------------------------
// Context assembly — role blindness as structure (RECONCILIATION §5 row 2)
// ---------------------------------------------------------------------------

export class BlindnessViolationError extends Error {
  constructor(public readonly role: PanelRole, public readonly input: string) {
    super(`Blindness violation: role ${role} was handed forbidden input "${input}" — refused before any model boundary.`);
  }
}

export class ContextAssemblyError extends Error {}

/**
 * Pure, allowlist-driven: a role receives exactly its declared inputs.
 * A forbidden key refuses (typed, naming role and input) BEFORE any
 * would-be model boundary; a missing required key refuses fail-closed.
 */
export function assembleJudgeContext(
  role: PanelRole,
  provided: Readonly<Record<string, unknown>>
): Record<string, unknown> {
  const def = ROLE_DEFINITIONS[role];
  const allowed = new Set<string>([...def.inputs.required, ...def.inputs.optional]);
  for (const key of Object.keys(provided).sort()) {
    if (!allowed.has(key)) throw new BlindnessViolationError(role, key);
  }
  for (const key of def.inputs.required) {
    if (provided[key] === undefined) {
      throw new ContextAssemblyError(`Context for ${role} is missing required input "${key}".`);
    }
  }
  const context: Record<string, unknown> = {};
  for (const key of [...allowed].sort()) {
    if (provided[key] !== undefined) context[key] = provided[key];
  }
  return context;
}

// ---------------------------------------------------------------------------
// Panel composition (RECONCILIATION §3 — the adopted R-29/R-30 design)
// ---------------------------------------------------------------------------

export interface JudgedCase {
  beliefId: string;
  claimMode: ClaimMode;
  /** Declared case properties for the R-29 gate; only an explicit `false` negates. */
  assumptions: Readonly<Record<string, boolean>>;
}

export class CompositionRefusedError extends Error {}

export class ContestedJudgeError extends Error {
  constructor(public readonly judgeId: string) {
    super(
      `Composition refused: judge "${judgeId}" is contested. A contested judge in the ` +
      `verdict stream means upstream selection already failed; recovery is human re-registration.`
    );
  }
}

export class AuditVerdictInCompositionError extends Error {
  constructor(judgeId: string) {
    super(`Composition refused: J4_AUDIT verdict from "${judgeId}" has no composition path (the audit role never gates).`);
  }
}

export interface ConflictRecord {
  kind: 'no_global_section';
  beliefId: string;
  parameter: string;
  judges: ReadonlyArray<{ judgeId: string; role: PanelRole; verdict: string; drawback: string | null }>;
}

export interface DisagreementRecord {
  kind: 'cross_role_disagreement';
  beliefId: string;
  registryEntry: string;
  judges: ReadonlyArray<{ judgeId: string; role: PanelRole; verdict: string; drawback: string | null }>;
}

export interface ExclusionRecord {
  judgeId: string;
  assumption: string;
}

export interface PanelComposition {
  opinion: SupportOpinion;
  conflicts: readonly ConflictRecord[];
  disagreements: readonly DisagreementRecord[];
  exclusions: readonly ExclusionRecord[];
  counts: { verdictsConsumed: number; verdictsWithheld: number; jurisdictionAbstains: number };
}

const summarize = (v: JudgeVerdict) => ({
  judgeId: v.judgeId, role: v.role, verdict: v.verdict, drawback: v.drawback,
});

/**
 * Engine-side composition over verdict records, in the RECONCILIATION
 * §3.4 order: schema → registry/contest → J4 exclusion → hard gates →
 * overlap test (no-global-section) → cross-role disagreement →
 * drilled v1 arithmetic. Pure and deterministic.
 */
export function composePanel(
  registry: JudgeRegistry,
  judgedCase: JudgedCase,
  rawVerdicts: readonly unknown[],
  asOfMs: number,
  params: SupportParams
): PanelComposition {
  // 1. Boundary validation, fail-closed.
  const verdicts = rawVerdicts.map(parseJudgeVerdict);
  for (const v of verdicts) {
    if (v.beliefId !== judgedCase.beliefId) {
      throw new CompositionRefusedError(
        `Composition refused: verdict from "${v.judgeId}" names belief "${v.beliefId}" but the case is "${judgedCase.beliefId}" — mixed-belief streams never merge silently.`
      );
    }
  }

  // 2. Registry and contest checks (whole-batch refusal, the Session-31 mold).
  for (const v of verdicts) {
    const entry = registry.get(v.judgeId);
    if (!entry) {
      throw new CompositionRefusedError(
        `Composition refused: verdict from unregistered judge "${v.judgeId}" — a wiring bug must not pose as epistemic humility.`
      );
    }
    if (entry.manifest.role !== v.role) {
      throw new CompositionRefusedError(
        `Composition refused: judge "${v.judgeId}" is registered as ${entry.manifest.role} but rendered a ${v.role} verdict.`
      );
    }
    if (entry.contested) throw new ContestedJudgeError(v.judgeId);
  }

  // 3. The audit role has no composition path (AB-9).
  for (const v of verdicts) {
    if (v.role === 'J4_AUDIT') throw new AuditVerdictInCompositionError(v.judgeId);
  }

  // 4a. R-29 hard compatibility gate, run over the registry's panel
  //     (selection semantics): a judge whose required assumption the
  //     case negates is excluded, typed and counted. Its verdicts are
  //     not expected in the stream at all.
  const exclusions: ExclusionRecord[] = [];
  const excludedIds = new Set<string>();
  for (const [judgeId, entry] of [...registry.entries()].sort(([a], [b]) => (a < b ? -1 : 1))) {
    if (!COMPOSITION_ROLES.includes(entry.manifest.role)) continue;
    for (const assumption of ROLE_DEFINITIONS[entry.manifest.role].requiredAssumptions) {
      if (judgedCase.assumptions[assumption] === false) {
        exclusions.push({ judgeId, assumption });
        excludedIds.add(judgeId);
      }
    }
  }
  for (const v of verdicts) {
    if (excludedIds.has(v.judgeId)) {
      throw new CompositionRefusedError(
        `Composition refused: excluded judge "${v.judgeId}" (required assumption negated by the case) rendered a verdict — judging happened past a hard gate.`
      );
    }
  }

  // 4b. Applicability (S10 layer 3): an inapplicable judge may only
  //     abstain for jurisdiction.
  let jurisdictionAbstains = 0;
  for (const v of verdicts) {
    const applicable = ROLE_DEFINITIONS[v.role].claimModes.includes(judgedCase.claimMode);
    if (!applicable) {
      if (v.verdict === 'abstain' && v.abstainReason === 'jurisdiction') {
        jurisdictionAbstains += 1;
      } else {
        throw new CompositionRefusedError(
          `Composition refused: judge "${v.judgeId}" (${v.role}) is not applicable to claim mode "${judgedCase.claimMode}" yet rendered a ${v.verdict} verdict — only a jurisdiction abstention is admissible.`
        );
      }
    }
  }

  // 5. R-30 overlap test: qualified-parameter overlap + opposing
  //    non-abstain verdicts = no valid global section. The conflicted
  //    group's verdicts are withheld from evidence accumulation — their
  //    mass reaches the opinion only as absence of evidence (u).
  const conflicts: ConflictRecord[] = [];
  const withheldIds = new Set<JudgeVerdict>();
  const opining = verdicts.filter((v) => v.verdict !== 'abstain');
  for (let i = 0; i < opining.length; i += 1) {
    for (let j = i + 1; j < opining.length; j += 1) {
      const a = opining[i];
      const b = opining[j];
      const defA = ROLE_DEFINITIONS[a.role];
      const defB = ROLE_DEFINITIONS[b.role];
      const overlap = defA.qualifiedParameters.filter((p) => defB.qualifiedParameters.includes(p));
      if (overlap.length === 0) continue;
      const pair: Array<[JudgeVerdict, JudgeVerdict, RoleDefinition]> = [[a, b, defA], [b, a, defB]];
      for (const [drawer, cleaner, drawerDef] of pair) {
        if (drawer.verdict !== 'drawback' || cleaner.verdict !== 'clean') continue;
        const parameter = drawerDef.taxonomy[drawer.drawback as string];
        if (!overlap.includes(parameter)) continue;
        conflicts.push({
          kind: 'no_global_section',
          beliefId: judgedCase.beliefId,
          parameter,
          judges: [summarize(drawer), summarize(cleaner)],
        });
        withheldIds.add(drawer);
        withheldIds.add(cleaner);
      }
    }
  }

  // 6. Cross-role disagreement (registry-level kinship, qualified-level
  //    disjoint): composes — disagreement is data — and flags.
  const disagreements: DisagreementRecord[] = [];
  for (let i = 0; i < opining.length; i += 1) {
    for (let j = i + 1; j < opining.length; j += 1) {
      const a = opining[i];
      const b = opining[j];
      if (withheldIds.has(a) || withheldIds.has(b)) continue;
      const pair: Array<[JudgeVerdict, JudgeVerdict]> = [[a, b], [b, a]];
      for (const [drawer, cleaner] of pair) {
        if (drawer.verdict !== 'drawback' || cleaner.verdict !== 'clean') continue;
        const drawerDef = ROLE_DEFINITIONS[drawer.role];
        const cleanerDef = ROLE_DEFINITIONS[cleaner.role];
        const qualified = drawerDef.taxonomy[drawer.drawback as string];
        if (cleanerDef.qualifiedParameters.includes(qualified)) continue; // that is §5's conflict, handled above
        const entry = registryEntry(qualified);
        const kin = cleanerDef.qualifiedParameters.some((p) => registryEntry(p) === entry);
        if (!kin) continue;
        disagreements.push({
          kind: 'cross_role_disagreement',
          beliefId: judgedCase.beliefId,
          registryEntry: entry,
          judges: [summarize(drawer), summarize(cleaner)],
        });
      }
    }
  }

  // 7. Fail-closed (R-02 at the panel boundary): a stream that is
  //    nothing but jurisdiction abstentions means no selected judge had
  //    jurisdiction at all — a selection failure, never an opinion.
  //    (An empty stream and evidential abstains stay legal: an unjudged
  //    or undecidable belief holds maximal uncertainty by §3.)
  const survivors = verdicts.filter((v) => !withheldIds.has(v));
  if (verdicts.length > 0 && jurisdictionAbstains === verdicts.length) {
    throw new CompositionRefusedError(
      `Composition refused: the gates left zero composition-side verdicts for "${judgedCase.beliefId}" — a panel of pure jurisdiction abstentions is a selection failure, not an opinion.`
    );
  }

  // 8. Surviving verdicts feed the drilled v1 arithmetic unchanged.
  const events: SupportEvent[] = survivors.map((v) => ({
    beliefId: v.beliefId,
    opId: v.judgeId,
    verdict: v.verdict,
    atMs: v.atMs,
    weight: v.weight,
  }));
  const opinion = computeSupportOpinion(events, asOfMs, params);

  return {
    opinion,
    conflicts,
    disagreements,
    exclusions,
    counts: {
      verdictsConsumed: survivors.length,
      verdictsWithheld: withheldIds.size,
      jurisdictionAbstains,
    },
  };
}
