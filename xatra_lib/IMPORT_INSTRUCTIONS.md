To forcibly re-seed the database, run 

```
uv run seed_libs.py --force
```


---------

## prompt that created and describes the seeding

Write a script that automatically creates maps corresponding to all the items in this directory (besides `default_theme.py`) with titles equal to their file names (without the .py extension) and username srajma.

1) The maps in map/ are full maps. The `xatrahub(xyz)` or `abc = xatrahub(xyz)` lines should be put in the "xatrahub imports" section of the map created; anything between `# <lib>` and `# </lib>` lines should be put in the "Custom Territory Library" section of the map created; anything inside an `if __name__ == "__main__"` (or `if __name__ == '__main__'`) block should be (stripped of their outer-most indentation and then) put in the Runtime code ("Do not expose to importers") section of the map created; everything else should be put under map code. srajma is an admin user, so the "Arbitrary Python" objects in the maps are fine.
2) The maps in lib/ are Custom territory libraries for other users to import. You will still create map objects in the database for these, but you will fill the contents of these files into the "Custom territory library" sections of the new map (except for the `abc = xatrahub(xyz)` lines, which should go into the xatrahub imports section). There will be no `# <lib>` tags here.

The "Custom Theme" section of every map created, in both cases should be pre-filled with the contents of `default_theme.py`. At present, I believe all new maps are pre-filled with this for Custom Theme:

```python
xatra.BaseOption("Esri.WorldTopoMap", name="Esri.WorldTopoMap", default=True)
xatra.FlagColorSequence(LinearColorSequence(colors=None, step=Color.hsl(1.6180339887, 0, 0)))
xatra.AdminColorSequence(LinearColorSequence(colors=None, step=Color.hsl(1.6180339887, 0, 0)))
xatra.DataColormap(LinearSegmentedColormap.from_list("custom_cmap", ["yellow", "orange", "red"]))
```
You should also replace this to use the contents of `default_theme.py`.

All your changes should directly refer to the contents of these files (i.e. don't copy the contents of these files, just refer to them) so that I can just make edits here to any library and re-run the script.

3) All this should replace the current code that tries to automatically generate the legacy "dtl" or "indic" territory library. We have split that library into the various sections in lib/.
4) Right now, every new map is initialized with a default xatrahub import `indic = xatrahub("/lib/dtl/alpha")`. We shall replace this with:
```
indic = xatrahub("/lib/indic_lib")
iran = xatrahub("/lib/iran_lib")
sb = xatrahub("/lib/sb_lib")
```

Typically the script should check if a map of that name already exists and only create it if it doesn't---but it should have a `--force` option to overwrite existing maps (specifically their "alpha" versions, leaving the numbered versions as-is). The script should be run every time the database is initialized for the first time.



---------

Map data/code sections structure:
- Python Imports (not really data, just the same read-only snippet in all cases)
- xatrahub imports (both `xatrahub(xyz)` and `abc = xatrahub(xyz)` code)
- Custom Territory Library
- Custom Theme
- Map Code
- Runtime Code (stuff under `if __name__ == "__main__"`)
  - xatrahub imports
  - Custom Territory Library
  - Custom Theme
  - Map Code

All these sections should show up under both Builder and Code.