from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "thesis_figures"
BASE_NAME = "fig4-14-function-module-diagram"

ROOT_LABEL = "基于深度学习的\n入侵检测系统"

# 按当前项目的真实功能划分绘制系统功能模块图。
MODULES: list[tuple[str, list[str]]] = [
    ("登录与权限控制", ["用户登录", "退出登录", "角色鉴权", "菜单权限"]),
    ("系统首页", ["统计总览", "攻击分布", "趋势统计", "角色数据范围"]),
    ("上传检测", ["模型选择", "CSV上传", "后台任务", "进度查看"]),
    ("检测结果", ["结果列表", "关键字检索", "结果详情", "攻击明细", "删除记录"]),
    ("告警中心", ["告警列表", "状态筛选", "状态更新"]),
    ("网站流量巡检", ["网卡配置", "启动监测", "停止监测", "提取测试"]),
    ("模型管理", ["模型上传", "模型列表", "启用模型", "删除模型", "指标维护"]),
    ("用户管理", ["新增用户", "编辑用户", "删除用户", "角色设置"]),
]


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float
    lines: list[str]


@dataclass(frozen=True)
class ModuleBlock:
    name_box: Box
    leaf_boxes: list[Box]
    branch_x: float


@dataclass(frozen=True)
class DiagramLayout:
    width: float
    height: float
    root_box: Box
    main_branch_x: float
    blocks: list[ModuleBlock]


CANVAS_WIDTH = 920
TOP_MARGIN = 54
BOTTOM_MARGIN = 54

ROOT_X = 40
ROOT_W = 190
ROOT_H = 86
MAIN_BRANCH_X = 290

MODULE_X = 350
MODULE_W = 186
MODULE_H = 52
MODULE_BRANCH_X = 620

LEAF_X = 670
LEAF_W = 160
LEAF_H = 40
LEAF_GAP = 16
MODULE_GAP = 28

LINE_COLOR = "#666666"
BOX_COLOR = "#000000"
TEXT_COLOR = "#222222"
FILL_COLOR = "#FFFFFF"
LINE_WIDTH = 2


def wrap_text(text: str, limit: int) -> list[str]:
    if "\n" in text:
        parts: list[str] = []
        for piece in text.splitlines():
            parts.extend(wrap_text(piece, limit))
        return parts
    if len(text) <= limit:
        return [text]
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def build_layout() -> DiagramLayout:
    current_y = TOP_MARGIN
    blocks: list[ModuleBlock] = []

    for module_name, leaf_names in MODULES:
        leaf_boxes: list[Box] = []
        for index, leaf_name in enumerate(leaf_names):
            leaf_y = current_y + index * (LEAF_H + LEAF_GAP)
            leaf_boxes.append(
                Box(
                    x=LEAF_X,
                    y=leaf_y,
                    w=LEAF_W,
                    h=LEAF_H,
                    lines=wrap_text(leaf_name, 6),
                )
            )

        block_height = len(leaf_boxes) * LEAF_H + (len(leaf_boxes) - 1) * LEAF_GAP
        module_center_y = current_y + block_height / 2
        name_box = Box(
            x=MODULE_X,
            y=module_center_y - MODULE_H / 2,
            w=MODULE_W,
            h=MODULE_H,
            lines=wrap_text(module_name, 6),
        )

        blocks.append(
            ModuleBlock(
                name_box=name_box,
                leaf_boxes=leaf_boxes,
                branch_x=MODULE_BRANCH_X,
            )
        )
        current_y += block_height + MODULE_GAP

    height = current_y - MODULE_GAP + BOTTOM_MARGIN
    root_box = Box(
        x=ROOT_X,
        y=height / 2 - ROOT_H / 2,
        w=ROOT_W,
        h=ROOT_H,
        lines=wrap_text(ROOT_LABEL, 8),
    )

    return DiagramLayout(
        width=CANVAS_WIDTH,
        height=height,
        root_box=root_box,
        main_branch_x=MAIN_BRANCH_X,
        blocks=blocks,
    )


def module_center_y(block: ModuleBlock) -> float:
    return block.name_box.y + block.name_box.h / 2


def box_center_y(box: Box) -> float:
    return box.y + box.h / 2


def iter_boxes(layout: DiagramLayout) -> Iterable[Box]:
    yield layout.root_box
    for block in layout.blocks:
        yield block.name_box
        yield from block.leaf_boxes


def svg_line(x1: float, y1: float, x2: float, y2: float) -> str:
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" '
        f'x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{LINE_COLOR}" stroke-width="{LINE_WIDTH}" />'
    )


def svg_rect(box: Box) -> str:
    return (
        f'<rect x="{box.x:.1f}" y="{box.y:.1f}" '
        f'width="{box.w:.1f}" height="{box.h:.1f}" '
        f'fill="{FILL_COLOR}" stroke="{BOX_COLOR}" '
        f'stroke-width="{LINE_WIDTH}" />'
    )


def svg_text(box: Box, font_size: int) -> str:
    line_height = font_size + 8
    total_height = line_height * len(box.lines)
    start_y = box.y + (box.h - total_height) / 2 + line_height / 2
    chunks: list[str] = []
    for index, line in enumerate(box.lines):
        y = start_y + index * line_height
        chunks.append(
            f'<text x="{box.x + box.w / 2:.1f}" y="{y:.1f}" '
            f'font-family="Microsoft YaHei, SimSun, Arial, sans-serif" '
            f'font-size="{font_size}" fill="{TEXT_COLOR}" '
            f'text-anchor="middle" dominant-baseline="middle">{escape(line)}</text>'
        )
    return "\n".join(chunks)


def write_svg(layout: DiagramLayout, path: Path) -> None:
    parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{layout.width:.0f}" height="{layout.height:.0f}" '
            f'viewBox="0 0 {layout.width:.0f} {layout.height:.0f}">'
        ),
        f'<rect width="{layout.width:.0f}" height="{layout.height:.0f}" fill="{FILL_COLOR}" />',
    ]

    first_center = module_center_y(layout.blocks[0])
    last_center = module_center_y(layout.blocks[-1])
    root_center_y = box_center_y(layout.root_box)
    root_right_x = layout.root_box.x + layout.root_box.w

    parts.append(svg_line(root_right_x, root_center_y, layout.main_branch_x, root_center_y))
    parts.append(svg_line(layout.main_branch_x, first_center, layout.main_branch_x, last_center))

    for block in layout.blocks:
        center_y = module_center_y(block)
        module_left_x = block.name_box.x
        module_right_x = block.name_box.x + block.name_box.w

        parts.append(svg_line(layout.main_branch_x, center_y, module_left_x, center_y))
        parts.append(svg_line(module_right_x, center_y, block.branch_x, center_y))

        first_leaf_center = box_center_y(block.leaf_boxes[0])
        last_leaf_center = box_center_y(block.leaf_boxes[-1])
        parts.append(svg_line(block.branch_x, first_leaf_center, block.branch_x, last_leaf_center))

        for leaf_box in block.leaf_boxes:
            leaf_center = box_center_y(leaf_box)
            parts.append(svg_line(block.branch_x, leaf_center, leaf_box.x, leaf_center))

    for box in iter_boxes(layout):
        parts.append(svg_rect(box))

    parts.append(svg_text(layout.root_box, 24))
    for block in layout.blocks:
        parts.append(svg_text(block.name_box, 20))
        for leaf_box in block.leaf_boxes:
            parts.append(svg_text(leaf_box, 18))

    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def load_font(size: int):
    from PIL import ImageFont

    font_candidates = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\msyh.ttf"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
    ]
    for font_path in font_candidates:
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default()


def draw_text_centered(draw, box: Box, lines: list[str], font, fill: str, scale: int) -> None:
    line_gap = 8 * scale
    line_boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    line_heights = [bbox[3] - bbox[1] for bbox in line_boxes]
    total_height = sum(line_heights) + line_gap * (len(lines) - 1)
    current_y = box.y * scale + ((box.h * scale) - total_height) / 2

    for line, bbox, height in zip(lines, line_boxes, line_heights):
        text_width = bbox[2] - bbox[0]
        text_x = box.x * scale + ((box.w * scale) - text_width) / 2
        draw.text((text_x, current_y), line, font=font, fill=fill)
        current_y += height + line_gap


def write_png(layout: DiagramLayout, path: Path) -> bool:
    try:
        from PIL import Image, ImageDraw
    except ModuleNotFoundError:
        return False

    scale = 2
    canvas = Image.new(
        "RGB",
        (int(layout.width * scale), int(layout.height * scale)),
        FILL_COLOR,
    )
    draw = ImageDraw.Draw(canvas)
    line_width = LINE_WIDTH * scale

    def dline(x1: float, y1: float, x2: float, y2: float) -> None:
        draw.line(
            (x1 * scale, y1 * scale, x2 * scale, y2 * scale),
            fill=LINE_COLOR,
            width=line_width,
        )

    first_center = module_center_y(layout.blocks[0])
    last_center = module_center_y(layout.blocks[-1])
    root_center_y = box_center_y(layout.root_box)
    root_right_x = layout.root_box.x + layout.root_box.w

    dline(root_right_x, root_center_y, layout.main_branch_x, root_center_y)
    dline(layout.main_branch_x, first_center, layout.main_branch_x, last_center)

    for block in layout.blocks:
        center_y = module_center_y(block)
        module_left_x = block.name_box.x
        module_right_x = block.name_box.x + block.name_box.w

        dline(layout.main_branch_x, center_y, module_left_x, center_y)
        dline(module_right_x, center_y, block.branch_x, center_y)

        first_leaf_center = box_center_y(block.leaf_boxes[0])
        last_leaf_center = box_center_y(block.leaf_boxes[-1])
        dline(block.branch_x, first_leaf_center, block.branch_x, last_leaf_center)

        for leaf_box in block.leaf_boxes:
            leaf_center = box_center_y(leaf_box)
            dline(block.branch_x, leaf_center, leaf_box.x, leaf_center)

    for box in iter_boxes(layout):
        draw.rectangle(
            (
                box.x * scale,
                box.y * scale,
                (box.x + box.w) * scale,
                (box.y + box.h) * scale,
            ),
            fill=FILL_COLOR,
            outline=BOX_COLOR,
            width=line_width,
        )

    root_font = load_font(24 * scale)
    module_font = load_font(20 * scale)
    leaf_font = load_font(18 * scale)

    draw_text_centered(draw, layout.root_box, layout.root_box.lines, root_font, TEXT_COLOR, scale)
    for block in layout.blocks:
        draw_text_centered(draw, block.name_box, block.name_box.lines, module_font, TEXT_COLOR, scale)
        for leaf_box in block.leaf_boxes:
            draw_text_centered(draw, leaf_box, leaf_box.lines, leaf_font, TEXT_COLOR, scale)

    canvas.save(path, format="PNG", dpi=(300, 300))
    return True


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    layout = build_layout()

    svg_path = OUTPUT_DIR / f"{BASE_NAME}.svg"
    png_path = OUTPUT_DIR / f"{BASE_NAME}.png"

    write_svg(layout, svg_path)
    png_ok = write_png(layout, png_path)

    print(f"SVG saved to: {svg_path}")
    if png_ok:
        print(f"PNG saved to: {png_path}")
    else:
        print("PNG was skipped because Pillow is not available in this Python environment.")
    print("Suggested caption: 图4-14 系统功能模块图")


if __name__ == "__main__":
    main()
