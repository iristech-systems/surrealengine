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


def handler(event):
    """Signal decorator to allow use of callback functions as class decorators."""
    def decorator(fn):
        def apply(cls):
            event.connect(fn, sender=cls)
            return cls

        fn.apply = apply
        return fn

    return decorator