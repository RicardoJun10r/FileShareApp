"""Histórico limitado de metadados para sincronização incremental."""
from collections import deque
from uuid import uuid4
from preview_cache import memory_size


class CatalogChanges:
    def __init__(self, capacity=1024, max_bytes=2 * 1024 * 1024):
        self.epoch = uuid4().hex
        self.revision = 0
        self.changes = deque()
        self.capacity = capacity
        self.max_bytes = max_bytes
        self.used = 0
        self.floor = 0

    def record(self, files=(), links=(), deleted=()):
        self.revision += 1
        change = {"revision": self.revision, "files": list(files),
                  "links": list(links), "deleted": list(deleted)}
        self.changes.append(change)
        self.used += memory_size(change)
        while self.changes and (len(self.changes) > self.capacity or self.used > self.max_bytes):
            removed = self.changes.popleft()
            self.used -= memory_size(removed)
            self.floor = removed["revision"]

    def read(self, since, epoch, files, links):
        reset = (epoch != self.epoch or since is None or since > self.revision
                 or since < self.floor)
        result = {"epoch": self.epoch, "revision": self.revision, "reset": bool(reset)}
        if reset:
            return {**result, "files": list(files), "links": list(links), "deleted": []}
        updated_files, updated_links, deleted = {}, {}, set()
        for change in self.changes:
            if change["revision"] <= since:
                continue
            for item in change["files"]:
                updated_files[item["id"]] = item
            for item in change["links"]:
                updated_links[item["id"]] = item
            for key in change["deleted"]:
                updated_files.pop(key, None)
                deleted.add(key)
        return {**result, "files": list(updated_files.values()),
                "links": list(updated_links.values()), "deleted": list(deleted)}
