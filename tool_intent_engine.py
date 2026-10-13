from __future__ import annotations
import os
import re
from datetime import datetime


# =========================================================
# NORMALIZE TEXT
# =========================================================

def normalize_text(text):

    text = text.lower().strip()

    text = text.replace("’", "'")

    # IMPORTANT:
    # Do NOT remove "." because filenames such as
    # Lily.py need to keep their extension.
    text = re.sub(r"[?!,]+", "", text)

    text = re.sub(r"\s+", " ", text)

    return text


# =========================================================
# MEMORY PROTECTION
# =========================================================

def looks_like_memory_request(text):

    # =====================================================
    # COMPUTER / TOOL QUESTIONS
    # =====================================================

    computer_questions = [

        # RAM
        "ram",
        "memory usage",
        "memory information",
        "memory info",
        "check my memory",
        "check my ram",
        "show my memory",
        "show my ram",
        "how much ram do i have",
        "how much memory do i have",
        "how much ram am i using",
        "how much memory am i using",
        "what is my ram usage",
        "what's my ram usage",
        "what is my memory usage",
        "what's my memory usage",
        "tell me my ram usage",
        "tell me my memory usage",

        # Storage
        "storage",
        "disk space",
        "hard drive",
        "hard disk",
        "drive space",
        "check my storage",
        "check my disk",
        "check my hard drive",
        "show my storage",
        "show my disk",
        "how much storage do i have",
        "how much disk space do i have",
        "how much space do i have",
        "how much space is left",
        "how much free space do i have",

        # Account
        "my username",
        "what is my username",
        "what's my username",
        "which username am i using",
        "who am i logged in as",
        "what account am i using",
        "which account am i using",
        "what is my computer name",
        "what's my computer name",
        "what is this computer called",
        "what's this computer called",

        # CPU
        "my cpu",
        "my processor",
        "what cpu do i have",
        "what processor do i have",
        "which cpu do i have",
        "which processor do i have",
        "check my cpu",
        "check my processor",

        # Battery
        "battery",
        "battery level",
        "check my battery",
        "show my battery",
        "how much battery do i have",
        "how much battery is left",

        # Network
        "network",
        "network information",
        "network info",
        "internet information",
        "internet info",
        "check my network",
        "check my internet",
        "what is my ip",
        "what's my ip",
        "what is my ip address",
        "what's my ip address",

        # Date/time
        "what time is it",
        "what's the time",
        "tell me the time",
        "current time",
        "what date is it",
        "what's today's date",
        "what is today's date",
        "current date",
        "what day is it",
        "what day is today",

        # Desktop
        "my desktop",
        "on my desktop",
        "desktop files",
        "files on my desktop",

    ]

    for phrase in computer_questions:

        if phrase in text:

            return False


    # =====================================================
    # REAL MEMORY QUESTIONS
    # =====================================================

    memory_phrases = [

        "do you remember",
        "what is my",
        "what's my",
        "remind me",
        "my name is",
        "my favorite",
        "my favourite",
        "remember that",
        "forget my",
        "change my",
        "update my"

    ]

    for phrase in memory_phrases:

        if phrase in text:

            return True


    return False


# =========================================================
# LAUNCH PROGRAM
# =========================================================

def understand_launch(text):

    patterns = [

        r"^open (.+)$",
        r"^launch (.+)$",
        r"^start (.+)$",
        r"^run (.+)$",
        r"^execute (.+)$",
        r"^turn on (.+)$",
        r"^load (.+)$"

    ]

    for pattern in patterns:

        match = re.match(pattern, text)

        if match:

            program = match.group(1).strip()

            if program:

                return {
                    "tool": "launch_program",
                    "args": [program]
                }

    return None


# =========================================================
# SCREENSHOT
# =========================================================

def understand_screenshot(text):

    patterns = [

        "take a screenshot",
        "take screenshot",
        "take a picture of my screen",
        "take a picture of the screen",
        "capture my screen",
        "capture the screen",
        "screenshot my screen",
        "screenshot the screen",
        "screen capture",
        "capture my display",
        "take a screen capture",
        "take a screenshot of my screen"

    ]

    for phrase in patterns:

        if phrase in text:

            screenshot_folder = os.path.join(
                os.path.dirname(
                    os.path.abspath(__file__)
                ),
                "screenshots"
            )

            os.makedirs(
                screenshot_folder,
                exist_ok=True
            )

            filename = os.path.join(
                screenshot_folder,
                "screenshot_" +
                datetime.now().strftime(
                    "%Y-%m-%d_%H-%M-%S"
                ) +
                ".png"
            )

            return {
                "tool": "take_screenshot",
                "args": [filename]
            }

    return None


# =========================================================
# BACKUP
# =========================================================

def understand_backup(text):

    patterns = [

        "make a backup",
        "create a backup",
        "create backup",
        "make backup",
        "backup lily",
        "back up lily",
        "back up yourself",
        "backup yourself",
        "save a backup",
        "save backup"

    ]

    for phrase in patterns:

        if phrase in text:

            return {
                "tool": "backup",
                "args": []
            }

    return None


# =========================================================
# LIST BACKUPS
# =========================================================

def understand_list_backups(text):

    patterns = [

        "show my backups",
        "show the backups",
        "show backups",
        "list my backups",
        "list the backups",
        "list backups",
        "what backups do i have",
        "which backups do i have",
        "what backups are there",
        "show me my backups"

    ]

    for phrase in patterns:

        if phrase in text:

            return {
                "tool": "list_backups",
                "args": []
            }

    return None


# =========================================================
# SYSTEM INFO
# =========================================================

def understand_system_info(text):

    patterns = [

        "system information",
        "system info",
        "computer information",
        "computer info",
        "tell me about my computer",
        "tell me about this computer",
        "what are my computer specs",
        "show my computer information",
        "show computer information",
        "show system information",
        "show system info",
        "give me system information"

    ]

    for phrase in patterns:

        if phrase in text:

            return {
                "tool": "system_info",
                "args": []
            }

    return None


# =========================================================
# CPU
# =========================================================

def understand_cpu(text):

    patterns = [

        "what processor do i have",
        "which processor do i have",
        "what cpu do i have",
        "which cpu do i have",
        "tell me about my processor",
        "tell me about my cpu",
        "check my processor",
        "check my cpu",
        "show my processor",
        "show my cpu",
        "processor information",
        "processor info",
        "cpu information",
        "cpu info",
        "my processor",
        "my cpu"

    ]

    for phrase in patterns:

        if phrase in text:

            return {
                "tool": "cpu_info",
                "args": []
            }

    return None


# =========================================================
# MEMORY / RAM
# =========================================================

def understand_memory(text):

    patterns = [

        "ram",
        "memory usage",
        "memory information",
        "memory info",
        "check my memory",
        "check my ram",
        "show my memory",
        "show my ram",
        "how much ram do i have",
        "how much memory do i have",
        "how much ram am i using",
        "how much memory am i using",
        "what is my ram usage",
        "what's my ram usage",
        "what is my memory usage",
        "what's my memory usage",
        "tell me my ram usage",
        "tell me my memory usage"

    ]

    for phrase in patterns:

        if phrase in text:

            return {
                "tool": "memory_info",
                "args": []
            }

    return None


# =========================================================
# DISK / STORAGE
# =========================================================

def understand_disk(text):

    patterns = [

        "disk space",
        "storage",
        "hard drive",
        "hard disk",
        "drive space",
        "check my storage",
        "check my disk",
        "check my hard drive",
        "show my storage",
        "show my disk",
        "how much storage do i have",
        "how much disk space do i have",
        "how much space do i have",
        "how much space is left",
        "how much free space do i have",
        "what is taking up space",
        "what's taking up space",
        "what is using my storage",
        "what's using my storage",
        "disk information",
        "disk info"

    ]

    for phrase in patterns:

        if phrase in text:

            return {
                "tool": "disk_info",
                "args": []
            }

    return None


# =========================================================
# BATTERY
# =========================================================

def understand_battery(text):

    patterns = [

        "battery",
        "battery level",
        "battery information",
        "battery info",
        "check my battery",
        "check battery",
        "show my battery",
        "how much battery do i have",
        "how much battery is left",
        "what is my battery level",
        "what's my battery level",
        "am i plugged in",
        "is my laptop plugged in",
        "is the charger connected",
        "is my charger connected"

    ]

    for phrase in patterns:

        if phrase in text:

            return {
                "tool": "battery_info",
                "args": []
            }

    return None


# =========================================================
# NETWORK
# =========================================================

def understand_network(text):

    patterns = [

        "network information",
        "network info",
        "internet information",
        "internet info",
        "check my network",
        "check my internet",
        "show my network",
        "show my internet",
        "what is my ip",
        "what's my ip",
        "what is my ip address",
        "what's my ip address",
        "what network am i connected to",
        "which network am i connected to",
        "am i connected to the internet",
        "am i connected to internet",
        "show my ip address",
        "network"

    ]

    for phrase in patterns:

        if phrase in text:

            return {
                "tool": "network_info",
                "args": []
            }

    return None


# =========================================================
# USER INFORMATION
# =========================================================

def understand_user_info(text):

    patterns = [

        "user information",
        "user info",
        "my username",
        "what is my username",
        "what's my username",
        "which username am i using",
        "who am i logged in as",
        "what account am i using",
        "which account am i using",
        "what is my computer name",
        "what's my computer name",
        "what is this computer called",
        "what's this computer called",
        "who is the current user",
        "show my user information"

    ]

    for phrase in patterns:

        if phrase in text:

            return {
                "tool": "user_info",
                "args": []
            }

    return None


# =========================================================
# DATE / TIME
# =========================================================

def understand_datetime(text):

    patterns = [

        "what time is it",
        "what's the time",
        "tell me the time",
        "current time",
        "time right now",
        "what date is it",
        "what's today's date",
        "what is today's date",
        "tell me today's date",
        "current date",
        "date today",
        "current date and time",
        "what is the date and time",
        "what's the date and time",
        "tell me the date and time",
        "what day is it",
        "what day is today"

    ]

    for phrase in patterns:

        if phrase in text:

            return {
                "tool": "datetime_info",
                "args": []
            }

    return None


# =========================================================
# LIST FILES
# =========================================================

def understand_list_files(text):

    desktop_phrases = [

        "show me my desktop",
        "show my desktop",
        "what is on my desktop",
        "what's on my desktop",
        "what is on the desktop",
        "what's on the desktop",
        "show my desktop files",
        "show the files on my desktop",
        "list my desktop files",
        "list the files on my desktop"

    ]

    for phrase in desktop_phrases:

        if phrase in text:

            desktop = os.path.join(
                os.path.expanduser("~"),
                "Desktop"
            )

            return {
                "tool": "list_files",
                "args": [desktop]
            }


    patterns = [

        r"^list files$",
        r"^show files$",
        r"^show my files$",
        r"^show the files$",
        r"^what files are here$",
        r"^list the files$"

    ]

    for pattern in patterns:

        if re.match(pattern, text):

            return {
                "tool": "list_files",
                "args": [os.getcwd()]
            }

    return None


# =========================================================
# SEARCH FILES
# =========================================================

def understand_search_files(text):

    desktop = os.path.join(
        os.path.expanduser("~"),
        "Desktop"
    )

    # -----------------------------------------------------
    # Desktop search
    # -----------------------------------------------------

    patterns = [

        r"^find (?:the )?file (.+?) on my desktop$",
        r"^find (.+?) on my desktop$",
        r"^where is (?:the )?file (.+?) on my desktop$",
        r"^where is (.+?) on my desktop$",
        r"^search my desktop for (.+)$",
        r"^search the desktop for (.+)$"

    ]

    for pattern in patterns:

        match = re.match(
            pattern,
            text
        )

        if match:

            filename = match.group(1).strip()

            if filename:

                return {
                    "tool": "search_files",
                    "args": [
                        desktop,
                        filename
                    ]
                }

    # -----------------------------------------------------
    # Generic file search
    # -----------------------------------------------------

    patterns = [

        # Find / where is with the word "file"
        r"^find (?:the )?file (.+)$",
        r"^where is (?:the )?file (.+)$",

        # Find / where is without the word "file"
        r"^find (.+)$",
        r"^where is (.+)$",

        # Search commands
        r"^search for (?:the )?file (.+)$",
        r"^search for (.+)$"

    ]

    for pattern in patterns:

        match = re.match(
            pattern,
            text
        )

        if match:

            filename = match.group(1).strip()

            if filename:

                return {
                    "tool": "search_files",
                    "args": [
                        os.getcwd(),
                        filename
                    ]
                }

    return None


# =========================================================
# ADVANCED TOOLS
# =========================================================

def understand_advanced_tools(text):

    home = os.path.expanduser("~")

    desktop = os.path.join(
        home,
        "Desktop"
    )


    # =====================================================
    # RESTART COMPUTER
    # =====================================================

    restart_phrases = [
        "restart my computer",
        "restart the computer",
        "restart computer",
        "reboot my computer",
        "reboot the computer",
        "reboot computer"
    ]

    if text in restart_phrases:
        return {
            "tool": "restart_computer",
            "args": []
        }


    # =====================================================
    # SHUT DOWN COMPUTER
    # =====================================================

    shutdown_phrases = [
        "shutdown my computer",
        "shutdown the computer",
        "shutdown computer",
        "shut down my computer",
        "shut down the computer",
        "shut down computer"
    ]

    if text in shutdown_phrases:
        return {
            "tool": "shutdown_computer",
            "args": []
        }
    # =====================================================
    # OPEN DESKTOP
    # =====================================================

    desktop_phrases = [

        "open my desktop",
        "open the desktop",
        "open desktop"

    ]

    for phrase in desktop_phrases:

        if phrase in text:

            return {
                "tool": "open_path",
                "args": [desktop]
            }


    # =====================================================
    # OPEN LILY FOLDER
    # =====================================================

    lily_folder_phrases = [

        "open lily folder",
        "open lily's folder",
        "open lily folder on my desktop"

    ]

    for phrase in lily_folder_phrases:

        if phrase in text:

            lily_folder = os.path.join(
                desktop,
                "Lily"
            )

            return {
                "tool": "open_path",
                "args": [lily_folder]
            }


    # =====================================================
    # LOCK COMPUTER
    # =====================================================

    lock_phrases = [

        "lock my computer",
        "lock the computer",
        "lock my pc",
        "lock the pc",
        "lock computer"

    ]

    for phrase in lock_phrases:

        if phrase in text:

            return {
                "tool": "lock_computer",
                "args": []
            }


    # =====================================================
    # DESKTOP FOLDER SIZE
    # =====================================================

    if (
        "how big is my desktop" in text
        or
        "how much space does my desktop use" in text
        or
        "how much space is my desktop using" in text
    ):

        return {
            "tool": "get_folder_size",
            "args": [desktop]
        }


    # =====================================================
    # CREATE TEXT FILE
    # =====================================================

    create_patterns = [

        r"^create (?:a )?text file called (.+)$",
        r"^create (?:a )?text file named (.+)$",
        r"^make (?:a )?text file called (.+)$",
        r"^make (?:a )?text file named (.+)$",
        r"^create (?:a )?file called (.+)$",
        r"^create (?:a )?file named (.+)$"

    ]

    for pattern in create_patterns:

        match = re.match(
            pattern,
            text
        )

        if match:

            filename = match.group(1).strip()

            if filename:

                return {
                    "tool": "create_text_file",
                    "args": [
                        os.path.join(
                            os.getcwd(),
                            filename
                        )
                    ]
                }


    # =====================================================
    # WRITE TEXT FILE
    # =====================================================

    write_patterns = [

        r'^write "(.+)" into (.+)$',
        r'^write "(.+)" to (.+)$',
        r'^write (.+) into (.+)$',
        r'^write (.+) to (.+)$'

    ]

    for pattern in write_patterns:

        match = re.match(
            pattern,
            text
        )

        if match:

            content = match.group(1).strip()
            filename = match.group(2).strip()

            return {
                "tool": "write_text_file",
                "args": [
                    os.path.join(
                        os.getcwd(),
                        filename
                    ),
                    content
                ]
            }


    # =====================================================
    # READ TEXT FILE
    # =====================================================

    read_patterns = [

        r"^read (?:the )?file (.+)$",
        r"^read (.+)$",
        r"^open and read (.+)$",
        r"^show me the contents of (.+)$",
        r"^show me what's inside (.+)$"

    ]

    for pattern in read_patterns:

        match = re.match(
            pattern,
            text
        )

        if match:

            filename = match.group(1).strip()

            if filename:

                return {
                    "tool": "read_text_file",
                    "args": [
                        os.path.join(
                            os.getcwd(),
                            filename
                        )
                    ]
                }


# =====================================================
# DELETE FILE OR FOLDER
# =====================================================

    delete_patterns = [
        r"^delete (?:the )?file (.+)$",
        r"^delete (.+)$",
        r"^remove (?:the )?file (.+)$",
        r"^remove (.+)$"
    ]

    for pattern in delete_patterns:

        match = re.match(
            pattern,
            text
        )

        if match:

            filename = match.group(1).strip()

            if filename:

                return {
                    "tool": "delete_path",
                    "args": [
                        os.path.join(
                            os.getcwd(),
                            filename
                        )
                    ]
                }
                
                
    return None

# =========================================================
# MAIN TOOL UNDERSTANDING FUNCTION
# =========================================================

def understand_tool(text):

    text = normalize_text(text)

    if not text:

        return None
    
    
    # =====================================================
    # FORCE DESKTOP TOOLS FIRST
    # =====================================================

    home = os.path.expanduser("~")
    desktop = os.path.join(home, "Desktop")


    # -----------------------------------------------------
    # OPEN DESKTOP
    # -----------------------------------------------------

    if text in [
        "open my desktop",
        "open the desktop",
        "open desktop"
    ]:

        return {
            "tool": "open_path",
            "args": [desktop]
        }


    # -----------------------------------------------------
    # DESKTOP FOLDER SIZE
    # -----------------------------------------------------

    if text in [
        "how big is my desktop",
        "how much space does my desktop use",
        "how much space is my desktop using",
        "how much space is my desktop taking",
        "how much storage does my desktop use",
        "how much storage is my desktop using"
    ]:

        return {
            "tool": "get_folder_size",
            "args": [desktop]
        }

    # -----------------------------------------------------
    # MEMORY PROTECTION
    # -----------------------------------------------------

    if looks_like_memory_request(text):

        return None


    # -----------------------------------------------------
    # SPECIFIC TOOLS FIRST
    # -----------------------------------------------------

    result = understand_advanced_tools(text)

    if result:
        return result
    
    
    result = understand_screenshot(text)

    if result:
        return result


    result = understand_backup(text)

    if result:
        return result


    result = understand_list_backups(text)

    if result:
        return result


    result = understand_list_files(text)

    if result:
        return result


    result = understand_search_files(text)

    if result:
        return result


    result = understand_launch(text)

    if result:
        return result


    result = understand_battery(text)

    if result:
        return result


    result = understand_network(text)

    if result:
        return result


    result = understand_datetime(text)

    if result:
        return result


    result = understand_user_info(text)

    if result:
        return result


    result = understand_cpu(text)

    if result:
        return result


    result = understand_memory(text)

    if result:
        return result


    result = understand_disk(text)

    if result:
        return result


    result = understand_system_info(text)

    if result:
        return result


    return None