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

print(f"\n==== 扩展测试: {sum(R)}/{len(R)} PASS ====")
sys.exit(0 if all(R) else 1)
