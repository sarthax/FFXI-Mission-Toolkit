# Attribution

This tool is a derivative work of [POLUtils](https://github.com/Windower/POLUtils) by Tim Van
Holder, Nevin Stepan, and the Windower Team, licensed under the Apache License 2.0 (see
`LICENSE.txt`).

Specifically:

- `src/FFXIEncoding.cs` is copied unmodified from POLUtils'
  `PlayOnline.FFXI/FFXIEncoding.cs`.
- `ConversionTables/*.dat` are copied unmodified from POLUtils'
  `PlayOnline.FFXI/ConversionTables/`.
- `data/ROMFileMappings.xml` is copied unmodified from POLUtils'
  `PlayOnline.FFXI.Utils.DataBrowser/ROMFileMappings.xml`.
- `data/Messages.xml` is copied unmodified from POLUtils'
  `PlayOnline.FFXI.Utils.DataBrowser/Messages.resx` (renamed to avoid the .NET SDK's implicit
  `.resx` handling; content and format are untouched).
- The parsing algorithms in `Program.cs` (`DialogTableParser`, `OffsetStringTableParser`, and the
  VTABLE/FTABLE resolver in `ResolveFilePath`) are transcribed from POLUtils'
  `PlayOnline.FFXI/FileTypes/DialogTable.cs`, `PlayOnline.FFXI/Things/DialogTableEntry.cs`, and
  `PlayOnline.FFXI/FFXIResourceManager.cs` respectively — rewritten as standalone functions
  without the original `Thing`/`IThing` class hierarchy (which pulls in WinForms/System.Drawing
  for GUI property-page support this tool doesn't need), but the parsing logic itself is
  POLUtils' algorithm, not independently developed.

This tool contains no FFXI game content. It's a client-side parser only — the DAT files it reads
are supplied by the user from their own licensed game install and are never bundled, embedded, or
redistributed by this tool or its source.
