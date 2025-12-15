# Supervisor Agent

A clean, configuration-driven supervisor agent that coordinates specialized worker agents. The supervisor is **agent-agnostic** and reads all configuration from a single YAML file.

## Architecture

The supervisor implements the **supervisor pattern** from LangChain:

```
┌─────────────────────────────────────┐
│     Supervisor Agent                │
│   (Routes to specialized workers)   │
└──────────────┬──────────────────────┘
               │
        ┌──────┴──────┐
        │             │
        ▼             ▼
   ┌─────────┐   ┌─────────┐
   │ Agent A │   │ Agent B │
   └─────────┘   └─────────┘
```

The supervisor:
- Routes user requests to appropriate specialized agents
- Coordinates multi-step workflows
- Supports human-in-the-loop review
- Uses checkpointing for stateful conversations

## Configuration

All agents and the supervisor are configured in `supervisor_config.yaml`:

```yaml
supervisor:
  name: "System Supervisor"
  llm:
    provider: "bedrock"
    model_id: "us.amazon.nova-pro-v1:0"
  system_prompt: "You are a helpful system supervisor..."

agents:
  - name: "agent_name"
    module_path: "path.to.module"
    tools_from_module: ["function1", "function2"]
    llm:
      provider: "bedrock"
      model_id: "..."
    system_prompt: "You are a..."
```

### Configuration Fields

**Supervisor Section:**
- `name`: Display name for the supervisor
- `description`: What the supervisor does
- `llm`: LLM configuration (provider, model_id, region, temperature, max_tokens)
- `system_prompt`: System instructions for the supervisor

**Agents Section:**
Each agent entry defines:
- `name`: Agent identifier (used as tool name)
- `description`: What the agent does
- `module_path`: Python module path (e.g., `Authorization_Agent.agents`)
- `tools_from_module`: List of function names to import and expose
- `llm`: Per-agent LLM configuration
- `system_prompt`: Agent-specific instructions
- `human_review` (optional): Human-in-the-loop settings

## Implementation

### Core Components

#### `SupervisorConfig`
Loads and parses the YAML configuration file.

#### `AgentToolFactory`
Dynamically loads modules and creates tool wrappers from functions:
- Imports modules by path
- Extracts specified functions
- Wraps functions as LangChain tools

#### `SupervisorAgentBuilder`
Orchestrates the supervisor creation:
1. Creates each sub-agent with its tools and LLM
2. Wraps sub-agents as tools for the supervisor
3. Creates the supervisor agent with a checkpointer for stateful conversations

#### `load_supervisor_agent()`
Main entry point to load and build the complete supervisor.

#### `run_supervisor()`
Convenience function to run the supervisor with streaming output.

## Usage

### Basic Usage

```python
from main import load_supervisor_agent, run_supervisor

# Load the supervisor
supervisor = load_supervisor_agent("supervisor_config.yaml")

# Run a query
run_supervisor(supervisor, "Your user query here")
```

### Programmatic Usage

```python
from main import load_supervisor_agent

supervisor = load_supervisor_agent()

# Invoke with checkpointing for stateful conversations
config = {"configurable": {"thread_id": "conversation_1"}}

result = supervisor.invoke(
    {"messages": [{"role": "user", "content": "Your query"}]},
    config
)

print(result["messages"][-1].content)
```

## Key Design Principles

1. **Configuration-Driven**: All agent setup in YAML, no code changes needed
2. **Agent-Agnostic**: Works with any module and function
3. **Clean Separation**: Each layer has focused responsibility
4. **Minimal Code**: No unnecessary abstractions
5. **Scalable**: Add new agents by editing YAML only
6. **Stateful**: Built-in checkpointing for conversations

## Adding New Agents

To add a new agent:

1. Create your agent module with functions that accept a string request
2. Add entry to `agents` in `supervisor_config.yaml`:

```yaml
agents:
  - name: "new_agent"
    module_path: "path.to.your.module"
    tools_from_module: ["function1", "function2"]
    llm:
      provider: "bedrock"
      model_id: "..."
    system_prompt: "..."
```

3. Done! The supervisor automatically discovers and wraps the agent.

## Human-in-the-Loop Review

Configure interrupt points in agent config:

```yaml
human_review:
  enabled: true
  interrupt_tools: ["send_email", "delete_data"]  # Tools that require approval
```

When enabled, sensitive operations will pause and wait for human approval before proceeding.

## Dependencies

- `langchain[aws]>=1.1.3`
- `langgraph>=1.0.4`
- `langsmith>=0.4.56`
- `pyyaml>=6.0`

Install with:
```bash
uv sync
```

## Environment Variables

Set these for AWS Bedrock:
- `AWS_REGION`: AWS region (default: us-east-2)
- `AWS_ACCESS_KEY_ID`: AWS credentials
- `AWS_SECRET_ACCESS_KEY`: AWS credentials

Or use AWS profile configuration.
