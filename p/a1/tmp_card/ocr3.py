import sys
from rapidocr_onnxruntime import RapidOCR
engine = RapidOCR()
for path in sys.argv[1:]:
    print("FILE:", path.split('/')[-1])
    res, _ = engine(path)
    if not res:
        print("  (no text)"); continue
    for box, text, score in res:
        xs = [p[0] for p in box]; ys = [p[1] for p in box]
        print("  [%4d,%4d] %s" % (int(min(xs)), int(min(ys)), text))
