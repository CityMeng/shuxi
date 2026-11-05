# -*- coding: utf-8 -*-
"""
数玺 · 零知识断言与同态承诺引擎 (Zero-Knowledge Range & Predicate Prover)
实现轻量级离散对数 Pedersen 承诺与 32 位比特分解非交互式零知识范围证明 (基于 Schnorr 1-out-of-2 OR 证明与 Fiat-Shamir 启发式)。
无需依赖重型 C++ 外部库，纯 Python 离线实现，严格遵循标准密码学大素数群。
"""
import hashlib
import os
from typing import Tuple, Dict, Any, List

# RFC 3526 2048-bit MODP Group (第 35 节安全参数)
_PRIME_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF"
)
P = int(_PRIME_HEX, 16)
Q = (P - 1) // 2
G = 2

# 通过标准 NUMS (Nothing-Up-My-Sleeve) 哈希试错派生第二个独立生成元 H
# 针对计数器计算 SHA-256 并寻找二次剩余，确保落入素数阶子群 (阶为 Q)
# 该派生过程单向公开且无后门陷门，数学上确保任何人无法计算 log_G(H)
def _derive_nums_h() -> int:
    counter = 0
    while True:
        h_bytes = hashlib.sha256(f"SHUXI_PEDERSEN_NUMS_GENERATOR_H_v3:{counter}".encode("utf-8")).digest()
        candidate = int.from_bytes(h_bytes, "big")
        # 检验 candidate 是否落入 Q 阶素数子群 (在 MODP 群中即二次剩余判定: candidate^Q == 1 mod P)
        if 1 < candidate < P - 1 and pow(candidate, Q, P) == 1:
            return candidate
        counter += 1

H = _derive_nums_h()
G_INV = pow(G, -1 % Q, P)


def pedersen_commit(val: int, r: int | None = None) -> Tuple[int, int]:
    """生成 Pedersen 同态承诺: C = G^val * H^r mod P"""
    if r is None:
        r = int.from_bytes(os.urandom(32), "big") % Q
    c = (pow(G, val % Q, P) * pow(H, r % Q, P)) % P
    return c, r


def _prove_single_bit(b: int, r_i: int, c_i: int, bit_idx: int) -> Dict[str, Any]:
    """
    针对单比特承诺 C_i = G^b * H^r_i mod P 生成 1-out-of-2 Schnorr OR 证明 (证 b in {0, 1})
    """
    c0_node = c_i
    c1_node = (c_i * G_INV) % P

    if b == 0:
        # 分支 1: 模拟假分支
        c1 = int.from_bytes(os.urandom(32), "big") % Q
        s1 = int.from_bytes(os.urandom(32), "big") % Q
        a1 = (pow(H, s1, P) * pow(c1_node, -c1 % Q, P)) % P

        # 分支 0: 真实见证
        w0 = int.from_bytes(os.urandom(32), "big") % Q
        a0 = pow(H, w0, P)

        # Fiat-Shamir 哈希派生总挑战
        ch_raw = f"{G}:{H}:{c_i}:{bit_idx}:{a0}:{a1}".encode("utf-8")
        c_total = int.from_bytes(hashlib.sha256(ch_raw).digest(), "big") % Q
        c0 = (c_total - c1) % Q
        s0 = (w0 + c0 * r_i) % Q
    elif b == 1:
        # 分支 0: 模拟假分支
        c0 = int.from_bytes(os.urandom(32), "big") % Q
        s0 = int.from_bytes(os.urandom(32), "big") % Q
        a0 = (pow(H, s0, P) * pow(c0_node, -c0 % Q, P)) % P

        # 分支 1: 真实见证
        w1 = int.from_bytes(os.urandom(32), "big") % Q
        a1 = pow(H, w1, P)

        # Fiat-Shamir 哈希派生总挑战
        ch_raw = f"{G}:{H}:{c_i}:{bit_idx}:{a0}:{a1}".encode("utf-8")
        c_total = int.from_bytes(hashlib.sha256(ch_raw).digest(), "big") % Q
        c1 = (c_total - c0) % Q
        s1 = (w1 + c1 * r_i) % Q
    else:
        raise ValueError(f"比特值必须为 0 或 1，收到: {b}")

    return {
        "A0": hex(a0)[2:],
        "A1": hex(a1)[2:],
        "c0": hex(c0)[2:],
        "c1": hex(c1)[2:],
        "s0": hex(s0)[2:],
        "s1": hex(s1)[2:]
    }


def _verify_single_bit(c_i: int, bit_idx: int, p_dict: Dict[str, Any]) -> bool:
    """核验单比特 Schnorr OR 证明"""
    try:
        a0 = int(p_dict["A0"], 16)
        a1 = int(p_dict["A1"], 16)
        c0 = int(p_dict["c0"], 16)
        c1 = int(p_dict["c1"], 16)
        s0 = int(p_dict["s0"], 16)
        s1 = int(p_dict["s1"], 16)

        c0_node = c_i
        c1_node = (c_i * G_INV) % P

        ch_raw = f"{G}:{H}:{c_i}:{bit_idx}:{a0}:{a1}".encode("utf-8")
        c_total = int.from_bytes(hashlib.sha256(ch_raw).digest(), "big") % Q
        if (c0 + c1) % Q != c_total:
            return False

        if pow(H, s0, P) != (a0 * pow(c0_node, c0, P)) % P:
            return False
        if pow(H, s1, P) != (a1 * pow(c1_node, c1, P)) % P:
            return False

        return True
    except Exception:
        return False


def prove_range_ge(val: int, r: int, threshold: int, bits_count: int = 32) -> Dict[str, Any]:
    """
    32 位比特分解非交互式零知识范围证明 (ZK Range Proof: val >= threshold):
    证明者对 delta = val - threshold 进行 32 位比特分解 (b_0, ..., b_31)，
    为每一位生成独立承诺 C_i 与 Schnorr OR 证明 (证每一位 b_i in {0, 1})。
    各承诺按权重复合必须等于同态差值承诺 C_delta = C_val * G^(-threshold) mod P。
    验证方仅凭公共承诺 C_val、门槛 threshold 与证明参数核验，绝不接触具体明文 val。
    """
    delta = val - threshold
    if delta < 0:
        raise ValueError(f"数值 {val} 小于门槛 {threshold}，差值为负，无法生成合法零知识范围证明")
    if delta >= (1 << bits_count):
        raise ValueError(f"差值 {delta} 超出 {bits_count} 位范围表示上限")

    # 分解盲化因子: sum_{i=0}^{31} r_i * 2^i = r mod Q
    # 前 31 位随机选取，最后一位按同余方程唯一确定
    inv_pow2_last = pow(1 << (bits_count - 1), -1, Q)
    r_bits: List[int] = [int.from_bytes(os.urandom(32), "big") % Q for _ in range(bits_count - 1)]
    sum_r = sum((r_bits[i] * (1 << i)) % Q for i in range(bits_count - 1)) % Q
    r_last = ((r - sum_r) * inv_pow2_last) % Q
    r_bits.append(r_last)

    bit_commitments: List[str] = []
    bit_proofs: List[Dict[str, str]] = []

    for i in range(bits_count):
        bi = (delta >> i) & 1
        ri = r_bits[i]
        ci = (pow(G, bi, P) * pow(H, ri, P)) % P
        bit_commitments.append(hex(ci)[2:])
        bit_proofs.append(_prove_single_bit(bi, ri, ci, i))

    commit_val, _ = pedersen_commit(val, r)

    return {
        "type": "zkp_bit_decomposition_range_32",
        "bits": bits_count,
        "threshold": threshold,
        "commitment": hex(commit_val)[2:],
        "bit_commitments": bit_commitments,
        "bit_proofs": bit_proofs
    }


def verify_range_ge(commitment: str | int, threshold: int, proof: Dict[str, Any]) -> bool:
    """
    核验 32 位比特分解零知识范围证明 (验证方零明文输入):
    1. 校验同态减法: C_delta = C * G^(-threshold) mod P
    2. 校验权重复合: prod_{i=0}^{31} (C_i)^(2^i) == C_delta mod P
    3. 校验每一位: b_i in {0, 1} 的 Schnorr OR 证明
    """
    try:
        if isinstance(commitment, str):
            c_val = int(commitment, 16)
        else:
            c_val = int(commitment)

        p_thresh = int(proof["threshold"])
        if p_thresh != int(threshold):
            return False

        p_commit = int(proof["commitment"], 16)
        if p_commit != c_val:
            return False

        bits_count = int(proof.get("bits", 32))
        bit_commit_hexes = proof["bit_commitments"]
        bit_proof_list = proof["bit_proofs"]

        if len(bit_commit_hexes) != bits_count or len(bit_proof_list) != bits_count:
            return False

        bit_commits = [int(h, 16) for h in bit_commit_hexes]

        # 1. 计算同态差值目标承诺 C_delta
        c_delta = (c_val * pow(G, (-threshold) % Q, P)) % P

        # 2. 累乘复合各比特承诺
        prod_c = 1
        for i in range(bits_count):
            ci = bit_commits[i]
            # 校验单比特有效性
            if not _verify_single_bit(ci, i, bit_proof_list[i]):
                return False
            # 按 2^i 权重复合
            prod_c = (prod_c * pow(ci, 1 << i, P)) % P

        # 3. 校验权重复合值与同态目标是否一致
        return prod_c == c_delta
    except Exception:
        return False


# 保持向后兼容别名
def prove_predicate_ge(val: int, r: int, threshold: int) -> Dict[str, Any]:
    return prove_range_ge(val, r, threshold)


def verify_predicate_ge(proof: Dict[str, Any]) -> bool:
    try:
        return verify_range_ge(proof["commitment"], int(proof["threshold"]), proof)
    except Exception:
        return False
