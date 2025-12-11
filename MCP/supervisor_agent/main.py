import os
import sys
# Add parent directory to path so we can import sibling agents
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Also ensure Authorization_Agent directory is in path for relative imports
auth_agent_dir = os.path.join(parent_dir, "Authorization_Agent")
if auth_agent_dir not in sys.path:
    sys.path.insert(0, auth_agent_dir)

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
        @tool
        def tool_wrapper(request: str) -> str:
            """Delegates the request to the specialized agent."""
            try:
                result = func(request)
                return str(result) if result is not None else "Operation completed"
            except Exception as e:
                return f"Error: {str(e)}"
        
        # Set the name and description manually on the tool instance
        tool_wrapper.name = f"{agent_name}_{func_name}"
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
        @tool
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
        
        agent_tool.name = agent_name
        agent_tool.description = f"Delegates to {agent_name} for domain-specific tasks."
        return agent_tool

    # Build the supervisor agent
    def build(self) -> Any:
        # Scope mappings for each agent
        scope_mappings = {
            "position_agent": ["MutualFunds", "Assets", "Wealth"],
            "order_details_agent": ["MutualFunds", "Assets", "General"],
            "order_ingestion_agent": ["MutualFunds", "Assets", "ACCOUNT_MANAGER"],
        }
        
        # Helper function to get user scope
        def get_user_scope() -> dict:
            """Extract scope and roles from authorization agent."""
            try:
                auth_module = AgentToolFactory.load_module("Authorization_Agent.wrapper")
                if hasattr(auth_module, "extract_scope_and_roles"):
                    return auth_module.extract_scope_and_roles()
            except Exception as e:
                print(f"Warning: Could not extract scope: {e}")
            return {"scope": "unauthorized", "roles": [], "token": ""}
        
        for agent_config in self.agents_config:
            agent_name = agent_config.get("name")
            module_path = agent_config.get("module_path")
            tool_names = agent_config.get("tools_from_module", [])
            
            # Skip authorization_agent in tool creation (it's used separately for scope extraction)
            if agent_name == "authorization_agent":
                continue
            
            # If process_request is in the tools, expose it directly as a tool
            # This avoids double-wrapping and works better with LangGraph agents
            # process_request is typically the main entry point for LangGraph-based agents
            # and handles the full workflow internally, so we don't need a sub-agent wrapper
            if "process_request" in tool_names:
                module = AgentToolFactory.load_module(module_path)
                if hasattr(module, "process_request"):
                    func = getattr(module, "process_request")
                    # Store agent_name and allowed_scopes in closure
                    allowed_scopes = scope_mappings.get(agent_name, [])
                    
                    # Create a direct tool wrapper for process_request with scope checking
                    @tool
                    def direct_agent_tool(request: str) -> str:
                        """Invoke specialized agent for domain-specific task."""
                        try:
                            # Get current scope
                            current_scope_info = get_user_scope()
                            current_scope = current_scope_info.get("scope", "unauthorized")
                            
                            # Check if scope is allowed for this agent
                            if current_scope not in allowed_scopes and current_scope != "unauthorized":
                                return f"Unauthorized: Scope '{current_scope}' is not allowed for {agent_name}. Required scopes: {', '.join(allowed_scopes)}"
                            
                            # Pass scope info in request (agents can extract it)
                            # Format: "SCOPE:{scope}|ROLES:{roles}|REQUEST:{actual_request}"
                            scope_payload = f"SCOPE:{current_scope}|ROLES:{','.join(current_scope_info.get('roles', []))}|REQUEST:{request}"
                            result = func(scope_payload)
                            
                            # STRICT OUTPUT WRAPPER (Restored)
                            result_str = str(result)
                            if not result_str or result_str == "None":
                                return "TOOL_ERROR: No data returned from tool."
                                
                            return (
                                f"DATA_FROM_TOOL_START\n"
                                f"{result_str}\n"
                                f"DATA_FROM_TOOL_END\n\n"
                                f"INSTRUCTION: The above data is the COMPLETE and ONLY truth. "
                                f"Return it EXACTLY as is. "
                                f"Do NOT add any fund names, investor names, dates, or details not present above. "
                                f"If the data is sparse (e.g. only ID and status), return ONLY ID and status."
                            )
                        except Exception as e:
                            import traceback
                            return f"Error in {agent_name}: {str(e)}\n{traceback.format_exc()}"
                    
                    direct_agent_tool.name = agent_name
                    direct_agent_tool.description = agent_config.get("description", f"Delegates to {agent_name} for domain-specific tasks.")
                    self.supervisor_tools.append(direct_agent_tool)
                    # Skip sub-agent creation when process_request is available
                    continue
            
            # For agents without process_request, use sub-agent approach
            agent = self.create_sub_agent(agent_config)
            self.sub_agents[agent_name] = agent

        for agent_name, agent in self.sub_agents.items():
            supervisor_tool = self.create_supervisor_tool(agent_name, agent)
            self.supervisor_tools.append(supervisor_tool)

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

    print("Supervisor Agent Ready. Type 'exit' or 'quit' to stop.")
    while True:
        try:
            query = input("You: ").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit"):
                break
            run_supervisor(supervisor, query)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break


if __name__ == "__main__":
    main()
