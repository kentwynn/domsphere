import { mkdirSync, writeFileSync } from 'fs';
import { resolve } from 'path';
import { zodToJsonSchema } from 'zod-to-json-schema';

// Import Zod schemas
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

// Convert each Zod schema -> JSON Schema (each returns an object that often contains { $ref, definitions })
const AtlasJS = zodToJsonSchema(ElementAtlasSchema, 'ElementAtlas');
const PlanReqJS = zodToJsonSchema(PlanRequestSchema, 'PlanRequest');
const PlanResJS = zodToJsonSchema(PlanResponseSchema, 'PlanResponse');
const DomPlanJS = zodToJsonSchema(DomActionPlanSchema, 'DomActionPlan');
const SelectorJS = zodToJsonSchema(SelectorSchema, 'Selector');
const ActionStepJS = zodToJsonSchema(ActionStepSchema, 'ActionStep');
const AssertionJS = zodToJsonSchema(AssertionSchema, 'Assertion');
const FallbackJS = zodToJsonSchema(FallbackSchema, 'Fallback');

// Helper to merge nested `definitions` maps safely
interface JsonSchemaWithDefinitions {
  definitions?: Record<string, unknown>;
}

function mergeDefs(...schemas: unknown[]) {
  const defs: Record<string, unknown> = {};
  for (const s of schemas) {
    const schema = s as JsonSchemaWithDefinitions;
    if (schema && schema.definitions) {
      for (const [k, v] of Object.entries(schema.definitions)) {
        defs[k] = v;
      }
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

// Build a root object that references the models we want generated.
// datamodel-codegen will walk these $refs and emit classes for them and anything they reference.
const bundled = {
  $schema: 'http://json-schema.org/draft-07/schema#',
  $id: 'domsphere.contracts',
  type: 'object',
  properties: {
    ElementAtlas: { $ref: '#/definitions/ElementAtlas' },
    PlanRequest: { $ref: '#/definitions/PlanRequest' },
    PlanResponse: { $ref: '#/definitions/PlanResponse' },
    DomActionPlan: { $ref: '#/definitions/DomActionPlan' },
    Selector: { $ref: '#/definitions/Selector' },
    ActionStep: { $ref: '#/definitions/ActionStep' },
    Assertion: { $ref: '#/definitions/Assertion' },
    Fallback: { $ref: '#/definitions/Fallback' },
  },
  definitions,
};

const outDir = resolve(__dirname, '../../../contracts');
mkdirSync(outDir, { recursive: true });
writeFileSync(
  `${outDir}/contracts.schema.json`,
  JSON.stringify(bundled, null, 2)
);
