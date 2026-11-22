# ATRF 2026 AequilibraE workshop and benchmarks

This repository contains two hands-on AequilibraE 2.0 workshop notebooks and traffic assignment comparisons with Quetzal.

## Clone the repository

```sh
git clone https://github.com/AequilibraE/atrf2026.git
cd atrf2026
```

## Install uv and platform dependencies

AequilibraE supports Python **3.11, 3.12, 3.13 and 3.14**. The commands below use Python 3.14, which the pinned AequilibraE release tests on macOS. Use Python 3.12 for the Quetzal comparisons to match the benchmark notebooks.

### Windows

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) from PowerShell, then open a new terminal so it is on your `PATH`.

```powershell
winget install --source winget --exact --id astral-sh.uv
```

**Do not use Python from the Microsoft Store.** Its SQLite build cannot load the SpatiaLite extension required by AequilibraE. The commands below use a uv-managed Python. On Windows x86-64, AequilibraE downloads SpatiaLite on first use if needed. See the [AequilibraE installation guide](https://www.aequilibrae.com/develop/python/useful_links/installation.html).

If uv builds AequilibraE from source on Windows, install [Microsoft C++ Build Tools](https://learn.microsoft.com/en-us/cpp/overview/acquire-msvc) with the **Desktop development with C++** workload, then retry the installation.

### macOS

Install the Xcode Command Line Tools and finish the installation prompt before continuing.

```sh
xcode-select --install
```

Install [Homebrew](https://brew.sh/), then run the following in Terminal. uv compiles AequilibraE from source on macOS using Homebrew LLVM for OpenMP support. AequilibraE loads the SQLite extension from `AEQ_SPATIALITE_DIR` when it opens a project. See the [AequilibraE release’s macOS instructions](https://github.com/AequilibraE/aequilibrae/blob/v2.0.0rc1/docs/source/useful_links/installation.rst#macos).

```sh
brew install uv llvm libspatialite
export CC="$(brew --prefix llvm)/bin/clang"
export CXX="$(brew --prefix llvm)/bin/clang++"
export AEQ_SPATIALITE_DIR="$(brew --prefix libspatialite)/lib"
```

Run the installation and launch JupyterLab from this terminal. Set `AEQ_SPATIALITE_DIR` again when launching from a new terminal, or add the export to `~/.zshrc`.

## Set up the Python environment

Run these commands from the repository root. To choose another Python version, replace `3.14` in both commands.

```sh
uv python install 3.14
uv venv --managed-python --python 3.14
uv pip install -r workshop/requirements.txt
```

Check that AequilibraE can load SpatiaLite. The command should print the installed SpatiaLite version.

```sh
uv run python -c "from aequilibrae.utils.spatialite_utils import connect_spatialite; db = connect_spatialite(':memory:'); print(db.execute('SELECT spatialite_version()').fetchone()[0]); db.close()"
```

## Run the workshop notebooks

```sh
cd workshop
uv run python -m jupyterlab
```

Open either notebook in JupyterLab and run the cells in order. Start JupyterLab from `workshop/` so the notebooks can find the bundled data and visualization modules.

| Notebook | What it covers |
| --- | --- |
| [Mount Isa network import and bicycle route choice](workshop/mount-isa-osm-example.ipynb) | Build a network from the bundled OpenStreetMap PBF and compare bicycle route sets. Overpass and Overture Maps are optional online sources. |
| [Chicago traffic assignment](workshop/chicago-traffic-assignment-example.ipynb) | Use the bundled Chicago sample model to find shortest paths and run single- and multiclass traffic assignments. |


