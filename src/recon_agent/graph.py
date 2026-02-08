"""
LangGraph reconciliation agent for ad-hoc file uploads.


Features:
- Tool-calling agent using AWS Bedrock (Claude)
- Multipart file upload for reconciliation
- Human-in-the-loop approval for write operations
- Authorization via user scope/role
- Robust error handling and logging
"""


from __future__ import annotations


import asyncio
import json
import logging
import os
from typing import Any


import httpx
from langchain.tools import tool
from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_aws.chat_models import ChatBedrock
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.types import Command, interrupt
from typing_extensions import Annotated, TypedDict


logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("AGENT_LOG_LEVEL", "INFO"))


class UserContext(TypedDict, total=False):
    user_id: str
    role: str
    roles: list[str]
    scope: list[str]


class Context(TypedDict):
    thread_id: str
    user: UserContext


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


AGENT_SYSTEM_PROMPT = """
You are a reconciliation agent responsible for ad-hoc reconciliation file uploads.


Rules:
- Be explicit about reconciliation actions
- Validate and confirm file details before upload
- All uploads are WRITE operations and require approval
- Never assume missing inputs
- Clearly summarize reconciliation submission status
"""


def _get_api_base_url() -> str:
    return os.getenv(
        "RECONCILIATION_API_BASE_URL",
        "http://localhost:8087",
    )


@tool
def upload_reconciliation_files(
    trade_date: str,
    currency: str,
    netting_file_path: str,
    settlement_file_path: str | None = None,
    description: str | None = None,
) -> str:
    """
    Upload netting/settlement files to trigger ad-hoc reconciliation.


    Args:
        trade_date: Trade date (YYYY-MM-DD)
        currency: Currency code (e.g. CAD, USD)
        netting_file_path: Local path to netting .txt file
        settlement_file_path: Optional local path to settlement .txt file
        description: Optional description
    """
    try:
        if not os.path.exists(netting_file_path):
            return f"Error: Netting file not found at {netting_file_path}"


        files = {}


        with open(netting_file_path, "rb") as nf:
            files["nettingFile"] = (
                os.path.basename(netting_file_path),
                nf.read(),
                "text/plain",
            )


        if settlement_file_path:
            if not os.path.exists(settlement_file_path):
                return f"Error: Settlement file not found at {settlement_file_path}"
            with open(settlement_file_path, "rb") as sf:
                files["settlementFile"] = (
                    os.path.basename(settlement_file_path),
                    sf.read(),
                    "text/plain",
                )


        params = {
            "tradeDate": trade_date,
            "currency": currency,
        }


        if description:
            params["description"] = description

        logger.info(f"Attempting upload to API base URL: {_get_api_base_url()}" )
        response = httpx.post(
            f"{_get_api_base_url()}/api/v1/reconciliation/adhoc/upload",
            params=params,
            files=files,
            timeout=60.0,
        )
        logger.info(f"Upload response status: {response.status_code}" )


        if response.status_code in (200, 202):
            logger.info(
                f"Reconciliation upload accepted "
                f"(tradeDate={trade_date}, currency={currency})"
            )
            return response.text


        logger.error(
            f"Upload failed ({response.status_code}): {response.text}"
        )
        return f"Error: Upload failed ({response.status_code}) - {response.text}"


    except Exception as e:
        logger.exception("Reconciliation upload failed")
        return f"Error uploading reconciliation files: {str(e)}"


async def _get_tools(user_context: UserContext) -> list[Any]:
    """
    Only allow users with reconciliation scope or admin role.
    """
    scope = user_context.get("scope", [])
    roles = user_context.get("roles", [])


    if isinstance(scope, str):
        scope = scope.split(" ")

    return [upload_reconciliation_files]


def _is_write_operation(tool_name: str) -> bool:
    write_keywords = ["create", "update", "delete", "add", "remove"]
    return any(k in tool_name.lower() for k in write_keywords)


async def call_model(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    try:
        user_context = config.get("configurable", {}).get("user", {})
        tools = await _get_tools(user_context)

        model = ChatBedrock(
            model_id=os.getenv(
                "BEDROCK_MODEL_ID",
                "anthropic.claude-3-5-sonnet-20241022-v2:0",
            ),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            temperature=0,
            max_tokens=4096,
        )


        model = model.bind_tools(tools)
        logger.info(f"Bound tools: {[t.name for t in tools]}")

        messages = state["messages"]
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=AGENT_SYSTEM_PROMPT)] + messages


        response = model.invoke(messages)
        return {"messages": [response]}


    except Exception as e:
        logger.exception("LLM failure")
        return {
            "messages": [
                AIMessage(content=f"Agent error: {str(e)}")
            ]
        }

def _should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "handle_tool_calls"
    return END


async def handle_tool_calls(
    state: AgentState,
    config: RunnableConfig,
) -> dict[str, Any]:


    messages = state["messages"]
    last_message = messages[-1]
    user_context = config.get("configurable", {}).get("user", {})


    tools = await _get_tools(user_context)
    tools_by_name = {t.name: t for t in tools}
    logger.info(f"Handling tool calls: {[call['name'] for call in last_message.tool_calls]}" )

    results = []


    for call in last_message.tool_calls:
        tool_name = call["name"]
        tool_args = call.get("args", {})


        if _is_write_operation(tool_name):
            approval = interrupt(
                {
                    "action": tool_name,
                    "args": tool_args,
                    "description": (
                        "Ad-hoc Reconciliation Upload Approval Required\n\n"
                        f"Tool: {tool_name}\n"
                        f"Arguments:\n{json.dumps(tool_args, indent=2)}"
                    ),
                }
            )


            if not (
                isinstance(approval, Command)
                and approval.resume
                and approval.resume.get("type") in ("approve", "edit")
            ):
                results.append(
                    ToolMessage(
                        content="Upload rejected by user.",
                        tool_call_id=call["id"],
                    )
                )
                continue


            if approval.resume.get("args"):
                tool_args = approval.resume["args"]


        tool = tools_by_name.get(tool_name)
        if not tool:
            results.append(
                ToolMessage(
                    content=f"Tool not found: {tool_name}",
                    tool_call_id=call["id"],
                )
            )
            continue


        try:
            observation = await tool.ainvoke(tool_args)
        except Exception as e:
            observation = f"Tool execution error: {str(e)}"


        results.append(
            ToolMessage(
                content=str(observation),
                tool_call_id=call["id"],
            )
        )


    has_error = any(
        isinstance(msg, ToolMessage) and str(msg.content).startswith("Error")
        for msg in results
    )

    if has_error:
        return Command(
            update={"messages": results},
            goto=END,
        )

    return {"messages": results}


async def create_agent_graph() -> StateGraph:
    graph = StateGraph(AgentState, config_schema=Context)


    graph.add_node("call_model", call_model)
    graph.add_node("handle_tool_calls", handle_tool_calls)


    graph.add_edge(START, "call_model")
    graph.add_conditional_edges(
        "call_model",
        _should_continue,
        {
            "handle_tool_calls": "handle_tool_calls",
            END: END,
        },
    )
    graph.add_edge("handle_tool_calls", "call_model")


    compiled = graph.compile(name="reconciliation-upload-agent")
    logger.info("Reconciliation upload agent compiled")
    return compiled


_graph = None


class _GraphProxy:
    async def ainvoke(self, *args, **kwargs):
        global _graph
        if _graph is None:
            _graph = await create_agent_graph()
        return await _graph.ainvoke(*args, **kwargs)


    def invoke(self, *args, **kwargs):
        global _graph
        if _graph is None:
            _graph = asyncio.run(create_agent_graph())
        return _graph.invoke(*args, **kwargs)


graph = _GraphProxy()



