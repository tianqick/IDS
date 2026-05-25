from __future__ import annotations

import json
import struct
import subprocess
import zlib
from pathlib import Path

import generate_chapter4_3_current_flowcharts as base
import generate_chapter4_3_paper_flowcharts as paper


ROOT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT_DIR / "thesis_figures" / "4_3_bw_flowcharts"
FONT_NAME = "SimSun"


NODE_STYLES = {
    "start": {
        "shape": "box",
        "style": "rounded",
        "color": "#222222",
        "penwidth": "1.4",
    },
    "process": {
        "shape": "box",
        "style": "",
        "color": "#222222",
        "penwidth": "1.2",
    },
    "decision": {
        "shape": "diamond",
        "style": "",
        "color": "#222222",
        "penwidth": "1.2",
    },
    "db": {
        "shape": "box",
        "style": "",
        "color": "#222222",
        "penwidth": "1.2",
    },
    "external": {
        "shape": "box",
        "style": "",
        "color": "#222222",
        "penwidth": "1.2",
    },
}


def q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def attrs(mapping: dict[str, str]) -> str:
    return ", ".join(f"{key}={q(str(value))}" for key, value in mapping.items())


def paeth_predictor(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def png_chunks(data: bytes):
    offset = 8
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        yield kind, payload
        offset += 12 + length


def make_png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def flatten_png_to_white(path: Path) -> None:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return

    ihdr = None
    idat_parts = []
    for kind, payload in png_chunks(data):
        if kind == b"IHDR":
            ihdr = payload
        elif kind == b"IDAT":
            idat_parts.append(payload)
    if ihdr is None or not idat_parts:
        return

    width, height, bit_depth, color_type, compression, png_filter, interlace = struct.unpack(">IIBBBBB", ihdr)
    if bit_depth != 8 or color_type not in {2, 6} or compression != 0 or png_filter != 0 or interlace != 0:
        return

    channels = 4 if color_type == 6 else 3
    row_bytes = width * channels
    raw = zlib.decompress(b"".join(idat_parts))
    rows = []
    pos = 0
    prev = bytearray(row_bytes)
    for _ in range(height):
        filter_type = raw[pos]
        pos += 1
        scan = bytearray(raw[pos : pos + row_bytes])
        pos += row_bytes
        recon = bytearray(row_bytes)
        for i, value in enumerate(scan):
            left = recon[i - channels] if i >= channels else 0
            up = prev[i]
            up_left = prev[i - channels] if i >= channels else 0
            if filter_type == 0:
                recon[i] = value
            elif filter_type == 1:
                recon[i] = (value + left) & 0xFF
            elif filter_type == 2:
                recon[i] = (value + up) & 0xFF
            elif filter_type == 3:
                recon[i] = (value + ((left + up) >> 1)) & 0xFF
            elif filter_type == 4:
                recon[i] = (value + paeth_predictor(left, up, up_left)) & 0xFF
            else:
                return
        rows.append(recon)
        prev = recon

    rgb_rows = []
    for row in rows:
        rgb = bytearray()
        for x in range(width):
            i = x * channels
            r, g, b = row[i], row[i + 1], row[i + 2]
            if channels == 4:
                a = row[i + 3]
                r = (r * a + 255 * (255 - a)) // 255
                g = (g * a + 255 * (255 - a)) // 255
                b = (b * a + 255 * (255 - a)) // 255
            rgb.extend((r, g, b))
        rgb_rows.append(b"\x00" + bytes(rgb))

    new_ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    output = bytearray(b"\x89PNG\r\n\x1a\n")
    output += make_png_chunk(b"IHDR", new_ihdr)
    output += make_png_chunk(b"IDAT", zlib.compress(b"".join(rgb_rows), level=9))
    output += make_png_chunk(b"IEND", b"")
    path.write_bytes(bytes(output))


def build_dot(graph_name: str, nodes, edges, rankdir: str = "TB") -> str:
    graph_attrs = {
        "charset": "UTF-8",
        "rankdir": rankdir,
        "splines": "ortho",
        "nodesep": "0.28",
        "ranksep": "0.32",
        "dpi": "160",
        "bgcolor": "white",
        "style": "filled",
        "fillcolor": "white",
        "pad": "0.08",
        "margin": "0.04",
    }
    default_node = {
        "fontname": FONT_NAME,
        "fontsize": "12",
        "margin": "0.10,0.07",
        "fontcolor": "#222222",
    }
    default_edge = {
        "fontname": FONT_NAME,
        "fontsize": "11",
        "color": "#222222",
        "fontcolor": "#222222",
        "arrowhead": "normal",
        "arrowsize": "0.7",
        "penwidth": "1.1",
    }
    lines = [
        f"digraph {graph_name} {{",
        f"  graph [{attrs(graph_attrs)}];",
        f"  node [{attrs(default_node)}];",
        f"  edge [{attrs(default_edge)}];",
    ]
    for node_id, label, kind in nodes:
        lines.append(f"  {node_id} [label={q(label)}, {attrs(NODE_STYLES[kind])}];")
    for src, dst, label in edges:
        label_attr = f" [xlabel={q(label)}]" if label else ""
        lines.append(f"  {src} -> {dst}{label_attr};")
    lines.append("}")
    return "\n".join(lines)


def render(name: str, title: str, nodes, edges, rankdir: str = "TB") -> None:
    del title
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bw_name = name.replace("paper", "bw")
    dot_path = OUTPUT_DIR / f"{bw_name}.dot"
    png_path = OUTPUT_DIR / f"{bw_name}.png"
    dot_path.write_text(build_dot(bw_name.replace("-", "_"), nodes, edges, rankdir), encoding="utf-8")
    subprocess.run(
        [base.dot_executable(), "-Tpng", str(dot_path), "-o", str(png_path)],
        cwd=str(ROOT_DIR),
        check=True,
    )
    flatten_png_to_white(png_path)
    print(f"generated {png_path}")


def main() -> None:
    paper.charts.render = render
    paper.main()


if __name__ == "__main__":
    main()
