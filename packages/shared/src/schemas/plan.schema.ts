import { z } from 'zod';
import { ElementAtlasSchema } from './atlas.schema';

export const SelectorSchema = z.object({
  strategy: z.enum(['CSS', 'ARIA', 'XPATH']),
  value: z.string().min(1),
});

export const AssertionSchema = z
  .object({
    selector: SelectorSchema,
    condition: z.enum(['EXISTS', 'VISIBLE', 'TEXT_CONTAINS']),
    text: z.string().optional(),
    timeoutMs: z.number().int().positive().optional(),
  })
  .refine((a) => a.condition !== 'TEXT_CONTAINS' || !!a.text, {
    message: 'text is required when condition is TEXT_CONTAINS',
  });

export const ActionStepSchema = z.object({
  action: z.enum(['CLICK', 'INPUT', 'SELECT', 'WAIT', 'SCROLL', 'NAVIGATE']),
  selector: SelectorSchema.optional(),
  inputValue: z.string().optional(),
  notes: z.string().optional(),
  assert: z.array(AssertionSchema).optional(),
});

export const FallbackSchema = z.object({
  when: z.enum(['selector_not_found', 'assert_failed']),
  try: SelectorSchema,
});

export const DomActionPlanSchema = z.object({
  agentVersion: z.string(),
  planId: z.string().uuid(),
  steps: z.array(ActionStepSchema).min(1),
  fallbacks: z.array(FallbackSchema).optional(),
  cacheKey: z.string().optional(),
  confidence: z.number().min(0).max(1).optional(),
});

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

export type PlanRequestInput = z.infer<typeof PlanRequestSchema>;
export type PlanResponseOutput = z.infer<typeof PlanResponseSchema>;
