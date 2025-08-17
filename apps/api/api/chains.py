from pydantic import BaseModel
from langchain_core.runnables import RunnableLambda

class InvokeInput(BaseModel):
    input: str

class InvokeOutput(BaseModel):
    output: str

def _echo(payload: InvokeInput) -> InvokeOutput:
    return InvokeOutput(output=f"DomSphere echo: {payload.input}")

# LangServe wants a callable that takes a dict-like; keep it simple
echo_chain = RunnableLambda(lambda data: {"output": f"DomSphere echo: {data.get('input','')}"})
