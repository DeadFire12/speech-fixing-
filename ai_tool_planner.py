from __future__ import annotations
import json


# =========================================================
# AI TOOL PLANNER
# =========================================================

def build_tool_prompt(
    user_text,
    tools
):

    tool_list = []

    for tool in tools:

        tool_list.append(
            tool["name"] +
            " - " +
            tool["description"]
        )

    available_tools = "\n".join(
        tool_list
    )


    prompt = f"""
You are Lily's computer tool planner.

The user said:

{user_text}

Available tools:

{available_tools}

Decide whether one of the tools should be used.

Return ONLY valid JSON.

If a tool should be used:

{{
    "use_tool": true,
    "tool": "tool_name",
    "args": []
}}

If no tool is needed:

{{
    "use_tool": false
}}

Do not explain your answer.
"""


    return prompt


# =========================================================
# PARSE AI TOOL PLAN
# =========================================================

def parse_tool_plan(text):

    text = text.strip()


    # -----------------------------------------------------
    # Try direct JSON
    # -----------------------------------------------------

    try:

        result = json.loads(
            text
        )

        return result

    except Exception:

        pass


    # -----------------------------------------------------
    # Try extracting JSON from text
    # -----------------------------------------------------

    start = text.find("{")

    end = text.rfind("}")


    if start != -1 and end != -1:

        possible_json = text[
            start:end + 1
        ]

        try:

            return json.loads(
                possible_json
            )

        except Exception:

            pass


    return {
        "use_tool": False
    }