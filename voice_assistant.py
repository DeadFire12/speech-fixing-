from __future__ import annotations
# =========================================================
# LILY VOICE ASSISTANT
# =========================================================

class VoiceAssistant:

    def __init__(
        self,
        listen_function,
        speak_function
    ):

        self.listen = listen_function

        self.speak = speak_function

        self.running = False


    # =====================================================
    # START VOICE MODE
    # =====================================================

    def start(self):

        self.running = True

        self.speak(
            "Voice mode activated."
        )

        while self.running:

            try:

                text = self.listen()

            except Exception:

                self.speak(
                    "I couldn't hear you."
                )

                continue


            if not text:

                continue


            text = str(
                text
            ).strip()


            lower = text.lower()


            # =================================================
            # EXIT VOICE MODE
            # =================================================

            if (
                lower == "exit voice"
                or
                lower == "stop listening"
                or
                lower == "voice mode off"
                or
                lower == "go to sleep"
            ):

                self.speak(
                    "Voice mode deactivated."
                )

                self.running = False

                break


            # =================================================
            # SEND COMMAND BACK TO LILY
            # =================================================

            yield text