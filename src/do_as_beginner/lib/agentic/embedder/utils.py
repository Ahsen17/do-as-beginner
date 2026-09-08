from collections.abc import Iterable
from itertools import islice


def iter_batch[T](iterable: Iterable[T], size: int) -> Iterable[list[T]]:

    source_iter = iter(iterable)
    while source_iter:
        b = list(islice(source_iter, size))
        if len(b) == 0:
            break
        yield b
