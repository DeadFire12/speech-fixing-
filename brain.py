from __future__ import annotations
from intent_engine import understand


def think(user, learning=None):

    intent = understand(user)

    # =========================================
    # INTENT DETECTED
    # =========================================

    if intent["intent"] != "UNKNOWN":

        return {
            "type": "intent",
            "data": intent
        }


    # =========================================
    # DEFAULT RESPONSE PLAN
    # =========================================

    response_mode = "normal"
    difficulty = "normal"
    answer_length = "normal"
    technical_terms = "normal"


    # =========================================
    # CHECK LEARNED PREFERENCES
    # =========================================

    if learning:

        for key, data in learning.items():

            value = data.get(
                "value",
                ""
            ).lower()


            # ---------------------------------
            # SIMPLE EXPLANATIONS
            # ---------------------------------

            if "prefer simple explanations" in value:

                response_mode = "simple"
                difficulty = "beginner"
                answer_length = "short"
                technical_terms = "low"

                break


            # ---------------------------------
            # DETAILED EXPLANATIONS
            # ---------------------------------

            elif "prefer detailed explanations" in value:

                response_mode = "detailed"
                difficulty = "normal"
                answer_length = "long"
                technical_terms = "normal"

                break


    # =========================================
    # RETURN COMPLETE RESPONSE PLAN
    # =========================================

    return {

        "type": "chat",

        "data": user,

        "response_mode": response_mode,

        "difficulty": difficulty,

        "answer_length": answer_length,

        "technical_terms": technical_terms

    }