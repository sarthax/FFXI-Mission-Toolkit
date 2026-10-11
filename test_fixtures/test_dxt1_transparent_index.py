from pathlib import Path
import shutil
import subprocess

PARSER = Path(__file__).resolve().parents[1] / "gui/static/ffxi-dat/TextureParser.js"


def test_dxt1_transparent_index_three():
    source = PARSER.read_text(encoding="utf-8")
    assert "pal[15] = 0;" in source
    if not shutil.which("node"):
        return
    script = r"""
import fs from 'node:fs';
const content = fs.readFileSync(process.argv[1], 'utf8');
const { decompressDXT1 } = await import('data:text/javascript;base64,' + Buffer.from(content).toString('base64'));
function alphaFor(c0, c1) {
  const d = new Uint8Array(8);
  d[0] = c0 & 255; d[1] = c0 >>> 8;
  d[2] = c1 & 255; d[3] = c1 >>> 8;
  d.fill(255, 4); // every DXT1 selector is index 3
  return decompressDXT1(d, 4, 4).filter((_, i) => i % 4 === 3);
}
const mask = alphaFor(0, 65535);
const opaque = alphaFor(65535, 0);
if (!mask.every(v => v === 0)) throw Error('DXT1 transparent palette index is opaque');
if (!opaque.every(v => v === 255)) throw Error('DXT1 four-color palette index has broken alpha');
"""
    subprocess.run(["node", "--input-type=module", "-e", script, str(PARSER)],
                   check=True, capture_output=True, text=True)
