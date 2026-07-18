"""Đánh giá OCR chuẩn metric trên bộ ảnh mẫu sample_docs/ — tái chạy được.

Chạy:  python -m scripts.eval_ocr                     (model mặc định từ .env)
       python -m scripts.eval_ocr --all               (so sánh cả 3 model)

Metrics: Field Accuracy (exact), CER (Levenshtein), Numeric Accuracy,
Decision Accuracy, latency, tokens. Kết quả in bảng + lưu docs/ocr_eval_results.json.
Chi tiết định nghĩa & phân tích: docs/OCR_BENCHMARK.md
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
import statistics
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import AsyncOpenAI  # noqa: E402
from rapidfuzz.distance import Levenshtein  # noqa: E402

from common import config  # noqa: E402

client = AsyncOpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)
SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_docs"

# Ground truth đối chiếu thủ công từ 6 ảnh (xem docs/OCR_BENCHMARK.md)
GT = {
    "CR-A01": {
        "text": {"ma_ho_so": "CR-A01",
                 "ten_khach_hang": "Công ty Cổ phần Bao bì VinaNova",
                 "nguoi_dai_dien": "Nguyễn Hoàng Nam"},
        "num": {"so_tien_de_nghi_ty": 80,
                "doanh_thu_theo_nam_ty": [520, 610, 705],
                "ebitda_theo_nam_ty": [62, 78, 98],
                "tong_gia_tri_tsdb_xu_ly_ty": 145},
        "decision": "PHÊ DUYỆT",
    },
    "CR-B02": {
        "text": {"ma_ho_so": "CR-B02",
                 "ten_khach_hang": "Công ty TNHH Bao bì Mekong Flex",
                 "nguoi_dai_dien": "Phạm Ngọc Mai"},
        "num": {"so_tien_de_nghi_ty": 80,
                "doanh_thu_theo_nam_ty": [420, 485, 530],
                "ebitda_theo_nam_ty": [42, 43, 38],
                "tong_gia_tri_tsdb_xu_ly_ty": 62},
        "decision": "PHÊ DUYỆT CÓ ĐIỀU KIỆN",
    },
    "CR-C03": {
        "text": {"ma_ho_so": "CR-C03",
                 "ten_khach_hang": "Công ty Cổ phần Bao bì Đại Thành Global",
                 "nguoi_dai_dien": "Vũ Anh Khoa"},
        "num": {"so_tien_de_nghi_ty": 80,
                "doanh_thu_theo_nam_ty": [360, 410, 395],
                "ebitda_theo_nam_ty": [14, 8, -22],
                "tong_gia_tri_tsdb_xu_ly_ty": 115},
        "decision": "TỪ CHỐI",
    },
    "CR-I01": {
        "text": {"ma_ho_so": "CR-I01", "ten_khach_hang": "Nguyễn Minh Khôi"},
        "num": {"so_tien_de_nghi_ty": 4, "tong_thu_nhap_thang_trieu": 250,
                "dti_phan_tram": 19.0, "tong_gia_tri_tsdb_xu_ly_ty": 6.4},
        "decision": "PHÊ DUYỆT",
    },
    "CR-I02": {
        "text": {"ma_ho_so": "CR-I02", "ten_khach_hang": "Lê Thị Thanh Hương"},
        "num": {"so_tien_de_nghi_ty": 4, "tong_thu_nhap_thang_trieu": 106,
                "dti_phan_tram": 40.9, "tong_gia_tri_tsdb_xu_ly_ty": 4.5},
        "decision": "PHÊ DUYỆT CÓ ĐIỀU KIỆN",
    },
    "CR-I03": {
        "text": {"ma_ho_so": "CR-I03", "ten_khach_hang": "Trần Quốc Bảo"},
        "num": {"so_tien_de_nghi_ty": 4, "tong_thu_nhap_thang_trieu": 46,
                "dti_phan_tram": 205.4, "tong_gia_tri_tsdb_xu_ly_ty": 3.8},
        "decision": "TỪ CHỐI",
    },
}

SCHEMA = ('{"ma_ho_so": str (định dạng "CR-" + 1 CHỮ CÁI IN HOA + 2 chữ số, '
          'vd CR-A01/CR-I03; ký tự sau "CR-" luôn là CHỮ CÁI, không phải số 1), '
          '"ten_khach_hang": str, "nguoi_dai_dien": str|null (chỉ họ tên, bỏ chức danh), '
          '"so_tien_de_nghi_ty": number (đơn vị TỶ đồng), "de_xuat_so_bo": str, '
          '"doanh_thu_theo_nam_ty": [number]|null (2023,2024,2025; số trong ngoặc đơn là số ÂM), '
          '"ebitda_theo_nam_ty": [number]|null (số trong ngoặc đơn là số ÂM), '
          '"tong_thu_nhap_thang_trieu": number|null (lấy thu nhập XÁC MINH/CHẤP NHẬN, '
          'không lấy thu nhập khai báo), "dti_phan_tram": number|null, '
          '"tong_gia_tri_tsdb_xu_ly_ty": number|null (đơn vị TỶ đồng)}')


def parse_loose(text: str) -> dict:
    if not text:
        raise ValueError("empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def num_eq(a, b) -> bool:
    try:
        return abs(float(a) - float(b)) < 1e-6 * max(1.0, abs(float(b))) + 1e-9
    except (TypeError, ValueError):
        return False


async def eval_model(model: str) -> dict:
    text_total = text_exact = cer_num = cer_den = 0
    num_total = num_ok = dec_total = dec_ok = 0
    latencies, tokens_in, tokens_out, fails = [], [], [], []

    for code, gt in GT.items():
        img = SAMPLE_DIR / f"{code}.jpg"
        b64 = base64.b64encode(img.read_bytes()).decode()
        t0 = time.perf_counter()
        try:
            r = await client.chat.completions.create(
                model=model, temperature=0, max_tokens=900,
                messages=[
                    {"role": "system", "content":
                     "Bạn là chuyên viên nhập liệu tín dụng. Trích xuất chính xác, "
                     "giữ nguyên dấu tiếng Việt. Chỉ trả về JSON.\nSchema:\n" + SCHEMA},
                    {"role": "user", "content": [
                        {"type": "text", "text": "Trích xuất thông tin từ phiếu này."},
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ]}])
            latencies.append(time.perf_counter() - t0)
            if r.usage:
                tokens_in.append(r.usage.prompt_tokens)
                tokens_out.append(r.usage.completion_tokens)
            d = parse_loose(r.choices[0].message.content)
        except Exception as e:  # noqa: BLE001 - tính toàn bộ trường ảnh này là sai
            fails.append(f"{code}: LỖI {str(e)[:80]}")
            text_total += len(gt["text"])
            cer_den += sum(len(v) for v in gt["text"].values())
            cer_num += sum(len(v) for v in gt["text"].values())
            num_total += sum(len(v) if isinstance(v, list) else 1
                             for v in gt["num"].values())
            dec_total += 1
            continue

        for k, ref in gt["text"].items():
            got = str(d.get(k) or "").strip()
            text_total += 1
            text_exact += (got == ref)
            cer_num += Levenshtein.distance(got, ref)
            cer_den += len(ref)
            if got != ref:
                fails.append(f"{code}.{k}: '{got}'")
        for k, ref in gt["num"].items():
            refs = ref if isinstance(ref, list) else [ref]
            gots = d.get(k) if isinstance(ref, list) else [d.get(k)]
            gots = gots or []
            for i, rv in enumerate(refs):
                num_total += 1
                ok = i < len(gots) and num_eq(gots[i], rv)
                num_ok += ok
                if not ok:
                    fails.append(f"{code}.{k}[{i}]: "
                                 f"{gots[i] if i < len(gots) else 'thiếu'} != {rv}")
        dec_total += 1
        dec_ok += (gt["decision"] in str(d.get("de_xuat_so_bo", "")).upper())

    return {
        "model": model,
        "field_accuracy": round(text_exact / text_total, 4),
        "cer": round(cer_num / cer_den, 4),
        "numeric_accuracy": round(num_ok / num_total, 4),
        "numeric_detail": f"{num_ok}/{num_total}",
        "decision_accuracy": round(dec_ok / dec_total, 4),
        "latency_avg_s": round(statistics.mean(latencies), 2) if latencies else None,
        "tokens_in_avg": round(statistics.mean(tokens_in)) if tokens_in else None,
        "tokens_out_avg": round(statistics.mean(tokens_out)) if tokens_out else None,
        "fails": fails,
    }


async def main() -> None:
    models = ([config.VISION_MODEL] if "--all" not in sys.argv else
              ["gemma-4-31B-it", "Qwen2.5-VL-7B-Instruct", "gemma-3-27b-it"])
    results = []
    for m in models:
        print(f"Đang đánh giá {m} trên {len(GT)} ảnh...")
        results.append(await eval_model(m))

    print(f"\n{'Model':<26} {'FieldAcc':>9} {'CER':>7} {'NumAcc':>10} "
          f"{'DecAcc':>7} {'Lat.tb':>7}")
    for r in results:
        print(f"{r['model']:<26} {r['field_accuracy']:>8.1%} {r['cer']:>7.3f} "
              f"{r['numeric_detail']:>5} {r['numeric_accuracy']:>4.0%} "
              f"{r['decision_accuracy']:>6.0%} {r['latency_avg_s']:>6.1f}s")
        for f in r["fails"]:
            print(f"    {f}")

    out = Path(__file__).resolve().parent.parent / "docs" / "ocr_eval_results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nĐã lưu {out}")


if __name__ == "__main__":
    asyncio.run(main())
