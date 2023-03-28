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
 - If it breaks, you get to keep both parts. That said, there shouldn't be
   any real _danger_ of e.g. deleting something that the existing GC wouldn't
   delete as we effectively just wrap the existing GC commands at a cpp-level.
