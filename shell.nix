{ pkgs ? import <nixpkgs> { config.allowUnfree = true; } }:
let
  hasCuda = builtins.pathExists /proc/driver/nvidia;
  cudaPkgs = if hasCuda then (with pkgs.cudaPackages; [
    cuda_cudart libcublas libcurand cuda_nvrtc
  ]) else [];
in
pkgs.mkShell {
  fontsConf = pkgs.makeFontsConf {
    fontDirectories = [ pkgs.noto-fonts pkgs.dejavu_fonts ];
  };
  packages = [
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.python311Packages.tkinter
    pkgs.stdenv.cc.cc.lib
    pkgs.noto-fonts
    pkgs.dejavu_fonts
    pkgs.fontconfig
  ] ++ cudaPkgs;
  shellHook = ''
    export FONTCONFIG_FILE=${fontsConf}
    export LD_LIBRARY_PATH=${pkgs.stdenv.cc.cc.lib}/lib:$LD_LIBRARY_PATH
    for d in /run/opengl-driver/lib /run/opengl-driver-32/lib; do
      [ -d "$d" ] && export LD_LIBRARY_PATH="$d:$LD_LIBRARY_PATH"
    done
  '' + pkgs.lib.optionalString hasCuda ''
    for d in /nix/store/*-cuda12*-lib/lib; do
      [ -d "$d" ] && export LD_LIBRARY_PATH="$d:$LD_LIBRARY_PATH"
    done
    _cudart=$(ls /nix/store/*/lib/libcudart.so.12 2>/dev/null | head -1)
    [ -n "$_cudart" ] && export LD_LIBRARY_PATH="$(dirname "$_cudart"):$LD_LIBRARY_PATH"
  '';
}
