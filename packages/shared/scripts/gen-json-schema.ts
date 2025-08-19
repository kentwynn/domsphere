import { mkdirSync, writeFileSync } from 'fs';
import { resolve } from 'path';
import { zodToJsonSchema } from 'zod-to-json-schema';

// Zod schemas (ensure these reflect the NO-ROUTES plan)
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

type JsonSchemaAny = Record<string, unknown>;
type JSchema = {
  definitions?: Record<string, JsonSchemaAny>;
  $defs?: Record<string, JsonSchemaAny>;
};

const AtlasJS = zodToJsonSchema(ElementAtlasSchema, 'ElementAtlas');
const PlanReqJS = zodToJsonSchema(PlanRequestSchema, 'PlanRequest');
const PlanResJS = zodToJsonSchema(PlanResponseSchema, 'PlanResponse');
const DomPlanJS = zodToJsonSchema(DomActionPlanSchema, 'DomActionPlan');
const SelectorJS = zodToJsonSchema(SelectorSchema, 'Selector');
const ActionJS = zodToJsonSchema(ActionStepSchema, 'ActionStep');
const AssertJS = zodToJsonSchema(AssertionSchema, 'Assertion');
const FallbackJS = zodToJsonSchema(FallbackSchema, 'Fallback');
// const ArrivalJS  = zodToJsonSchema(ArrivalCheckSchema,   'ArrivalCheck');

function extractDefs(schema: unknown): Record<string, JsonSchemaAny> {
  const js = schema as JSchema;
  return { ...(js.definitions ?? {}), ...(js.$defs ?? {}) };
}

// Merge with collision detection + ensure titles stay stable
function mergeDefsWithChecks(...schemas: unknown[]) {
  const defs: Record<string, JsonSchemaAny> = {};
  for (const s of schemas) {
    const bucket = extractDefs(s);
    for (const [k, v] of Object.entries(bucket)) {
      if (defs[k]) {
        throw new Error(
          `JSON Schema definition name collision: "${k}". ` +
            `Rename your Zod schema or pass a unique second arg to zodToJsonSchema().`
        );
      }
      // Add a stable title if missing (helps some generators)
      if (typeof v === 'object' && v && !('title' in v)) {
        (v as JsonSchemaAny).title = k;
      }
      defs[k] = v;
    }
  }
  return defs;
}

const definitions = mergeDefsWithChecks(
  AtlasJS,
  PlanReqJS,
  PlanResJS,
  DomPlanJS,
  SelectorJS,
  ActionJS,
  AssertJS,
  FallbackJS
  // , ArrivalJS
);

// Decide which ref bucket we’ll use in the bundled root (draft-07)
const REF_BUCKET = 'definitions' as const;

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
    // ArrivalCheck:  { $ref: `#/${REF_BUCKET}/ArrivalCheck` },
  },
  // Optional: force traversal of all top-level models
  required: [
    'ElementAtlas',
    'PlanRequest',
    'PlanResponse',
    'DomActionPlan',
    'Selector',
    'ActionStep',
    'Assertion',
    'Fallback',
    // ,'ArrivalCheck'
  ],
  definitions,
};

const outDir = resolve(__dirname, '../../../contracts');
mkdirSync(outDir, { recursive: true });
writeFileSync(
  resolve(outDir, 'contracts.schema.json'),
  JSON.stringify(bundled, null, 2)
);
