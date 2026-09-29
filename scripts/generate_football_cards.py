import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
out_dir = ROOT / "output" / "de_fussball_30_v2" / "cards"


players = [
    {
        "id": "q01_ronaldo",
        "name": "CRISTIANO RONALDO",
        "nat": "PORTUGAL 🇵🇹",
        "pos": "ST",
        "num": "7",
        "clue": "Über 900 Karrieretore",
        "accent": (231, 76, 60),
    },
    {
        "id": "q02_messi",
        "name": "LIONEL MESSI",
        "nat": "ARGENTINIEN 🇦🇷",
        "pos": "RF",
        "num": "10",
        "clue": "Weltmeister & 8x Ballon d'Or",
        "accent": (52, 152, 219),
    },
    {
        "id": "q03_mbappe",
        "name": "KYLIAN MBAPPÉ",
        "nat": "FRANKREICH 🇫🇷",
        "pos": "LF/ST",
        "num": "9",
        "clue": "WM-Torschützenkönig",
        "accent": (41, 128, 185),
    },
    {
        "id": "q04_haaland",
        "name": "ERLING HAALAND",
        "nat": "NORWEGEN 🇳🇴",
        "pos": "ST",
        "num": "9",
        "clue": "Premier League Rekord 36 Tore",
        "accent": (46, 204, 113),
    },
    {
        "id": "q06_neymar",
        "name": "NEYMAR JR.",
        "nat": "BRASILIEN 🇧🇷",
        "pos": "LF/OM",
        "num": "10",
        "clue": "Samba-Dribbler",
        "accent": (241, 196, 15),
    },
    {
        "id": "q08_neuer",
        "name": "MANUEL NEUER",
        "nat": "DEUTSCHLAND 🇩🇪",
        "pos": "TW",
        "num": "1",
        "clue": "Welttorhüter & Rekordsieger",
        "accent": (230, 126, 34),
    },
    {
        "id": "q11_kimmich",
        "name": "JOSHUA KIMMICH",
        "nat": "DEUTSCHLAND 🇩🇪",
        "pos": "RV/ZM",
        "num": "6",
        "clue": "Leipzig zu Bayern München",
        "accent": (231, 76, 60),
    },
    {
        "id": "q15_gnabry",
        "name": "SERGE GNABRY",
        "nat": "DEUTSCHLAND 🇩🇪",
        "pos": "RA/LA",
        "num": "7",
        "clue": "Cooking-Jubel • Arsenal zu Bayern",
        "accent": (155, 89, 182),
    },
]

def get_f(sz, bold=True):
    for f_cand in ["arialbd.ttf", "segoeuib.ttf", "calibrib.ttf", "arial.ttf"]:
        try:
            return ImageFont.truetype(f_cand, sz)
        except Exception:
            pass
    return ImageFont.load_default()

def nationality_text(value):
    return "".join(c for c in value if not 0x1F1E6 <= ord(c) <= 0x1F1FF).strip()


def render_photo_reveal(p, photo_path, credit):
    """Require a real supplied portrait; never silently substitute a text card."""
    with Image.open(photo_path) as source:
        portrait = ImageOps.fit(source.convert("RGB"), (216, 290), centering=(0.5, 0.25))
    image = Image.new("RGBA", (580, 360), (15, 25, 45, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((3, 3, 576, 356), radius=20, outline=(46, 204, 113), width=4)
    image.paste(portrait, (16, 16))
    draw.rounded_rectangle((250, 20, 560, 60), radius=10, fill=(46, 204, 113))
    draw.line([(264, 39), (272, 47), (288, 31)], fill="white", width=5)
    draw.text((303, 40), "RICHTIG!", font=get_f(23), fill="white", anchor="lm")
    words = p["name"].split()
    draw.text((250, 98), " ".join(words[:-1]), font=get_f(27), fill=(255, 215, 0), anchor="lm")
    draw.text((250, 135), words[-1], font=get_f(33), fill=(255, 215, 0), anchor="lm")
    draw.text((250, 188), nationality_text(p["nat"]), font=get_f(23), fill="white", anchor="lm")
    draw.text((250, 223), f"#{p['num']}  |  {p['pos']}", font=get_f(24), fill=(80, 220, 180), anchor="lm")
    # Nationality is spelled out rather than rendered as unsupported flag emoji.
    clue_font = get_f(20)
    size = 20
    while draw.textbbox((0, 0), p["clue"], font=clue_font)[2] > 308 and size > 10:
        size -= 1
        clue_font = get_f(size)
    draw.text((250, 273), p["clue"], font=clue_font, fill="white", anchor="lm")
    draw.text((18, 330), credit, font=get_f(12), fill=(195, 205, 220), anchor="lm")
    return image


def generate_card(p, out_dir, photo_path=None, credit=""):
    # Complete portrait validation before writing either asset.
    reveal = render_photo_reveal(p, photo_path, credit) if photo_path else None
    out_dir.mkdir(parents=True, exist_ok=True)
    num_str = "#" + p["num"]
    pos_str = f"[ {p['pos']} ]"
    clue_str = p["clue"]
    
    # 1. Silhouette Card (Question Clue)
    img_q = Image.new("RGBA", (580, 360), (0, 0, 0, 0))
    d_q = ImageDraw.Draw(img_q)
    
    # Outer Card
    d_q.rounded_rectangle([4, 4, 576, 356], radius=24, fill=(15, 20, 35), outline=p["accent"], width=4)
    # Inner Glass
    d_q.rounded_rectangle([16, 16, 564, 344], radius=18, fill=(22, 30, 52), outline=(255, 255, 255, 30), width=2)
    
    # Top Left: Jersey Number
    d_q.rounded_rectangle([30, 30, 110, 95], radius=12, fill=p["accent"], outline=(255, 255, 255), width=2)
    d_q.text((70, 62), num_str, font=get_f(34, True), fill=(255, 255, 255), anchor="mm")
    
    # Top Right: Position Tag
    d_q.rounded_rectangle([450, 30, 550, 80], radius=12, fill=(35, 48, 80), outline=(255, 215, 0), width=2)
    d_q.text((500, 55), pos_str, font=get_f(22, True), fill=(255, 215, 0), anchor="mm")
    
    # Center Silhouette Art
    cx, cy = 290, 175
    for r in range(80, 40, -10):
        d_q.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*p["accent"][:3], 25))
    d_q.ellipse([cx - 50, cy - 50, cx + 50, cy + 50], fill=(28, 38, 65), outline=(255, 255, 255), width=3)
    d_q.text((cx, cy), "?", font=get_f(64, True), fill=(255, 215, 0), anchor="mm")
    
    # Nationality Tag
    d_q.rounded_rectangle([140, 235, 440, 275], radius=10, fill=(30, 40, 68), outline=(255, 255, 255, 60), width=1)
    d_q.text((290, 255), nationality_text(p["nat"]), font=get_f(20, True), fill=(240, 240, 255), anchor="mm")
    
    # Clue Banner at Bottom
    d_q.rounded_rectangle([30, 288, 550, 336], radius=14, fill=p["accent"], outline=(255, 255, 255), width=2)
    d_q.text((290, 312), clue_str, font=get_f(20, True), fill=(255, 255, 255), anchor="mm")
    
    p_q_path = out_dir / f"{p['id']}_card_clue.png"
    img_q.save(p_q_path)
    
    # 2. Reveal Card (Answer Revealed)
    img_a = Image.new("RGBA", (580, 360), (0, 0, 0, 0))
    d_a = ImageDraw.Draw(img_a)
    
    # Outer Green / Golden Border
    d_a.rounded_rectangle([4, 4, 576, 356], radius=24, fill=(15, 25, 45), outline=(46, 204, 113), width=5)
    d_a.rounded_rectangle([16, 16, 564, 344], radius=18, fill=(20, 35, 60), outline=(255, 215, 0), width=2)
    
    # Jersey & Pos
    d_a.rounded_rectangle([30, 30, 110, 95], radius=12, fill=(46, 204, 113), outline=(255, 255, 255), width=2)
    d_a.text((70, 62), num_str, font=get_f(34, True), fill=(255, 255, 255), anchor="mm")
    
    d_a.rounded_rectangle([450, 30, 550, 80], radius=12, fill=(46, 204, 113), outline=(255, 255, 255), width=2)
    d_a.text((500, 55), pos_str, font=get_f(22, True), fill=(255, 215, 0), anchor="mm")
    
    # Center Confirmed Icon
    d_a.ellipse([cx - 50, cy - 50, cx + 50, cy + 50], fill=(46, 204, 113), outline=(255, 255, 255), width=3)
    d_a.line([(cx - 24, cy), (cx - 5, cy + 20), (cx + 28, cy - 24)], fill=(255, 255, 255), width=8)
    
    # Player Full Name (Golden bold)
    d_a.rounded_rectangle([50, 230, 530, 280], radius=12, fill=(28, 42, 75), outline=(255, 215, 0), width=2)
    d_a.text((290, 255), p["name"], font=get_f(26, True), fill=(255, 215, 0), anchor="mm")
    
    # Nationality + Clue
    d_a.rounded_rectangle([30, 290, 550, 336], radius=14, fill=(46, 204, 113), outline=(255, 255, 255), width=2)
    d_a.text((290, 313), f"{nationality_text(p['nat'])} · {p['clue']}", font=get_f(19, True), fill=(255, 255, 255), anchor="mm")
    
    p_a_path = out_dir / f"{p['id']}_reveal.png"
    (reveal if reveal is not None else img_a).save(p_a_path)
    return p_q_path, p_a_path

def main():
    parser = argparse.ArgumentParser(description="Generate football clue/reveal cards")
    parser.add_argument("--output-dir", type=Path, default=out_dir)
    parser.add_argument("--player", choices=[p["id"] for p in players])
    parser.add_argument("--photo", type=Path)
    parser.add_argument("--credit", default="")
    args = parser.parse_args()
    if args.photo and (not args.player or not args.credit):
        parser.error("--photo requires --player and --credit")
    for p in players:
        if not args.player or args.player == p["id"]:
            print(generate_card(p, args.output_dir, args.photo, args.credit))


if __name__ == "__main__":
    main()
