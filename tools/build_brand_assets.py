"""Build the canonical Q.U.A.T.I. raster assets from the approved masters.

The menu keeps its approved scanner.  The access logo uses local, organic pixel
breakups and a fluid light confined to the artwork.  The loading asset uses a real
eight-pose walk cycle rather than moving an effect over a static mascot.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageSequence

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src" / "quati" / "assets"
DOC_ASSETS = ROOT / "docs" / "assets"

BLACK = (6, 8, 7)
RED = (255, 23, 56)
WHITE = (246, 248, 246)


def clean_alpha(image: Image.Image, *, floor: int = 12) -> Image.Image:
    """Remove generative haze while retaining antialiased subject edges."""
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A").point(lambda value: 0 if value <= floor else min(255, value + 1))
    rgba.putalpha(alpha)
    return rgba


def darken_outer_edge(image: Image.Image, *, radius: int = 5) -> Image.Image:
    """Replace pale premultiplied edge pixels with the logo's dark outline."""
    rgba = clean_alpha(image)
    alpha = rgba.getchannel("A")
    subject = alpha.point(lambda value: 255 if value > 22 else 0)
    interior = subject.filter(ImageFilter.MinFilter(radius))
    outer_edge = ImageChops.subtract(subject, interior)
    color = rgba.convert("RGB")
    color.paste(BLACK, mask=outer_edge)
    cleaned = color.convert("RGBA")
    cleaned.putalpha(alpha.point(lambda value: 0 if value <= 22 else value))
    return cleaned


def crop_alpha(image: Image.Image, *, padding: int = 0, threshold: int = 16) -> Image.Image:
    alpha = image.getchannel("A").point(lambda value: 255 if value > threshold else 0)
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError("Asset sem conteúdo visível.")
    left = max(0, bbox[0] - padding)
    top = max(0, bbox[1] - padding)
    right = min(image.width, bbox[2] + padding)
    bottom = min(image.height, bbox[3] + padding)
    return image.crop((left, top, right, bottom))


def fit_on_canvas(
    image: Image.Image,
    canvas_size: tuple[int, int],
    content_size: tuple[int, int],
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    source = image.copy()
    source.thumbnail(content_size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    x = (canvas_size[0] - source.width) // 2
    y = (canvas_size[1] - source.height) // 2
    canvas.alpha_composite(source, (x, y))
    return canvas, (x, y, x + source.width, y + source.height)


def draw_target_corners(
    layer: Image.Image,
    bbox: tuple[int, int, int, int],
    *,
    alpha: int,
    scale: int,
) -> None:
    draw = ImageDraw.Draw(layer)
    left, top, right, bottom = bbox
    inset = max(4, scale * 2)
    length = max(12, scale * 7)
    width = max(2, scale)
    corners = (
        ((left - inset, top - inset), (1, 1)),
        ((right + inset, top - inset), (-1, 1)),
        ((left - inset, bottom + inset), (1, -1)),
        ((right + inset, bottom + inset), (-1, -1)),
    )
    color = (*RED, alpha)
    for (x, y), (dx, dy) in corners:
        draw.line((x, y, x + dx * length, y), fill=color, width=width)
        draw.line((x, y, x, y + dy * length), fill=color, width=width)
        draw.rectangle(
            (x - width, y - width, x + width, y + width),
            fill=(*RED, min(255, alpha + 35)),
        )


def add_scanner(
    base: Image.Image,
    bbox: tuple[int, int, int, int],
    *,
    progress: float,
    frame_index: int,
    orientation: str,
) -> Image.Image:
    frame = base.copy()
    subject_alpha = base.getchannel("A")
    left, top, right, bottom = bbox
    width = right - left
    height = bottom - top
    scale = max(1, round(min(base.size) / 260))

    # Both ends of the cycle are visually neutral, making the loop seamless.
    visibility = math.sin(math.pi * progress) ** 0.75
    target = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw_target_corners(
        target,
        bbox,
        alpha=round(130 * visibility),
        scale=scale,
    )
    frame = Image.alpha_composite(frame, target)

    glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    core = Image.new("RGBA", base.size, (0, 0, 0, 0))
    core_draw = ImageDraw.Draw(core)
    tint = Image.new("RGBA", base.size, (0, 0, 0, 0))
    tint_alpha = Image.new("L", base.size, 0)
    tint_draw = ImageDraw.Draw(tint_alpha)

    if orientation == "vertical":
        position = round((left - width * 0.10) + progress * (width * 1.20))
        glow_draw.line(
            (position, top - 8, position, bottom + 8),
            fill=(*RED, round(190 * visibility)),
            width=scale * 5,
        )
        core_draw.line(
            (position, top - 5, position, bottom + 5),
            fill=(255, 236, 239, round(245 * visibility)),
            width=max(1, scale),
        )
        tint_draw.rectangle(
            (position - scale * 10, top, position + scale * 10, bottom),
            fill=round(155 * visibility),
        )
        particle_axis = position
    else:
        position = round((top - height * 0.10) + progress * (height * 1.20))
        glow_draw.line(
            (left - 8, position, right + 8, position),
            fill=(*RED, round(190 * visibility)),
            width=scale * 5,
        )
        core_draw.line(
            (left - 5, position, right + 5, position),
            fill=(255, 236, 239, round(245 * visibility)),
            width=max(1, scale),
        )
        tint_draw.rectangle(
            (left, position - scale * 10, right, position + scale * 10),
            fill=round(155 * visibility),
        )
        particle_axis = position

    glow = glow.filter(ImageFilter.GaussianBlur(radius=max(3, scale * 4)))
    clipped_tint = ImageChops.multiply(tint_alpha, subject_alpha)
    tint.paste((*RED, 0), (0, 0, *base.size))
    tint.putalpha(clipped_tint)
    frame = Image.alpha_composite(frame, glow)
    frame = Image.alpha_composite(frame, tint)
    frame = Image.alpha_composite(frame, core)

    particles = Image.new("RGBA", base.size, (0, 0, 0, 0))
    particle_draw = ImageDraw.Draw(particles)
    for index in range(7):
        phase = (frame_index * 3 + index * 11) % 29
        if phase not in {2, 3, 7, 13, 17, 23}:
            continue
        size = scale * (1 if index % 3 else 2)
        if orientation == "vertical":
            x = particle_axis + (index % 3 - 1) * scale * 8
            y = top + ((index * 47 + frame_index * 19) % max(1, height))
        else:
            x = left + ((index * 61 + frame_index * 23) % max(1, width))
            y = particle_axis + (index % 3 - 1) * scale * 8
        particle_draw.rectangle((x, y, x + size, y + size), fill=(*RED, 190))
    return Image.alpha_composite(frame, particles)


def add_internal_flow(
    base: Image.Image,
    *,
    frame_index: int,
    frame_count: int,
) -> Image.Image:
    """Move soft psychedelic ribbons only through the opaque white artwork."""
    progress = frame_index / frame_count
    luminance = base.convert("L")
    white_areas = luminance.point(
        lambda value: 0 if value < 105 else min(255, round((value - 105) * 1.7))
    )
    internal_mask = ImageChops.multiply(white_areas, base.getchannel("A"))
    ribbons = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(ribbons)
    palette = (
        (255, 22, 67, 118),
        (96, 226, 255, 86),
        (210, 55, 255, 78),
    )
    amplitude = max(16, round(base.height * 0.10))
    for band, color in enumerate(palette):
        phase = progress * math.tau + band * 2.05
        center = base.height * (0.46 + 0.24 * math.sin(phase))
        points = []
        for x in range(-30, base.width + 31, 12):
            flow = math.sin(x * 0.034 + phase * (1.2 + band * 0.12))
            points.append((x, round(center + flow * amplitude)))
        draw.line(
            points,
            fill=color,
            width=max(15, round(base.height * (0.055 + band * 0.012))),
            joint="curve",
        )
    ribbons = ribbons.filter(ImageFilter.GaussianBlur(max(8, base.height // 42)))
    ribbon_alpha = ImageChops.multiply(ribbons.getchannel("A"), internal_mask)
    ribbons.putalpha(ribbon_alpha)
    return Image.alpha_composite(base, ribbons)


def add_organic_pixels(
    base: Image.Image,
    *,
    frame_index: int,
    frame_count: int,
) -> Image.Image:
    """Displace short-lived pixel clusters that quickly settle back into place."""
    frame = base.copy()
    alpha = base.getchannel("A")
    bbox = alpha.point(lambda value: 255 if value > 32 else 0).getbbox()
    if bbox is None:
        return frame
    left, top, right, bottom = bbox
    width = right - left
    height = bottom - top
    events = (
        (0.16, 0.24, 1, 1),
        (0.78, 0.18, 5, -1),
        (0.34, 0.46, 9, -1),
        (0.67, 0.39, 13, 1),
        (0.21, 0.67, 17, 1),
        (0.52, 0.61, 21, -1),
        (0.82, 0.73, 25, 1),
        (0.39, 0.84, 29, -1),
    )
    cadence = (0.32, 1.0, 0.62, 0.18)
    for event_index, (fx, fy, start, direction) in enumerate(events):
        age = (frame_index - start) % frame_count
        if age >= len(cadence):
            continue
        strength = cadence[age]
        unit = 3 + event_index % 3
        center_x = round(left + fx * width)
        center_y = round(top + fy * height)
        for fragment in range(3):
            fragment_width = unit * (1 + (fragment + event_index) % 2)
            fragment_height = unit * (1 + fragment % 2)
            source_x = center_x + (fragment - 1) * unit * 2
            source_y = center_y + ((fragment + event_index) % 3 - 1) * unit
            box = (
                source_x,
                source_y,
                source_x + fragment_width,
                source_y + fragment_height,
            )
            piece = base.crop(box)
            if not piece.getchannel("A").getbbox():
                continue
            ImageDraw.Draw(frame).rectangle(box, fill=(0, 0, 0, 0))
            offset_x = round(direction * (3 + fragment * 2) * strength)
            offset_y = round((fragment - 1) * 2 * strength)
            frame.alpha_composite(piece, (source_x + offset_x, source_y + offset_y))

            accent = Image.new("RGBA", piece.size, (0, 0, 0, 0))
            accent_alpha = piece.getchannel("A").point(
                lambda value, strength=strength: round(value * 0.46 * strength)
            )
            accent_color = (255, 23, 56) if fragment != 1 else (86, 224, 255)
            accent.paste((*accent_color, 0), (0, 0, *piece.size))
            accent.putalpha(accent_alpha)
            frame.alpha_composite(
                accent,
                (source_x - offset_x, source_y - offset_y),
            )
    return frame


def gif_frame(image: Image.Image) -> Image.Image:
    """Quantize one RGBA frame while reserving palette index 255 for transparency."""
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    rgb = Image.new("RGB", rgba.size, BLACK)
    rgb.paste(rgba.convert("RGB"), mask=alpha)
    paletted = rgb.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    palette = paletted.getpalette() or []
    palette = (palette + [0] * 768)[:768]
    palette[255 * 3 : 255 * 3 + 3] = [0, 0, 0]
    paletted.putpalette(palette)
    transparent = alpha.point(lambda value: 255 if value <= 18 else 0)
    paletted.paste(255, mask=transparent)
    paletted.info["transparency"] = 255
    return paletted


def build_scan_gif(
    source: Image.Image,
    destination: Path,
    *,
    canvas_size: tuple[int, int],
    content_size: tuple[int, int],
    orientation: str,
    frame_count: int = 28,
    duration: int = 65,
) -> None:
    base, bbox = fit_on_canvas(
        crop_alpha(clean_alpha(source), padding=6), canvas_size, content_size
    )
    frames = [
        gif_frame(
            add_scanner(
                base,
                bbox,
                progress=index / (frame_count - 1),
                frame_index=index,
                orientation=orientation,
            )
        )
        for index in range(frame_count)
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        destination,
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=duration,
        disposal=2,
        transparency=255,
        optimize=False,
    )


def build_organic_start_gif(
    source: Image.Image,
    destination: Path,
    *,
    frame_count: int = 32,
    duration: int = 70,
) -> None:
    subject = crop_alpha(darken_outer_edge(source), padding=3)
    base, _ = fit_on_canvas(subject, (480, 460), (430, 418))
    rgba_frames = []
    for index in range(frame_count):
        lit = add_internal_flow(base, frame_index=index, frame_count=frame_count)
        rgba_frames.append(
            add_organic_pixels(lit, frame_index=index, frame_count=frame_count)
        )
    frames = [gif_frame(frame) for frame in rgba_frames]
    frames[0].save(
        destination,
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=duration,
        disposal=2,
        transparency=255,
        optimize=False,
    )


def remove_light_grid_background(image: Image.Image) -> Image.Image:
    """Extract outlined sprites from a generated light checkerboard background."""
    rgba = image.convert("RGBA")
    if rgba.getchannel("A").getextrema()[0] < 255:
        return darken_outer_edge(rgba, radius=3)

    luminance = rgba.convert("L")
    barriers = luminance.point(lambda value: 255 if value < 185 else 0)
    barriers = barriers.filter(ImageFilter.MaxFilter(3))
    flooded = barriers.copy()
    ImageDraw.floodfill(flooded, (0, 0), 128, thresh=0)
    background = flooded.point(lambda value: 255 if value == 128 else 0)
    subject_alpha = ImageChops.invert(background).filter(ImageFilter.GaussianBlur(0.55))
    subject_alpha = subject_alpha.point(
        lambda value: 0 if value < 24 else 255 if value > 232 else value
    )
    extracted = rgba.copy()
    extracted.putalpha(subject_alpha)
    return darken_outer_edge(extracted, radius=3)


def build_walking_gif(
    source_frames: list[Image.Image],
    destination: Path,
    *,
    duration: int = 110,
) -> None:
    if len(source_frames) != 8:
        raise ValueError("O ciclo de caminhada precisa ter exatamente oito poses.")

    cleaned = [remove_light_grid_background(frame) for frame in source_frames]
    union_alpha = Image.new("L", cleaned[0].size, 0)
    for frame in cleaned:
        union_alpha = ImageChops.lighter(union_alpha, frame.getchannel("A"))
    bbox = union_alpha.point(lambda value: 255 if value > 24 else 0).getbbox()
    if bbox is None:
        raise ValueError("O ciclo de caminhada não contém desenho visível.")

    left = max(0, bbox[0] - 5)
    top = max(0, bbox[1] - 5)
    right = min(cleaned[0].width, bbox[2] + 5)
    bottom = min(cleaned[0].height, bbox[3] + 5)
    cycle_width = right - left
    cycle_height = bottom - top
    scale = min(320 / cycle_width, 196 / cycle_height)
    rendered_size = (round(cycle_width * scale), round(cycle_height * scale))

    frames: list[Image.Image] = []
    for frame in cleaned:
        pose = frame.crop((left, top, right, bottom)).resize(
            rendered_size,
            Image.Resampling.LANCZOS,
        )
        canvas = Image.new("RGBA", (360, 250), (0, 0, 0, 0))
        x = (canvas.width - pose.width) // 2
        y = (canvas.height - pose.height) // 2
        canvas.alpha_composite(pose, (x, y))
        frames.append(gif_frame(canvas))

    frames[0].save(
        destination,
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=duration,
        disposal=2,
        transparency=255,
        optimize=False,
    )


def square_icon(source: Image.Image, size: int) -> Image.Image:
    subject = crop_alpha(clean_alpha(source), padding=20)
    subject.thumbnail((round(size * 0.82), round(size * 0.82)), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(subject, ((size - subject.width) // 2, (size - subject.height) // 2))
    return canvas


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        "C:/Windows/Fonts/consolab.ttf",
        "C:/Windows/Fonts/consola.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "DejaVuSansMono-Bold.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def build_social_preview(horizontal: Image.Image) -> None:
    canvas = Image.new("RGB", (1280, 640), BLACK)
    draw = ImageDraw.Draw(canvas)
    for y in range(0, canvas.height, 4):
        draw.line((0, y, canvas.width, y), fill=(12, 15, 13))
    draw.rectangle((0, 0, 18, canvas.height), fill=RED)
    draw.rectangle((1262, 0, 1279, canvas.height), fill=RED)
    draw.rectangle((50, 46, 1230, 594), outline=(68, 18, 28), width=2)

    logo = crop_alpha(clean_alpha(horizontal), padding=8)
    logo.thumbnail((980, 310), Image.Resampling.LANCZOS)
    logo_x = (canvas.width - logo.width) // 2
    logo_y = 112
    canvas.paste(logo.convert("RGB"), (logo_x, logo_y), logo.getchannel("A"))

    tagline = "BUSCA LOCAL DE VAGAS PUBLICAS NO BRASIL"
    status = "[ OPEN SOURCE ]   [ PRIVACIDADE LOCAL ]   [ CANDIDATURA SOB SEU CONTROLE ]"
    tagline_font = font(31)
    status_font = font(18)
    tagline_box = draw.textbbox((0, 0), tagline, font=tagline_font)
    status_box = draw.textbbox((0, 0), status, font=status_font)
    draw.text(
        ((canvas.width - (tagline_box[2] - tagline_box[0])) // 2, 455),
        tagline,
        font=tagline_font,
        fill=WHITE,
    )
    draw.text(
        ((canvas.width - (status_box[2] - status_box[0])) // 2, 522),
        status,
        font=status_font,
        fill=RED,
    )
    DOC_ASSETS.mkdir(parents=True, exist_ok=True)
    canvas.save(DOC_ASSETS / "github-social-preview.png", optimize=True)


def main() -> None:
    icon_master = clean_alpha(Image.open(ASSETS / "quati-icon-master.png"))
    horizontal_master = clean_alpha(Image.open(ASSETS / "quati-horizontal-master.png"))
    mascot_master = clean_alpha(Image.open(ASSETS / "quati-mascot-master.png"))
    with Image.open(ASSETS / "quati-walk-master.gif") as walk_animation:
        walk_frames = [frame.convert("RGBA") for frame in ImageSequence.Iterator(walk_animation)]
    with Image.open(ASSETS / "quati-inicio-master.gif") as initial_gif:
        initial_master = initial_gif.seek(0) or initial_gif.convert("RGBA")

    approved_icon = square_icon(icon_master, 1024)
    approved_icon.save(ASSETS / "quati-icon-approved.png", optimize=True)
    icon = square_icon(icon_master, 512)
    icon.save(ASSETS / "quati-icon.png", optimize=True)
    icon.save(
        ASSETS / "quati-icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    horizontal = crop_alpha(horizontal_master, padding=24)
    horizontal.thumbnail((1800, 600), Image.Resampling.LANCZOS)
    horizontal.save(ASSETS / "quati-horizontal-white.png", optimize=True)

    mascot = crop_alpha(mascot_master, padding=24)
    mascot.thumbnail((1200, 800), Image.Resampling.LANCZOS)
    mascot.save(ASSETS / "quati-mascot.png", optimize=True)

    build_scan_gif(
        horizontal,
        ASSETS / "quati-menu-scan.gif",
        canvas_size=(720, 240),
        content_size=(650, 176),
        orientation="vertical",
    )
    build_organic_start_gif(
        initial_master,
        ASSETS / "quati-inicio-scan.gif",
    )
    build_scan_gif(
        mascot,
        ASSETS / "quati-solo-scan.gif",
        canvas_size=(640, 420),
        content_size=(566, 350),
        orientation="vertical",
    )
    build_walking_gif(walk_frames, ASSETS / "quati-loading.gif")
    build_social_preview(horizontal)


if __name__ == "__main__":
    main()
