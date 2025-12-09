import os
import importlib
from typing import Any
import yaml

from langchain.tools import tool, BaseTool
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_aws import ChatBedrock
from langgraph.checkpoint.memory import InMemorySaver

#Load and manage supervisor configuration from YAML.
class SupervisorConfig:
    def __init__(self, config_path: str = "supervisor_config.yaml"):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self) -> dict:
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, "r") as f:
            return yaml.safe_load(f)

    def get_supervisor_config(self) -> dict:
        return self.config.get("supervisor", {})

    def get_agents_config(self) -> list:
        return self.config.get("agents", [])

# Dynamically load tools from agent module.
class AgentToolFactory:
    @staticmethod
    def load_module(module_path: str) -> Any:
        try:
            return importlib.import_module(module_path)
        except ImportError as e:
            raise ImportError(f"Failed to import {module_path}: {e}")

    @staticmethod
    def get_functions_from_module(module: Any, function_names: list) -> dict:
        functions = {}
        for name in function_names:
            if not hasattr(module, name):
                raise AttributeError(f"Function '{name}' not found in module")
            functions[name] = getattr(module, name)
        return functions

    @staticmethod
    def create_tool_wrapper(func_name: str, func: callable, agent_name: str) -> BaseTool:
        @tool(name=f"{agent_name}_{func_name}")
        def tool_wrapper(request: str) -> str:
            try:
                result = func(request)
                return str(result) if result is not None else "Operation completed"
            except Exception as e:
                return f"Error: {str(e)}"

        tool_wrapper.description = (
            f"{agent_name}: {func_name} - "
            f"Delegates to {agent_name} for specialized handling"
        )
        return tool_wrapper


class SupervisorAgentBuilder:
    def __init__(self, config: SupervisorConfig):
        self.config = config
        self.supervisor_config = config.get_supervisor_config()
        self.agents_config = config.get_agents_config()
        self.sub_agents = {}
        self.supervisor_tools = []

    def create_llm(self, llm_config: dict) -> Any:
        provider = llm_config.get("provider", "bedrock")

        if provider == "bedrock":
            return ChatBedrock(
                model_id=llm_config.get("model_id", "us.amazon.nova-pro-v1:0"),
                region_name=llm_config.get("region", "us-east-2"),
                temperature=llm_config.get("temperature", 0.2),
                model_kwargs={
                    "max_tokens": llm_config.get("max_tokens", 512)
                }
            )
        else:
            return init_chat_model(
                llm_config.get("model_id"),
                temperature=llm_config.get("temperature", 0.2),
            )

    def create_sub_agent(self, agent_config: dict) -> Any:
        agent_name = agent_config.get("name")
        module_path = agent_config.get("module_path")
        tool_names = agent_config.get("tools_from_module", [])
        llm_config = agent_config.get("llm", {})
        system_prompt = agent_config.get("system_prompt", "")

        module = AgentToolFactory.load_module(module_path)
        functions = AgentToolFactory.get_functions_from_module(module, tool_names)

        tools = [
            AgentToolFactory.create_tool_wrapper(name, func, agent_name)
            for name, func in functions.items()
        ]

        llm = self.create_llm(llm_config)

        agent = create_agent(
            llm,
            tools=tools,
            system_prompt=system_prompt,
        )

        return agent
    
    # Create a tool wrapper to invoke a sub-agent.
    def create_supervisor_tool(self, agent_name: str, agent: Any) -> BaseTool:
        @tool(name=agent_name)
        def agent_tool(request: str) -> str:
            """Invoke specialized agent for domain-specific task."""
            try:
                result = agent.invoke({
                    "messages": [{"role": "user", "content": request}]
                })
                if hasattr(result, "get"):
                    messages = result.get("messages", [])
                    if messages:
                        last_msg = messages[-1]
                        if hasattr(last_msg, "text"):
                            return last_msg.text
                        elif hasattr(last_msg, "content"):
                            return last_msg.content
                return str(result)
            except Exception as e:
                return f"Error in {agent_name}: {str(e)}"

        return agent_tool

    # Build the supervisor agent
    def build(self) -> Any:
        for agent_config in self.agents_config:
            agent_name = agent_config.get("name")
            agent = self.create_sub_agent(agent_config)
            self.sub_agents[agent_name] = agent

        for agent_name, agent in self.sub_agents.items():
            tool = self.create_supervisor_tool(agent_name, agent)
            self.supervisor_tools.append(tool)

        supervisor_llm = self.create_llm(self.supervisor_config.get("llm", {}))

        supervisor = create_agent(
            supervisor_llm,
            tools=self.supervisor_tools,
            system_prompt=self.supervisor_config.get("system_prompt", ""),
            checkpointer=InMemorySaver(),
        )

        return supervisor

# Load and build supervisor agent from configuration
def load_supervisor_agent(config_path: str = "supervisor_config.yaml") -> Any:
    config = SupervisorConfig(config_path)
    builder = SupervisorAgentBuilder(config)
    return builder.build()


def run_supervisor(supervisor: Any, query: str, config_id: str = "default") -> None:
    config = {"configurable": {"thread_id": config_id}}

    print(f"\n{'='*80}")
    print(f"Query: {query}")
    print(f"{'='*80}\n")

    for step in supervisor.stream(
        {"messages": [{"role": "user", "content": query}]},
        config,
    ):
        for update in step.values():
            if isinstance(update, dict):
                for message in update.get("messages", []):
                    if hasattr(message, "pretty_print"):
                        message.pretty_print()
                    else:
                        print(f"{message.type}: {message.content}")
            else:
                if hasattr(update, "id"):
                    print(f"\n[INTERRUPTED] Event ID: {update.id}")
                    if hasattr(update, "value"):
                        print(f"Details: {update.value}")


def main():
    supervisor = load_supervisor_agent()

    example_queries = [
        "Extract token LIC_123 from this request and determine my scope",
        "and get me the pet with id 2",
    ]

    for query in example_queries:
        run_supervisor(supervisor, query)


if __name__ == "__main__":
    main()
