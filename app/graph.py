"""M6 encapsulado + barrera HITL antes del efecto persistente."""
from typing import Literal

from langgraph.graph import END, START, StateGraph

from app.hitl import approval
from app.m6.graph import build_graph as build_m6
from app.m6.state import State as M6State
from app.m6.state import initial_state


class State(M6State):
    action: str
    approved: bool
    publication: str


def build_graph(checkpointer, model=None):
    child = build_m6(model=model)

    async def orchestrate(state):
        result = await child.ainvoke(initial_state(state['query']))
        if not result['task_completed']:
            raise RuntimeError(result.get('error') or 'M6 no completó la tarea')
        return {k: v for k, v in result.items() if k != 'messages'}

    def route(state) -> Literal['approval', '__end__']:
        return 'approval' if state['action'] == 'publish_report' else END

    def publish(state):
        # El worker materializa este informe una vez, usando job_id como clave.
        return {'publication': state['final_answer'] if state['approved'] else ''}

    builder = StateGraph(State)
    builder.add_node('multi_agent_m6', orchestrate)
    builder.add_node('approval', approval)
    builder.add_node('publish', publish)
    builder.add_edge(START, 'multi_agent_m6')
    builder.add_conditional_edges('multi_agent_m6', route)
    builder.add_edge('approval', 'publish')
    builder.add_edge('publish', END)
    return builder.compile(checkpointer=checkpointer)
