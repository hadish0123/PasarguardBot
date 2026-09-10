class MessageNotModifiedError(Exception):
    pass
class MessageIdInvalidError(Exception):
    pass
class UserNotParticipantError(Exception):
    pass
class ChatAdminRequiredError(Exception):
    pass
class FloodWaitError(Exception):
    def __init__(self, seconds=1):
        self.seconds = seconds
        super().__init__(f"Flood wait: {seconds}s")
