{ pkgs ? import <nixpkgs> {}
, pythonPackages ? pkgs.python310Packages
, forTest ? true
, forDev ? true
}:
{
  nagcpyEnv = pkgs.stdenv.mkDerivation {
    name = "nagcpy-env";

#     NIX_CFLAGS_COMPILE = [
#       "-I ${pkgs.nix}/include/eigen3"
#     ];

    buildInputs = [
      pythonPackages.pybind11
      pythonPackages.setuptools
      pythonPackages.retworkx
      pkgs.boost
      pkgs.nix
    ] ++ pkgs.lib.optionals forTest [
    ] ++ pkgs.lib.optionals forDev [
    ];
  };
}
