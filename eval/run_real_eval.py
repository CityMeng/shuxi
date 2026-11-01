# -*- coding: utf-8 -*-
"""
数玺真实语料验证 (real-v1): 法定披露文件 (巨潮资讯网年度报告摘要)。

方法: 取真实上市公司年度报告摘要 PDF 为原件, 每份构造四类用例 —
  pristine 原件原样 (期望 甲)、resave PDF 重存 (载体变内容等价, 期望 乙)、
  rescan 逐页渲染成图再装订 (扫描件形态, 期望 乙)、
  tamper 篡改一处关键金额 (期望 丁)。
原件先登记再逐例验真, 结果与期望对照; 同场给单哈希基线。
真实文件本身勾稽自洽, 不构造 丙 类 (丙 已由合成语料 corpus-v1 覆盖)。
产出: real_corpus/manifest.json + REPORT_REAL.md (实测数字, 失败逐条列明)。
"""
import hashlib
import json
import os
import sys
import tempfile
import urllib.parse
import urllib.request
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
sys.path.insert(0, ROOT)
import pymupdf as fitz  # noqa: E402
from engine.ledger import KeyPair, Ledger  # noqa: E402
from engine import service as svc  # noqa: E402
from engine import fp as fplib  # noqa: E402

CORPUS = os.path.join(BASE, "real_corpus")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Referer": "https://www.cninfo.com.cn/new/disclosure"}


def _query_category(category, page_size=30, page_num=1, column="szse"):
    data = urllib.parse.urlencode({
        "pageNum": page_num, "pageSize": page_size, "column": column,
        "tabName": "fulltext", "category": category, "searchkey": "",
        "seDate": "", "sortName": "", "sortType": "",
        "isHLtitle": "true"}).encode()
    req = urllib.request.Request(
        "https://www.cninfo.com.cn/new/hisAnnouncement/query",
        data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("announcements") or []


def fetch_candidates(want=20):
    """从巨潮资讯网取定期报告摘要公告清单 (年报+半年报, 不同公司)。"""
    anns = []
    for cat in ("category_ndbg_szsh", "category_bndbg_szsh"):
        for column in ("szse", "sse"):
            for page_num in (1, 2, 3):
                try:
                    anns += _query_category(cat, page_num=page_num,
                                            column=column)
                except Exception as e:
                    print(f"品类 {cat}/{column}/p{page_num} 查询失败: {e}")
    out, seen = [], set()
    for a in anns:
        size = a.get("adjunctSize") or 0
        if a["secCode"] in seen or not (100 <= size <= 900):
            continue
        seen.add(a["secCode"])
        out.append({"sec_code": a["secCode"], "sec_name": a["secName"],
                    "title": a["announcementTitle"], "size_kb": size,
                    "url": "https://static.cninfo.com.cn/" + a["adjunctUrl"],
                    "file": a["adjunctUrl"].rsplit("/", 1)[-1]})
        if len(out) >= want:
            break
    out.sort(key=lambda c: c["size_kb"])
    return out


def download(cand):
    path = os.path.join(CORPUS, cand["file"])
    if not os.path.exists(path):
        req = urllib.request.Request(cand["url"], headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r, \
                open(path, "wb") as f:
            f.write(r.read())
    with open(path, "rb") as f:
        return f.read()


def build_variants(pdf_bytes):
    """由原件构造 resave / rescan / tamper 三种变体; 返回 (变体字典, 篡改说明)。"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    variants = {}
    # resave: 重新序列化 (字节全变, 内容不变)
    variants["resave"] = doc.tobytes(garbage=4, deflate=True)
    # rescan: 逐页 150 DPI 渲染成图再装订 (扫描件形态)
    img_doc = fitz.open()
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        p = img_doc.new_page(width=pix.width / 150 * 72,
                             height=pix.height / 150 * 72)
        p.insert_image(p.rect, stream=pix.tobytes("png"))
    variants["rescan"] = img_doc.tobytes(deflate=True)
    img_doc.close()
    # tamper: 找出现次数最多的长金额串, 改其首位数字 (全文每一处都改)
    full_text = "\n".join(page.get_text() for page in doc)
    import re
    nums = re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{5,}(?:\.\d+)?", full_text)
    target = None
    for cand_num, cnt in Counter(nums).most_common():
        if len(cand_num.replace(",", "").replace(".", "")) >= 6:
            target, target_cnt = cand_num, cnt
            break
    note = "未找到可篡改金额"
    if target:
        digits = target.replace(",", "")
        first = digits[0]
        repl_first = str((int(first) + 1) % 10) if first != "0" else "1"
        tampered_str = repl_first + target[1:]
        tdoc = fitz.open(stream=pdf_bytes, filetype="pdf")
        hits = 0
        for page in tdoc:
            for rect in page.search_for(target):
                page.add_redact_annot(rect, fill=(1, 1, 1))
                hits += 1
            page.apply_redactions()
            for rect in page.search_for(target):  # 已删除, 应为空
                pass
        # 在原位置写回改后数字: 重新按坐标插入 (用第一次搜索的坐标)
        tdoc2 = fitz.open(stream=pdf_bytes, filetype="pdf")
        placed = 0
        for pno, page in enumerate(tdoc2):
            rects = page.search_for(target)
            tpage = tdoc[pno]
            for rect in rects:
                tpage.insert_text(
                    (rect.x0, rect.y1 - 1), tampered_str,
                    fontsize=max(6, rect.height * 0.82), fontname="helv",
                    color=(0, 0, 0))
                placed += 1
        variants["tamper"] = tdoc.tobytes(deflate=True)
        note = (f"金额 {target} 出现 {hits} 处, 首位数字 {first}→{repl_first}, "
                f"回写 {placed} 处")
        tdoc.close()
        tdoc2.close()
    doc.close()
    return variants, note


def main():
    os.makedirs(CORPUS, exist_ok=True)
    cands = fetch_candidates()
    print(f"候选公告 {len(cands)} 条")
    kept = []
    for cand in cands:
        try:
            data = download(cand)
        except Exception as e:
            print(f"下载失败 {cand['sec_name']}: {e}")
            continue
        doc = fitz.open(stream=data, filetype="pdf")
        pages = len(doc)
        doc.close()
        if pages > 16:
            print(f"{cand['sec_name']}: {pages} 页, 超过 16 页跳过")
            continue
        text = fplib.extract_text(data, "pdf")
        fields = fplib.extract_fields(text)
        print(f"{cand['sec_name']}: {pages} 页, 抽出字段 {len(fields)} 个")
        if len(fields) >= 3:
            cand.update({"pages": pages, "n_fields": len(fields),
                         "sha256": hashlib.sha256(data).hexdigest()})
            kept.append((cand, data))
        if len(kept) >= 6:
            break
    print(f"入选 {len(kept)} 份真实文件")

    tmp = tempfile.mkdtemp(prefix="shuxi-real-")
    ledger = Ledger(os.path.join(tmp, "ledger.jsonl"))
    packages = svc.PackageStore(os.path.join(tmp, "packages.json"))
    registrar, verifier = KeyPair.generate(), KeyPair.generate()

    cases = []  # (file, case, expected, grade, confidence, baseline_hit)
    for cand, data in kept:
        cert = svc.register_file(ledger, packages, registrar, "真实语料评测登记方",
                                 cand["file"], data, "pdf", "eval-pass")
        variants, note = build_variants(data)
        cand["tamper_note"] = note
        jobs = [("pristine", data, "甲级"), ("resave", variants["resave"], "乙级"),
                ("rescan", variants["rescan"], "乙级")]
        if "tamper" in variants:
            jobs.append(("tamper", variants["tamper"], "丁级"))
        for name, blob, expected in jobs:
            rep = svc.verify_file(ledger, packages, verifier, "真实语料评测验真方",
                                  cert, blob, "pdf", f"{name}.pdf")
            base_hit = hashlib.sha256(blob).digest() == hashlib.sha256(data).digest()
            cases.append({"sec_name": cand["sec_name"], "case": name,
                          "expected": expected,
                          "grade": rep.get("grade", "错误"),
                          "confidence": rep.get("confidence"),
                          "baseline_ok": base_hit == (expected in ("甲级", "乙级"))})
            print(f"  {cand['sec_name']} {name}: 期望 {expected} 实得 "
                  f"{rep.get('grade')} (把握 {rep.get('confidence')})")

    total = len(cases)
    ok = sum(1 for c in cases if c["grade"] == c["expected"])
    base_ok = sum(1 for c in cases if c["baseline_ok"])
    per = {}
    for c in cases:
        per.setdefault(c["expected"], []).append(c["grade"] == c["expected"])
    equiv = [c for c in cases if c["expected"] == "乙级"]
    fails = [c for c in cases if c["grade"] != c["expected"]]

    with open(os.path.join(CORPUS, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"files": [{k: c[k] for k in
                              ("sec_code", "sec_name", "title", "url", "file",
                               "pages", "n_fields", "sha256", "tamper_note")}
                             for c, _ in kept],
                   "cases": cases}, f, ensure_ascii=False, indent=2)

    lines = ["# 数玺真实语料验证报告 (real-v1)", "",
             "语料: 巨潮资讯网法定披露定期报告摘要 (年度/半年度), 共 "
             f"{len(kept)} 份真实文件, {total} 个用例。每份原件登记后构造 "
             "resave (重存)、rescan (渲染成图装订)、tamper (篡改关键金额) "
             "三类变体逐一验真。", "",
             f"- 数玺判定与期望一致: **{ok}/{total} = {ok/total:.2%}**",
             f"- 单哈希基线 (二值判定, 字节全等才判真): {base_ok}/{total} = "
             f"{base_ok/total:.2%}; 对 {len(equiv)} 例内容等价文件 "
             f"接受 0 例 (全部误判为假)", ""]
    for g in ("甲级", "乙级", "丁级"):
        if g in per:
            xs = per[g]
            lines.append(f"- 期望 {g}: {sum(xs)}/{len(xs)} 命中")
    lines += ["", "## 文件清单 (可按 URL 回巨潮资讯网复核原件)", ""]
    for c, _ in kept:
        lines.append(f"- {c['sec_name']}《{c['title']}》 {c['pages']} 页, "
                     f"抽出字段 {c['n_fields']} 个, SHA-256 {c['sha256'][:16]}…, "
                     f"{c['url']}")
        lines.append(f"  篡改构造: {c['tamper_note']}")
    lines += ["", "## 逐例结果", "",
              "| 文件 | 用例 | 期望 | 实得 | 把握度 |", "|---|---|---|---|---|"]
    for c in cases:
        conf = c["confidence"]
        conf_s = f"{float(conf):.0%}" if isinstance(conf, (int, float)) else str(conf)
        lines.append(f"| {c['sec_name']} | {c['case']} | {c['expected']} | "
                     f"{c['grade']} | {conf_s} |")
    if fails:
        lines += ["", "## 未命中用例 (如实列明)", ""]
        for c in fails:
            lines.append(f"- {c['sec_name']} {c['case']}: 期望 {c['expected']} "
                         f"实得 {c['grade']}")
    lines += ["", "说明: 真实审计报告自身勾稽自洽, 本轮不构造丙类用例, "
              "丙类判定由合成语料 corpus-v1 标定覆盖 (见 REPORT.md)。"]
    with open(os.path.join(BASE, "REPORT_REAL.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n==== 真实语料: {ok}/{total} 命中, 基线 {base_ok}/{total} ====")


if __name__ == "__main__":
    main()
