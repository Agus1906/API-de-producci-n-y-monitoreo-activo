"""LangChain emite spans y uso de tokens reales a LangSmith."""
import os


def configure(config):
    os.environ['LANGSMITH_TRACING'] = str(config.langsmith_tracing).lower()
    os.environ['LANGSMITH_PROJECT'] = config.langsmith_project
    if config.langsmith_tracing:
        if not config.langsmith_api_key:
            raise ValueError('LANGSMITH_API_KEY requerida para tracing')
        os.environ['LANGSMITH_API_KEY'] = config.langsmith_api_key.get_secret_value()


def model(config):
    if config.agent_mode == 'offline':
        return None
    from langchain_openai import ChatOpenAI
    if not config.openai_api_key:
        raise ValueError('OPENAI_API_KEY requerida en modo llm')
    return ChatOpenAI(model=config.openai_model,
                      api_key=config.openai_api_key.get_secret_value(),
                      timeout=30, max_retries=1)
