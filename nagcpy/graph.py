from dataclasses import dataclass
import heapq
from os.path import (
    join as path_join,
    split as path_split,
)

import libstore_wrapper as libstore
import retworkx as rx

from nagcpy.atime import path_max_atime


class GarbageGraph:
    @dataclass(slots=True, frozen=True)
    class StorePathNode:
        path: str
        nar_size: int
        max_atime: int

    def __init__(self):
        nix_store_path = libstore.get_nix_store_path()

        self.store = libstore.Store()
        garbage_path_set, _ = self.store.collect_garbage()

        garbage_store_path_set = {
            libstore.StorePath(path_split(str(p))[1]) for p in garbage_path_set
        }
        garbage_store_paths_sorted = self.store.topo_sort_paths(garbage_store_path_set)

        self.graph = rx.PyDAG(multigraph=False)
        self.path_index_mapping = {}
        self.invalid_paths = set()

        for store_path in reversed(garbage_store_paths_sorted):
            try:
                path_info = self.store.query_path_info(store_path)
            except RuntimeError:
                self.invalid_paths.add(str(store_path))
            else:
                node_data = self.StorePathNode(
                    str(path_info.path),
                    path_info.nar_size,
                    int(path_max_atime(path_join(nix_store_path, str(path_info.path)))),
                )
                node_index = self.graph.add_node(node_data)
                self.path_index_mapping[str(path_info.path)] = node_index

                for ref_sp in path_info.references:
                    ref_node_index = self.path_index_mapping.get(str(ref_sp))
                    if ref_node_index is not None:
                        self.graph.add_edge(node_index, ref_node_index, None)
                # else path being referenced is not garbage and we can ignore it

        self.heap = []
        for i in self.graph.node_indices():
            if self.graph.in_degree(i) == 0:
                heapq.heappush(self.heap, (self.graph[i].max_atime, i))

    def remove_heap_root(self):
        atime, idx = heapq.heappop(self.heap)
        node_data = self.graph[idx]
        ref_idxs = tuple(t for _, t, _ in self.graph.out_edges(idx))
        self.graph.remove_node(idx)
        del self.path_index_mapping[node_data.path]

        for ref_idx in ref_idxs:
            if self.graph.in_degree(ref_idx) == 0:
                heapq.heappush(self.heap, (self.graph[ref_idx].max_atime, ref_idx))

        return node_data

    def remove_nar_bytes(self, nar_bytes):
        removed_node_data = []
        removed_bytes = 0
        while removed_bytes < nar_bytes:
            node_data = self.remove_heap_root()
            removed_bytes += node_data.nar_size
            removed_node_data.append(node_data)

        return removed_node_data