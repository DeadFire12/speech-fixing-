from __future__ import annotations
import os


# =========================================================
# LIST FILES
# =========================================================

def list_files(folder):

    if not os.path.exists(folder):

        return {
            "success": False,
            "message": "Folder does not exist."
        }

    if not os.path.isdir(folder):

        return {
            "success": False,
            "message": "That path is not a folder."
        }

    items = []

    try:

        for item in os.listdir(folder):

            full_path = os.path.join(
                folder,
                item
            )

            if os.path.isdir(full_path):

                item_type = "Folder"

            else:

                item_type = "File"

            items.append({
                "name": item,
                "type": item_type
            })

        return {
            "success": True,
            "folder": folder,
            "items": items
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }


# =========================================================
# SEARCH FILES
# =========================================================

def search_files(folder, filename):

    if not os.path.exists(folder):

        return {
            "success": False,
            "message": "Folder does not exist."
        }

    results = []

    filename = filename.lower()

    try:

        for root, directories, files in os.walk(folder):

            for file in files:

                if filename in file.lower():

                    results.append(
                        os.path.join(
                            root,
                            file
                        )
                    )

        return {
            "success": True,
            "results": results
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }