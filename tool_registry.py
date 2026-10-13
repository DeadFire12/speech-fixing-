from __future__ import annotations
from tool_manager import ToolManager

from computer_manager import (
    get_system_info,
    get_cpu_info,
    get_memory_info,
    get_disk_info,
    get_battery_info,
    get_network_info,
    get_user_info,
    get_datetime_info,
    launch_program,
    take_screenshot
)

from file_manager import (
    list_files,
    search_files
)

from backup_manager import (
    create_backup,
    list_backups
)

from advanced_tools import (
    open_path,
    create_text_file,
    read_text_file,
    write_text_file,
    delete_path,
    lock_computer,
    restart_computer,
    shutdown_computer,
    get_folder_size
)


# =========================================================
# TOOL REGISTRY
# =========================================================

def create_tool_manager():

    manager = ToolManager()


    # =====================================================
    # EXISTING TOOLS
    # =====================================================

    manager.register(
        "backup",
        "Create a backup of Lily's data.",
        create_backup
    )

    manager.register(
        "list_backups",
        "List Lily's existing backups.",
        list_backups
    )

    manager.register(
        "system_info",
        "Get basic computer information.",
        get_system_info
    )

    manager.register(
        "cpu_info",
        "Get CPU information.",
        get_cpu_info
    )

    manager.register(
        "memory_info",
        "Get RAM information.",
        get_memory_info
    )

    manager.register(
        "disk_info",
        "Get disk information.",
        get_disk_info
    )

    manager.register(
        "battery_info",
        "Get battery information.",
        get_battery_info
    )

    manager.register(
        "network_info",
        "Get network information.",
        get_network_info
    )

    manager.register(
        "user_info",
        "Get current Windows user and computer name.",
        get_user_info
    )

    manager.register(
        "datetime_info",
        "Get the current date and time.",
        get_datetime_info
    )

    manager.register(
        "launch_program",
        "Launch a Windows program.",
        launch_program
    )

    manager.register(
        "list_files",
        "List files and folders.",
        list_files
    )

    manager.register(
        "search_files",
        "Search for files.",
        search_files
    )

    manager.register(
        "take_screenshot",
        "Take a screenshot of the screen.",
        take_screenshot
    )


    # =====================================================
    # NEW COMPUTER / FILE TOOLS
    # =====================================================

    manager.register(
        "open_path",
        "Open a file or folder.",
        open_path
    )

    manager.register(
        "create_text_file",
        "Create a text file.",
        create_text_file
    )

    manager.register(
        "read_text_file",
        "Read a text file.",
        read_text_file
    )

    manager.register(
        "write_text_file",
        "Write text into a file.",
        write_text_file
    )

    manager.register(
        "delete_path",
        "Delete a file or folder after confirmation.",
        delete_path
    )

    manager.register(
        "lock_computer",
        "Lock the Windows computer.",
        lock_computer
    )

    manager.register(
        "restart_computer",
        "Restart Windows after confirmation.",
        restart_computer
    )

    manager.register(
        "shutdown_computer",
        "Shut down Windows after confirmation.",
        shutdown_computer
    )

    manager.register(
        "get_folder_size",
        "Calculate the size of a folder.",
        get_folder_size
    )


    return manager