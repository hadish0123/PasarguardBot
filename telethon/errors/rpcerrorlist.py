class RPCError(Exception):
    pass

class MessageNotModifiedError(RPCError):
    pass
class MessageIdInvalidError(RPCError):
    pass
class UserNotParticipantError(RPCError):
    pass
class ChatAdminRequiredError(RPCError):
    pass
class FloodWaitError(RPCError):
    def __init__(self, seconds=1):
        self.seconds = seconds
        super().__init__(f"Flood wait: {seconds}s")
