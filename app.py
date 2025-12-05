from langgraph.graph import StateGraph, END
from typing import TypedDict, Dict, Any, List
import asyncio
from functools import partial

from Authorization_Agent.auth_service import get_role_from_token
from MCPAgent.main import (
    ModeSelector,
    load_config,
    load_server_configs,
    setup_fastmcp_server_from_openapi_spec,
)


# Represents the state of Langgraph agent
class AgentState(TypedDict):
    prompt: str
    data: Dict[str, Any]
    history: List[Any]


# Base of all Langgraph agent
class BaseAgent:
    def __init__(self, name: str):
        self.name = name

    async def execute(self, state: AgentState) -> Dict[str, Any]:
        raise NotImplementedError


# Auth Agent to extract user claims
class AuthorizationAgent(BaseAgent):
    async def execute(self, state: AgentState) -> Dict[str, Any]:
        prompt = state["prompt"]
        try:
            token = prompt.split("token:")[1].split(",")[0].strip()
        except RuntimeError:
            token = ""

        role = get_role_from_token(token)
        print(f"[{self.name}] Authorization successful. Role: {role}")

        return {"role": role}


# Agent Connected with MCP Tools
class MCPAgent(BaseAgent):
    async def execute(self, state: AgentState) -> Dict[str, Any]:
        prompt = state["prompt"]
        role = state["data"].get("role")

        if role == "unauthorized":
            return {"result": "Unauthorized to perform this action."}

        # Load MCPAgent config
        config = load_config("MCPAgent/config.json")
        server_cfg_path = config["servers_config_file"]
        server_configs = load_server_configs(f"MCPAgent/{server_cfg_path}")

        if not server_configs:
            return {"result": "MCPAgent not configured. No servers found."}

        servers = []
        for sc in server_configs:
            spec_url = sc.get("spec_url") or sc.get("spec_link")
            base_url = sc.get("base_url", "")
            name = sc.get("name", "Unknown API")

            server = setup_fastmcp_server_from_openapi_spec(spec_url, base_url, name)
            if server:
                servers.append(server)

        if not servers:
            return {"result": "MCPAgent not configured. No API servers loaded."}

        mode_selector = ModeSelector(servers, server_configs, config)

        # Prepend the role to the prompt for the MCPAgent
        mcp_prompt = f"User with role '{role}' asks: {prompt}"

        print(f"[{self.name}] Invoking MCP with prompt: {mcp_prompt}")
        result = await mode_selector.route(mcp_prompt)

        return {"result": result}


# Agent Orchestrator to provide communication between the Agents
class AgentOrchestrator:
    """Orchestrates the communication between a sequence of agents."""

    def __init__(self, agents: List[BaseAgent]):
        self.agents = agents
        self.graph = StateGraph(AgentState)
        self._build_graph()

    async def _agent_node(self, state: AgentState, agent: BaseAgent) -> Dict[str, Any]:
        """Generic node for executing an agent."""
        result = await agent.execute(state)

        new_data = state["data"].copy()
        new_data.update(result)

        history = state["history"] + [result]

        return {"data": new_data, "history": history}

    def _build_graph(self):
        self.graph.add_node("start", lambda state: {})
        self.graph.set_entry_point("start")

        for i, agent in enumerate(self.agents):
            node_name = agent.name
            self.graph.add_node(node_name, partial(self._agent_node, agent=agent))

            previous_node = self.agents[i - 1].name if i > 0 else "start"
            self.graph.add_edge(previous_node, node_name)

        if self.agents:
            self.graph.add_edge(self.agents[-1].name, END)

    async def run(self, prompt: str):
        print(f"[AgentOrchestrator] Starting workflow with prompt: {prompt}")

        app = self.graph.compile()
        inputs = {"prompt": prompt, "data": {}, "history": []}

        async for output in app.astream(inputs):
            # astream() yields the full state of the graph after each node completes
            print("---")
            for key, value in output.items():
                print(f"Node: {key}")
                # Don't print the whole state for the final output
                if key != "__end__":
                    print(f"  State: {value}")
            print("---")


async def main():
    # Agents in the desired order of execution
    agents = [AuthorizationAgent("AuthorizationAgent"), MCPAgent("MCPAgent")]

    # Create and run the orchestrator
    orchestrator = AgentOrchestrator(agents)

    prompt = (
        "token: MF_456, find pets by status available and then get the pet with id 2"
    )

    await orchestrator.run(prompt)


if __name__ == "__main__":
    asyncio.run(main())
