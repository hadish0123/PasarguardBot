from __future__ import annotations

class Message:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    async def reply(self, *args, **kwargs):
        return await self._client.send_message(entity=self.chat_id, message=args[0] if args else kwargs.pop("message", ""), **kwargs)
    async def respond(self, *args, **kwargs):
        return await self.reply(*args, **kwargs)
    async def edit(self, text=None, **kwargs):
        return await self._client.edit_message(self.chat_id, self.id, text, **kwargs)
    async def delete(self, *args, **kwargs):
        return await self._client.delete_messages(self.chat_id, [self.id])
    async def download_media(self, *args, **kwargs):
        return await self._client.download_media(self, *args, **kwargs)
