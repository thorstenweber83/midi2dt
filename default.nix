{python3, xdotool}:

python3.pkgs.buildPythonApplication {
  pname = "midi2dt";
  version = "0.0.1";

  src = ./.;
  propagatedBuildInputs = [
    python3.pkgs.tkinter
    xdotool
  ];

  dontBuild = true;
  format = "other";
  
  installPhase = ''
    mkdir -p $out/bin
    mkdir -p $out/share/config
    cp midi2dt.py $out/bin/midi2dt
    cp *.json $out/share/config/
  '';
}