# Enhanced Rule Agent & Assistant - Advanced Use Cases

## 🚀 **Enhanced Capabilities**

Your rule agent and assistant now support sophisticated targeting and interaction patterns that go far beyond simple ID-based matching.

### **1. Role-Based Targeting**

```javascript
// Natural language: "help users with submit buttons"
// Generated trigger:
{
  "eventType": "dom_click",
  "when": [
    {"field": "telemetry.attributes.role", "op": "equals", "value": "button"},
    {"field": "telemetry.elementText", "op": "contains", "value": "submit"}
  ]
}
```

### **2. Time-Based Conditions**

```javascript
// Natural language: "show help after 10 seconds on checkout page"
// Generated trigger:
{
  "eventType": "time_spent",
  "when": [
    {"field": "telemetry.attributes.path", "op": "equals", "value": "/checkout"},
    {"field": "session.timeOnPage", "op": "gte", "value": 10}
  ]
}
```

### **3. Data Attribute Targeting**

```javascript
// Natural language: "target expensive electronics products"
// Generated trigger:
{
  "eventType": "dom_click",
  "when": [
    {"field": "telemetry.attributes.data-category", "op": "equals", "value": "electronics"},
    {"field": "telemetry.attributes.data-price", "op": "gt", "value": 100}
  ]
}
```

### **4. Pattern Matching with Regex**

```javascript
// Natural language: "validate positive numbers in quantity field"
// Generated trigger:
{
  "eventType": "input_change",
  "when": [
    {"field": "telemetry.attributes.id", "op": "equals", "value": "quantity"},
    {"field": "telemetry.elementText", "op": "regex", "value": "^[1-9][0-9]*$"}
  ]
}
```

### **5. Engagement Tracking**

```javascript
// Natural language: "reward users who scroll 75% down product page"
// Generated trigger:
{
  "eventType": "scroll",
  "when": [
    {"field": "telemetry.attributes.path", "op": "equals", "value": "/products"},
    {"field": "session.scrollDepth", "op": "gte", "value": 75}
  ]
}
```

## 🎯 **Universal Website Compatibility**

The enhanced system works across **any website** by leveraging universal web standards:

### **Standard HTML Attributes**

- `id`, `class` - Universal identifiers
- `role`, `aria-label` - Accessibility standards
- `data-*` - Custom data attributes

### **CSS Patterns**

- Complex selectors: `div.product[data-price]`
- Pseudo-selectors: `:nth-child()`, `:contains()`
- Attribute selectors: `[role="button"]`

### **Session Context**

- Time tracking: `timeOnPage`, `timeOnSite`
- Interaction counts: `clickCount`, `scrollDepth`
- User context: `referrer`, `userAgent`, `viewport`

## 🧠 **Intelligent Agent Training**

The rule agent now understands complex natural language instructions:

**Simple:** "Show promo on products page"
**Advanced:** "Help users who spend more than 30 seconds on checkout without clicking submit"
**Complex:** "Target returning users from Google who view expensive electronics"

## 🔄 **System Flow Enhancement**

```
Natural Language → Enhanced Agent → Advanced Triggers → Smart Assistant → Contextual Suggestions
```

### **Enhanced Agent Processing:**

1. **Semantic Analysis** - Understands intent and context
2. **Real DOM Discovery** - Finds actual elements using atlas
3. **Pattern Generation** - Creates sophisticated conditions
4. **Contract Validation** - Ensures type safety

### **Smart Assistant Evaluation:**

1. **Multi-condition Matching** - Complex boolean logic
2. **Session State Tracking** - Time, interactions, context
3. **Performance Optimization** - Efficient event filtering
4. **Real-time Suggestions** - Contextual help delivery

## ✅ **Benefits**

- **🎯 Precise Targeting** - Role, data attributes, patterns
- **⏰ Time-Aware** - Duration-based conditions
- **🔍 Pattern Matching** - Regex, complex selectors
- **📊 Session Tracking** - User behavior analysis
- **♿ Accessibility** - ARIA and role support
- **🌐 Universal** - Works on any website
- **🚀 Scalable** - Contract-driven architecture

Your system now rivals enterprise personalization platforms while maintaining simplicity and type safety!
