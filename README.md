# nix-heuristic-gc

A more discerning cousin of `nix-collect-garbage`, mostly intended as a
testbed to allow experimentation with more advanced selection processes.

Developers and users who make use of a lot of packages ephemerally end up
with a large nix store full of packages which _may_ or _may not_ be used
again in the near future, but aren't referenced from a GC-root. While
`nix-collect-garbage`'s `--max-freed` option is handy here, it still
selects _which_ paths to delete at random.

`nix-heuristic-gc` uses a greedy algorithm to prefer deletion of less-recently
accessed (or more easily replaceable) store paths.

## Caveats

 - Since we're unable to hold nix's garbage-collection lock between calls to
   discover unreachable store paths and then request deletion of them, it's
   possible we may request deletion of paths that are no longer unreachable.
 - Whether a path is "recently used" is determined using atime, which is far
   from perfect and may even be disabled on your filesystem.
 - This may not work (at all) well with both `keep-derivations` and
   `keep-outputs` nix settings enabled.
 - This is unable to delete invalid paths (i.e. the partial products of failed
   builds) because libnixstore lacks the interface to precisely request such
   a thing.
 - If it breaks, you get to keep both parts. That said, there shouldn't be
   any real _danger_ of e.g. deleting something that the existing GC wouldn't
   delete as we effectively just wrap the existing GC commands at a cpp-level.

## Usage

```
usage: nix-heuristic-gc [-h]
                        [--penalize-drvs | --no-penalize-drvs | --penalize-drvs-weight WEIGHT]
                        [--penalize-substitutable | --no-penalize-substitutable | --penalize-substitutable-weight WEIGHT]
                        [--penalize-inodes | --no-penalize-inodes | --penalize-inodes-weight WEIGHT]
                        [--penalize-size | --no-penalize-size | --penalize-size-weight WEIGHT]
                        [--penalize-exceeding-limit | --no-penalize-exceeding-limit | --penalize-exceeding-limit-weight WEIGHT]
                        [--inherit-atime | --no-inherit-atime] [--dry-run | --no-dry-run]
                        [--threads THREADS] [--version] [--verbose | --quiet]
                        limit

delete the least recently used or most easily replaced nix store paths based on customizable
heuristics

positional arguments:
  limit                 Amount of garbage to collect, specified either in units of bytes (with
                        optional multiplier prefix) or in units of 'I' (uppercase) - the number
                        of inodes to be freed. Numbers with no units are assumed to be bytes.
                        E.g. '100MiB' - 100 Mebibytes, '12KI' - 12 thousand inodes, '2G' - 2
                        Gigabytes

options:
  -h, --help            show this help message and exit
  --penalize-drvs
  --no-penalize-drvs
  --penalize-drvs-weight WEIGHT
                        Prefer choosing .drv paths for deletion, with weighting WEIGHT
                        typically being a value from 1 (weak) to 10 (strong). --penalize-drvs
                        flag applies a WEIGHT of 5. .drv files are usually easily regenerated
                        and occupy an inode each.
  --penalize-substitutable
  --no-penalize-substitutable
  --penalize-substitutable-weight WEIGHT
                        Prefer choosing paths for deletion that are substitutable from a binary
                        cache, with weighting WEIGHT typically being a value from 1 (weak) to
                        10 (strong). --penalize-substitutable flag applies a WEIGHT of 5. Disabled by
                        default, this can slow down the path selection process for large
                        collections due to the mass querying of binary cache(s).
  --penalize-inodes
  --no-penalize-inodes
  --penalize-inodes-weight WEIGHT
                        Prefer choosing paths for deletion that will free up a lot of inodes,
                        with weighting WEIGHT typically being a value from 1 (weak) to 10
                        (strong). --penalize-inodes flag applies a WEIGHT of 5. When specifying
                        a deletion limit by number of inodes, this will tend to select fewer,
                        more inode-heavy paths to reach that limit - but it can be prone to
                        overshoot, so recommend use with --penalize-exceeding-limit in this
                        case..
  --penalize-size
  --no-penalize-size
  --penalize-size-weight WEIGHT
                        Prefer choosing larger (by nar size) paths for deletion, with weighting
                        WEIGHT typically being a value from 1 (weak) to 10 (strong).
                        --penalize-size flag applies a WEIGHT of 5. When specifying a deletion
                        limit in bytes, this will tend to select fewer, larger paths to reach
                        that limit - but it can be prone to overshoot, so recommend use with
                        --penalize-exceeding-limit in this case..
  --penalize-exceeding-limit
  --no-penalize-exceeding-limit
  --penalize-exceeding-limit-weight WEIGHT
                        Attempt to avoid going significantly over the size limit, with
                        weighting WEIGHT typically being a value from 1 (weak) to 10 (strong).
                        --penalize-exceeding-limit flag applies a WEIGHT of 5. This penalizes
                        path selections that would cause more deletion than requested by limit
                        proportional to the overshoot.
  --inherit-atime, --no-inherit-atime
                        Whether recent-usage calculations should take into account recent usage
                        of referring paths. The idea of this being to avoid removal of packages
                        which may not *themselves* have been accessed recently, but may still
                        have been required by a path that *was* accessed recently. This can
                        only use information from paths that still exist at time of invocation,
                        so repeated calls for small deletions will produce less accurate
                        results than a single call for a larger deletion which has more
                        information to work with. (default: False)
  --dry-run, --no-dry-run
                        Don't actually delete any paths, but print list of paths that would be
                        deleted to stdout. (default: False)
  --threads THREADS, -t THREADS
                        Maximum number of threads to use when gathering path information. 0
                        disables multi-threading entirely. Default automatic. Concurrency is
                        also limited by store settings' max-connections value - for best
                        results increase that to a sensible value (perhaps via NIX_REMOTE?).
  --version             show program's version number and exit
  --verbose, -v
  --quiet, -q
```
