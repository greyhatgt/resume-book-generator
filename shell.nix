with import <nixpkgs> {};
let unstable = import <unstable> {};
in mkShell {
	buildInputs = [
		typst
		ghostscript
		libreoffice
	];
}
