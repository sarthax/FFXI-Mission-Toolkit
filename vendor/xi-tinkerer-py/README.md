# xi-tinkerer-py

PyO3 bindings for the [xi-tinkerer](https://github.com/InoUno/xi-tinkerer) `dats` crate.

```python
from xi_tinkerer import parse_menu_table

data = parse_menu_table("ROM/118/114.DAT")
# native dict, ready to use
```

Exposed parsers: `parse_menu_table`, `parse_dmsg_table`, `parse_dialog`, `parse_entity_names`, `parse_events`, `parse_item_info`, `parse_status_info`, `parse_xistring_table`.

## Install

```bash
pip install https://github.com/sruon/xi-tinkerer-py/releases/download/latest/xi_tinkerer-<version>-<platform>.whl
```

## Build

```bash
maturin build --release
```

Pushes to `main` build linux/windows/macos wheels and update the rolling `latest` release.
