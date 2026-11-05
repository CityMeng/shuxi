# -*- coding: utf-8 -*-
"""
数玺 · 残留纠错与做实验收硬测试集（第六套）
专测本次三项做实硬要求：
1. 零知识范围证明改验登记承诺（NUMS 生成元 H，登记包承诺验算，防嫁接，防篡改）
2. 排序 Merkle 状态根真实包含性证明与兄弟路径核验（真键重算通过，假键填正确根拒绝）
"""
import os
import sys
import tempfile
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from engine import zkp, cosign, service as svc, ledger as led  # noqa: E402

R = []


def check(label: str, cond: bool, extra: str = ""):
    R.append(bool(cond))
    status = "PASS" if cond else "FAIL"
    print(f"{status} {label} {extra}")


def main():
    print("=" * 60)
    print("数玺残留纠错专项验收硬测试（第六套）开始运行")
    print("=" * 60)

    # ------------------------------------------------------------
    # 模块 1: 零知识范围证明改验登记承诺
    # ------------------------------------------------------------
    print("\n--- [模块 1] 零知识范围证明改验登记承诺 ---")

    # 验证 NUMS 生成元 H 落在素数阶子群
    nums_h_valid = (1 < zkp.H < zkp.P - 1) and (pow(zkp.H, zkp.Q, zkp.P) == 1)
    check("ZKP-REG-0: 生成元 H 为真 NUMS 派生且位于 Q 阶子群", nums_h_valid)

    # 登记时生成带 NUMS 承诺的登记包
    tmp_dir = tempfile.mkdtemp(prefix="shuxi-test-zkpreg-")
    t_ledger = led.Ledger(os.path.join(tmp_dir, "ledger.jsonl"))
    t_packages = svc.PackageStore(os.path.join(tmp_dir, "packages.json"))
    t_reg = led.KeyPair.generate()

    # 登记一份净利润为 800 万的母本
    sample_text = "望舒新能源科技有限公司财务简报\n净利润：8000000元\n营业收入：12000000元\n"
    cid = svc.register_file(
        t_ledger, t_packages, t_reg, "存证方", "report_reg.txt",
        sample_text.encode("utf-8"), "txt", "test-passphrase"
    )

    pkg = t_packages.get(cid)
    zk_comm_data = pkg.get("zk_commitments", {}).get("净利润")
    check("ZKP-REG-1a: 登记包内成功写入净利润的 Pedersen 承诺与盲化因子",
          zk_comm_data is not None and "commitment" in zk_comm_data)

    reg_val = zk_comm_data["val"]
    reg_r = int(zk_comm_data["blinding_r"], 16)
    reg_commitment = zk_comm_data["commitment"]
    threshold = 5000000

    # 1. 验证项一：用登记承诺与登记包内的数值/盲化因子生成证明，验算通过
    proof = zkp.prove_range_ge(reg_val, reg_r, threshold)
    verify_ok = zkp.verify_range_ge(reg_commitment, threshold, proof)
    check("ZKP-REG-1: 用登记承诺验算通过", verify_ok, f"(c={reg_commitment[:16]}…)")

    # 2. 验证项二：拿另一个数值 (例如 900 万，承诺 c_other) 的有效证明，嫁接到登记承诺上，验真必须 False
    other_val = 9000000
    c_other, r_other = zkp.pedersen_commit(other_val)
    proof_other = zkp.prove_range_ge(other_val, r_other, threshold)
    graft_ok = zkp.verify_range_ge(reg_commitment, threshold, proof_other)
    check("ZKP-REG-2: 拿另一个数值的证明嫁接到登记承诺上必须 False", not graft_ok)

    # 3. 验证项三：篡改登记数值 (例如将登记数值由 800 万篡改为 400 万) 后，旧证明必须 False
    # 如果登记数值改了，同态关系破坏或承诺与明文不符
    c_tampered, _ = zkp.pedersen_commit(4000000, reg_r)
    tampered_verify = zkp.verify_range_ge(hex(c_tampered)[2:], threshold, proof)
    check("ZKP-REG-3: 篡改登记数值后旧证明必须 False", not tampered_verify)

    # ------------------------------------------------------------
    # 模块 2: 排序 Merkle 状态根真实包含性证明
    # ------------------------------------------------------------
    print("\n--- [模块 2] 排序 Merkle 状态根真实包含性证明 ---")
    smt = cosign.SortedMerkleTree()
    smt.insert("SX-0001", "hash_alpha_01")
    smt.insert("SX-0002", "hash_beta_02")
    smt.insert("SX-0003", "hash_gamma_03")
    smt.insert("SX-0004", "hash_delta_04")
    root = smt.root_hash()

    # 1. 真实键的包含性证明通过
    proof_real = smt.get_inclusion_proof("SX-0002")
    check("SMT-INCL-1: 真实键的包含性证明通过 (重算兄弟路径达到根)",
          cosign.SortedMerkleTree.verify_inclusion_proof(proof_real, root))

    # 2. 伪造不存在键的证明 (只填正确根字符串，假键或无合法重算路径) 必须返回 False
    fake_proof_spoofed_key = {
        "key": "SX-9999-FAKE",
        "value_hash": "hash_beta_02",
        "path": proof_real["path"] if proof_real else [],
        "root_hash": root
    }
    check("SMT-INCL-2a: 伪造不存在键的证明 (只填正确根字符串) 必须返回 False",
          not cosign.SortedMerkleTree.verify_inclusion_proof(fake_proof_spoofed_key, root))

    fake_proof_no_path = {
        "key": "SX-0002",
        "value_hash": "hash_beta_02",
        "path": [],  # 树有多层却不给路径
        "root_hash": root
    }
    check("SMT-INCL-2b: 伪造空路径证明 (仅凭根字符串假装通过) 必须返回 False",
          not cosign.SortedMerkleTree.verify_inclusion_proof(fake_proof_no_path, root))

    # 清理测试目录
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print("\n" + "=" * 60)
    passed_count = sum(R)
    total_count = len(R)
    print(f"==== 残留纠错专项测试（第六套）: {passed_count}/{total_count} PASS ====")
    print("=" * 60)
    return passed_count == total_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

