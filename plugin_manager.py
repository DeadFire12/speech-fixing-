from __future__ import annotations
import os
import importlib.util


class PluginManager:

    def __init__(self, plugin_directory):

        self.plugin_directory = (
            plugin_directory
        )

        self.plugins = {}


    def register(
        self,
        name,
        description,
        function
    ):

        self.plugins[name] = {
            "description": description,
            "function": function
        }


    def load_plugins(self):

        if not os.path.exists(
            self.plugin_directory
        ):

            os.makedirs(
                self.plugin_directory,
                exist_ok=True
            )

            return


        for filename in os.listdir(
            self.plugin_directory
        ):

            if not filename.endswith(
                ".py"
            ):

                continue


            if filename.startswith(
                "_"
            ):

                continue


            path = os.path.join(
                self.plugin_directory,
                filename
            )


            module_name = (
                "plugin_"
                + filename[:-3]
            )


            try:

                spec = (
                    importlib.util
                    .spec_from_file_location(
                        module_name,
                        path
                    )
                )

                module = (
                    importlib.util
                    .module_from_spec(
                        spec
                    )
                )

                spec.loader.exec_module(
                    module
                )


                if hasattr(
                    module,
                    "register"
                ):

                    module.register(
                        self
                    )


            except Exception as e:

                print(
                    f"Plugin error "
                    f"({filename}):",
                    e
                )


    def run(
        self,
        name,
        *args,
        **kwargs
    ):

        if name not in self.plugins:

            return {
                "success": False,
                "message": (
                    f"Unknown plugin: {name}"
                )
            }


        try:

            result = self.plugins[name][
                "function"
            ](
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


    def list_plugins(self):

        return [
            {
                "name": name,
                "description": data[
                    "description"
                ]
            }

            for name, data in self.plugins.items()
        ]