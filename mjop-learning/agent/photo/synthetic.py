"""Synthetische testgevel (geen echte foto): deterministische tekening met bekende grondwaarheid.
Alleen voor demo en tests; Pillow wordt pas bij het renderen geimporteerd."""
import io

from agent.photo.contract import sha256_bytes

W, H = 640, 480

# Grondwaarheid van de synthetische gevel (genormaliseerde bbox, [x1,y1,x2,y2]).
GROUND_TRUTH = [
    {"gt_id": "S-RW1", "element_type": "ROOF_WINDOW", "bbox_norm": [0.42, 0.06, 0.50, 0.16], "visibility": "FULL", "parts": 1},
    {"gt_id": "S-W1", "element_type": "WINDOW_OPENING", "bbox_norm": [0.08, 0.25, 0.22, 0.42], "visibility": "FULL", "parts": 2},
    {"gt_id": "S-W2", "element_type": "WINDOW_OPENING", "bbox_norm": [0.30, 0.25, 0.44, 0.42], "visibility": "FULL", "parts": 1},
    {"gt_id": "S-W3", "element_type": "WINDOW_OPENING", "bbox_norm": [0.54, 0.25, 0.68, 0.42], "visibility": "FULL", "parts": 1},
    {"gt_id": "S-W4", "element_type": "WINDOW_OPENING", "bbox_norm": [0.76, 0.25, 0.84, 0.42], "visibility": "PARTIAL", "parts": 1},
    {"gt_id": "S-W5", "element_type": "WINDOW_OPENING", "bbox_norm": [0.08, 0.55, 0.22, 0.72], "visibility": "FULL", "parts": 1},
    {"gt_id": "S-W6", "element_type": "WINDOW_OPENING", "bbox_norm": [0.54, 0.55, 0.68, 0.72], "visibility": "OCCLUDED", "parts": 1},
    {"gt_id": "S-D1", "element_type": "EXTERIOR_DOOR", "bbox_norm": [0.30, 0.52, 0.44, 0.90], "visibility": "FULL", "parts": 1},
]


def _px(box):
    return [round(box[0] * W), round(box[1] * H), round(box[2] * W), round(box[3] * H)]


def render():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), (176, 98, 78))                    # baksteen
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, round(0.20 * H)], fill=(70, 70, 78))        # dakvlak
    for y in range(round(0.22 * H), H, 12):                           # metselwerkvoegen
        d.line([0, y, W, y], fill=(150, 80, 62))
    for g in GROUND_TRUTH:
        x1, y1, x2, y2 = _px(g["bbox_norm"])
        if g["element_type"] == "EXTERIOR_DOOR":
            d.rectangle([x1, y1, x2, y2], fill=(38, 58, 92))
            d.rectangle([x1 + 6, y1 + 6, x2 - 6, y1 + 40], fill=(150, 190, 215))
        elif g["element_type"] == "ROOF_WINDOW":
            d.rectangle([x1, y1, x2, y2], fill=(235, 235, 235))
            d.rectangle([x1 + 3, y1 + 3, x2 - 3, y2 - 3], fill=(150, 190, 215))
        else:
            d.rectangle([x1, y1, x2, y2], fill=(240, 240, 240))
            d.rectangle([x1 + 4, y1 + 4, x2 - 4, y2 - 4], fill=(150, 190, 215))
            if g["parts"] == 2:                                       # twee draaiende delen in EEN opening
                xm = (x1 + x2) // 2
                d.line([xm, y1 + 4, xm, y2 - 4], fill=(240, 240, 240), width=5)
    d.rectangle([round(0.84 * W), round(0.20 * H), W, round(0.52 * H)], fill=(46, 112, 58))      # boom naast venster 4
    d.rectangle([round(0.50 * W), round(0.56 * H), round(0.72 * W), round(0.78 * H)], fill=(52, 120, 64))  # haag voor venster 6
    return img


def png_bytes(img=None):
    img = img or render()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def pixel_sha256(img):
    return sha256_bytes(img.convert("RGB").tobytes())


def model_like_recording(derivative_sha256):
    """Gemockt 'modelantwoord' (ReplayProvider-opname): kleine afwijkingen, een gemist dakraam, een onterecht voorstel,
    de twee draaiende delen als EEN opening (parts_visible=2). Bewust handgeschreven, geen willekeur."""
    def j(box, dx=0.004, dy=-0.003):
        return [round(box[0] + dx, 4), round(box[1] + dy, 4), round(box[2] + dx, 4), round(box[3] + dy, 4)]
    gt = {g["gt_id"]: g for g in GROUND_TRUTH}
    prop = []
    for gid, unc in (("S-W1", []), ("S-W2", []), ("S-W3", []), ("S-W4", [{"code": "OCCLUDED_BY_VEGETATION", "level": "MEDIUM"}]),
                     ("S-W5", []), ("S-W6", [{"code": "OCCLUDED_BY_VEGETATION", "level": "HIGH"}]), ("S-D1", [])):
        g = gt[gid]
        row = {"element_type": g["element_type"], "bbox_norm": j(g["bbox_norm"]), "visibility": g["visibility"],
               "uncertainties": unc, "observation": {"WINDOW_OPENING": "kozijnopening met glas", "EXTERIOR_DOOR": "buitendeur"}[g["element_type"]]}
        if g["parts"] > 1:
            row["parts_visible"] = g["parts"]
        prop.append(row)
    prop.append({"element_type": "UNKNOWN_OPENING", "bbox_norm": [0.60, 0.80, 0.66, 0.86], "visibility": "PARTIAL",
                 "uncertainties": [{"code": "AMBIGUOUS_TYPE", "level": "HIGH"}], "observation": "mogelijke opening, type onduidelijk"})
    return {derivative_sha256: {"proposals": prop, "hidden_element_hypotheses": [
        {"element_type": "WINDOW_OPENING", "reason": "begane grond links is niet zichtbaar; mogelijk een opening achter de gevel"}]}}
