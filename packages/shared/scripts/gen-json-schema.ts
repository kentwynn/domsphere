import { mkdirSync, writeFileSync } from 'fs';
import { resolve } from 'path';
import { zodToJsonSchema } from 'zod-to-json-schema';

// Zod schemas
import { ElementAtlasSchema } from '../src/schemas/atlas.schema';
import {
  ActionStepSchema,
  AssertionSchema,
  DomActionPlanSchema,
  FallbackSchema,
  PlanRequestSchema,
  PlanResponseSchema,
  SelectorSchema,
} from '../src/schemas/plan.schema';

// Convert Zod -> JSON Schema
const AtlasJS = zodToJsonSchema(ElementAtlasSchema, 'ElementAtlas');
const PlanReqJS = zodToJsonSchema(PlanRequestSchema, 'PlanRequest');
const PlanResJS = zodToJsonSchema(PlanResponseSchema, 'PlanResponse');
const DomPlanJS = zodToJsonSchema(DomActionPlanSchema, 'DomActionPlan');
const SelectorJS = zodToJsonSchema(SelectorSchema, 'Selector');
const ActionStepJS = zodToJsonSchema(ActionStepSchema, 'ActionStep');
const AssertionJS = zodToJsonSchema(AssertionSchema, 'Assertion');
const FallbackJS = zodToJsonSchema(FallbackSchema, 'Fallback');

type JSchema = {
  definitions?: Record<string, unknown>;
  $defs?: Record<string, unknown>;
};

// Merge both `definitions` (draft-07) and `$defs` (2020-12) into a single map
function mergeDefs(...schemas: unknown[]) {
  const defs: Record<string, unknown> = {};
  for (const s of schemas) {
    const js = s as JSchema;
    const bucket = js.definitions ?? js.$defs;
    if (bucket) {
      for (const [k, v] of Object.entries(bucket)) defs[k] = v;
    }
  }
  return defs;
}

const definitions = mergeDefs(
  AtlasJS,
  PlanReqJS,
  PlanResJS,
  DomPlanJS,
  SelectorJS,
  ActionStepJS,
  AssertionJS,
  FallbackJS
);

// Decide which ref bucket we’ll use in the bundled root
const REF_BUCKET = 'definitions' as const;

// Build a root that references the models we want generated.
// datamodel-codegen will traverse these $refs and emit classes (plus deps).
const bundled = {
  $schema: 'http://json-schema.org/draft-07/schema#',
  $id: 'domsphere.contracts',
  type: 'object',
  properties: {
    ElementAtlas: { $ref: `#/${REF_BUCKET}/ElementAtlas` },
    PlanRequest: { $ref: `#/${REF_BUCKET}/PlanRequest` },
    PlanResponse: { $ref: `#/${REF_BUCKET}/PlanResponse` },
    DomActionPlan: { $ref: `#/${REF_BUCKET}/DomActionPlan` },
    Selector: { $ref: `#/${REF_BUCKET}/Selector` },
    ActionStep: { $ref: `#/${REF_BUCKET}/ActionStep` },
    Assertion: { $ref: `#/${REF_BUCKET}/Assertion` },
    Fallback: { $ref: `#/${REF_BUCKET}/Fallback` },
  },
  // Always output draft-07 'definitions' so datamodel-codegen is happy
  definitions,
};

const outDir = resolve(__dirname, '../../../contracts');
mkdirSync(outDir, { recursive: true });
writeFileSync(
  resolve(outDir, 'contracts.schema.json'),
  JSON.stringify(bundled, null, 2)
);
