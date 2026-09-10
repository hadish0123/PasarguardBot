class _Request:
    def __init__(self,*args,**kwargs): self.__dict__.update(kwargs); self.args=args
def __getattr__(name):
    cls=type(name,(_Request,),{}); globals()[name]=cls; return cls
