# -*- coding: utf-8 -*-
"""
独立证据包 (自包含导出 + 离线复核)。

设计: 由登记方把某一凭证的全部复核材料打包成单个 JSON —
  登记条目、全账本条目副本、登记包 (字段表/盐/抽取文本)、
  最近检查点 (含外部锚定证明)、可选的当次验真报告。
任何人拿到证据包和待验文件, 在装有本仓库代码的机器上断网运行
  python verify_bundle.py 证据包.json 待验文件
即可独立重算三层指纹、复验全链签名与锚定绑定, 得到同一结论,
全程不依赖数玺平台在线服务。

诚实边界:
- 登记包按规范 §1 本只存登记方本地; 是否签发证据包 (即向复核方
  披露字段表与盐) 由登记方决定, 这本身就是一种授权行为。
- 证据包内是导出时刻的账本副本; 导出之后发生的作废等状态变化
  不在包内, 以在线账本为准。
- 证据包不含任何私钥材料: 登记包中的口令加密私钥 (privkey_pem)
  导出时剔除, 复核只需字段表/盐/抽取文本, 不需要私钥。
"""
import json
import os
import tempfile

from . import anchor as anchor_mod
from . import service as svc
from .ledger import KeyPair, Ledger

BUNDLE_FORMAT = "shuxi-evidence-bundle/1"
MAX_ENTRIES = 2000
# 导出时从登记包剔除的敏感键 (私钥绝不随证据包外发)
_BUNDLE_EXCLUDE_KEYS = ("privkey_pem",)


def build_bundle(ledger: Ledger, packages: svc.PackageStore, cert_id: str,
                 report: dict | None = None) -> dict:
    """把一张凭证的复核材料打包为自包含字典 (可直接 json 序列化)。"""
    reg = ledger.find_registration(cert_id)
    if reg is None:
        raise ValueError("凭证不存在")
    if len(ledger.entries) > MAX_ENTRIES:
        raise ValueError("账本条目过多, 超出证据包上限")
    pkg = packages.get(cert_id)
    if pkg is None:
        raise ValueError("登记包不存在, 无法签发完整证据包")
    # 浅拷贝后剔除: 不改动 PackageStore 内存中的原对象
    safe_pkg = {k: v for k, v in pkg.items() if k not in _BUNDLE_EXCLUDE_KEYS}
    checkpoints = ledger.by_type("checkpoint")
    return {
        "format": BUNDLE_FORMAT,
        "spec_version": svc.fp.SPEC_VERSION,
        "cert_id": cert_id,
        "registration": reg,
        "package": safe_pkg,
        "entries": ledger.entries,
        "checkpoint": checkpoints[-1] if checkpoints else None,
        "report": report,
    }


def verify_bundle(bundle: dict, data: bytes, ext: str,
                  filename: str) -> dict:
    """在临时账本上独立复核: 全链验签 → 锚定绑定 → 对待验文件重跑判定。

    返回 {chain_ok, chain_detail, anchor_status, report, grade_matches}。
    """
    if bundle.get("format") != BUNDLE_FORMAT:
        raise ValueError("证据包格式不符")
    tmp = tempfile.mkdtemp(prefix="shuxi-bundle-")
    lpath = os.path.join(tmp, "ledger.jsonl")
    with open(lpath, "w", encoding="utf-8") as f:
        for e in bundle["entries"]:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    ledger = Ledger(lpath)
    ok, bad_seq, why = ledger.verify_chain()
    packages = svc.PackageStore(os.path.join(tmp, "packages.json"))
    packages.save(bundle["cert_id"], bundle["package"])

    anchor_status = {"status": "none"}
    cp = bundle.get("checkpoint")
    if cp:
        anch = (cp.get("payload") or {}).get("anchor") or {}
        if anch.get("ots_b64"):
            bound = anchor_mod.verify_binding(
                anch["ots_b64"], (cp["payload"].get("head_hash") or ""))
            st = anchor_mod.proof_status(anch["ots_b64"])
            anchor_status = {**st, "binding_ok": bound}

    report = None
    if ok:
        verifier = KeyPair.generate()
        report = svc.verify_file(ledger, packages, verifier, "离线复核",
                                 bundle["cert_id"], data, ext, filename)
    bundled_grade = (bundle.get("report") or {}).get("grade")
    grade_matches = None
    if bundled_grade and report and "grade" in report:
        grade_matches = report["grade"] == bundled_grade
    return {"chain_ok": ok, "chain_detail": (bad_seq, why),
            "anchor_status": anchor_status, "report": report,
            "grade_matches": grade_matches}
