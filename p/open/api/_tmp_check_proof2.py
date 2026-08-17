import glob, os
from rapidocr_onnxruntime import RapidOCR
ocr = RapidOCR()
d = r"E:\AI24X\ai24x-website\ai24x01\ops\creem-proof-www-20260807_check"
for name in ["proof-www-pricing-20260807.jpg", "proof-www-console-20260807.png", "proof-www-guides-20260807.png"]:
    f = os.path.join(d, name)
    res, _ = ocr(f)
    txt = " | ".join(r[1] for r in res[:20]) if res else "(no text)"
    print("=====", name)
    print(txt[:600])