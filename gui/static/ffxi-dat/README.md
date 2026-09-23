Vendored from https://github.com/Soverance/Vanalytics (MIT License, Copyright (c) 2026 Soverance
Studios -- see LICENSE-vanalytics.txt). Only src/Vanalytics.Web/src/lib/ffxi-dat/ was taken.

These are esbuild transpile-only output (no bundling) of the original TypeScript source, which
lives at D:\Claude\FFXI-Tools\vanalytics-ffxi-dat\*.ts. To rebuild after pulling an upstream
update to that source:

    cd D:\Claude\FFXI-Tools\vanalytics-ffxi-dat
    node build.mjs
    # then re-copy dist/*.js (+ .js.map) into this folder

Not modified from the transpile output except for import-specifier `.js` suffixes (added by
build.mjs itself, needed for native browser ES module loading -- esbuild's transpile-only mode
doesn't add them).
