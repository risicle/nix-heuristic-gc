from concurrent.futures import ThreadPoolExecutor
import logging
from os.path import join as path_join
from typing import Optional

from humanfriendly import format_size

import nix_heuristic_gc.libnixstore_wrapper as libstore
from nix_heuristic_gc.graph import GarbageGraph
from nix_heuristic_gc.naive_executor import NaiveExecutor
from nix_heuristic_gc.quantity import Quantity

logger = logging.getLogger(__name__)


def _unfriendly_weight(
    friendly_weight:int,
    default_unfriendly_weight:float,
    exp_base:float=7,
    default_friendly_weight:float=5,
):
    if not friendly_weight:
        return None
    return (
        exp_base ** (friendly_weight-default_friendly_weight)
    ) * default_unfriendly_weight


def nix_heuristic_gc(
    limit:Quantity,
    penalize_substitutable:int=5,
    penalize_drvs:int=0,
    penalize_inodes:int=0,
    penalize_size:int=0,
    penalize_exceeding_limit:int=0,
    threads:Optional[int]=None,
    dry_run:bool=True,
):
    store = libstore.Store()

    if (threads or 0) < 0:
        raise ValueError("Negative values for threads argument make no sense")
    elif threads == 0:
        executor = NaiveExecutor()
    else:
        executor = ThreadPoolExecutor(max_workers=threads)

    garbage_graph = GarbageGraph(
        store=store,
        limit_unit=limit.unit,
        executor=executor,
        penalize_substitutable=_unfriendly_weight(penalize_substitutable, 1e5),
        penalize_drvs=_unfriendly_weight(penalize_drvs, 1e5),
        penalize_inodes=_unfriendly_weight(penalize_inodes, 1e6),
        penalize_size=_unfriendly_weight(penalize_size, 1e-3),
        penalize_exceeding_limit=_unfriendly_weight(penalize_exceeding_limit, 5e5),
    )
    logger.info("selecting store paths for removal")
    logger.debug("using limit of %s", limit)
    to_reclaim = garbage_graph.remove_to_limit(limit.value)

    logger.info(
        "%(maybe_not)srequesting deletion of %(count)s store paths, total nar_size %(size)s, %(inodes)s inodes",
        {
            "maybe_not": "(not) " if dry_run else "",
            "count": len(to_reclaim),
            "size": format_size(sum(spn.nar_size for spn in to_reclaim), binary=True),
            "inodes": sum(spn.inodes for spn in to_reclaim),
        },
    )

    if dry_run:
        nix_store_path = libstore.get_nix_store_path()
        for spn in to_reclaim:
            print(path_join(nix_store_path, spn.path))
    else:
        _, bytes_freed = store.collect_garbage(
            action=libstore.GCAction.GCDeleteSpecific,
            paths_to_delete={
                libstore.StorePath(spn.path) for spn in to_reclaim
            },
        )
        logger.info("freed %(size)s", {"size": format_size(bytes_freed, binary=True)})
