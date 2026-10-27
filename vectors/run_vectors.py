# -*- coding: utf-8 -*-
"""
数玺标准测试向量运行器 (规范 §15)
用法:
  .venv/bin/python vectors/run_vectors.py           # 按 test_vectors.json 全量核对
  .venv/bin/python vectors/run_vectors.py --freeze  # 重新冻结根值到 JSON (等级期望为手工常量, 不被覆盖)
核对内容: 已知答案密码学校验 / 向量根值与字段数 / 分级期望 / 披露证明 / 边界单元。
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import fp, grade as gr  # noqa: E402
import gen_samples  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
VEC_JSON = os.path.join(HERE, "test_vectors.json")
SAMPLES = os.path.join(HERE, "samples")

RESULTS = []


def check(label, cond, extra=""):
    RESULTS.append((label, bool(cond)))
    print(("PASS" if cond else "FAIL"), label, extra)


def salt_for(key: str) -> str:
    return hashlib.sha256(f"shuxi-vector-salt:{key}".encode()).hexdigest()[:32]


def load(name: str) -> bytes:
    with open(os.path.join(SAMPLES, name), "rb") as f:
        return f.read()


def reg_view(comp: dict) -> dict:
    """登记记录公开视图 + 登记方另行出示的原文 (原文不进记录, 仅供比对)。"""
    return {**fp.public_view(comp), "text": comp["text"]}


def compute(name: str):
    data = load(name)
    ext = name.rsplit(".", 1)[-1]
    comp = fp.compute_all(data, ext)
    salts = {k: salt_for(k) for k in comp["fields"]}
    if comp["fields"]:
        comp = fp.compute_all(data, ext, salts)
    aud = gr.audit(data, ext, comp["text"], comp["fields"])
    return data, comp, aud


def freeze():
    hashes = gen_samples.main()
    vectors = []
    for name in ["report.txt", "report_tampered.txt", "report_converted.txt",
                 "fake.txt", "contract_bad.txt", "big.bin", "scan_a.png"]:
        _, comp, _ = compute(name)
        vectors.append({
            "id": f"V-{name}", "file": name, "sha256": hashes[name],
            "exact": comp["exact"], "semantic_root": comp["semantic"]["root"],
            "field_count": len(comp["fields"]),
        })
    doc = {
        "spec_version": fp.SPEC_VERSION, "suite": fp.SUITE_ID,
        "vectors": vectors,
        "grade_cases": [
            {"id": "G1-exact", "reg": "report.txt", "cand": "report.txt",
             "expect": "甲级", "expect_conf": 0.99},
            {"id": "G2-tamper", "reg": "report.txt", "cand": "report_tampered.txt",
             "expect": "丁级", "expect_conf": 0.95, "expect_diff_field": "净利润"},
            {"id": "G3-convert", "reg": "report.txt", "cand": "report_converted.txt",
             "expect": "乙级", "expect_conf": 0.90},
            {"id": "G4-fake-standalone", "reg": None, "cand": "fake.txt",
             "expect": "丙级", "expect_conf": 0.85},
            {"id": "G5-scan", "reg": "scan_a.png", "cand": "scan_b.jpg",
             "expect": "乙级", "expect_conf": 0.90},
            {"id": "G6-badcase-standalone", "reg": None, "cand": "contract_bad.txt",
             "expect": "丙级", "expect_conf": 0.85},
        ],
        "disclosure": {"file": "report.txt", "field": "净利润", "expect_value": "4200000"},
    }
    with open(VEC_JSON, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print("frozen:", VEC_JSON)


def run():
    gen_samples.main()
    doc = json.load(open(VEC_JSON, encoding="utf-8"))

    # A. 已知答案校验 (独立常量, 非引擎自产)
    check("A1 空树根 = sha256(0x00) 已知常量",
          fp.merkle_root("sha256", []) == "6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d")
    check("A2 SM3 空树根与 hashlib 直算一致",
          fp.merkle_root("sm3", []) == hashlib.new("sm3", b"\x00").hexdigest())
    check("A3 单块根 = sha256(0x00|data) 直算一致",
          fp.merkle_root("sha256", [b"hello shuxi"])
          == hashlib.sha256(b"\x00hello shuxi").hexdigest())
    big = load("big.bin")
    chunks = [big[i:i + fp.CHUNK_SIZE] for i in range(0, len(big), fp.CHUNK_SIZE)]
    proof = fp.merkle_proof("sha256", chunks, 2)
    root = fp.merkle_root("sha256", chunks)
    check("A4 大文件 3 分块 (奇数层) Merkle 证明可验",
          len(chunks) == 3 and fp.verify_proof("sha256", chunks[2], proof, root))
    check("A5 篡改数据 Merkle 证明不可验",
          not fp.verify_proof("sha256", b"tampered", proof, root))

    # B. 向量根值与字段数
    comps = {}
    for v in doc["vectors"]:
        data, comp, aud = compute(v["file"])
        comps[v["file"]] = (data, comp, aud)
        check(f"B {v['id']} sha256", hashlib.sha256(data).hexdigest() == v["sha256"])
        check(f"B {v['id']} 精确双根",
              comp["exact"]["sha256_root"] == v["exact"]["sha256_root"]
              and comp["exact"]["sm3_root"] == v["exact"]["sm3_root"])
        check(f"B {v['id']} 语义根", comp["semantic"]["root"] == v["semantic_root"])
        check(f"B {v['id']} 字段数", len(comp["fields"]) == v["field_count"],
              f"fields={list(comp['fields'])}")

    # C. 分级期望
    for case in doc["grade_cases"]:
        _, ccomp, caud = comps[case["cand"]] if case["cand"] in comps else compute(case["cand"])
        if case["reg"] is None:
            res = gr.grade_standalone(caud)
        else:
            _, rcomp, raud = comps[case["reg"]]
            res = gr.grade(reg_view(rcomp), ccomp, raud, caud, rcomp["fields"])
        ok = res["grade"] == case["expect"] and abs(res["confidence"] - case["expect_conf"]) < 1e-9
        extra = f"got {res['grade']}/{res['confidence']}"
        if ok and "expect_diff_field" in case:
            fields = [d["field"] for d in res["evidence"].get("field_diffs", [])]
            ok = case["expect_diff_field"] in fields
            extra += f" diffs={fields}"
        check(f"C {case['id']} -> {case['expect']}", ok, extra)

    # C2. 规则级合成用例: 待验件抽不出字段 (登记侧有字段) -> 不得判丁,
    #     感知通过判乙并封顶 60% (规范 §6 特别规则)
    _, rcomp, raud = comps["report.txt"]
    synth_cand = {
        "exact": {"sha256_root": "0" * 64, "sm3_root": "0" * 64,
                  "chunk_count": 1, "size": 1},
        "perceptual": {"phashes": []},
        "text": rcomp["text"], "fields": {},
        "semantic": {"root": fp.merkle_root("sha256", []),
                     "salts": {}, "leaves": [], "keys": []},
    }
    res = gr.grade(reg_view(rcomp), synth_cand, raud, raud, rcomp["fields"])
    check("C2 字段无法核验 -> 乙级封顶60% (不误判丁级)",
          res["grade"] == "乙级" and abs(res["confidence"] - 0.60) < 1e-9
          and res["evidence"].get("fields_unverifiable") is True,
          f"got {res['grade']}/{res['confidence']}")

    # C3. 规则级用例 (v1.3): 登记方未出示字段表 -> 无法核验,
    #     感知通过判乙并封顶 60% (原"比根判丁级嫌疑"路径已删除)
    _, ccomp3, caud3 = comps["report_converted.txt"]
    res3 = gr.grade(reg_view(rcomp), ccomp3, raud, caud3, None)
    check("C3 无字段表 -> 乙级封顶60% (v1.3)",
          res3["grade"] == "乙级" and abs(res3["confidence"] - 0.60) < 1e-9,
          f"got {res3['grade']}/{res3['confidence']}")

    # D. 选择性披露
    d = doc["disclosure"]
    _, comp, _ = comps[d["file"]]
    sem = {"fields": comp["fields"], "salts": comp["semantic"]["salts"],
           "leaves": comp["semantic"]["leaves"], "keys": comp["semantic"]["keys"],
           "root": comp["semantic"]["root"]}
    p = fp.field_proof(sem, d["field"])
    check("D1 披露证明有效",
          p is not None and p["value"] == d["expect_value"]
          and fp.verify_field_proof(p["key"], p["value"], p["salt"], p["proof"], p["root"]))
    check("D2 篡改值披露证明无效",
          not fp.verify_field_proof(p["key"], "9999999", p["salt"], p["proof"], p["root"]))

    # E. 边界单元
    check("E1 金额规范化 亿元", fp.canon_amount("1.25亿元") == "125000000")
    check("E2 金额规范化 千分位", fp.canon_amount("12,500,000元") == "12500000")
    f_bad = fp.extract_fields("截止日期：2026年13月40日\n金额：100元")
    check("E3 非法日期不入字段", "截止日期" not in f_bad and f_bad.get("金额") == "100")
    check("E4 大写金额含角", gr.chinese_amount("肆拾捌万陆仟元伍角") is not None
          and str(gr.chinese_amount("肆拾捌万陆仟元伍角")) == "486000.5")
    a_bad = gr.audit(b"", "txt", "合同金额：500000元\n金额大写：肆拾捌万陆仟元整", {})
    check("E5 G2 大小写不符被检出", any(i["code"] == "G2" for i in a_bad["issues"]))
    sim = fp.text_similarity("营业收入 12500000", "营业收入12500000")
    check("E6 文本相似 空白差异归一", sim == 1.0)
    check("E7 文本相似 双空不可用", fp.text_similarity("", "") is None)

    # F. 跨实现交叉校验 (社区通行做法: 不只信自家实现)
    import subprocess
    out = subprocess.run(["sha256sum"], input=b"\x00hello shuxi",
                         capture_output=True).stdout.decode().split()[0]
    check("F1 精确层叶子与 coreutils sha256sum 一致",
          out == fp.merkle_root("sha256", [b"hello shuxi"]))
    check("F2 SM3 与 GM/T 0004 公布向量一致 (abc)",
          __import__("hashlib").new("sm3", b"abc").hexdigest()
          == "66c7f0f462eeedd9d1f2d46bdc10e4e24167c4875cf2f7a2297da02b8f4ba8e0")
    check("F3 百分比归一 12.50% == 12.5%", fp.canon_amount("12.50%") == "12.5%")
    a1 = gr.audit(b"", "txt", "", {})
    g_a = "甲产品 | 9000000\n乙产品 | 3500000\n合计 | 13000000\n".encode()
    g_b = "甲产品 | 9000000\n丙产品 | 100\n乙产品 | 3500000\n合计 | 13000000\n".encode()
    ia = gr.audit(g_a, "txt", g_a.decode(), {})["issues"]
    ib = gr.audit(g_b, "txt", g_b.decode(), {})["issues"]
    check("F4 G1 问题键插行稳定 (相对丙不误判)",
          ia and ib and ia[0]["key"] == ib[0]["key"],
          f"{[i['key'] for i in ia]} vs {[i['key'] for i in ib]}")
    try:
        import imagehash
        from PIL import Image as PILImage
        ours = fp.phash64(PILImage.open(os.path.join(SAMPLES, "scan_a.png")))
        theirs = str(imagehash.phash(PILImage.open(os.path.join(SAMPLES, "scan_a.png"))))
        d = fp.hamming_hex(ours, theirs)
        check("F5 pHash 与 imagehash 社区实现同图距离小 (统计口径不同, 不要求相等)",
              d <= 20, f"dist={d} ours={ours} lib={theirs}")
    except ImportError:
        check("F5 pHash 跨实现校验 (imagehash 未安装, 跳过)", True, "SKIP")

    fails = [r for r in RESULTS if not r[1]]
    print(f"\n==== 向量核对: {len(RESULTS) - len(fails)}/{len(RESULTS)} PASS ====")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--freeze" in sys.argv:
        freeze()
    else:
        sys.exit(run())
