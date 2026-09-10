"""Generic compatibility objects for legacy Telethon type imports.

Runtime Telegram objects are represented by lightweight Python objects. Unknown
Telethon type names are generated on demand so the application does not need
MTProto schema classes or API_ID/API_HASH.
"""
class _TLObject:
    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)
        if args:
            self.args = args

    def to_dict(self):
        return dict(self.__dict__)

def __getattr__(name):
    cls = type(name, (_TLObject,), {})
    globals()[name] = cls
    return cls
