"""Duplicate / same-asset matching (the same defect photographed on consecutive daily patrols).
Proxy protocol: each query is a re-capture simulation of a gallery image (crop, rotation, scale, lighting
change) – the model must retrieve its source among 300 railway images. Models: DINOv2-small (Apache-2.0),
SigLIP base (Apache-2.0). Metric: Recall@1, Recall@5. Field re-captures needed to confirm."""
import os
import time

import albumentations as A
import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModel, SiglipModel, SiglipProcessor

from common import write_report
from datasets import find_images, mendeley_rail_defects

N = int(os.environ.get("DEDUP_N", 300))
RECAP = A.Compose([A.RandomResizedCrop(size=(448, 448), scale=(0.6, 0.9), p=1), A.Rotate(limit=12, p=1),
                   A.RandomBrightnessContrast(0.25, 0.25, p=1)], seed=0)


def embed_fn(mid):
    if "siglip" in mid:
        p, m = SiglipProcessor.from_pretrained(mid), SiglipModel.from_pretrained(mid).eval()
        return lambda ims: m.get_image_features(**p(images=ims, return_tensors="pt"))
    p, m = AutoImageProcessor.from_pretrained(mid), AutoModel.from_pretrained(mid).eval()
    return lambda ims: m(**p(images=ims, return_tensors="pt")).pooler_output


def main():
    paths = find_images(mendeley_rail_defects(), N)
    gal = [Image.open(p).convert("RGB") for p in paths]
    qry = [Image.fromarray(RECAP(image=np.array(g))["image"]) for g in gal]
    rows = []
    for mid in ("facebook/dinov2-small", "google/siglip-base-patch16-224"):
        f = embed_fn(mid)
        with torch.no_grad():
            t = time.perf_counter()
            G = torch.cat([f(gal[i:i + 16]) for i in range(0, len(gal), 16)])
            Q = torch.cat([f(qry[i:i + 16]) for i in range(0, len(qry), 16)])
            dt = (time.perf_counter() - t) / (2 * len(gal))
        G, Q = torch.nn.functional.normalize(G, dim=1), torch.nn.functional.normalize(Q, dim=1)
        rank = (Q @ G.T).argsort(dim=1, descending=True)
        target = torch.arange(len(gal)).unsqueeze(1)
        rows.append({"model": mid, "gallery": len(gal), "recall@1": float((rank[:, :1] == target).any(1).float().mean()),
                     "recall@5": float((rank[:, :5] == target).any(1).float().mean()), "sec_per_image_cpu": dt})
    write_report("dedup", "Same-asset re-identification for duplicate suppression", "Synthetic re-captures of Indian railway images.", rows,
                 notes=["Gallery images of the same defect class look alike; GNSS distance gating is applied first in production."])


if __name__ == "__main__":
    main()
