import os

from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore.identity.auth import requires_api_key
from ddtrace.llmobs import LLMObs

from cosmic_explorer_agent.agent import create_agent

app = BedrockAgentCoreApp()
_datadog_enabled = False


def enable_datadog(api_key: str) -> None:
    global _datadog_enabled

    if _datadog_enabled:
        return

    LLMObs.enable(
        ml_app="cosmic-explorer-agent",
        api_key=api_key,
        site=os.getenv("DD_SITE", "datadoghq.com"),
        agentless_enabled=True,
        integrations_enabled=True,
    )
    _datadog_enabled = True


@requires_api_key(provider_name="cosmicExplorerDatadog")
def enable_datadog_from_identity(*, api_key: str) -> None:
    enable_datadog(api_key)


def run_agent(prompt: str, api_key: str) -> str:
    agent = create_agent(api_key=api_key)
    return str(agent(prompt))


@requires_api_key(provider_name="agcorenasa1OpenAI")
def run_with_agentcore_identity(prompt: str, *, api_key: str) -> str:
    return run_agent(prompt, api_key)


@app.entrypoint
def invoke(payload: dict) -> dict:
    prompt = payload.get("prompt")

    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")

    prompt = prompt.strip()

    local_datadog_key = os.getenv("DD_API_KEY")
    if local_datadog_key:
        enable_datadog(local_datadog_key)
    else:
        enable_datadog_from_identity()

    local_model_key = (
        os.getenv("GROQ_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )

    try:
        with LLMObs.workflow(name="cosmic_explorer_request"):
            LLMObs.annotate(input_data=prompt)

            if local_model_key:
                response = run_agent(prompt, local_model_key)
            else:
                response = run_with_agentcore_identity(prompt)

            LLMObs.annotate(output_data=response)
    finally:
        # AgentCore is serverless, so flush before returning.
        LLMObs.flush()

    return {"response": response}


if __name__ == "__main__":
    app.run()