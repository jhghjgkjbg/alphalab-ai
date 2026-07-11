from collections.abc import Awaitable, Callable
from typing import Any, TypeAlias


EventHandler: TypeAlias = Callable[[Any], Awaitable[None]]
