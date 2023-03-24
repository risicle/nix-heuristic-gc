from dataclasses import dataclass
import enum
import heapq
import logging
from os.path import (
    join as path_join,
    split as path_split,
)
from typing import Optional

import libstore_wrapper as libstore
import retworkx as rx

from nagcpy.fs import path_stat_agg


logger = logging.getLogger(__name__)

_nix_store_path = libstore.get_nix_store_path()
_gc_keep_derivations = libstore.get_gc_keep_derivations()
_gc_keep_outputs = libstore.get_gc_keep_outputs()


class GarbageGraph:
    @dataclass(slots=True)
    class BaseStorePathNode:
        path: str
        nar_size: int
        _max_atime:Optional[int] = None
        _inodes:Optional[int] = None
        _substitutable:Optional[int] = None

    class EdgeType(enum.Enum):
        REFERENCE = enum.auto()
        DRV_OUTPUT = enum.auto()
        OUTPUT_DRV = enum.auto()

    class HeapEmptyError(IndexError): pass

    def __init__(
        self,
        store:libstore.Store,
        penalize_substitutable:Optional[float]=None,
        penalize_drvs:Optional[float]=None,
        penalize_inodes:Optional[float]=None,
        penalize_size:Optional[float]=None,
        penalize_exceeding_limit:Optional[float]=None,
    ):
        self.store = store
        self.penalize_exceeding_limit = penalize_exceeding_limit

        class StorePathNode(self.BaseStorePathNode):
            __slots__ = ()

            @property
            def inodes(_self):
                if _self._max_atime is None:
                    _self._max_atime, _self._inodes = path_stat_agg(path_join(
                        _nix_store_path,
                        _self.path,
                    ))
                return _self._inodes

            @property
            def max_atime(_self):
                if _self._inodes is None:
                    _self._max_atime, _self._inodes = path_stat_agg(path_join(
                        _nix_store_path,
                        _self.path,
                    ))
                return _self._max_atime

            @property
            def substitutable(_self):
                if _self._substitutable is None:
                    _self._substitutable = bool(self.store.query_substitutable_paths(
                        {libstore.StorePath(_self.path)},
                    ))
                return _self._substitutable

            @property
            def score(_self):
                s = float(_self.max_atime)
                if penalize_drvs is not None and _self.path.endswith(".drv"):
                    s -= penalize_drvs
                if penalize_substitutable is not None and _self.substitutable:
                    s -= penalize_substitutable
                if penalize_inodes is not None:
                    # divide by nar_size - we want to free many inodes before
                    # we hit the limit, and the limit is based on nar_size.
                    # add one to nar_size to avoid zero-division
                    s -= penalize_inodes * _self.inodes / (_self.nar_size+1)
                if penalize_size is not None:
                    s -= penalize_size *_self.nar_size
                return s

        self.StorePathNode = StorePathNode

        global _gc_keep_derivations, _gc_keep_outputs

        if _gc_keep_derivations and _gc_keep_outputs:
            logger.warning(
                "both keep-derivations and keep-outputs are enabled in your "
                "nix configuration. this will likely not work very well due to "
                "reference loops."
            )

        logger.info("querying dead paths")
        garbage_path_set, _ = self.store.collect_garbage(
            action=libstore.GCAction.GCReturnDead,
        )

        garbage_store_path_set = {
            libstore.StorePath(path_split(str(p))[1]) for p in garbage_path_set
        }
        logger.info("topologically sorting paths")
        garbage_store_paths_sorted = self.store.topo_sort_paths(garbage_store_path_set)

        # not (necessarily) a DAG due to DRV_OUTPUT and OUTPUT_DRV edges
        self.graph = rx.PyDiGraph()
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
                )
                node_index = self.graph.add_node(node_data)
                self.path_index_mapping[str(path_info.path)] = node_index

                for ref_sp in path_info.references:
                    ref_node_index = self.path_index_mapping.get(str(ref_sp))
                    if ref_node_index is not None:
                        self.graph.add_edge(
                            node_index,
                            ref_node_index,
                            self.EdgeType.REFERENCE,
                        )
                    # else path being referenced is not garbage and we can ignore it

        # topo_sort_paths doesn't respect these pseudo-references so we need to
        # add these edges on a second pass
        if _gc_keep_derivations or _gc_keep_outputs:
            logger.info("populating output-drv or drv-output edges")
            for path, idx in self.path_index_mapping.items():
                if path.endswith(".drv"):
                    for output in self.store.query_derivation_outputs(
                        libstore.StorePath(path),
                    ):
                        output_idx = self.path_index_mapping.get(str(output))
                        if output_idx is not None:
                            if _gc_keep_derivations:
                                self.graph.add_edge(
                                    output_idx,
                                    idx,
                                    self.EdgeType.OUTPUT_DRV,
                                )
                            if _gc_keep_outputs:
                                self.graph.add_edge(
                                    idx,
                                    output_idx,
                                    self.EdgeType.DRV_OUTPUT,
                                )

        logger.debug("gathering nodes for heap")
        pseudo_root_idxs = {
            i for i in self.graph.node_indices() if self.graph.in_degree(i) == 0
        }
        if penalize_substitutable:
            logger.info("bulk querying path substitutability")
            substitutable_paths = self.store.query_substitutable_paths({
                libstore.StorePath(self.graph[i].path) for i in pseudo_root_idxs
            })
            for i in pseudo_root_idxs:
                self.graph[i]._substitutable = (
                    libstore.StorePath(self.graph[i].path) in substitutable_paths
                )

        logger.info("constructing heap")
        self.heap = []
        for i in pseudo_root_idxs:
            heapq.heappush(self.heap, (self.graph[i].score, i))

    def remove_heap_root(self):
        if not self.heap:
            raise self.HeapEmptyError()

        idx = heapq.heappop(self.heap)[-1]
        node_data = self.graph[idx]
        ref_idxs = tuple(t for _, t, _ in self.graph.out_edges(idx))
        self.graph.remove_node(idx)
        del self.path_index_mapping[node_data.path]

        for ref_idx in ref_idxs:
            if self.graph.in_degree(ref_idx) == 0:
                heapq.heappush(self.heap, (self.graph[ref_idx].score, ref_idx))

        return node_data

    def correct_heap_root_for_limit_excess(
        self,
        nar_bytes_removed:int,
        nar_bytes_limit:int,
    ):
        if not self.heap:
            raise self.HeapEmptyError()

        if self.penalize_exceeding_limit is None:
            raise TypeError("This makes no sense to do without penalize_exceeding_limit")

        nar_bytes_remaining = nar_bytes_limit - nar_bytes_removed

        for _ in range(len(self.heap)):
            candidate_heapscore, candidate_idx = self.heap[0]
            candidate_spn = self.graph[candidate_idx]
            if candidate_spn.nar_size <= nar_bytes_remaining:
                # this entry needs no score correction
                return

            corrected_score = candidate_spn.score + (
                (candidate_spn.nar_size - nar_bytes_remaining)
                * self.penalize_exceeding_limit / nar_bytes_limit
            )
            if candidate_heapscore == corrected_score:
                # score in heap is up to date and the next
                # pop should yield the lowest scoring entry
                return

            # candidate hadn't had its score corrected for this
            # value of nar_bytes_remaining. pop and push back into
            # the heap with its updated score. if it's still the
            # lowest scoring entry it will get picked straight out
            # again on the next iteration.
            # this works because we can only ever increase a candidate's
            # score when correcting it - we know that correcting any
            # heap entry other than the root couldn't make it lower than
            # the root's score.
            logger.debug(
                "correcting score of %(path)s from %(prev_score)s to %(new_score)s",
                {
                    "path": candidate_spn.path,
                    "prev_score": candidate_heapscore,
                    "new_score": corrected_score,
                },
            )
            heapq.heappushpop(self.heap, (corrected_score, candidate_idx))
        else:
            raise AssertionError(
                "Performed correction shuffle more times than there are "
                "items in heap. This should not be possible."
            )

    def remove_nar_bytes(self, nar_bytes:int):
        removed_node_data = []
        removed_bytes = 0
        while removed_bytes < nar_bytes:
            if self.penalize_exceeding_limit is not None:
                self.correct_heap_root_for_limit_excess(removed_bytes, nar_bytes)
            node_data = self.remove_heap_root()
            removed_bytes += node_data.nar_size
            removed_node_data.append(node_data)

        return removed_node_data
