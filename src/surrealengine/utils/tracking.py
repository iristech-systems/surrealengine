from typing import Any, Dict, List, Optional, TypeVar, Union, Iterable, Mapping, SupportsIndex

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

class TrackedObject:
    """Base class for tracked objects."""
    _parent: Any = None
    _field_name: Optional[str] = None

    def _set_parent(self, parent: Any, field_name: str) -> None:
        self._parent = parent
        self._field_name = field_name
        
    def _mark_changed(self) -> None:
        if self._parent and self._field_name and hasattr(self._parent, '_mark_field_changed'):
            self._parent._mark_field_changed(self._field_name)

class TrackedList(List[T], TrackedObject):
    """A list that notifies its parent of changes."""
    
    def __init__(self, iterable: Iterable[T] = (), parent: Any = None, field_name: Optional[str] = None):
        super().__init__(iterable)
        if parent and field_name:
            self._set_parent(parent, field_name)

    def __setitem__(self, index: Union[SupportsIndex, slice], value: Any) -> None:
        super().__setitem__(index, value)
        self._mark_changed()

    def __delitem__(self, index: Any) -> None:
        super().__delitem__(index)
        self._mark_changed()

    def append(self, value: T) -> None:
        super().append(value)
        self._mark_changed()

    def extend(self, iterable: Iterable[T]) -> None:
        super().extend(iterable)
        self._mark_changed()

    def insert(self, index: SupportsIndex, value: T) -> None:
        super().insert(index, value)
        self._mark_changed()

    def remove(self, value: T) -> None:
        super().remove(value)
        self._mark_changed()

    def pop(self, index: SupportsIndex = -1) -> T:
        result = super().pop(index)
        self._mark_changed()
        return result

    def clear(self) -> None:
        super().clear()
        self._mark_changed()
        
    def sort(self, *, key: Any = None, reverse: bool = False) -> None:
        super().sort(key=key, reverse=reverse)
        self._mark_changed()
        
    def reverse(self) -> None:
        super().reverse()
        self._mark_changed()

class TrackedDict(Dict[K, V], TrackedObject):
    """A dictionary that notifies its parent of changes."""

    def __init__(self, mapping: Union[Mapping[K, V], Iterable] = (), parent: Any = None, field_name: Optional[str] = None, **kwargs: Any):
        super().__init__(mapping, **kwargs)
        if parent and field_name:
            self._set_parent(parent, field_name)

    def __setitem__(self, key: K, value: V) -> None:
        super().__setitem__(key, value)
        self._mark_changed()

    def __delitem__(self, key: K) -> None:
        super().__delitem__(key)
        self._mark_changed()

    def update(self, *args: Any, **kwargs: Any) -> None:
        super().update(*args, **kwargs)
        self._mark_changed()

    def pop(self, key: K, default: Any = ...) -> Any: # type: ignore
        # Ellipsis is used for default sentinel to match dict.pop signature
        if default is ...:
            result = super().pop(key)
        else:
            result = super().pop(key, default)
        self._mark_changed()
        return result

    def popitem(self) -> Any:
        result = super().popitem()
        self._mark_changed()
        return result

    def clear(self) -> None:
        super().clear()
        self._mark_changed()
        
    def setdefault(self, key: K, default: Any = None) -> Any:
        if key not in self:
            self._mark_changed()
        return super().setdefault(key, default)
