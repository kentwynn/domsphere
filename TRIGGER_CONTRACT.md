# Rule Trigger Contract Specification

## Overview

This document defines the standardized trigger format used across the entire domsphere system: agent, API, and SDK.

## Contract Definition

### RuleTrigger

```python
class RuleTrigger(BaseModel):
    eventType: DomEventType  # "page_load" | "dom_click" | "input_change" | "submit" | "route_change"
    when: List[TriggerCondition]  # All conditions must be true

class TriggerCondition(BaseModel):
    field: str  # Telemetry field path
    op: ConditionOp  # Comparison operator
    value: Any  # Value to compare against
```

## Field Paths (Generic for all websites)

- `telemetry.attributes.path` - URL path (e.g., "/cart", "/checkout")
- `telemetry.attributes.id` - Element ID (e.g., "cart-count", "submit-btn")
- `telemetry.attributes.class` - CSS class (e.g., "btn-primary")
- `telemetry.elementText` - Element text content (e.g., "2", "Add to Cart")
- `telemetry.cssPath` - CSS selector (e.g., "#cart-count", ".product-link")

## Operators

- `equals` - Exact match
- `gt`, `gte` - Greater than (for numbers)
- `lt`, `lte` - Less than (for numbers)
- `contains` - Substring match
- `in` - Value in array
- `regex` - Regular expression match

## Example Triggers

### Simple Page Load

```json
{
  "eventType": "page_load",
  "when": [{ "field": "telemetry.attributes.path", "op": "equals", "value": "/products" }]
}
```

### Numeric Range (cart items between 2 and 10)

```json
[
  {
    "eventType": "page_load",
    "when": [
      { "field": "telemetry.attributes.path", "op": "equals", "value": "/cart" },
      { "field": "telemetry.attributes.id", "op": "equals", "value": "cart-count" },
      { "field": "telemetry.elementText", "op": "gt", "value": 2 }
    ]
  },
  {
    "eventType": "page_load",
    "when": [
      { "field": "telemetry.attributes.path", "op": "equals", "value": "/cart" },
      { "field": "telemetry.attributes.id", "op": "equals", "value": "cart-count" },
      { "field": "telemetry.elementText", "op": "lt", "value": 10 }
    ]
  }
]
```

### Click Event

```json
{
  "eventType": "dom_click",
  "when": [
    { "field": "telemetry.attributes.path", "op": "equals", "value": "/checkout" },
    { "field": "telemetry.attributes.id", "op": "equals", "value": "place-order" }
  ]
}
```

## System Flow

1. **Agent** (`/agent/rule`) - Generates triggers from natural language

   - Input: `{siteId, ruleInstruction}`
   - Output: `{triggers: List[RuleTrigger]}`
   - Uses sitemap and atlas to find real DOM elements

2. **API** (`/rule`) - Stores and validates triggers

   - Enforces RuleTrigger contract
   - Provides triggers to SDK

3. **SDK** - Evaluates triggers in real-time
   - Matches events against trigger conditions
   - Fires rules when all conditions met

## Benefits

✅ **Type Safety** - Pydantic models ensure valid structure
✅ **Consistency** - Same format across all components  
✅ **Generic** - Works for any website structure
✅ **Maintainable** - Single source of truth for format
✅ **Extensible** - Easy to add new operators/fields
