from concurrent.futures import Executor
from dataclasses import dataclass
import enum
import heapq
import logging
from os.path import (
    join as path_join,
    split as path_split,
)
from typing import Optional

import retworkx as rx

import nix_heuristic_gc.libnixstore_wrapper as libstore
from nix_heuristic_gc.fs import path_stat_agg
from nix_heuristic_gc.naive_executor import NaiveExecutor
from nix_heuristic_gc.quantity import Quantity, QuantityUnit


logger = logging.getLogger(__name__)

_nix_store_path = libstore.get_nix_store_path()
_gc_keep_derivations = libstore.get_gc_keep_derivations()
_gc_keep_outputs = libstore.get_gc_keep_outputs()


class GarbageGraph:
    @dataclass(slots=True)
    class BaseStorePathNode:
        path: str
        nar_size: int
        _inherited_max_atime:Optional[int] = None
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
        limit_unit:QuantityUnit,
        executor:Executor=NaiveExecutor(),
        penalize_substitutable:Optional[float]=None,
        penalize_drvs:Optional[float]=None,
        penalize_inodes:Optional[float]=None,
        penalize_size:Optional[float]=None,
        penalize_exceeding_limit:Optional[float]=None,
        inherit_max_atime:bool=True,
    ):
        self.store = store
        self.penalize_exceeding_limit = penalize_exceeding_limit
        self.inherit_max_atime = inherit_max_atime
        self._executor = executor

        class StorePathNode(self.BaseStorePathNode):
            __slots__ = ()

            @property
            def inodes(_self):
                if _self._inodes is None:
                    _self._max_atime, _self._inodes = path_stat_agg(path_join(
                        _nix_store_path,
                        _self.path,
                    ))
                return _self._inodes

            @property
            def max_atime(_self):
                if _self._max_atime is None:
                    _self._max_atime, _self._inodes = path_stat_agg(path_join(
                        _nix_store_path,
                        _self.path,
                    ))
                if self.inherit_max_atime:
                    return max(_self._max_atime or 0, _self._inherited_max_atime or 0)
                else:
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
                    s -= penalize_inodes * _self.inodes_score
                if penalize_size is not None:
                    s -= penalize_size * _self.nar_size_score
                return s

            if limit_unit == QuantityUnit.BYTES:
                @property
                def limit_measurement(_self):
                    return _self.nar_size

                @property
                def inodes_score(_self):
                    # divide by nar_size - we want to free many inodes before
                    # we hit the limit, and the limit is based on nar_size.
                    # add one to nar_size to avoid zero-division
                    return _self.inodes / (_self.nar_size+1)

                @property
                def nar_size_score(_self):
                    return _self.nar_size
            elif limit_unit == QuantityUnit.INODES:
                @property
                def limit_measurement(_self):
                    return _self.inodes

                @property
                def inodes_score(_self):
                    return _self.inodes

                @property
                def nar_size_score(_self):
                    # divide by inodes - we want to free many bytes before
                    # we hit the limit, and the limit is based on inodes.
                    # add one to inodes to avoid zero-division
                    return _self.nar_size / (_self.inodes+1)
            else:
                raise ValueError(f"Don't know how to measure {limit_unit!r}")

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

        logger.info("building graph")
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
                    if ref_node_index == node_index:
                        logger.debug(
                            "omitting self-referencing edge from path %s",
                            str(path_info.path),
                        )
                    elif ref_node_index is not None:
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
        # this shouldn't require any locking as long as each task only
        # references one unique StorePathNode
        for heap_tuple in self._executor.map(
            self._get_heap_tuple,
            pseudo_root_idxs,
        ):
            heapq.heappush(self.heap, heap_tuple)

    def _get_heap_tuple(self, ref_idx):
        return self.graph[ref_idx].score, ref_idx

    def remove_heap_root(self):
        if not self.heap:
            raise self.HeapEmptyError()

        idx = heapq.heappop(self.heap)[-1]
        node_data = self.graph[idx]
        ref_idxs = frozenset((t for _, t, _ in self.graph.out_edges(idx)))
        self.graph.remove_node(idx)
        del self.path_index_mapping[node_data.path]

        if self.inherit_max_atime:
            # ensure our direct references inherit our max_atime
            # before we go (a path's atime is irrelevant until its
            # referrers have been deleted so this should be the
            # only place we need to propagate atimes)
            for ref_idx in ref_idxs:
                ref_spn = self.graph[ref_idx]
                ref_spn._inherited_max_atime = max(
                    node_data.max_atime or 0,
                    ref_spn._inherited_max_atime or 0,
                )

        # this shouldn't require any locking as long as each task only
        # references one unique StorePathNode
        for heap_tuple in self._executor.map(
            self._get_heap_tuple,
            (ref_idx for ref_idx in ref_idxs if self.graph.in_degree(ref_idx) == 0),
        ):
            heapq.heappush(self.heap, heap_tuple)

        return node_data

    def correct_heap_root_for_limit_excess(
        self,
        limit:int,
        limit_removed:int,
    ):
        if not self.heap:
            raise self.HeapEmptyError()

        if self.penalize_exceeding_limit is None:
            raise TypeError("This makes no sense to do without penalize_exceeding_limit")

        limit_remaining = limit - limit_removed

        for _ in range(len(self.heap)):
            candidate_heapscore, candidate_idx = self.heap[0]
            candidate_spn = self.graph[candidate_idx]
            if candidate_spn.limit_measurement <= limit_remaining:
                # this entry needs no score correction
                return

            corrected_score = candidate_spn.score + (
                (candidate_spn.limit_measurement - limit_remaining)
                * self.penalize_exceeding_limit / limit
            )
            if candidate_heapscore == corrected_score:
                # score in heap is up to date and the next
                # pop should yield the lowest scoring entry
                return

            # candidate hadn't had its score corrected for this
            # value of limit_remaining. pop and push back into
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

    def remove_to_limit(self, limit:int):
        removed_node_data = []
        limit_removed = 0

        try:
            while limit_removed < limit:
                if self.penalize_exceeding_limit is not None:
                    self.correct_heap_root_for_limit_excess(limit, limit_removed)
                node_data = self.remove_heap_root()
                limit_removed += node_data.limit_measurement
                removed_node_data.append(node_data)
        except self.HeapEmptyError:
            logger.warning("ran out of zero-reference paths to remove")
            if self.graph.num_nodes():
                logger.warning(
                    "%(path_count)s remaining paths may have reference loops - "
                    "use regular nix gc commands to remove these.",
                    {
                        "path_count": self.graph.num_nodes(),
                    },
                )
                logger.debug(
                    "%(count)s pseudo-roots left in graph",
                    {
                        "count": sum(1 for i in self.graph.node_indices() if self.graph.in_degree(i) == 0),
                    },
                )
                logger.debug(
                    "first encountered cycle: %s",
                    [str(self.graph[i].path) for i in rx.digraph_find_cycle(self.graph)],
                )

        return removed_node_data
