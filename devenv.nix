{ pkgs, lib, config, inputs, ... }:

{
  # https://devenv.sh/packages/
  packages = [ pkgs.git pkgs.jdk17 pkgs.just ];

  env.JAVA_HOME = "${pkgs.jdk17}/lib/openjdk";
  env.PYSPARK_PYTHON = "python3";

  # https://devenv.sh/languages/
  # Python is pinned to 3.11: PySpark 3.5.1's bundled cloudpickle recurses
  # infinitely serializing closures under 3.14 (devenv's default at the time
  # this was pinned). See AGENTS.md's gotchas list before touching this.
  languages.python = {
    enable = true;
    version = "3.11";
    venv.enable = true;
    uv = {
      enable = true;
      sync.enable = true;
    };
  };

  # https://devenv.sh/basics/
  enterShell = ''
    java -version
    python3 --version
    uv --version
  '';

  # https://devenv.sh/git-hooks/
  # git-hooks.hooks.shellcheck.enable = true;

  # See full reference at https://devenv.sh/reference/options/
}
