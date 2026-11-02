# -*- coding: utf-8 -*-
"""扩展测试: 外部时间锚定 (engine/anchor) + 独立证据包 (engine/bundle)。"""
import json
import os
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
sys.path.insert(0, ROOT)
os.environ["SHUXI_ANCHOR"] = "off"  # 套件内不真连公共日历 (夹具是真证明)

from engine import anchor as anchor_mod  # noqa: E402
from engine import bundle as bundle_mod  # noqa: E402
from engine import service as svc  # noqa: E402
from engine.ledger import KeyPair, Ledger  # noqa: E402

R = []
def check(name, cond):
    R.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name)

fx = json.load(open(os.path.join(BASE, "fixtures", "ots_fixture.json"),
                    encoding="utf-8"))
check("锚定夹具绑定校验为真", anchor_mod.verify_binding(fx["ots_b64"], fx["digest"]))
check("锚定夹具绑定错摘要为假",
      not anchor_mod.verify_binding(fx["ots_b64"], "00" * 32))
st = anchor_mod.proof_status(fx["ots_b64"])
check("锚定夹具状态可解析", st["status"] in ("pending", "bitcoin"))
check("锚定停用模式如实标注",
      anchor_mod.stamp_digest(fx["digest"])["status"] == "disabled")

# 日历全灭时 stamp 降级不抛错
saved = anchor_mod.DEFAULT_CALENDARS
anchor_mod.DEFAULT_CALENDARS = ("http://127.0.0.1:9",)
del os.environ["SHUXI_ANCHOR"]
try:
    r = anchor_mod.stamp_digest(fx["digest"])
finally:
    anchor_mod.DEFAULT_CALENDARS = saved
    os.environ["SHUXI_ANCHOR"] = "off"
check("锚定日历不可达降级为 failed", r["status"] == "failed" and r["ots_b64"] is None)

# AnchorStore 往返
p = os.path.join(tempfile.mkdtemp(), "anchors.json")
anchor_mod.AnchorStore(p).put(3, fx["ots_b64"])
check("锚定旁路存储往返", anchor_mod.AnchorStore(p).get(3) == fx["ots_b64"])

# 检查点携带锚点入账且全链仍可验
tmp = tempfile.mkdtemp()
ledger = Ledger(os.path.join(tmp, "ledger.jsonl"))
packages = svc.PackageStore(os.path.join(tmp, "packages.json"))
reg, ver = KeyPair.generate(), KeyPair.generate()
data = open(os.path.join(ROOT, "vectors", "samples", "report.txt"), "rb").read()
tamp = open(os.path.join(ROOT, "vectors", "samples", "report_tampered.txt"),
            "rb").read()
cert = svc.register_file(ledger, packages, reg, "登记方", "report.txt",
                         data, "txt", "pass")
anch = anchor_mod.stamp_digest(ledger.head_hash())
svc.checkpoint(ledger, reg, anchor=anch)
cp = ledger.by_type("checkpoint")[-1]
check("检查点携带锚点入账", cp["payload"]["anchor"]["status"] == "disabled")
ok, _, _ = ledger.verify_chain()
check("带锚点检查点全链可验", ok)

# 证据包: 原件复核同结论 / 篡改件出丁级 / 改包内条目被链校验抓出
rep = svc.verify_file(ledger, packages, ver, "验真方", cert, data, "txt",
                      "report.txt")
b = json.loads(json.dumps(bundle_mod.build_bundle(ledger, packages, cert,
                                                  report=rep),
                          ensure_ascii=False))
r1 = bundle_mod.verify_bundle(b, data, "txt", "report.txt")
check("证据包原件复核甲级且结论一致",
      r1["chain_ok"] and r1["report"]["grade"] == rep["grade"]
      and r1["grade_matches"])
r2 = bundle_mod.verify_bundle(b, tamp, "txt", "report_tampered.txt")
check("证据包篡改件复核丁级", r2["report"]["grade"] == "丁级")
b_bad = json.loads(json.dumps(b))
b_bad["entries"][0]["payload"]["filename"] = "evil.txt"
r3 = bundle_mod.verify_bundle(b_bad, data, "txt", "report.txt")
check("证据包内条目被改可检出", r3["chain_ok"] is False)

# CLI 离线复核退出码
bp = os.path.join(tmp, "bundle.json")
fp_ = os.path.join(tmp, "report.txt")
with open(bp, "w", encoding="utf-8") as f:
    json.dump(b, f, ensure_ascii=False)
with open(fp_, "wb") as f:
    f.write(data)
proc = subprocess.run([sys.executable, os.path.join(ROOT, "verify_bundle.py"),
                       bp, fp_], capture_output=True, text=True, timeout=120)
check("离线复核脚本退出码 0", proc.returncode == 0 and "甲级" in proc.stdout)

# 随手查: 精确反查命中 / 勾稽异常判丙 / 空账本未登记
def _load(n):
    with open(os.path.join(ROOT, "vectors", "samples", n), "rb") as f:
        return f.read()

sa1 = svc.standalone_check(ledger, _load("report.txt"), "txt", "report.txt")
check("随手查原件反查命中判甲级",
      sa1["matched_cert"] == cert and sa1["verdict"]["grade"] == "甲级")
sa2 = svc.standalone_check(ledger, _load("fake.txt"), "txt", "fake.txt")
check("随手查勾稽不平判丙级", sa2["verdict"]["grade"] == "丙级")
sa3 = svc.standalone_check(ledger, _load("contract_bad.txt"), "txt",
                           "contract_bad.txt")
check("随手查大小写不符判丙级", sa3["verdict"]["grade"] == "丙级")
l_empty = Ledger(os.path.join(tempfile.mkdtemp(), "ledger.jsonl"))
sa4 = svc.standalone_check(l_empty, _load("report.txt"), "txt", "report.txt")
check("随手查空账本判未登记",
      sa4["verdict"]["grade"] == "未登记" and sa4["matched_cert"] is None)

# PDF 验真报告 + 锚定摘要
import fitz as _fitz
from engine import report_pdf as _rpm
from engine.anchor import latest_anchor_summary as _las
_pdf = _rpm.build_report_pdf(ledger, packages, cert, rep, _las(ledger, tmp))
check("PDF 验真报告生成", _pdf[:4] == b"%PDF" and 3000 < len(_pdf) < 500000)
_doc = _fitz.open(stream=_pdf, filetype="pdf")
_ptxt = "".join(p.get_text() for p in _doc)
check("PDF 报告含凭证号与等级",
      cert in _ptxt and rep["grade"] in _ptxt)
check("锚定摘要返回一句话", isinstance(_las(ledger, tmp), str)
      and len(_las(ledger, tmp)) >= 6)

# 改名迁移回归: 旧名 actors.json 启动后, 当前主体自动补齐且旧条目保留
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location(
    "shuxi_app", os.path.join(ROOT, "app.py"))
_app = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_app)
_mig_dir = tempfile.mkdtemp()
_old_kp = KeyPair.generate()
_old_raw = {"示例新能源有限公司 · 财务部": {
    "privkey_pem": _old_kp.private_pem_encrypted(_app.DEMO_PASS),
    "pub": _old_kp.public_b64, "fp": _old_kp.fingerprint}}
with open(os.path.join(_mig_dir, "actors.json"), "w",
          encoding="utf-8") as _f:
    json.dump(_old_raw, _f, ensure_ascii=False)
_l3, _p3, _a3 = _app.init_stores(_mig_dir)
check("改名后旧实例自动补齐当前主体密钥",
      _app.REGISTRAR_NAME in _a3 and _app.VERIFIER_NAME in _a3
      and "示例新能源有限公司 · 财务部" in _a3)

print(f"\n==== 扩展测试: {sum(R)}/{len(R)} PASS ====")
sys.exit(0 if all(R) else 1)
