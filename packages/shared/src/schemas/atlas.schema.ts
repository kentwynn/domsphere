import { z } from 'zod';

export const AtlasNodeSchema = z.object({
  id: z.string().min(1),
  tag: z.string().min(1),
  role: z.string().optional(),
  testid: z.string().optional(),
  name: z.string().optional(),
  ariaLabel: z.string().optional(),
  textSnippet: z.string().max(160).optional(),
  cssFingerprint: z.string().max(128).optional(),
  pathFingerprint: z.string().min(1),
  visible: z.boolean(),
  hrefOriginSafe: z.string().url().optional(),
});

export const ElementAtlasSchema = z.object({
  atlasVersion: z.string().min(1),
  url: z.string().url(),
  title: z.string().optional(),
  capturedAt: z.string().datetime(),
  snapshotSha256: z.string().min(16),
  nodes: z.array(AtlasNodeSchema).min(1),
});

export type ElementAtlasInput = z.infer<typeof ElementAtlasSchema>;
