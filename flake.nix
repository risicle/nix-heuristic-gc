{
  description = "nix-heuristic-gc";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachSystem flake-utils.lib.allSystems (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      nhgc = import ./default.nix { inherit pkgs system; };
    in {
      packages.nix-heuristic-gc = nhgc.pkg;
      packages.default = nhgc.pkg;
    });
}
