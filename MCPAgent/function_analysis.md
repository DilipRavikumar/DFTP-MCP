# Function Usage Analysis for workflow_core.py

## Function Dependency Tree

### MODE 1 (Single-step keyword-based):
```
main.py::handle_mode_1()
  ├── get_api_specs()
  │     └── _extract_base_url_from_spec() [internal helper]
  ├── find_matching_endpoints()
  │     └── expand_id_ranges() [internal helper]
  └── execute_api_call()
```

### MODE 2 (Multi-step LLM-driven):
```
agent_graph.py::act()
  └── execute_multi_stage_workflow()
        ├── get_api_specs()
        │     └── _extract_base_url_from_spec() [internal helper]
        ├── _build_endpoint_catalog()
        ├── parse_sequential_query()
        │     └── _call_llm()
        │           └── _init_llm()
        ├── _llm_plan_operation() [called in loop]
        │     └── _call_llm()
        │           └── _init_llm()
        └── execute_api_call() [called in loop]
```

## All Functions Status:

1. ✅ `_init_llm()` - **NECESSARY** - Mode 2 only
2. ✅ `_call_llm()` - **NECESSARY** - Mode 2 only  
3. ✅ `_extract_base_url_from_spec()` - **NECESSARY** - Used by get_api_specs (both modes)
4. ✅ `get_api_specs()` - **NECESSARY** - Used by both Mode 1 & Mode 2
5. ✅ `expand_id_ranges()` - **NECESSARY** - Used by find_matching_endpoints (Mode 1)
6. ✅ `find_matching_endpoints()` - **NECESSARY** - Mode 1 only
7. ✅ `parse_sequential_query()` - **NECESSARY** - Mode 2 only
8. ✅ `_build_endpoint_catalog()` - **NECESSARY** - Mode 2 only
9. ✅ `_llm_plan_operation()` - **NECESSARY** - Mode 2 only
10. ✅ `execute_api_call()` - **NECESSARY** - Used by both Mode 1 & Mode 2
11. ✅ `execute_multi_stage_workflow()` - **NECESSARY** - Mode 2 only

## Conclusion:
**ALL 11 FUNCTIONS ARE NECESSARY** - Each serves a specific purpose in either Mode 1, Mode 2, or both.

