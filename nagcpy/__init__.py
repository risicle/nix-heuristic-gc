import logging

import libstore_wrapper as libstore

from nagcpy.graph import GarbageGraph

logger = logging.getLogger(__name__)

def nix_heuristic_gc(
    reclaim_bytes:int,
    penalize_substitutable:bool=True,
    penalize_drvs:bool=True,
    dry_run:bool=True,
):
    store = libstore.Store()

    garbage_graph = GarbageGraph(
        store=store,
        penalize_substitutable=1e5 if penalize_substitutable else None,
        penalize_drvs=1e5 if penalize_drvs else None,
    )
    logger.info("selecting store paths for removal")
    to_reclaim = garbage_graph.remove_nar_bytes(reclaim_bytes)

    logger.info(
        "requesting deletion of %(count)s store paths, total nar_size %(size)s bytes",
        {
            "count": len(to_reclaim),
            "size": sum(spn.nar_size for spn in to_reclaim),
        },
    )

    if not dry_run:
        _, bytes_freed = store.collect_garbage(
            action=libstore.GCAction.GCDeleteSpecific,
            paths_to_delete={
                libstore.StorePath(spn.path) for spn in to_reclaim
            },
        )
        logger.info("freed %(size)s bytes", {"size": bytes_freed})
