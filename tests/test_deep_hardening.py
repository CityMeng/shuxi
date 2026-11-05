# -*- coding: utf-8 -*-
"""
数玺 · 深度升级与做实验收硬测试集 (Deep Hardening Acceptance Test Suite)
专测五大深升级做实模块：
1. 真实 32 位比特分解零知识范围证明 (ZKP Range Proof)
2. 真实 Ed25519 门限共签与排序 Merkle 状态根 (Threshold Co-Signing & Sorted Merkle Root)
3. 冗余视觉嵌入模块安全移除验证 (Vision Embed Deletion)
4. 可插拔 DSL 规则引擎、别名归一与免重启动态加载 (Pluggable AST DSL Rules Engine)
5. 针对所选母本现场变异攻防沙盒 (Red-Blue Adversarial Mutation Engine)
"""
import base64
import json
import os
import sys
import tempfile
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from engine import zkp, cosign, dsl, sandbox, fp, grade as gr, service as svc, ledger as led  # noqa: E402

R = []


def check(label: str, cond: bool, extra: str = ""):
    R.append(bool(cond))
    status = "PASS" if cond else "FAIL"
    print(f"{status} {label} {extra}")


def main():
    print("=" * 60)
    print("数玺深度升级做实专项验收硬测试开始运行")
    print("=" * 60)

    # ------------------------------------------------------------
    # 模块 1: 真实 32 位比特分解零知识范围证明 (ZKP)
    # ------------------------------------------------------------
    print("\n--- [模块 1] 真实 32 位比特分解零知识范围证明 (ZKP) ---")
    val_pass, thresh = 8000000, 5000000
    c_pass, r_pass = zkp.pedersen_commit(val_pass)
    proof_pass = zkp.prove_range_ge(val_pass, r_pass, thresh)
    ok_pass = zkp.verify_range_ge(c_pass, thresh, proof_pass)
    check("ZKP-1: 800 万对门槛 500 万证明通过", ok_pass, f"(c={proof_pass['commitment'][:16]}…)")

    # 100 万对门槛 500 万: 正常证明必须直接拦截拒绝
    val_fail = 1000000
    c_fail, r_fail = zkp.pedersen_commit(val_fail)
    rejected_at_prover = False
    try:
        zkp.prove_range_ge(val_fail, r_fail, thresh)
    except ValueError as e:
        rejected_at_prover = True
    check("ZKP-2a: 100 万对门槛 500 万证明者生成直接拦截拒收", rejected_at_prover)

    # 任何方式伪造的证明在验证方必须返回 False
    # 伪造方式 1: 将 800 万的有效证明嫁接到 100 万的承诺上
    forged_1 = zkp.verify_range_ge(c_fail, thresh, proof_pass)
    check("ZKP-2b: 嫁接有效证明至 100 万承诺验真返回 False", not forged_1)

    # 伪造方式 2: 篡改证明中任意参数 (如篡改第一个比特承诺)
    tampered_p1 = dict(proof_pass)
    tampered_p1["bit_commitments"] = list(proof_pass["bit_commitments"])
    orig_b0 = int(tampered_p1["bit_commitments"][0], 16)
    tampered_p1["bit_commitments"][0] = hex((orig_b0 + 1) % zkp.P)[2:]
    t_ok1 = zkp.verify_range_ge(c_pass, thresh, tampered_p1)
    check("ZKP-3a: 篡改证明中比特承诺参数验真返回 False", not t_ok1)

    # 伪造方式 3: 篡改 Schnorr OR 响应标量 s0
    tampered_p2 = dict(proof_pass)
    tampered_p2["bit_proofs"] = [dict(p) for p in proof_pass["bit_proofs"]]
    tampered_p2["bit_proofs"][0]["s0"] = hex(99999999)[2:]
    t_ok2 = zkp.verify_range_ge(c_pass, thresh, tampered_p2)
    check("ZKP-3b: 篡改证明中 Schnorr 标量参数验真返回 False", not t_ok2)

    # 伪造方式 4: 篡改门槛值
    t_ok3 = zkp.verify_range_ge(c_pass, 6000000, proof_pass)
    check("ZKP-3c: 篡改门槛参数验真返回 False", not t_ok3)

    # ------------------------------------------------------------
    # 模块 2: 真实 Ed25519 门限共签与排序 Merkle 状态根
    # ------------------------------------------------------------
    print("\n--- [模块 2] 真实 Ed25519 门限共签与排序 Merkle 状态根 ---")
    tc = cosign.ThresholdCosign(threshold=2, total_signers=3)
    entry_hash = "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"

    e_wangshu = tc.sign_endorsement("望舒新能源 · 财务部", entry_hash)
    e_linxi = tc.sign_endorsement("临溪商业银行 · 风险管控部", entry_hash)
    e_zhongchuang = tc.sign_endorsement("中创公证仲裁云链 · 鉴证中心", entry_hash)

    # 2 份有效签名通过
    ok_2sig, agg_sig = tc.aggregate_and_verify(entry_hash, [e_wangshu, e_linxi])
    check("COSIGN-1: 2 份有效签名通过聚合核验", ok_2sig, f"(聚合摘要: {agg_sig[:16]}…)")

    # 只有 1 份不通过
    ok_1sig, msg_1sig = tc.aggregate_and_verify(entry_hash, [e_wangshu])
    check("COSIGN-2: 只有 1 份有效签名不通过", not ok_1sig, f"({msg_1sig})")

    # 错误私钥签名的不通过
    fake_key = Ed25519PrivateKey.generate()
    fake_sig_b64 = base64.b64encode(fake_key.sign(entry_hash.encode("utf-8"))).decode("ascii")
    e_forged = dict(e_wangshu)
    e_forged["signature_b64"] = fake_sig_b64
    ok_wrong, msg_wrong = tc.aggregate_and_verify(entry_hash, [e_forged, e_linxi])
    check("COSIGN-3: 错误密钥签名无法通过聚合核验", not ok_wrong, f"({msg_wrong})")

    # 同一主体重复签名不通过
    ok_dup, msg_dup = tc.aggregate_and_verify(entry_hash, [e_wangshu, e_wangshu])
    check("COSIGN-4: 同一主体重复签署不通过 (防重放)", not ok_dup, f"({msg_dup})")

    # 排序 Merkle 状态根树测试 (包含性证明验证真实路径重算)
    smt = cosign.SortedMerkleTree()
    smt.insert("SX-0001", "hash_0001")
    smt.insert("SX-0002", "hash_0002")
    smt_root = smt.root_hash()
    proof_smt = smt.get_inclusion_proof("SX-0001")
    check("COSIGN-5a: 真实键的包含性证明通过",
          cosign.SortedMerkleTree.verify_inclusion_proof(proof_smt, smt_root))

    # 伪造不存在键的证明 (只填正确根字符串但未提供合法重算路径) 必须返回 False
    fake_proof_smt = {
        "key": "SX-NON-EXISTENT",
        "value_hash": "hash_0001",
        "path": proof_smt["path"] if proof_smt else [],
        "root_hash": smt_root
    }
    check("COSIGN-5b: 伪造不存在键的证明 (只填正确根字符串) 必须返回 False",
          not cosign.SortedMerkleTree.verify_inclusion_proof(fake_proof_smt, smt_root))

    # ------------------------------------------------------------
    # 模块 3: 视觉嵌入模块安全移除验证
    # ------------------------------------------------------------
    print("\n--- [模块 3] 视觉嵌入模块安全移除验证 ---")
    vision_file_path = os.path.join(BASE_DIR, "engine", "vision_embed.py")
    check("CLEAN-1: engine/vision_embed.py 文件已物理删除", not os.path.exists(vision_file_path))
    with open(os.path.join(BASE_DIR, "app.py"), "r", encoding="utf-8") as f:
        app_code = f.read()
    check("CLEAN-2: app.py 已彻底移除 vision_embed 导入与调用", "vision_embed" not in app_code)

    # ------------------------------------------------------------
    # 模块 4: 可插拔 DSL 规则引擎与动态配置免重启验证
    # ------------------------------------------------------------
    print("\n--- [模块 4] 可插拔 DSL 规则引擎与别名归一测试 ---")
    # 别名映射测试: 本年净收益 映射到 净利润
    fields_alias = {
        "本年净收益": "4200000",
        "营业收入": "12500000",
        "营业成本": "8300000",
        "产品销售收入": "9000000",
        "服务收入": "3500000",
        "合计": "12500000"
    }
    dsl_res = dsl.evaluate_dsl_rules(fields_alias)
    check("DSL-1: 别名归一生效 (本年净收益自动映射为净利润)", len(dsl_res["passed"]) >= 3)
    check("DSL-2: AST 表达式求值无 eval 且容差比对无误", dsl_res["is_all_passed"])

    # 免重启动态修改配置文件测试
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        tmp_cfg_path = tf.name
        json.dump({
            "aliases": {},
            "rules": [{
                "id": "RULE-TEST-DYNAMIC",
                "name": "动态测试等式",
                "formula": "营业收入 == 营业成本 * 2",
                "tolerance": 0.05,
                "severity": "CRITICAL"
            }]
        }, tf)

    dyn_res1 = dsl.evaluate_dsl_rules({"营业收入": "200", "营业成本": "100"}, config_path=tmp_cfg_path)
    check("DSL-3a: 动态加载外部规则配置评估通过", len(dyn_res1["passed"]) == 1)

    # 立即修改该外部配置文件中公式为 3 倍，代码不重启再次求值
    with open(tmp_cfg_path, "w", encoding="utf-8") as tf:
        json.dump({
            "aliases": {},
            "rules": [{
                "id": "RULE-TEST-DYNAMIC",
                "name": "动态测试等式",
                "formula": "营业收入 == 营业成本 * 3",
                "tolerance": 0.05,
                "severity": "CRITICAL"
            }]
        }, tf)

    dyn_res2 = dsl.evaluate_dsl_rules({"营业收入": "200", "营业成本": "100"}, config_path=tmp_cfg_path)
    check("DSL-3b: 配置文件修改后无需重启代码评估结果即刻改变", len(dyn_res2["violated"]) == 1)
    if os.path.exists(tmp_cfg_path):
        os.remove(tmp_cfg_path)

    # ------------------------------------------------------------
    # 模块 5: 红蓝对抗母本动态变异攻防沙盒测试
    # ------------------------------------------------------------
    print("\n--- [模块 5] 红蓝对抗母本动态变异攻防沙盒测试 ---")
    samples_dir = os.path.join(BASE_DIR, "vectors", "samples")
    with open(os.path.join(samples_dir, "report.txt"), "r", encoding="utf-8") as f:
        demo_text = f.read()

    status_demo = sandbox.get_strategies_status(demo_text)
    check("SANDBOX-1: 演示母本具备全量攻击策略可用性",
          status_demo["A"]["available"] and status_demo["B"]["available"] and status_demo["C"]["available"])

    with open(os.path.join(samples_dir, "contract_bad.txt"), "r", encoding="utf-8") as f:
        contract_text = f.read()
    status_contract = sandbox.get_strategies_status(contract_text)
    check("SANDBOX-2: 缺少合计结构的文件策略 B/C 自动置灰并注明原因",
          status_contract["A"]["available"] and not status_contract["B"]["available"] and not status_contract["C"]["available"],
          f"({status_contract['B']['reason']})")

    # 运行变异件生成并实测判定结果
    tmp_ledger_dir = tempfile.mkdtemp(prefix="shuxi-test-sb-")
    t_ledger = led.Ledger(os.path.join(tmp_ledger_dir, "ledger.jsonl"))
    t_packages = svc.PackageStore(os.path.join(tmp_ledger_dir, "packages.json"))
    t_reg = led.KeyPair.generate()
    t_ver = led.KeyPair.generate()

    with open(os.path.join(samples_dir, "report.txt"), "rb") as f:
        report_bytes = f.read()
    demo_cid = svc.register_file(t_ledger, t_packages, t_reg, "存证方", "report.txt", report_bytes, "txt", "test-pass")

    # 策略 A 变异件实测
    mut_a, _ = sandbox.generate_variant(demo_text, "A")
    rep_a = svc.verify_file(t_ledger, t_packages, t_ver, "核验方", demo_cid, mut_a, "txt", "mutant_A.txt")
    check("SANDBOX-3a: 策略 A 对演示母本验真结果为 乙级 (内容等价)", rep_a["grade"] == "乙级", f"got {rep_a['grade']}")

    # 策略 B 变异件实测
    mut_b, _ = sandbox.generate_variant(demo_text, "B")
    rep_b = svc.verify_file(t_ledger, t_packages, t_ver, "核验方", demo_cid, mut_b, "txt", "mutant_B.txt")
    check("SANDBOX-3b: 策略 B 对演示母本验真结果为 丁级 (做平篡改定位拦截)", rep_b["grade"] == "丁级", f"got {rep_b['grade']}")

    # 策略 C 变异件实测 (随手查穿透 / 勾稽审查)
    mut_c, _ = sandbox.generate_variant(demo_text, "C")
    sa_c = svc.standalone_check(t_ledger, mut_c, "txt", "mutant_C.txt")
    check("SANDBOX-3c: 策略 C 对演示母本初判/穿透审查为 丙级 (勾稽矛盾穿帮)", sa_c["verdict"]["grade"] == "丙级", f"got {sa_c['verdict']['grade']}")

    # 清理临时目录
    import shutil
    shutil.rmtree(tmp_ledger_dir, ignore_errors=True)

    print("\n" + "=" * 60)
    passed_count = sum(R)
    total_count = len(R)
    print(f"==== 深度升级做实验收测试: {passed_count}/{total_count} PASS ====")
    print("=" * 60)
    return passed_count == total_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

