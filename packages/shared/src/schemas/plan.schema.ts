import { z } from 'zod';
import { ElementAtlasSchema } from './atlas.schema';

/** ---------- Core primitives ---------- */
export const SelectorSchema = z.object({
  strategy: z.enum(['CSS', 'ARIA', 'XPATH']),
  value: z.string().min(1),
});

// Use a raw object (no effects) for reuse in .pick/.shape
export const ConditionEnum = z.enum(['EXISTS', 'VISIBLE', 'TEXT_CONTAINS']);

const RawAssertionSchema = z.object({
  selector: SelectorSchema,
  condition: ConditionEnum,
  text: z.string().optional(),
  timeoutMs: z.number().int().positive().optional(),
});

// Refined, exported Assertion with validation rule
export const AssertionSchema = RawAssertionSchema.superRefine((a, ctx) => {
  if (a.condition === 'TEXT_CONTAINS' && !a.text) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'text is required when condition is TEXT_CONTAINS',
      path: ['text'],
    });
  }
});

/** ---------- Arrival checks (route‑less navigation signals) ---------- */
// Build selector-based arrival checks from the *raw* schema (plain ZodObject)
const SelectorArrivalCheckSchema = RawAssertionSchema.pick({
  selector: true,
  condition: true,
  text: true,
});

export const ArrivalCheckSchema = z.union([
  SelectorArrivalCheckSchema, // { selector, condition, text? }
  z.object({ urlChange: z.literal(true) }),
  z.object({ urlIncludes: z.string().min(1) }),
  z.object({ networkIdle: z.literal(true) }),
]);

export const UntilSchema = z.object({
  anyOf: z.array(ArrivalCheckSchema).min(1),
});

/** ---------- Optional execution context ---------- */
export const PlanContextSchema = z.object({
  baseUrl: z.string().url().optional(),
  vars: z
    .record(z.string(), z.union([z.string(), z.number(), z.boolean()]))
    .optional(),
});

/** ---------- Step union (discriminated by action) ---------- */
/** ---------- Step base ---------- */
const StepBase = z.object({
  notes: z.string().optional(),
  preconditions: z.array(AssertionSchema).optional(),
  until: UntilSchema.optional(),
  timeoutMs: z.number().int().positive().optional(),
});

/** ---------- Per-action schemas (NO refine/superRefine here) ---------- */
const ClickStepSchema = StepBase.extend({
  action: z.literal('CLICK'),
  selector: SelectorSchema,
  inputValue: z.never().optional(),
});

const InputStepSchema = StepBase.extend({
  action: z.literal('INPUT'),
  selector: SelectorSchema,
  inputValue: z.string().min(1),
});

const SelectStepSchema = StepBase.extend({
  action: z.literal('SELECT'),
  selector: SelectorSchema,
  inputValue: z.string().min(1),
});

const WaitStepSchema = StepBase.extend({
  action: z.literal('WAIT'),
  assert: z.array(AssertionSchema).min(1),
  selector: z.never().optional(),
  inputValue: z.never().optional(),
});

const ScrollStepSchema = StepBase.extend({
  action: z.literal('SCROLL'),
  selector: SelectorSchema.optional(),
  to: z.enum(['top', 'bottom', 'center']).optional(),
  inputValue: z.never().optional(),
});

const NavigateStepSchema = StepBase.extend({
  action: z.literal('NAVIGATE'),
  url: z.string().min(1),
  selector: z.never().optional(),
  inputValue: z.never().optional(),
});

/** ---------- Discriminated union ---------- */
const ActionStepDU = z.discriminatedUnion('action', [
  ClickStepSchema,
  InputStepSchema,
  SelectStepSchema,
  WaitStepSchema,
  ScrollStepSchema,
  NavigateStepSchema,
]);

/** ---------- Add cross-option validation AFTER the union ---------- */
export const ActionStepSchema = ActionStepDU.superRefine((val, ctx) => {
  if (val.action === 'SCROLL') {
    const hasSelector = !!val.selector;
    const hasTo = !!val.to;
    if (!hasSelector && !hasTo) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'SCROLL requires either a selector or "to".',
        path: ['action'], // or [] if you want it at the root
      });
    }
  }
});

/** ---------- Fallbacks ---------- */
export const FallbackSchema = z.object({
  when: z.enum([
    'selector_not_found',
    'assert_failed',
    'navigation_failed',
    'timeout',
  ]),
  // Allow multiple alternative selectors in order
  try: z.array(SelectorSchema).min(1),
});

/** ---------- Plan ---------- */
export const DomActionPlanSchema = z.object({
  agentVersion: z.string(),
  planId: z.string().uuid(),
  steps: z.array(ActionStepSchema).min(1),
  fallbacks: z.array(FallbackSchema).optional(),
  cacheKey: z.string().optional(),
  confidence: z.number().min(0).max(1).optional(),
  context: PlanContextSchema.optional(), // <-- NEW
});

/** ---------- Request/Response ---------- */
export const PlanRequestSchema = z.object({
  siteId: z.string().uuid().optional(),
  url: z.string().url(),
  intent: z.string().min(1),
  atlasVersion: z.string().min(1),
  domSnapshot: ElementAtlasSchema,
  doNotStore: z.boolean().optional(),
});

export const PlanResponseSchema = z.object({
  sessionId: z.string().uuid(),
  agentVersion: z.string(),
  planId: z.string().uuid(),
  cache: z.enum(['HIT', 'MISS']),
  plan: DomActionPlanSchema,
});

/** ---------- TS Types ---------- */
export type PlanRequestInput = z.infer<typeof PlanRequestSchema>;
export type PlanResponseOutput = z.infer<typeof PlanResponseSchema>;
