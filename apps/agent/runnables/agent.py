# apps/agent/runnables/agent.py
import uuid
from langchain_core.runnables import RunnableLambda
from models.contracts import PlanResponse

def _mock_plan_response() -> PlanResponse:
    plan_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    return {
        "sessionId": session_id,
        "agentVersion": "v1-mock",
        "planId": plan_id,
        "cache": "MISS",
        "plan": {
            "agentVersion": "v1-mock",
            "planId": plan_id,
            "confidence": 0.92,
            "steps": [
                # /products
                {"action":"WAIT","assert":[
                    {"selector":{"strategy":"CSS","value":"[data-testid='product-card']"},"condition":"EXISTS"}
                ]},
                {"action":"CLICK","selector":{
                    "strategy":"CSS","value":"[data-testid='product-link']"
                }, "notes":"open first product"},
                # /product
                {"action":"WAIT","assert":[
                    {"selector":{"strategy":"CSS","value":"[data-testid='product-title']"},"condition":"VISIBLE"}
                ]},
                {"action":"INPUT","selector":{"strategy":"CSS","value":"[data-testid='coupon-input']"},"inputValue":"SAVE10"},
                {"action":"CLICK","selector":{"strategy":"CSS","value":"[data-testid='apply-coupon']"}},
                {"action":"WAIT","assert":[
                    {"selector":{"strategy":"CSS","value":"[data-testid='coupon-applied']"},"condition":"VISIBLE"}
                ]},
                {"action":"CLICK","selector":{"strategy":"CSS","value":"[data-testid='checkout']"}},
                # /checkout
                {"action":"WAIT","assert":[
                    {"selector":{"strategy":"CSS","value":"[data-testid='shipping-form']"},"condition":"VISIBLE"}
                ]},
                {"action":"INPUT","selector":{"strategy":"CSS","value":"[data-testid='shipping-name']"},"inputValue":"Jane Doe"},
                {"action":"INPUT","selector":{"strategy":"CSS","value":"[data-testid='shipping-address']"},"inputValue":"123 Demo St"},
                {"action":"CLICK","selector":{"strategy":"CSS","value":"[data-testid='continue-to-payment']"}},
                # /payment
                {"action":"WAIT","assert":[
                    {"selector":{"strategy":"CSS","value":"[data-testid='payment-form']"},"condition":"VISIBLE"}
                ]},
                {"action":"INPUT","selector":{"strategy":"CSS","value":"[data-testid='card-number']"},"inputValue":"4242424242424242"},
                {"action":"INPUT","selector":{"strategy":"CSS","value":"[data-testid='card-exp']"},"inputValue":"12/28"},
                {"action":"INPUT","selector":{"strategy":"CSS","value":"[data-testid='card-cvc']"},"inputValue":"123"},
                {"action":"CLICK","selector":{"strategy":"CSS","value":"[data-testid='pay']"}}
            ]
        }
    }

def build_agent():
    # Input is ignored in mock; later you can read {url, intent, domSnapshot}
    return RunnableLambda(lambda _: _mock_plan_response())
