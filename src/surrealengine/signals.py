"""
Signal support for SurrealEngine.

This module provides signal support for SurrealEngine using the blinker library.
Signal support is optional and requires the blinker library to be installed.
"""

try:
    from blinker import signal
    SIGNAL_SUPPORT = True
except ImportError:
    SIGNAL_SUPPORT = False

    def signal(*args, **kwargs):
        """Dummy signal function when blinker is not available."""
        class DummySignal:
            def connect(self, *args, **kwargs):
                pass
            
            def send(self, *args, **kwargs):
                pass
        
        return DummySignal()


# Document signals
pre_init = signal('pre_init')
post_init = signal('post_init')
pre_save = signal('pre_save')
pre_save_post_validation = signal('pre_save_post_validation')
post_save = signal('post_save')
pre_delete = signal('pre_delete')
post_delete = signal('post_delete')
pre_bulk_insert = signal('pre_bulk_insert')
post_bulk_insert = signal('post_bulk_insert')

# Field signals
pre_validate = signal('pre_validate')
post_validate = signal('post_validate')
pre_to_db = signal('pre_to_db')
post_to_db = signal('post_to_db')
pre_from_db = signal('pre_from_db')
post_from_db = signal('post_from_db')


def receiver(signal, **kwargs):
    """Decorator to register a signal receiver.
    
    Can be used on standalone functions (must specify sender) or methods within a
    Document class (sender inferred from class).
    
    Args:
        signal: The signal to connect to
        **kwargs: Additional arguments for signal.connect (e.g. sender)
        
    Example:
        @receiver(pre_save, sender=User)
        def my_handler(sender, document, **kwargs): ...
        
        class User(Document):
            @receiver(pre_save)
            def on_save(self, **kwargs): ...
    """
    def decorator(fn):
        if 'sender' in kwargs:
            # Connect immediately if sender is known
            signal.connect(fn, **kwargs)
        else:
            # Mark for connection by DocumentMetaclass
            fn._signal_receiver = (signal, kwargs)
        return fn
    return decorator

# Decorator shortcuts (implicit receiver)
# These allow @pre_save usage inside Document classes
def _make_decorator(sig):
    def decorator(fn=None, **kwargs):
        # Support both @pre_save and @pre_save(sender=...) syntax
        if fn is None:
            return receiver(sig, **kwargs)
        if callable(fn):
            return receiver(sig, **kwargs)(fn)
        # If fn is not callable and not None (e.g. usage as @pre_save during definition?), unlikely.
        return receiver(sig, **kwargs)(fn)
    return decorator

# Monkey patch signal objects to be callable as decorators? 
# Or just expose function names matching signals?
# User asked for @pre_save. The variable `pre_save` is currently a Signal object.
# To allow @pre_save, pre_save must be callable. Blinkers signals ARE callable?
# No, blinker Signal is not a decorator.
# I need to rename the actual signals or provide different names for decorators.
# Convention: signals are objects. Decorators are usually `receiver`.
# But user example: "@pre_save".
# I should wrap the signals themselves?
# Or maybe expose `on_pre_save` decorator?
# OR: Override the module globals?
# Actually, I can overwrite `pre_save` with an object that acts as BOTH a Signal AND a decorator.
# That's cool but magic.
# Simplest: `from surrealengine.signals import pre_save` -> Signal.
# `from surrealengine.signals import receiver`.
# If I change `pre_save` to be a Proxy that supports `__call__` as decorator...

class SignalProxy:
    def __init__(self, signal):
        self.signal = signal
    
    def __getattr__(self, name):
        return getattr(self.signal, name)
        
    def connect(self, *args, **kw):
        return self.signal.connect(*args, **kw)
        
    def send(self, *args, **kw):
        return self.signal.send(*args, **kw)
        
    def __call__(self, fn=None, **kwargs):
        # Acts as decorator
        return _make_decorator(self.signal)(fn, **kwargs)
        
# Re-wrap signals
if SIGNAL_SUPPORT:
    pre_init = SignalProxy(pre_init)
    post_init = SignalProxy(post_init)
    pre_save = SignalProxy(pre_save)
    post_save = SignalProxy(post_save)
    pre_delete = SignalProxy(pre_delete)
    post_delete = SignalProxy(post_delete)
    pre_validate = SignalProxy(pre_validate)
    # ... and others