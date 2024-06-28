{ pkgs ? import <nixpkgs> {}
, system ? builtins.currentSystem
, pythonPackages ? pkgs.python311Packages
, forTest ? true
, forDev ? true
}:
{
  nhgcEnv = pkgs.stdenv.mkDerivation {
    name = "nix-heuristic-gc-env";

    NIX_SYSTEM = system;

    buildInputs = [
      pythonPackages.humanfriendly
      pythonPackages.pybind11
      pythonPackages.setuptools
      pythonPackages.rustworkx
      pkgs.boost
      pkgs.nix
    ] ++ pkgs.lib.optionals forTest [
      pythonPackages.pytest
    ] ++ pkgs.lib.optionals forDev [
      pythonPackages.ipython
      pythonPackages.matplotlib
      pkgs.pwndbg
      pkgs.less
    ];
  };

  pkg = pythonPackages.buildPythonPackage {
    pname = "nix-heuristic-gc";
    version = pkgs.lib.removeSuffix "\n" (builtins.readFile ./VERSION);
    src = pkgs.nix-gitignore.gitignoreSource ["*.nix" "flake.lock"] ./.;

    NIX_SYSTEM = system;

    buildInputs = [
      pkgs.boost
      pkgs.nix
      pythonPackages.pybind11
      pythonPackages.setuptools
    ];
    propagatedBuildInputs = [
      pythonPackages.humanfriendly
      pythonPackages.rustworkx
    ];

    checkInputs = [
      pythonPackages.pytestCheckHook
    ];
    preCheck = ''
      mv nix_heuristic_gc .nix_heuristic_gc
    '';
  };
}
