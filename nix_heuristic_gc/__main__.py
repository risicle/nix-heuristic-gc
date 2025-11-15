
def _add_penalize_args(
    grp,
    name:str,
    default:bool,
    help:str="",
    boolean_basic_desc:str|None=None,
    default_weight:int=5,
):
    dest_sc = name.replace('-','_')
    dest = f"penalize_{dest_sc}"

    grp.add_argument(
        f"--penalize-{name}",
        dest=dest,
        action="store_const",
        const=5,
    )
    grp.add_argument(
        f"--no-penalize-{name}",
        dest=dest,
        action="store_const",
        const=None,
    )
    grp.add_argument(
        f"--penalize-{name}-weight",
        dest=dest,
        action="store",
        type=int,
        metavar="WEIGHT",
        help=help,
    )

    if boolean_basic_desc:
        bool_dest = f"collect_{dest_sc}"
        grp.add_argument(
            f"--no-{name}",
            dest=bool_dest,
            action="store_false",
            help=f"Don't choose {boolean_basic_desc} for deletion",
        )
        grp.add_argument(
            f"--only-{name}",
            dest=bool_dest,
            action="store_const",
            const="only",
            help=f"Only choose {boolean_basic_desc} for deletion",
        )
        grp.set_defaults(**{bool_dest: True})

    if default:
        grp.set_defaults(**{dest: 5})


def _weighting_help_text(
    basic:str,
    sflag:str,
    expl:str,
) -> str:
    return (
        f"{basic}, with weighting WEIGHT typically being a value from "
        f"1 (weak) to 10 (strong). {sflag} flag applies a WEIGHT of 5. {expl}."
    )


def main():
    import argparse
    from importlib.metadata import version as metadata_version, PackageNotFoundError
    import logging

    from nix_heuristic_gc import nix_heuristic_gc
    from nix_heuristic_gc.quantity import parse_quantity

    try:
        version = metadata_version("nix_heuristic_gc")
    except PackageNotFoundError:
        version = "unknown"

    parser = argparse.ArgumentParser(
        description="delete the least recently used or most easily replaced "
        "nix store paths based on customizable heuristics",
    )

    _add_penalize_args(
        parser.add_mutually_exclusive_group(),
        "invalid",
        True,
        _weighting_help_text(
            "Prefer choosing 'invalid' paths for deletion",
            "--penalize-invalid",
            "Enabled by default. Invalid paths are usually the result of a failed "
            "build and generally have no use other than debugging",
        ),
        "'invalid' paths",
    )
    _add_penalize_args(
        parser.add_mutually_exclusive_group(),
        "drvs",
        False,
        _weighting_help_text(
            "Prefer choosing .drv paths for deletion",
            "--penalize-drvs",
            ".drv files are usually easily regenerated and occupy an inode each",
        ),
        ".drv paths",
    )
    _add_penalize_args(
        parser.add_mutually_exclusive_group(),
        "substitutable",
        False,
        _weighting_help_text(
            "Prefer choosing paths for deletion that are substitutable from a "
            "binary cache",
            "--penalize-substitutable",
            "Disabled by default, this can slow down the path selection process for "
            "large collections due to the mass querying of binary cache(s)",
        ),
        "substitutable paths",
    )
    _add_penalize_args(
        parser.add_mutually_exclusive_group(),
        "inodes",
        False,
        _weighting_help_text(
            "Prefer choosing paths for deletion that will free up a lot of inodes",
            "--penalize-inodes",
            "When specifying a deletion limit by number of inodes, this will "
            "tend to select fewer, more inode-heavy paths to reach that limit - "
            "but it can be prone to overshoot, so recommend use with "
            "--penalize-exceeding-limit in this case.",
        )
    )
    _add_penalize_args(
        parser.add_mutually_exclusive_group(),
        "size",
        False,
        _weighting_help_text(
            "Prefer choosing larger (by nar size) paths for deletion",
            "--penalize-size",
            "When specifying a deletion limit in bytes, this will tend to "
            "select fewer, larger paths to reach that limit - but it can be "
            "prone to overshoot, so recommend use with "
            "--penalize-exceeding-limit in this case.",
        )
    )
    _add_penalize_args(
        parser.add_mutually_exclusive_group(),
        "exceeding-limit",
        False,
        _weighting_help_text(
            "Attempt to avoid going significantly over the size limit",
            "--penalize-exceeding-limit",
            "This penalizes path selections that would cause more deletion "
            "than requested by limit proportional to the overshoot",
        )
    )

    parser.add_argument(
        "--inherit-atime",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Whether recent-usage calculations should take into account recent "
        "usage of referring paths. The idea of this being to avoid removal of "
        "packages which may not *themselves* have been accessed recently, but "
        "may still have been required by a path that *was* accessed recently. "
        "This can only use information from paths that still exist at time of "
        "invocation, so repeated calls for small deletions will produce less "
        "accurate results than a single call for a larger deletion which has "
        "more information to work with.",
    )

    parser.add_argument(
        "--dry-run",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Don't actually delete any paths, but print list of paths "
        "that would be deleted to stdout.",
    )
    parser.add_argument(
        "--threads", "-t",
        type=int,
        help="Maximum number of threads to use when gathering path information. 0 "
        "disables multi-threading entirely. Default automatic. Concurrency is "
        "also limited by store settings' max-connections value - for best "
        "results increase that to a sensible value (perhaps via NIX_REMOTE?).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=version,
    )

    loglvl_grp = parser.add_mutually_exclusive_group()
    loglvl_grp.add_argument("--verbose", "-v", dest="loglevel", action="store_const", const=logging.DEBUG)
    loglvl_grp.add_argument("--quiet", "-q", dest="loglevel", action="store_const", const=logging.WARNING)

    parser.add_argument(
        "limit",
        help="Amount of garbage to collect, specified either in units of bytes "
        "(with optional multiplier prefix) or in units of 'I' (uppercase) - the "
        "number of inodes to be freed. Numbers with no units are assumed to be "
        "bytes. E.g. '100MiB' - 100 Mebibytes, '12KI' - 12 thousand inodes, "
        "'2G' - 2 Gigabytes",
    )

    parsed = vars(parser.parse_args())

    parsed["limit"] = parse_quantity(parsed["limit"])

    loglevel = parsed.pop("loglevel", None)
    if loglevel is None:
        loglevel = logging.INFO

    logging.basicConfig(
        level=parsed.pop("loglevel", loglevel),
        format="%(asctime)s:%(levelname)s:%(name)s: %(message)s",
    )

    nix_heuristic_gc(**parsed)


if __name__ == "__main__":
    main()
