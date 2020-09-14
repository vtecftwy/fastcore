# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/03_dispatch.ipynb (unless otherwise specified).

__all__ = ['type_hints', 'anno_ret', 'cmp_instance', 'TypeDispatch', 'DispatchReg', 'typedispatch', 'cast',
           'retain_meta', 'default_set_meta', 'retain_type', 'retain_types', 'explode_types']

# Cell
from .imports import *
from .foundation import *
from .utils import *
from collections import defaultdict

# Cell
def type_hints(f):
    "Same as `typing.get_type_hints` but returns `{}` if not allowed type"
    return typing.get_type_hints(f) if isinstance(f, typing._allowed_types) else {}

# Cell
def anno_ret(func):
    "Get the return annotation of `func`"
    if not func: return None
    ann = type_hints(func)
    if not ann: return None
    return ann.get('return')

# Cell
cmp_instance = functools.cmp_to_key(lambda a,b: 0 if a==b else 1 if issubclass(a,b) else -1)

# Cell
def _chk_defaults(f, ann):
    pass
# Implementation removed until we can figure out how to do this without `inspect` module
#     try: # Some callables don't have signatures, so ignore those errors
#         params = list(inspect.signature(f).parameters.values())[:min(len(ann),2)]
#         if any(p.default!=inspect.Parameter.empty for p in params):
#             warn(f"{f.__name__} has default params. These will be ignored.")
#     except ValueError: pass

# Cell
def _p2_anno(f):
    "Get the 1st 2 annotations of `f`, defaulting to `object`"
    hints = type_hints(f)
    ann = [o for n,o in hints.items() if n!='return']
    if callable(f): _chk_defaults(f, ann)
    while len(ann)<2: ann.append(object)
    return ann[:2]

# Cell
class _TypeDict:
    def __init__(self): self.d,self.cache = {},{}

    def _reset(self):
        self.d = {k:self.d[k] for k in sorted(self.d, key=cmp_instance, reverse=True)}
        self.cache = {}

    def add(self, t, f):
        "Add type `t` and function `f`"
        if not isinstance(t,tuple): t=tuple(L(t))
        for t_ in t: self.d[t_] = f
        self._reset()

    def all_matches(self, k):
        "Find first matching type that is a super-class of `k`"
        if k not in self.cache:
            types = [f for f in self.d if k==f or (isinstance(k,type) and issubclass(k,f))]
            self.cache[k] = [self.d[o] for o in types]
        return self.cache[k]

    def __getitem__(self, k):
        "Find first matching type that is a super-class of `k`"
        res = self.all_matches(k)
        return res[0] if len(res) else None

    def __repr__(self): return self.d.__repr__()
    def first(self): return first(self.d.values())

# Cell
@docs
class TypeDispatch:
    "Dictionary-like object; `__getitem__` matches keys of types using `issubclass`"
    def __init__(self, funcs=(), bases=()):
        self.funcs,self.bases = _TypeDict(),L(bases).filter(is_not(None))
        for o in L(funcs): self.add(o)
        self.inst = None

    def add(self, f):
        "Add type `t` and function `f`"
        a0,a1 = _p2_anno(f)
        t = self.funcs.d.get(a0)
        if t is None:
            t = _TypeDict()
            self.funcs.add(a0, t)
        t.add(a1, f)

    def first(self): return self.funcs.first().first()
    def returns(self, x): return anno_ret(self[type(x)])
    def returns_none(self, x):
        r = anno_ret(self[type(x)])
        return r if r == NoneType else None

    def _attname(self,k): return getattr(k,'__name__',str(k))
    def __repr__(self):
        r = [f'({self._attname(k)},{self._attname(l)}) -> {getattr(v, "__name__", v.__class__.__name__)}'
             for k in self.funcs.d for l,v in self.funcs[k].d.items()]
        r = r + [o.__repr__() for o in self.bases]
        return '\n'.join(r)

    def __call__(self, *args, **kwargs):
        ts = L(args).map(type)[:2]
        f = self[tuple(ts)]
        if not f: return args[0]
        if self.inst is not None: f = MethodType(f, self.inst)
        return f(*args, **kwargs)

    def __get__(self, inst, owner):
        self.inst = inst
        return self

    def __getitem__(self, k):
        "Find first matching type that is a super-class of `k`"
        k = L(k)
        while len(k)<2: k.append(object)
        r = self.funcs.all_matches(k[0])
        for t in r:
            o = t[k[1]]
            if o is not None: return o
        for base in self.bases:
            res = base[k]
            if res is not None: return res
        return None

    _docs = dict(first="Get first function in ordered dict of type:func.",
                 returns="Get the return type of annotation of `x`.",
                 returns_none="Returns `None` if return type annotation is `None` or `NoneType`.")

# Cell
class DispatchReg:
    "A global registry for `TypeDispatch` objects keyed by function name"
    def __init__(self): self.d = defaultdict(TypeDispatch)
    def __call__(self, f):
        nm = f'{f.__qualname__}'
        self.d[nm].add(f)
        return self.d[nm]

typedispatch = DispatchReg()

# Cell
#nbdev_comment _all_=['cast']

# Cell
def retain_meta(x, res, copy_meta=False):
    "Call `res.set_meta(x)`, if it exists"
    if hasattr(res,'set_meta'): res.set_meta(x, copy_meta=copy_meta)
    return res

# Cell
def default_set_meta(self, x, copy_meta=False):
    "Copy over `_meta` from `x` to `res`, if it's missing"
    if hasattr(x, '_meta') and not hasattr(self, '_meta'):
        meta = x._meta
        if copy_meta: meta = copy(meta)
        self._meta = meta
    return self

# Cell
@typedispatch
def cast(x, typ):
    "cast `x` to type `typ` (may also change `x` inplace)"
    res = typ._before_cast(x) if hasattr(typ, '_before_cast') else x
    if isinstance_str(res, 'ndarray'): res = res.view(typ)
    elif hasattr(res, 'as_subclass'): res = res.as_subclass(typ)
    else:
        try: res.__class__ = typ
        except: res = typ(res)
    return retain_meta(x, res)

# Cell
def retain_type(new, old=None, typ=None, copy_meta=False):
    "Cast `new` to type of `old` or `typ` if it's a superclass"
    # e.g. old is TensorImage, new is Tensor - if not subclass then do nothing
    if new is None: return
    assert old is not None or typ is not None
    if typ is None:
        if not isinstance(old, type(new)): return new
        typ = old if isinstance(old,type) else type(old)
    # Do nothing the new type is already an instance of requested type (i.e. same type)
    if typ==NoneType or isinstance(new, typ): return new
    return retain_meta(old, cast(new, typ), copy_meta=copy_meta)

# Cell
def retain_types(new, old=None, typs=None):
    "Cast each item of `new` to type of matching item in `old` if it's a superclass"
    if not is_listy(new): return retain_type(new, old, typs)
    if typs is not None:
        if isinstance(typs, dict):
            t = first(typs.keys())
            typs = typs[t]
        else: t,typs = typs,None
    else: t = type(old) if old is not None and isinstance(old,type(new)) else type(new)
    return t(L(new, old, typs).map_zip(retain_types, cycled=True))

# Cell
def explode_types(o):
    "Return the type of `o`, potentially in nested dictionaries for thing that are listy"
    if not is_listy(o): return type(o)
    return {type(o): [explode_types(o_) for o_ in o]}