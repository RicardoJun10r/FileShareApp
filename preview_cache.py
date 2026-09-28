"""LRU limitado pelo tamanho dos objetos Python, além do número de entradas."""
from collections import OrderedDict
from sys import getsizeof


def memory_size(value):
    if isinstance(value, dict):
        return getsizeof(value) + sum(memory_size(k) + memory_size(v) for k, v in value.items())
    if isinstance(value, (tuple, list)):
        return getsizeof(value) + sum(memory_size(item) for item in value)
    return getsizeof(value)


class PreviewCache:
    def __init__(self, limit, entries=24):
        self.limit = limit
        self.entries = entries
        self.used = 0
        self.items = OrderedDict()

    def get(self, key):
        item = self.items.get(key)
        if item is None:
            return None
        self.items.move_to_end(key)
        return item[0]

    def put(self, key, value):
        size = memory_size(value) + memory_size(key)
        self.remove(key)
        if size > self.limit:
            return
        while self.items and (self.used + size > self.limit or len(self.items) >= self.entries):
            self.remove(next(iter(self.items)))
        self.items[key] = (value, size)
        self.used += size

    def remove(self, key):
        item = self.items.pop(key, None)
        if item is not None:
            self.used -= item[1]

    def discard_file(self, file_id):
        for key in list(self.items):
            if key[0] == file_id:
                self.remove(key)
