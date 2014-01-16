import functools
import inspect
from asyncio import futures
from .log import logger

# If you set _DEBUG to true, @coroutine will wrap the resulting
# generator objects in a CoroWrapper instance (defined below).  That
# instance will log a message when the generator is never iterated
# over, which may happen when you forget to use "yield from" with a
# coroutine call.  Note that the value of the _DEBUG flag is taken
# when the decorator is used, so to be of any use it must be set
# before you define your coroutines.  A downside of using this feature
# is that tracebacks show entries for the CoroWrapper.__next__ method
# when _DEBUG is true.
_DEBUG = False


class Return(StopIteration):
    def __init__(self, *value):
        StopIteration.__init__(self)
        if not value:
            self.value = None
        elif len(value) == 1:
            self.value = value[0]
        else:
            self.value = value
        self.raised = False

    def __del__(self):
        if not self.raised:
            logger.error('Return(%r) used without raise', self.value)


class CoroWrapper(object):
    """Wrapper for coroutine in _DEBUG mode."""

    __slot__ = ['gen', 'func']

    def __init__(self, gen, func):
        assert inspect.isgenerator(gen), gen
        self.gen = gen
        self.func = func

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.gen)
    next = __next__

    def send(self, value):
        return self.gen.send(value)

    def throw(self, exc):
        return self.gen.throw(exc)

    def close(self):
        return self.gen.close()

    def __del__(self):
        frame = self.gen.gi_frame
        if frame is not None and frame.f_lasti == -1:
            func = self.func
            code = func.__code__
            filename = code.co_filename
            lineno = code.co_firstlineno
            logger.error(
                'Coroutine %r defined at %s:%s was never yielded from',
                func.__name__, filename, lineno)


def coroutine(func):
    """Decorator to mark coroutines.

    If the coroutine is not yielded from before it is destroyed,
    an error message is logged.
    """
    if inspect.isgeneratorfunction(func):
        coro = func
    else:
        @functools.wraps(func)
        def coro(*args, **kw):
            res = func(*args, **kw)
            if isinstance(res, futures.Future) or inspect.isgenerator(res):
                res = yield res
            raise Return(res)

    if not _DEBUG:
        wrapper = coro
    else:
        @functools.wraps(func)
        def wrapper(*args, **kwds):
            w = CoroWrapper(coro(*args, **kwds), func)
            w.__name__ = coro.__name__
            w.__doc__ = coro.__doc__
            return w

    wrapper._is_coroutine = True  # For iscoroutinefunction().
    return wrapper


def iscoroutinefunction(func):
    """Return True if func is a decorated coroutine function."""
    return getattr(func, '_is_coroutine', False)


def iscoroutine(obj):
    """Return True if obj is a coroutine object."""
    return isinstance(obj, CoroWrapper) or inspect.isgenerator(obj)

