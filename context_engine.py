from __future__ import annotations
import re


# =========================================================
# CURRENT CONVERSATION CONTEXT
# =========================================================

last_key = None
last_value = None


# =========================================================
# SET CONTEXT
# =========================================================

def set_context(key, value):
    """
    Store the latest important conversation subject.
    """

    global last_key
    global last_value

    if key is None or value is None:
        return

    last_key = key
    last_value = value



# =========================================================
# CLEAR CONTEXT
# =========================================================

def clear_context():

    global last_key
    global last_value

    last_key = None
    last_value = None



# =========================================================
# GET CONTEXT
# =========================================================

def get_context():

    return {

        "key": last_key,

        "value": last_value

    }



# =========================================================
# HAS CONTEXT
# =========================================================

def has_context():

    return (

        last_key is not None

        and last_value is not None

    )



# =========================================================
# NORMALIZE TEXT
# =========================================================

def normalize_text(text):

    text = text.lower().strip()

    text = text.replace(
        "’",
        "'"
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text



# =========================================================
# REFERENCE DETECTION
# =========================================================

def contains_reference(text):

    """
    Detect indirect references.

    Examples:

    I don't like it anymore.
    I hate that.
    I used to like this.
    """

    text = normalize_text(
        text
    )


    references = [

        r"\bit\b",

        r"\bthat\b",

        r"\bthis\b"

    ]


    for pattern in references:

        if re.search(
            pattern,
            text
        ):

            return True


    return False



# =========================================================
# RESOLVE REFERENCE
# =========================================================

def resolve_reference():

    if not has_context():

        return None


    return {

        "key": last_key,

        "value": last_value

    }



# =========================================================
# DISLIKE DETECTION
# =========================================================

def detect_dislike(text):

    """
    Detect when the user stops liking something.

    Examples:

    I don't like it anymore.
    I dont like that.
    I do not like this now.
    I hate it.
    """

    text = normalize_text(
        text
    )


    patterns = [

    r"^i (don't|dont|do not) like .+?( anymore| now)?$",

    r"^i hate .+?( now)?$",

    r"^i no longer like .+$",

    r"^i stopped liking .+$"

]


    for pattern in patterns:

        if re.fullmatch(
            pattern,
            text
        ):

            return True


    return False



# =========================================================
# USED TO LIKE DETECTION
# =========================================================

def detect_used_to_like(text):

    """
    Detect past likes.

    Examples:

    I used to like it.
    I used to love that.
    """

    text = normalize_text(
        text
    )


    patterns = [

    r"^i used to like .+$",

    r"^i used to love .+$"

]


    for pattern in patterns:

        if re.fullmatch(
            pattern,
            text
        ):

            return True


    return False



# =========================================================
# CONTEXT UNDERSTANDING
# =========================================================

def understand_context(text):

    if not has_context():

        return {

            "has_context": False,

            "key": None,

            "value": None

        }


    return {

        "has_context":
            contains_reference(text),

        "key":
            last_key,

        "value":
            last_value

    }



# =========================================================
# TEST AREA
# =========================================================

if __name__ == "__main__":


    set_context(
        "favorite game",
        "Minecraft"
    )


    tests = [

        "I don't like it anymore.",

        "I dont like that.",

        "I hate it now.",

        "I used to like it.",

        "Tell me about that."

    ]


    for test in tests:

        print()

        print(
            "YOU:",
            test
        )


        print(
            "REFERENCE:",
            contains_reference(test)
        )


        print(
            "DISLIKE:",
            detect_dislike(test)
        )


        print(
            "USED TO LIKE:",
            detect_used_to_like(test)
        )


        print(
            "CONTEXT:",
            understand_context(test)
        )