from langchain_core.runnables import RunnableLambda
def _echo(inputs: dict): return {"output": f"DomSphere echo: {inputs.get('input','')}"}
echo_chain = RunnableLambda(_echo)
