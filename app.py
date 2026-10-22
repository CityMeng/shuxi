# -*- coding: utf-8 -*-
"""
数玺 · 数据可信管理工具 (原型)
三页: 登记 / 验真 / 授权与账本 — 实现《数玺协议规范 v1.2》。

设计语言: Apple 风格 — 系统字体栈、#F5F5F7 浅灰底、白色大圆角卡片、
#0071E3 强调蓝、胶囊按钮; 结论先行 (冰山演示), 证据一键深挖。

数据目录: 环境变量 SHUXI_DATA_DIR, 缺省为项目下 data/。
演示口令: 环境变量 SHUXI_DEMO_PASS, 缺省 shuxi-demo (原型演示用,
正式部署应由各主体自行保管口令)。
"""
from __future__ import annotations

import io
import json
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "vectors"))

import streamlit as st  # noqa: E402

from engine import fp, grade as gr  # noqa: E402
from engine import service as svc  # noqa: E402
from engine.ledger import KeyPair, Ledger  # noqa: E402

DATA_DIR = os.environ.get("SHUXI_DATA_DIR", os.path.join(BASE_DIR, "data"))
DEMO_PASS = os.environ.get("SHUXI_DEMO_PASS", "shuxi-demo")
REGISTRAR_NAME = "示例新能源有限公司 · 财务部"
VERIFIER_NAME = "合作银行 · 核验岗"

GRADE_COLORS = {
    "甲级": "#34C759", "乙级": "#0071E3", "丙级": "#FF9F0A",
    "丁级": "#FF3B30", "丁级嫌疑": "#FF3B30", "待人工复核": "#8E8E93",
    "已作废": "#636366", "未登记": "#8E8E93",
}

CSS = """
<style>
html, body, [class*="css"], .stApp {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text",
               "PingFang SC", "Microsoft YaHei", sans-serif !important;
  color: #1D1D1F;
}
#MainMenu, footer, [data-testid="stDecoration"] { visibility: hidden; }
.block-container { max-width: 980px; padding-top: 2.2rem; }
h1, h2, h3 { letter-spacing: -0.02em; font-weight: 700; }
.stButton > button {
  border-radius: 980px; padding: 0.45rem 1.4rem; font-weight: 600;
  border: none; transition: all .18s ease;
}
.stButton > button:hover { opacity: .85; transform: translateY(-1px); }
div[data-testid="stExpander"] {
  background: #FFFFFF; border: 1px solid rgba(0,0,0,.06);
  border-radius: 18px; box-shadow: 0 4px 24px rgba(0,0,0,.05);
}
.sx-card {
  background: #FFFFFF; border: 1px solid rgba(0,0,0,.06);
  border-radius: 20px; padding: 26px 30px; margin: 14px 0;
  box-shadow: 0 8px 32px rgba(0,0,0,.06);
}
.sx-grade { font-size: 56px; font-weight: 800; letter-spacing: -0.03em; line-height: 1.05; }
.sx-conf { font-size: 17px; color: #6E6E73; }
.sx-cert-id { font-family: "SF Mono", ui-monospace, Menlo, monospace;
  font-size: 30px; font-weight: 700; letter-spacing: .02em; }
.sx-mono { font-family: "SF Mono", ui-monospace, Menlo, monospace;
  font-size: 12.5px; word-break: break-all; color: #3A3A3C; }
.sx-label { font-size: 12px; color: #86868B; text-transform: uppercase;
  letter-spacing: .08em; margin-bottom: 2px; }
.sx-chip { display: inline-block; background: #F5F5F7; border-radius: 980px;
  padding: 3px 12px; margin: 2px 4px 2px 0; font-size: 13px; color: #1D1D1F; }
.sx-hero-title { font-size: 40px; font-weight: 800; letter-spacing: -0.03em; }
.sx-sub { color: #6E6E73; font-size: 16px; margin-top: -6px; }
.stDataFrame { border-radius: 14px; overflow: hidden; }
</style>
"""


# ---------------------------------------------------------------- 数据与主体

def init_stores(data_dir: str):
    """初始化账本/登记包/主体密钥 (首次运行自动生成演示主体)。"""
    os.makedirs(data_dir, exist_ok=True)
    ledger = Ledger(os.path.join(data_dir, "ledger.jsonl"))
    packages = svc.PackageStore(os.path.join(data_dir, "packages.json"))
    actors_path = os.path.join(data_dir, "actors.json")
    actors: dict[str, KeyPair] = {}
    if os.path.exists(actors_path):
        raw = json.load(open(actors_path, encoding="utf-8"))
        for name, rec in raw.items():
            actors[name] = KeyPair.from_encrypted_pem(rec["privkey_pem"], DEMO_PASS)
    else:
        raw = {}
        for name in (REGISTRAR_NAME, VERIFIER_NAME):
            kp = KeyPair.generate()
            actors[name] = kp
            raw[name] = {"privkey_pem": kp.private_pem_encrypted(DEMO_PASS),
                         "pub": kp.public_b64, "fp": kp.fingerprint}
        with open(actors_path, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=1)
    return ledger, packages, actors


def ext_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def do_register(ledger, packages, registrar_kp, filename, data):
    return svc.register_file(ledger, packages, registrar_kp, REGISTRAR_NAME,
                             filename, data, ext_of(filename), DEMO_PASS)


def do_verify(ledger, packages, verifier_kp, cert_id, filename, data,
              auth_id=None):
    t0 = time.perf_counter()
    report = svc.verify_file(ledger, packages, verifier_kp, VERIFIER_NAME,
                             cert_id, data, ext_of(filename), filename,
                             auth_id=auth_id)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    comp = fp.compute_all(data, ext_of(filename))
    reg = ledger.find_registration(cert_id)
    return {"report": report, "comp": comp, "reg": reg, "data": data,
            "filename": filename, "elapsed_ms": elapsed_ms}


def find_cert_by_filename(ledger, filename):
    found = None
    for e in ledger.by_type("registration"):
        if e["payload"]["filename"] == filename:
            found = e["payload"]["cert_id"]
    return found


def do_batch(ledger, packages, verifier_kp, files):
    """批量验真: 按文件名匹配登记记录; 无匹配的只做勾稽审计。"""
    rows, stats = [], {}
    t0 = time.perf_counter()
    for filename, data in files:
        ts = time.perf_counter()
        cert = find_cert_by_filename(ledger, filename)
        if cert:
            rep = svc.verify_file(ledger, packages, verifier_kp, VERIFIER_NAME,
                                  cert, data, ext_of(filename), filename)
            grade, conf = rep.get("grade", "错误"), rep.get("confidence", "")
        else:
            comp = fp.compute_all(data, ext_of(filename))
            aud = gr.audit(data, ext_of(filename), comp["text"], comp["fields"])
            res = gr.grade_standalone(aud)
            grade, conf = res["grade"], str(res["confidence"])
        ms = (time.perf_counter() - ts) * 1000
        rows.append({"文件": filename, "凭证": cert or "—", "等级": grade,
                     "把握": conf, "耗时ms": round(ms, 1)})
        stats[grade] = stats.get(grade, 0) + 1
    return rows, stats, (time.perf_counter() - t0) * 1000


def seed_demo(ledger, packages, registrar_kp):
    """一键载入演示数据 (虚构样本): 已登记过则跳过。"""
    if ledger.by_type("registration"):
        return []
    import gen_samples
    gen_samples.main()
    sdir = os.path.join(BASE_DIR, "vectors", "samples")
    certs = []
    for name in ("report.txt", "contract_bad.txt", "scan_a.png"):
        with open(os.path.join(sdir, name), "rb") as f:
            certs.append(do_register(ledger, packages, registrar_kp, name, f.read()))
    return certs


def cert_qr_png(cert_id, payload):
    import qrcode
    text = json.dumps({
        "cert_id": cert_id, "filename": payload["filename"],
        "sha256_root": payload["exact"]["sha256_root"],
        "sm3_root": payload["exact"]["sm3_root"],
        "semantic_root": payload["semantic_root"],
    }, ensure_ascii=False)
    img = qrcode.make(text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- 通用渲染

def registrations(ledger):
    return [e["payload"] for e in ledger.by_type("registration")]


def grade_hero(report, elapsed_ms=None):
    g = report.get("grade", "错误")
    color = GRADE_COLORS.get(g, "#FF3B30")
    conf = report.get("confidence", "")
    try:
        conf_pct = f"{float(conf) * 100:.0f}%"
    except (TypeError, ValueError):
        conf_pct = conf
    extra = f" · 本次验真耗时 {elapsed_ms:.0f} ms" if elapsed_ms is not None else ""
    st.markdown(f"""
    <div class="sx-card">
      <div class="sx-label">验真结论</div>
      <div class="sx-grade" style="color:{color}">{g}</div>
      <div class="sx-conf">把握 {conf_pct}{extra}</div>
    </div>""", unsafe_allow_html=True)
    for r in report.get("reasons", []):
        st.markdown(f"- {r}")
    if report.get("error"):
        st.error(report["error"])


# ---------------------------------------------------------------- 页面: 登记

def page_register(ledger, packages, actors):
    st.markdown('<div class="sx-hero-title">登记</div>', unsafe_allow_html=True)
    st.markdown('<div class="sx-sub">为文件计算三层指纹并写入账本，领取防伪凭证。原件与字段明文不进账本。</div>',
                unsafe_allow_html=True)
    up = st.file_uploader("选择要登记的文件", key="reg_up",
                          type=["pdf", "docx", "xlsx", "txt", "csv", "md",
                                "png", "jpg", "jpeg"])
    if up is not None:
        data = up.getvalue()
        st.caption(f"{up.name} · {len(data)} 字节")
        if st.button("开始登记", type="primary"):
            try:
                cert = do_register(ledger, packages, actors[REGISTRAR_NAME],
                                   up.name, data)
                st.session_state["last_cert"] = cert
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    cert = st.session_state.get("last_cert")
    if cert:
        reg = ledger.find_registration(cert)
        if reg:
            p = reg["payload"]
            chips = "".join(f'<span class="sx-chip">{k}</span>' for k in p["field_keys"])
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"""
                <div class="sx-card">
                  <div class="sx-label">数玺凭证 · 登记成功</div>
                  <div class="sx-cert-id">{cert}</div>
                  <div style="margin:10px 0 4px">{p['filename']} · 登记主体 {p['registrar']}</div>
                  <div class="sx-label">精确根 SHA-256</div><div class="sx-mono">{p['exact']['sha256_root']}</div>
                  <div class="sx-label" style="margin-top:6px">精确根 SM3</div><div class="sx-mono">{p['exact']['sm3_root']}</div>
                  <div class="sx-label" style="margin-top:6px">语义根</div><div class="sx-mono">{p['semantic_root']}</div>
                  <div class="sx-label" style="margin-top:10px">已登记字段（仅名）</div><div>{chips or '无'}</div>
                </div>""", unsafe_allow_html=True)
                if p["degraded"]:
                    st.warning("降级登记：" + "、".join(p["degraded"])
                               + "（已按规范第 14 节注明）")
                if p["reg_audit"]:
                    st.info("登记时勾稽提示（老问题，只记录不判罪）："
                            + "；".join(i["msg"] for i in p["reg_audit"]))
            with col2:
                st.image(cert_qr_png(cert, p), caption="凭证二维码", width=180)


# ---------------------------------------------------------------- 页面: 验真

def page_verify(ledger, packages, actors):
    st.markdown('<div class="sx-hero-title">验真</div>', unsafe_allow_html=True)
    st.markdown('<div class="sx-sub">五步得出结论，每一步都可点开深挖底层证据。</div>',
                unsafe_allow_html=True)
    regs = registrations(ledger)
    if not regs:
        st.info("尚无登记记录。先到「登记」页登记一份文件，或在左侧一键载入演示数据。")
        return
    labels = {f"{p['cert_id']} · {p['filename']}": p["cert_id"] for p in regs}
    cert = labels[st.selectbox("选择凭证", list(labels))]
    reg = ledger.find_registration(cert)
    rp = reg["payload"]

    sample_dir = os.path.join(BASE_DIR, "vectors", "samples")
    quick = {}
    if os.path.isdir(sample_dir):
        quick = {n: os.path.join(sample_dir, n) for n in
                 ("report.txt", "report_tampered.txt", "report_converted.txt",
                  "scan_b.jpg") if os.path.exists(os.path.join(sample_dir, n))}
    col_a, col_b = st.columns(2)
    with col_a:
        up = st.file_uploader("上传待验文件", key="ver_up")
    with col_b:
        pick = st.selectbox("或选用演示文件", ["—"] + list(quick))

    data, fname = None, None
    if up is not None:
        data, fname = up.getvalue(), up.name
    elif pick != "—":
        with open(quick[pick], "rb") as f:
            data = f.read()
        fname = pick
    if data is not None and st.button("开始验真", type="primary"):
        st.session_state["last_verify"] = do_verify(
            ledger, packages, actors[VERIFIER_NAME], cert, fname, data)
        st.rerun()

    res = st.session_state.get("last_verify")
    if res and res["reg"] and res["reg"]["payload"]["cert_id"] == cert:
        report, comp = res["report"], res["comp"]
        grade_hero(report, res["elapsed_ms"])
        if "error" not in report:
            with st.expander("深挖证据 · 三层指纹 / 勾稽 / 报告凭证"):
                st.markdown("**第一层 · 精确指纹**")
                st.markdown(
                    f"<div class='sx-mono'>登记 SHA-256　{rp['exact']['sha256_root']}<br>"
                    f"待验 SHA-256　{comp['exact']['sha256_root']}<br>"
                    f"登记 SM3　　　{rp['exact']['sm3_root']}<br>"
                    f"待验 SM3　　　{comp['exact']['sm3_root']}</div>",
                    unsafe_allow_html=True)
                st.markdown("**第二层 · 感知指纹**")
                rp_h, cp_h = rp["phashes"], comp["perceptual"]["phashes"]
                if rp_h and cp_h and len(rp_h) == len(cp_h):
                    dists = [fp.hamming_hex(a, b) for a, b in zip(rp_h, cp_h)]
                    st.write(f"逐页汉明距离：{dists}（均值 "
                             f"{sum(dists) / len(dists):.2f}，阈值 ≤ 8）")
                else:
                    st.write(f"登记 {len(rp_h)} 页 / 待验 {len(cp_h)} 页"
                             "（页数不一致时感知哈希不参与判定）")
                sim = fp.text_similarity(rp_text(ledger, packages, cert), comp["text"])
                st.write(f"文本相似度（3-gram Jaccard）：{sim if sim is not None else '不可用'}（阈值 ≥ 0.90）")
                st.markdown("**第三层 · 语义字段**")
                pkg = packages.get(cert)
                rows = []
                keys = sorted(set((pkg["fields"] if pkg else {})) | set(comp["fields"]),
                              key=lambda k: k.encode("utf-8"))
                for k in keys:
                    rv = pkg["fields"].get(k) if pkg else None
                    cv = comp["fields"].get(k)
                    rows.append({"字段": k, "登记值": rv, "待验值": cv,
                                 "状态": "一致" if rv == cv else "不同"})
                if rows:
                    st.dataframe(rows, use_container_width=True, hide_index=True)
                else:
                    st.write("无语义字段（纯图像或无标签内容）")
                st.markdown(f"<div class='sx-mono'>登记语义根　{rp['semantic_root']}<br>"
                            f"待验语义根　{comp['semantic']['root']}</div>",
                            unsafe_allow_html=True)
                aud = gr.audit(res["data"], ext_of(res["filename"]),
                               comp["text"], comp["fields"])
                st.markdown("**勾稽复算**")
                if aud["issues"]:
                    for i in aud["issues"]:
                        st.write(f"- {i['code']}：{i['msg']}")
                else:
                    st.write("G1/G2 未见异常")
                for h in aud["hints"]:
                    st.write(f"- {h}")
                st.markdown("**验真报告凭证**")
                st.markdown(f"<div class='sx-mono'>回执编号　{report.get('receipt_id')}<br>"
                            f"报告哈希　{report.get('report_hash')}<br>"
                            f"回执入账　{report.get('receipt_entry_hash')}</div>",
                            unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                with c1:
                    st.download_button(
                        "下载验真报告 JSON",
                        json.dumps(report, ensure_ascii=False, indent=1),
                        file_name=f"shuxi-report-{cert}.json",
                        mime="application/json")
                with c2:
                    if st.button("复核这份报告"):
                        if svc.verify_report(ledger, report):
                            st.success("复核通过：报告未被篡改，且与账本回执一致。")
                        else:
                            st.error("复核不通过：报告与账本不一致。")

    st.divider()
    st.markdown("### 批量验真")
    st.caption("一次上传多份文件：按文件名自动匹配凭证，五十份也是一张表。")
    ups = st.file_uploader("批量上传", key="batch_up", accept_multiple_files=True)
    if ups and st.button("开始批量验真"):
        files = [(u.name, u.getvalue()) for u in ups]
        rows, stats, total = do_batch(ledger, packages, actors[VERIFIER_NAME], files)
        chips = "　".join(f"{g} × {n}" for g, n in stats.items())
        st.markdown(f"**{len(rows)} 份 · 总耗时 {total:.0f} ms**　{chips}")
        st.dataframe(rows, use_container_width=True, hide_index=True)


def rp_text(ledger, packages, cert):
    pkg = packages.get(cert)
    return pkg["text"] if pkg else ""


# ---------------------------------------------------------------- 页面: 授权与账本

def page_ledger(ledger, packages, actors):
    st.markdown('<div class="sx-hero-title">授权与账本</div>', unsafe_allow_html=True)
    st.markdown('<div class="sx-sub">授权有期限、有次数，每次查验都留回执；账本全链可验。</div>',
                unsafe_allow_html=True)
    ok, broken, reason = ledger.verify_chain()
    head = ledger.head_hash()
    st.markdown(f"""
    <div class="sx-card">
      <div class="sx-label">账本状态</div>
      <div style="font-size:22px;font-weight:700">{'全链校验通过' if ok else '链已断裂 @ ' + str(broken) + '：' + reason}</div>
      <div class="sx-mono" style="margin-top:6px">高度 {len(ledger.entries)} · 链头 {head}</div>
    </div>""", unsafe_allow_html=True)
    if st.button("写入检查点（封印当前链头）"):
        svc.checkpoint(ledger, actors[REGISTRAR_NAME])
        st.success("检查点已入账。")
        st.rerun()

    regs = registrations(ledger)
    labels = {f"{p['cert_id']} · {p['filename']}": p["cert_id"] for p in regs}
    st.markdown("### 新建授权")
    if labels:
        with st.form("auth_form"):
            cert = labels[st.selectbox("凭证", list(labels))]
            grantee = st.text_input("被授权方", VERIFIER_NAME)
            c1, c2 = st.columns(2)
            days = c1.number_input("有效天数", 1, 365, 7)
            maxc = c2.number_input("最多查验次数", 1, 100, 2)
            if st.form_submit_button("创建授权", type="primary"):
                au = svc.create_authorization(
                    ledger, actors[REGISTRAR_NAME], cert, grantee,
                    actors[VERIFIER_NAME].fingerprint, int(days), int(maxc))
                st.success(f"授权已入账：{au}")
                st.rerun()
    auths = ledger.by_type("authorization")
    if auths:
        rows = []
        for e in auths:
            p = e["payload"]
            chk = svc.check_authorization(ledger, p["auth_id"])
            rows.append({"授权号": p["auth_id"], "凭证": p["cert_id"],
                         "被授权方": p["grantee"], "已用/上限":
                         f"{chk['used']}/{p['max_count']}",
                         "状态": "有效" if chk["valid"] else chk["reason"]})
        st.dataframe(rows, use_container_width=True, hide_index=True)

    receipts = ledger.by_type("receipt")
    st.markdown("### 验真回执")
    if receipts:
        rows = [{"回执": e["payload"]["receipt_id"], "凭证": e["payload"]["cert_id"],
                 "验真方": e["payload"]["verifier"], "结论": e["payload"]["grade"],
                 "时间": e["ts"]} for e in receipts]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("暂无回执。")

    st.markdown("### 作废与密钥公告")
    if labels:
        cert = labels[st.selectbox("选择凭证", list(labels), key="revoke_cert")]
        state = svc.resolve_status(ledger, cert)
        st.caption(f"当前状态：{state['status']}"
                   + ("；".join(state["annotations"]) if state["annotations"] else ""))
        if st.button("作废这张凭证（登记方签名，不可逆）"):
            svc.revoke(ledger, actors[REGISTRAR_NAME], cert)
            st.success("已作废并入账。")
            st.rerun()


# ---------------------------------------------------------------- 主入口

def main():
    st.set_page_config(page_title="数玺", page_icon="玺", layout="centered")
    st.markdown(CSS, unsafe_allow_html=True)
    ledger, packages, actors = init_stores(DATA_DIR)
    with st.sidebar:
        st.markdown("## 数玺")
        st.caption("数据可信管理工具 · 原型\n规范 v1.2 · 套件 SXA1")
        page = st.radio("导航", ["登记", "验真", "授权与账本"])
        st.divider()
        ok, _, _ = ledger.verify_chain()
        st.caption(f"账本高度 {len(ledger.entries)} · "
                   f"{'全链可验' if ok else '链异常'}")
        if st.button("一键载入演示数据"):
            certs = seed_demo(ledger, packages, actors[REGISTRAR_NAME])
            st.success(f"已载入 {len(certs)} 张演示凭证" if certs else "演示数据已存在")
            st.rerun()
        st.caption("演示主体：登记方「示例新能源有限公司 · 财务部」、"
                   "验真方「合作银行 · 核验岗」（均为虚构）")
    if page == "登记":
        page_register(ledger, packages, actors)
    elif page == "验真":
        page_verify(ledger, packages, actors)
    else:
        page_ledger(ledger, packages, actors)


if __name__ == "__main__":
    main()
