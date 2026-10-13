from __future__ import annotations
# =========================================================
# TOOL CHAIN
# =========================================================

class ToolChain:

    def __init__(self, tool_manager):

        self.tool_manager = tool_manager


    # =====================================================
    # RUN ONE TOOL
    # =====================================================

    def run_tool(
        self,
        tool_name,
        *args
    ):

        result = self.tool_manager.run(
            tool_name,
            *args
        )

        return result


    # =====================================================
    # RUN MULTIPLE TOOLS
    # =====================================================

    def run_chain(
        self,
        steps
    ):

        results = []

        for step in steps:

            tool_name = step["tool"]

            args = step.get(
                "args",
                []
            )

            result = self.tool_manager.run(
                tool_name,
                *args
            )

            results.append({
                "tool": tool_name,
                "result": result
            })


            if not result["success"]:

                return {
                    "success": False,
                    "results": results,
                    "failed_tool": tool_name
                }


        return {
            "success": True,
            "results": results
        }