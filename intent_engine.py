from __future__ import annotations
import re

from context_engine import (
    detect_dislike,
    detect_used_to_like
)


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_text(text):

    text = text.lower().strip()

    text = text.replace(
        "’",
        "'"
    )

    text = re.sub(
        r"[?!.,]+",
        "",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text



def normalize_key(key):

    key = key.lower().strip()

    key = re.sub(
        r"[?!.,]+$",
        "",
        key
    )


    prefixes = [

        "my ",
        "the ",
        "what ",
        "which "

    ]


    changed = True

    while changed:

        changed = False

        for prefix in prefixes:

            if key.startswith(prefix):

                key = key[
                    len(prefix):
                ].strip()

                changed = True

                break


    return key



def clean_value(value):

    value = value.strip()

    value = value.strip(
        "\"'"
    )

    value = value.rstrip(
        ".,!?"
    )


    if re.match(
        r"^it's\s+",
        value,
        re.IGNORECASE
    ):

        value = re.sub(
            r"^it's\s+",
            "",
            value,
            flags=re.IGNORECASE
        )


    elif re.match(
        r"^it is\s+",
        value,
        re.IGNORECASE
    ):

        value = re.sub(
            r"^it is\s+",
            "",
            value,
            flags=re.IGNORECASE
        )


    return value.strip()



# =========================================================
# MEMORY MANAGER
# =========================================================

def memory_manager_intent(text):

    text = normalize_text(
        text
    )


    list_patterns = [

    r"what do you remember",

    r"what do you remember about me",

    r"what memories do you have",

    r"show me my memories",
    
    r"show my memories",

    r"show memory",

    r"show everything",

    r"tell me everything you know",

    r"what information do you have about me",

    r"list my memories",

    r"what have you remembered about me",

    r"tell me what you remember",

    r"what have you stored",

    r"what do you know about me"

    ]


    for pattern in list_patterns:

        if re.fullmatch(
            pattern,
            text
        ):

            return {

                "intent":
                    "LIST_MEMORIES",

                "key":
                    None,

                "value":
                    None

            }


    # =========================================
    # SHOW CATEGORY
    # =========================================

    category_patterns = {

        "preferences": [

            r"show my preferences",

            r"what are my preferences"

        ],


        "likes": [

            r"show my likes",

            r"Show my like"

            r"what do i like",

            r"what are my likes"

        ],


        "personal": [

            r"show my personal information",

            r"what personal information do you know"

        ],


        "history": [

            r"show my history"

        ]

    }


    for category, patterns in category_patterns.items():

        for pattern in patterns:

            if re.fullmatch(
                pattern,
                text
            ):

                return {

                    "intent":
                        "SHOW_CATEGORY",

                    "key":
                        category,

                    "value":
                        None

                }
                
                
    count_patterns = [

        r"how many memories do you have",

        r"how many memories do you remember",

        r"how much do you remember about me"

    ]


    for pattern in count_patterns:

        if re.fullmatch(
            pattern,
            text
        ):

            return {

                "intent":
                    "COUNT_MEMORIES",

                "key":
                    None,

                "value":
                    None

            }



    clear_patterns = [

        r"forget everything",

        r"forget everything you know about me",

        r"forget all my memories",

        r"clear all memories",

        r"delete all memories",

        r"erase everything you know about me"

    ]


    for pattern in clear_patterns:

        if re.fullmatch(
            pattern,
            text
        ):

            return {

                "intent":
                    "CLEAR_ALL_MEMORIES",

                "key":
                    None,

                "value":
                    None

            }


    return None



# =========================================================
# CONTEXT INTENTS
# =========================================================

def contextual_intent(text):

    if detect_dislike(text):

        return {

            "intent":
                "CONTEXTUAL_DISLIKE",

            "key":
                None,

            "value":
                None

        }


    if detect_used_to_like(text):

        return {

            "intent":
                "CONTEXTUAL_USED_TO_LIKE",

            "key":
                None,

            "value":
                None

        }


    return None



# =========================================================
# READ MEMORY
# =========================================================

def read_memory_intent(text):

    text = normalize_text(
        text
    )


    # =====================================================
    # DISLIKE MEMORY
    # =====================================================

    patterns = [

        r"what (?:food|foods) do i dislike",

        r"what (?:food|foods) don't i like",

        r"what (?:food|foods) do i not like",

        r"what do i dislike",

        r"what don't i like",

        r"what do i not like"

    ]


    for pattern in patterns:

        if re.fullmatch(
            pattern,
            text
        ):

            return {
                "intent":
                    "READ_MEMORY",

                "key":
                    "dislike food",

                "value":
                    None
            }


    # =====================================================
    # USED TO LIKE MEMORY
    # =====================================================

    patterns = [

        r"what did i used to like",

        r"what did i use to like",

        r"what (?:food|foods) did i used to like",

        r"what (?:food|foods) did i use to like"

    ]


    for pattern in patterns:

        if re.fullmatch(
            pattern,
            text
        ):

            return {
                "intent":
                    "READ_MEMORY",

                "key":
                    "used to like food",

                "value":
                    None
            }


    # =====================================================
    # NORMAL MEMORY QUESTIONS
    # =====================================================

    patterns = [

        r"what is my (.+)",

        r"what's my (.+)",

        r"do you remember my (.+)",

        r"remind me what my (.+?) is",

        r"remind me of my (.+)"

    ]


    for pattern in patterns:

        match = re.match(
            pattern,
            text
        )


        if match:

            key = normalize_key(
                match.group(1)
            )


            return {
                "intent":
                    "READ_MEMORY",

                "key":
                    key,

                "value":
                    None
            }


    # =====================================================
    # FAVORITE THING QUESTIONS
    # =====================================================

    match = re.match(
        r"what (.+) do i (?:like|love|prefer)",
        text
    )


    if match:

        category = normalize_key(
            match.group(1)
        )


        return {
            "intent":
                "READ_MEMORY",

            "key":
                "favorite " + category,

            "value":
                None
        }


    return None

# =========================================================
# UPDATE MEMORY
# =========================================================

def update_memory_intent(text):

    text = normalize_text(text)


    text = re.sub(
        r"^actually,?\s+",
        "",
        text,
        flags=re.IGNORECASE
    )


    patterns = [

    r"my (.+?) is (.+?) now",

    r"my (.+?) changed to (.+)",

    r"i changed my (.+?) to (.+)",

    r"change my (.+?) to (.+)"

    ]


    for pattern in patterns:

        match = re.match(
            pattern,
            text,
            re.IGNORECASE
        )


        if match:

            return {

                "intent":
                    "UPDATE_MEMORY",

                "key":
                    normalize_key(
                        match.group(1)
                    ),

                "value":
                    clean_value(
                        match.group(2)
                    )

            }


    return None



# =========================================================
# SAVE MEMORY
# =========================================================

def save_memory_intent(text):
    
    text = normalize_text(text)

    patterns = [

        # -----------------------------------------
        # "remember my brother's name is Moein"
        # "remember that my favorite game is Minecraft"
        # -----------------------------------------
        r"remember(?: that)? my (.+?) is (.+)",

        # -----------------------------------------
        # "my brother's name is Moein"
        # "my favorite game is Minecraft"
        # -----------------------------------------
        r"my (.+?) is (.+)",

        # -----------------------------------------
        # "I live in Baku"
        # -----------------------------------------
        r"i live in (.+)",

        # -----------------------------------------
        # "I am from Azerbaijan"
        # -----------------------------------------
        r"i am from (.+)",

        # -----------------------------------------
        # "I'm from Azerbaijan"
        # -----------------------------------------
        r"i'm from (.+)",

        # -----------------------------------------
        # "My name is Kiyoto"
        # -----------------------------------------
        r"my name is (.+)",

        # -----------------------------------------
        # "I am 25 years old"
        # -----------------------------------------
        r"i am (\d+) years old",

        # -----------------------------------------
        # "I'm 25 years old"
        # -----------------------------------------
        r"i'm (\d+) years old",

        # -----------------------------------------
        # "My birthday is June 5"
        # -----------------------------------------
        r"my birthday is (.+)"
    ]


    for pattern in patterns:

        match = re.fullmatch(
            pattern,
            text,
            re.IGNORECASE
        )

        if not match:
            continue


        # =========================================
        # SPECIAL NATURAL SENTENCES
        # =========================================

        if pattern == r"i live in (.+)":

            return {
                "intent": "SAVE_MEMORY",
                "key": "location",
                "value": clean_value(match.group(1))
            }


        if pattern in [
            r"i am from (.+)",
            r"i'm from (.+)"
        ]:

            return {
                "intent": "SAVE_MEMORY",
                "key": "country",
                "value": clean_value(match.group(1))
            }


        if pattern == r"my name is (.+)":

            return {
                "intent": "SAVE_MEMORY",
                "key": "name",
                "value": clean_value(match.group(1))
            }


        if pattern in [
            r"i am (\d+) years old",
            r"i'm (\d+) years old"
        ]:

            return {
                "intent": "SAVE_MEMORY",
                "key": "age",
                "value": clean_value(match.group(1))
            }


        if pattern == r"my birthday is (.+)":

            return {
                "intent": "SAVE_MEMORY",
                "key": "birthday",
                "value": clean_value(match.group(1))
            }


        # =========================================
        # NORMAL "MY X IS Y" MEMORY
        # =========================================

        return {
            "intent": "SAVE_MEMORY",

            "key": normalize_key(
                match.group(1)
            ),

            "value": clean_value(
                match.group(2)
            )
        }


    return None



# =========================================================
# DELETE MEMORY
# =========================================================

def delete_memory_intent(text):

    text = normalize_text(
        text
    )


    match = re.match(
        r"forget my (.+)",
        text
    )


    if match:

        return {

            "intent":
                "DELETE_MEMORY",

            "key":
                normalize_key(
                    match.group(1)
                ),

            "value":
                None

        }


    return None


# =========================================================
# GENERAL LIKES
# =========================================================

def like_intent(text):

    text = normalize_text(text)


    patterns = [

        r"i like (.+)",

        r"i love (.+)",

        r"i enjoy (.+)"

    ]


    for pattern in patterns:

        match = re.fullmatch(
            pattern,
            text
        )


        if match:

            value = clean_value(
                match.group(1)
            )


            return {

                "intent":
                    "SAVE_LIKE",

                "key":
                    "like " + value,

                "value":
                    value

            }


    return None


# =========================================================
# USER STYLE PREFERENCES
# =========================================================

def preference_intent(text):
    
    text = normalize_text(text)


    simple_patterns = [

        r"i like simple explanations",

        r"i prefer simple explanations",

        r"i want simple explanations",

        r"i want simple answers",

        r"i want simple answer",

        r"explain things simply",

        r"explain it simply",

        r"make it simple",

        "keep explanations simple",

            r"keep it simple"

    ]


    detailed_patterns = [

        r"i like detailed explanations",

        r"i prefer detailed explanations",

        r"i want detailed explanations",

        r"give me detailed explanations"

    ]


    for pattern in simple_patterns:

        if re.fullmatch(pattern, text):

            return {

                "intent":
                    "SAVE_PREFERENCE",

                "key":
                    "explanation style",

                "value":
                    "simple"

            }



    for pattern in detailed_patterns:

        if re.fullmatch(pattern, text):

            return {

                "intent":
                    "SAVE_PREFERENCE",

                "key":
                    "explanation style",

                "value":
                    "detailed"

            }



    return None


# =========================================================
# GOAL INTENTS
# =========================================================

def goal_intent(text):

    text = normalize_text(text)


    if re.fullmatch(
        r"show my goals",
        text
    ):

        return {
            "intent": "LIST_GOALS",
            "key": None,
            "value": None
        }


    match = re.match(
        r"(?:my goal is|i want to|i want|i plan to) (.+)",
        text
    )


    if match:

        return {
            "intent": "ADD_GOAL",
            "key": None,
            "value": clean_value(
                match.group(1)
            )
        }


    match = re.match(
        r"(?:complete|finish|done with) (.+)",
        text
    )


    if match:

        return {
            "intent": "COMPLETE_GOAL",
            "key": None,
            "value": clean_value(
                match.group(1)
            )
        }


    return None


# =========================================================
# MAIN ENGINE
# =========================================================

def understand(text):
    
    result = memory_manager_intent(text)

    if result:
        return result

    
    result = goal_intent(text)

    if result:
            return result
    
    result = preference_intent(text)

    if result:
        return result
    
    
    result = like_intent(text)

    if result:
        return result
    
    
    result = delete_memory_intent(text)

    if result:
        return result
    

    result = contextual_intent(text)

    if result:
        return result


    result = update_memory_intent(text)

    if result:
        return result


    result = read_memory_intent(text)

    if result:
        return result


    result = save_memory_intent(text)

    if result:
        return result


    return {

        "intent":
            "UNKNOWN",

        "key":
            None,

        "value":
            None

    }


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":
    
    tests = [

        # Personality preference tests
        "I like simple explanations",

        "I prefer detailed explanations",

        "I want simple answers",


        # Normal memory tests
        "My favorite game is Minecraft",

        "What is my favorite game",


        # Context memory tests
        "I don't like Minecraft anymore",

        "I used to like Minecraft",


        # Delete test
        "Forget my favorite game",
        
        "I like pizza",

        "I love programming",

        "I enjoy music",
        
        "My brother's name is Moein",

        "Remember my brother's name is Moein",

        "My sister's name is Sara",

        "My favorite game is Minecraft",

        "I live in Baku",

        "I am from Azerbaijan",

        "My name is Kiyoto",

        "I am 25 years old",

        "My birthday is June 5"
    ]


    for test in tests:

        print()

        print(
            "YOU:",
            test
        )

        print(
            understand(test)
        )