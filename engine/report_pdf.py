# -*- coding: utf-8 -*-
"""验真报告 PDF (打印版): 把一次验真结论排成正式文书。

纯渲染, 不写账本。字体优先系统 Noto CJK, 缺失时退 PyMuPDF 内置
CJK 字体 (china-s), 保证云端无字体环境也能生成。
"""
from __future__ import annotations

import os
from datetime import datetime

import fitz

RED = (0.76, 0.21, 0.19)
DARKRED = (0.60, 0.11, 0.11)
GOLD = (0.85, 0.47, 0.02)
INK = (0.12, 0.16, 0.22)
GRAY = (0.45, 0.44, 0.42)
LINE = (0.91, 0.89, 0.84)
GRADE_COLORS = {"甲级": (0.02, 0.58, 0.40), "乙级": (0.01, 0.52, 0.78),
                "丙级": (0.85, 0.47, 0.02), "丁级": (0.76, 0.21, 0.19),
                "待人工复核": (0.42, 0.45, 0.50),
                "已作废": (0.42, 0.45, 0.50), "未登记": (0.42, 0.45, 0.50)}
PW, PH, M = 595, 842, 48

def _register_fonts(page):
    """优先单文件 CJK 字体 (可子集嵌入); TTC 集合字体嵌入会带入
    全字体文件 (30+ MB) 且文本层字符映射异常, 不用; 退内置 china-s。"""
    import glob as _glob
    pats = ["/usr/share/fonts/**/NotoSansSC-*.otf",
            "/usr/share/fonts/**/NotoSansSC-*.ttf",
            "/usr/share/fonts/**/*CJK*SC*.otf",
            "/usr/share/fonts/**/*CJK*SC*.ttf"]
    found = []
    for p in pats:
        found += [f for f in _glob.glob(p, recursive=True)
                  if not f.endswith(".ttc")]
    if not found:
        return "china-s", "china-s", False
    page.insert_font(fontname="sxreg", fontfile=sorted(found)[0])
    return "sxreg", "sxreg", True


def _fmt(v):
    if v is None:
        return "（无）"
    try:
        f = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return str(v)
    return f"{f:,.2f}".rstrip("0").rstrip(".")


class _Pen:
    def __init__(self, page, freg, fbold):
        self.page, self.freg, self.fbold = page, freg, fbold

    def text(self, x, y, s, size=11, bold=False, color=INK):
        self.page.insert_text(fitz.Point(x, y), str(s), fontsize=size,
                              fontname=self.fbold if bold else self.freg,
                              color=color)

    def wrap(self, x, y, s, size=10.5, width=500, leading=15, color=INK):
        per = max(8, int(width / (size * 0.99)))
        cur = ""
        for ch in str(s):
            cur += ch
            if len(cur) >= per:
                self.text(x, y, cur, size=size, color=color)
                y += leading
                cur = ""
        if cur:
            self.text(x, y, cur, size=size, color=color)
            y += leading
        return y

    def section(self, y, title):
        self.text(M, y, title, size=13, bold=True, color=DARKRED)
        self.page.draw_line(fitz.Point(M, y + 5),
                            fitz.Point(PW - M, y + 5), color=LINE, width=1)
        return y + 25

    def kv(self, y, label, value, size=10.5, vsize=None, label_w=96):
        self.text(M, y, label, size=size, color=GRAY)
        return self.wrap(M + label_w, y, value, size=vsize or size,
                         width=PW - M - (M + label_w),
                         leading=(vsize or size) + 5)


def build_report_pdf(ledger, packages, cert_id, report,
                     anchor_line: str = "", comp: dict | None = None) -> bytes:
    reg = ledger.find_registration(cert_id)
    rp = reg["payload"] if reg else {}
    pkg = packages.get(cert_id) if packages else None
    fields = (pkg or {}).get("fields") or {}
    diff_map = {d["field"]: d for d in (report.get("field_diffs") or [])}
    grade = report.get("grade", "")
    gcol = GRADE_COLORS.get(grade, GRAY)

    doc = fitz.open()
    page = doc.new_page(width=PW, height=PH)
    freg, fbold, embedded = _register_fonts(page)
    pen = _Pen(page, freg, fbold)

    # 红抬头
    page.draw_rect(fitz.Rect(0, 0, PW, 66), fill=RED, color=RED)
    pen.text(M, 41, "数 玺", size=24, bold=True, color=(1, 1, 1))
    pen.text(M + 76, 41, "SHUXI SEAL", size=10, color=(1, 0.92, 0.78))
    pen.text(PW - M - 172, 43, "数 据 验 真 报 告", size=19, bold=True,
             color=(1, 1, 1))
    page.draw_rect(fitz.Rect(0, 66, PW, 69), fill=GOLD, color=GOLD)

    y = 94
    pen.text(M, y, f"报告编号　{report.get('receipt_id') or '—'}",
             size=10.5, color=GRAY)
    pen.text(336, y, "生成时间　" + datetime.now().strftime("%Y-%m-%d %H:%M"),
             size=10.5, color=GRAY)
    y += 15
    pen.text(M, y, f"报告哈希　{report.get('report_hash') or '—'}",
             size=8.5, color=GRAY)
    y += 28

    # 一、结论 + 印章
    y = pen.section(y, "一、验真结论")
    top = y
    page.draw_rect(fitz.Rect(M, top - 13, M + 108, top + 37),
                   color=gcol, width=1.4)
    pen.text(M + 16, top + 19, grade or "—", size=25, bold=True, color=gcol)
    try:
        conf_s = f"把握 {float(report.get('confidence')) * 100:.0f}%"
    except (TypeError, ValueError):
        conf_s = ""
    pen.text(178, top + 1, conf_s, size=12, bold=True)
    ry = top + 19
    for r in report.get("reasons") or []:
        ry = pen.wrap(178, ry, "· " + str(r), size=10.5, width=246,
                      leading=14.5)
    sx, sy = PW - M - 96, top - 13
    page.draw_rect(fitz.Rect(sx, sy, sx + 96, sy + 76), color=RED, width=2)
    page.draw_rect(fitz.Rect(sx + 4, sy + 4, sx + 92, sy + 72),
                   color=RED, width=0.7)
    pen.text(sx + 22, sy + 24, "数玺验真", size=11, bold=True, color=RED)
    pen.text(sx + 26, sy + 50, grade[:2] or "验真", size=17, bold=True,
             color=RED)
    pen.text(sx + 30, sy + 66, "SHUXI", size=7.5, color=RED)
    y = max(top + 56, ry + 6)

    # 二、文件与凭证
    y = pen.section(y, "二、文件与凭证")
    reg_ts = str(reg["ts"])[:19].replace("T", " ") if reg else "—"
    for label, value in (
            ("凭证编号", cert_id),
            ("登记文件", rp.get("filename") or "—"),
            ("待验文件", report.get("filename") or "—"),
            ("登记方", rp.get("registrar") or "—"),
            ("登记时间", reg_ts),
            ("核验方", report.get("verifier") or "—"),
            ("核验方指纹", report.get("verifier_fp") or "—")):
        y = pen.kv(y, label, value) + 3
    y += 8

    # 三、字段比对
    y = pen.section(y, "三、字段比对")
    if fields:
        pen.text(M, y, "字段", size=10, bold=True, color=GRAY)
        pen.text(M + 150, y, "登记值", size=10, bold=True, color=GRAY)
        pen.text(M + 300, y, "待验值", size=10, bold=True, color=GRAY)
        pen.text(M + 452, y, "状态", size=10, bold=True, color=GRAY)
        y += 6
        page.draw_line(fitz.Point(M, y), fitz.Point(PW - M, y),
                       color=LINE, width=1)
        y += 14
        keys = sorted(fields, key=lambda k: k.encode("utf-8"))
        shown = keys[:14]
        for k in shown:
            rv = fields.get(k)
            d = diff_map.get(k)
            cv = d["candidate"] if d else rv
            pen.text(M, y, k, size=10)
            pen.text(M + 150, y, _fmt(rv), size=10)
            pen.text(M + 300, y, _fmt(cv), size=10,
                     bold=bool(d), color=RED if d else INK)
            pen.text(M + 452, y, "不同" if d else "一致", size=10,
                     bold=bool(d),
                     color=RED if d else (0.02, 0.58, 0.40))
            y += 15
        if len(keys) > len(shown):
            pen.text(M, y, f"其余 {len(keys) - len(shown)} 个字段略，"
                           "完整比对见验真报告 JSON。", size=9.5, color=GRAY)
            y += 15
    else:
        pen.text(M, y, "无语义字段（纯图像或无标签内容）", size=10.5)
        y += 16
    y += 8

    # 四、指纹与链上凭证 (空间不足时换页)
    if y > PH - 300:
        page = doc.new_page(width=PW, height=PH)
        freg, fbold, _e2 = _register_fonts(page)
        pen = _Pen(page, freg, fbold)
        y = 60
    y = pen.section(y, "四、指纹与链上凭证")
    exact = rp.get("exact") or {}
    rows = [("登记 SHA-256 根", exact.get("sha256_root")),
            ("登记 SM3 根", exact.get("sm3_root"))]
    if comp:
        rows += [("待验 SHA-256 根", comp["exact"]["sha256_root"]),
                 ("待验 SM3 根", comp["exact"]["sm3_root"])]
    rows += [("登记语义根", rp.get("semantic_root")),
             ("精确匹配", "SHA-256 "
              + ("一致" if report.get("exact_sha256_match") else "不一致")
              + " · SM3 "
              + ("一致" if report.get("exact_sm3_match") else "不一致")),
             ("回执编号", report.get("receipt_id")),
             ("回执入账哈希", report.get("receipt_entry_hash")),
             ("账本链头", ledger.head_hash()),
             ("外部锚定", anchor_line or "—")]
    for label, value in rows:
        y = pen.kv(y, label, value or "—", vsize=8.5, label_w=132) + 3
    y += 10

    # 页脚
    page.draw_line(fitz.Point(M, PH - 64), fitz.Point(PW - M, PH - 64),
                   color=LINE, width=1)
    pen.wrap(M, PH - 48,
             "说明：本报告由数玺原型系统生成，记录待验文件与登记原件的"
             "比对结果。凭报告编号与报告哈希可在数玺账本中复核，"
             "或使用独立证据包离线复核。本系统为竞赛演示原型，"
             "报告不构成法定证据效力的认定。",
             size=8.5, width=PW - 2 * M, leading=12, color=GRAY)
    doc.set_metadata({"title": f"数玺验真报告 {cert_id}",
                      "author": "数玺 SHUXI SEAL"})
    if embedded:
        doc.subset_fonts()
    return doc.tobytes()
