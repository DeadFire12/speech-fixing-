from __future__ import annotations
class ToolManager:
    
    def __init__(self):

        self.tools = {}


    def register(
        self,
        name,
        description,
        function
    ):

        self.tools[name] = {
            "description": description,
            "function": function
        }


    def run(
        self,
        name,
        *args,
        **kwargs
    ):

        if name not in self.tools:

            return {
                "success": False,
                "message": f"Unknown tool: {name}"
            }

        try:

            result = self.tools[name]["function"](
                *args,
                **kwargs
            )

            return {
                "success": True,
                "result": result
            }

        except Exception as e:

            return {
                "success": False,
                "message": str(e)
            }


    def list_tools(self):

        result = []

        for name, data in self.tools.items():

            result.append({
                "name": name,
                "description": data["description"]
            })

        return result