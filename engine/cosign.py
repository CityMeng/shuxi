# -*- coding: utf-8 -*-
"""
数玺 · 门限共签与状态根引擎 (Threshold Co-Signing & Sorted Merkle State Root)
实现基于 Ed25519 多方公私钥体系的门限联合共签机制 (m-of-n 门限背书) 与排序 Merkle 状态根 (Sorted Merkle State Root)。
多方共签使单方伪造无法通过聚合验证。
"""
import base64
import hashlib
import time
from typing import List, Dict, Any, Tuple, Optional
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization


class ThresholdCosign:
    """门限联合共签与聚合验签器 (Ed25519 多方签名，默认 2-of-3)"""

    DEMO_PARTIES = (
        "望舒新能源 · 财务部",
        "临溪商业银行 · 风险管控部",
        "中创公证仲裁云链 · 鉴证中心"
    )

    def __init__(self, threshold: int = 2, total_signers: int = 3):
        self.threshold = threshold
        self.total = total_signers
        self._private_keys: Dict[str, Ed25519PrivateKey] = {}
        self.authorized_signers: Dict[str, Dict[str, str]] = {}

        # 演示环境中三方私钥为公开演示密钥，由公开种子派生，任何人可复现，仅用于演示流程
        # 生产环境中各主体将在独立物理服务器或 HSM 硬件中自主持钥，私钥不进入代码仓库
        for name in self.DEMO_PARTIES[:total_signers]:
            seed = hashlib.sha256(f"SHUXI_ED25519_DEMO_SEED_{name}_v2".encode("utf-8")).digest()
            priv = Ed25519PrivateKey.from_private_bytes(seed)
            pub = priv.public_key()
            pub_bytes = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            pub_b64 = base64.b64encode(pub_bytes).decode("ascii")
            pub_fp = hashlib.sha256(pub_bytes).hexdigest()

            self._private_keys[name] = priv
            self.authorized_signers[name] = {
                "public_b64": pub_b64,
                "pub_fp": pub_fp
            }

    def sign_endorsement(self, actor_name: str, entry_hash: str) -> Dict[str, Any]:
        """指定背书主体对条目哈希执行真实的 Ed25519 签名"""
        if actor_name not in self._private_keys:
            raise ValueError(f"未授权或非公开演示主体的背书方: {actor_name}")

        priv = self._private_keys[actor_name]
        msg = entry_hash.encode("utf-8")
        sig_bytes = priv.sign(msg)
        sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

        auth_info = self.authorized_signers[actor_name]
        return {
            "actor": actor_name,
            "public_b64": auth_info["public_b64"],
            "pub_fp": auth_info["pub_fp"],
            "signature_b64": sig_b64,
            "entry_hash": entry_hash,
            "ts": int(time.time())
        }

    def verify_single_endorsement(self, endorsement: Dict[str, Any], expected_entry_hash: Optional[str] = None) -> Tuple[bool, str]:
        """核验单个背书签名的真实性与授权合法性"""
        actor = endorsement.get("actor")
        if not actor or actor not in self.authorized_signers:
            return False, f"未授权的背书主体: {actor}"

        expected_pub = self.authorized_signers[actor]["public_b64"]
        if endorsement.get("public_b64") != expected_pub:
            return False, f"背书公钥与授权注册不匹配: {actor}"

        item_hash = endorsement.get("entry_hash")
        if expected_entry_hash and item_hash != expected_entry_hash:
            return False, f"背书针对的条目哈希与待验目标不一致"

        sig_b64 = endorsement.get("signature_b64")
        if not sig_b64:
            return False, "签名数据缺失"

        try:
            pub_bytes = base64.b64decode(expected_pub)
            pub = Ed25519PublicKey.from_public_bytes(pub_bytes)
            sig_bytes = base64.b64decode(sig_b64)
            pub.verify(sig_bytes, item_hash.encode("utf-8"))
            return True, "签名核验有效"
        except Exception as e:
            return False, f"Ed25519 签名无效: {str(e)}"

    def aggregate_and_verify(self, entry_hash: str, endorsements: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        聚合门限核验:
        1. 收集不少于门限数 (threshold) 的背书
        2. 校验背书主体无重复
        3. 对每份背书执行真实的 Ed25519 签名验签
        4. 全部通过后计算不可篡改的联合共识指纹
        """
        if len(endorsements) < self.threshold:
            return False, f"未达到共识门槛: 当前 {len(endorsements)} 份 / 需 {self.threshold} 份有效签名"

        seen_actors = set()
        valid_signatures = []

        for end in endorsements:
            actor = end.get("actor")
            if not actor:
                return False, "缺少主体信息"
            if actor in seen_actors:
                return False, f"检测到重放或重复签署主体: {actor}"
            seen_actors.add(actor)

            ok, reason = self.verify_single_endorsement(end, expected_entry_hash=entry_hash)
            if not ok:
                return False, reason
            valid_signatures.append(f"{actor}:{end.get('signature_b64')}")

        # 联合共识防伪摘要
        agg_raw = f"{entry_hash}:" + ":".join(sorted(valid_signatures))
        agg_sig = hashlib.sha256(agg_raw.encode("utf-8")).hexdigest()
        return True, agg_sig


def _smt_leaf_hash(key: str, value_hash: str) -> bytes:
    """排序 Merkle 树叶子域哈希: SHA-256(0x00 | key | : | value_hash)"""
    data = f"{key}:{value_hash}".encode("utf-8")
    return hashlib.sha256(b"\x00" + data).digest()


def _smt_node_hash(left: bytes, right: bytes) -> bytes:
    """排序 Merkle 树内部节点域哈希: SHA-256(0x01 | left | right)"""
    return hashlib.sha256(b"\x01" + left + right).digest()


class SortedMerkleTree:
    """排序 Merkle 状态根树 (Sorted Merkle State Root & Audit Path)"""
    def __init__(self):
        self.leaves: Dict[str, str] = {}

    def insert(self, key: str, value_hash: str) -> str:
        self.leaves[key] = value_hash
        return self.root_hash()

    def _sorted_items(self) -> List[Tuple[str, str]]:
        return sorted(self.leaves.items(), key=lambda x: x[0].encode("utf-8"))

    def root_hash(self) -> str:
        if not self.leaves:
            return hashlib.sha256(b"\x00EMPTY_SORTED_MERKLE_ROOT").hexdigest()
        items = self._sorted_items()
        level = [_smt_leaf_hash(k, v) for k, v in items]
        while len(level) > 1:
            if len(level) % 2 == 1:
                level.append(level[-1])
            level = [_smt_node_hash(level[i], level[i + 1]) for i in range(0, len(level), 2)]
        return level[0].hex()

    def get_inclusion_proof(self, key: str) -> Optional[Dict[str, Any]]:
        """
        生成键值在当前状态根中的真 Merkle 排序包含性证明 (包含兄弟节点哈希路径)。
        """
        if key not in self.leaves:
            return None
        items = self._sorted_items()
        idx = [k for k, _ in items].index(key)
        leaf_hashes = [_smt_leaf_hash(k, v) for k, v in items]

        path: List[Dict[str, Any]] = []
        cur_idx = idx
        level = list(leaf_hashes)
        while len(level) > 1:
            if len(level) % 2 == 1:
                level.append(level[-1])
            if cur_idx % 2 == 0:
                path.append({"sibling": level[cur_idx + 1].hex(), "is_right": True})
            else:
                path.append({"sibling": level[cur_idx - 1].hex(), "is_right": False})
            level = [_smt_node_hash(level[i], level[i + 1]) for i in range(0, len(level), 2)]
            cur_idx //= 2

        return {
            "key": key,
            "value_hash": self.leaves[key],
            "index": idx,
            "total_leaves": len(items),
            "path": path,
            "root_hash": self.root_hash()
        }

    @staticmethod
    def verify_inclusion_proof(proof: Dict[str, Any], root: str) -> bool:
        """
        严格核验包含性证明：从叶子节点起沿兄弟路径逐层重算到根，与目标根一致才算通过。
        严禁仅比对根字符串。
        """
        if not proof or not isinstance(proof, dict):
            return False
        if proof.get("root_hash") != root:
            return False
        key = proof.get("key")
        val_hash = proof.get("value_hash")
        if not key or not val_hash:
            return False
        path = proof.get("path")
        if path is None or not isinstance(path, list):
            return False

        # 如果树上只有 1 个叶子，path 为 []
        cur = _smt_leaf_hash(key, val_hash)
        for step in path:
            if not isinstance(step, dict) or "sibling" not in step or "is_right" not in step:
                return False
            try:
                sib = bytes.fromhex(step["sibling"])
            except Exception:
                return False
            if step["is_right"]:
                cur = _smt_node_hash(cur, sib)
            else:
                cur = _smt_node_hash(sib, cur)

        return cur.hex() == root


# 兼容既有调用别名
MPTStateTree = SortedMerkleTree
