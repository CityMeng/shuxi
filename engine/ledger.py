# -*- coding: utf-8 -*-
"""
数玺核心引擎 · 账本与密钥 (实现《数玺协议规范 v1.2》第 2、11、12 节)

设计要点 (含社区通行做法的采纳记录):
  - 规范序列化: 等价 RFC 8785 (JCS) — 键按字典序、紧凑分隔符、UTF-8、
    禁 NaN; 且负载中**禁止浮点数** (社区共识: 数字是签名跨实现翻车的
    头号原因), 一切数值以 int 或 str 形式入账。
  - 哈希链: JSONL 追加写; 条目哈希 = SHA-256(域标签 | 上条哈希 | 规范
    序列化), 每条自带签名者公钥与 Ed25519 签名 (规范允许 SM2 或
    Ed25519, 本实现选 Ed25519), 任何人离线可验全链。
  - 检查点即"封印": 含条目序号与链头哈希, 预留外部时间锚字段
    (RFC 3161 / 公链), 防尾部截断在锚定后不可隐匿。
  - 私钥只存登记包, 以口令加密的 PEM 形式落盘 (规范 §11)。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=8))
GENESIS_HASH = "0" * 64
_ENTRY_DOMAIN = b"shuxi-entry-v1\x00"


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


# ---------------------------------------------------------------- 规范序列化

def _reject_floats(obj, path="$"):
    if isinstance(obj, float):
        raise ValueError(f"canonical: 负载禁止浮点数 ({path}), 请改用 int 或 str")
    if isinstance(obj, dict):
        for k, v in obj.items():
            _reject_floats(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _reject_floats(v, f"{path}[{i}]")


def canonical_bytes(obj) -> bytes:
    """RFC 8785 等价的规范序列化 (键字典序/紧凑/UTF-8/禁 NaN 与浮点)。"""
    _reject_floats(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


# ---------------------------------------------------------------- 密钥

class KeyPair:
    """Ed25519 密钥对 (规范 §2 允许 SM2 或 Ed25519)。"""

    def __init__(self, priv):
        self._priv = priv

    @classmethod
    def generate(cls) -> "KeyPair":
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        return cls(Ed25519PrivateKey.generate())

    @property
    def public_raw(self) -> bytes:
        from cryptography.hazmat.primitives import serialization
        return self._priv.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    @property
    def public_b64(self) -> str:
        return base64.b64encode(self.public_raw).decode()

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.public_raw).hexdigest()

    def sign(self, msg: bytes) -> str:
        return base64.b64encode(self._priv.sign(msg)).decode()

    def private_pem_encrypted(self, passphrase: str) -> str:
        from cryptography.hazmat.primitives import serialization
        pem = self._priv.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(passphrase.encode("utf-8")))
        return pem.decode()

    @classmethod
    def from_encrypted_pem(cls, pem: str, passphrase: str) -> "KeyPair":
        from cryptography.hazmat.primitives import serialization
        priv = serialization.load_pem_private_key(
            pem.encode(), password=passphrase.encode("utf-8"))
        return cls(priv)


def verify_signature(public_b64: str, msg: bytes, sig_b64: str) -> bool:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_b64))
        pub.verify(base64.b64decode(sig_b64), msg)
        return True
    except Exception:
        return False


def fingerprint_of(public_b64: str) -> str:
    return hashlib.sha256(base64.b64decode(public_b64)).hexdigest()


# ---------------------------------------------------------------- 哈希链账本

class Ledger:
    """追加写 JSONL 哈希链。条目结构:
    {seq, ts, type, payload, prev_hash, signer_fp, signer_pub, sig, hash}
    hash = SHA-256(域标签 | prev_hash | canonical(除 sig/hash 外的全部字段))
    sig  = 签名者对 hash 字节的 Ed25519 签名。
    """

    def __init__(self, path: str):
        self.path = path
        self.entries: list[dict] = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.entries.append(json.loads(line))

    # -- 内部
    @staticmethod
    def _entry_hash(unsigned: dict) -> str:
        prev = bytes.fromhex(unsigned["prev_hash"])
        return hashlib.sha256(_ENTRY_DOMAIN + prev + canonical_bytes(unsigned)).hexdigest()

    def head_hash(self) -> str:
        return self.entries[-1]["hash"] if self.entries else GENESIS_HASH

    def next_seq(self) -> int:
        return len(self.entries) + 1

    def latest_ts(self) -> str | None:
        if not self.entries:
            return None
        # 按时间值比较 (不依赖字符串字典序, 混时区亦成立)
        return max((e["ts"] for e in self.entries), key=parse_ts)

    # -- 写入 (写入前自验签名, 规范 §2 "账本验签才收录")
    def append(self, entry_type: str, payload: dict, kp: KeyPair,
               ts: str | None = None) -> dict:
        # 回执随机数防重放 (规范 §8): 同一 nonce 的回执不得重复入账,
        # 否则验真方可重放旧回执虚增授权已用次数。
        if entry_type == "receipt":
            nonce = payload.get("nonce")
            for e in self.entries:
                if (e["type"] == "receipt"
                        and e["payload"].get("nonce") == nonce):
                    raise ValueError("append: 回执随机数重复, 防重放拦截")
        unsigned = {
            "seq": self.next_seq(),
            "ts": ts or now_iso(),
            "type": entry_type,
            "payload": payload,
            "prev_hash": self.head_hash(),
            "signer_fp": kp.fingerprint,
            "signer_pub": kp.public_b64,
        }
        h = self._entry_hash(unsigned)
        entry = {**unsigned, "sig": kp.sign(bytes.fromhex(h)), "hash": h}
        if not verify_signature(entry["signer_pub"], bytes.fromhex(h), entry["sig"]):
            raise ValueError("append: 签名自验失败, 拒绝收录")
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())  # 落盘确认, 防崩溃丢尾条
        self.entries.append(entry)
        return entry

    # -- 全链校验: 定位首个断裂序号
    def verify_chain(self) -> tuple[bool, int | None, str]:
        prev = GENESIS_HASH
        for e in self.entries:
            if e["prev_hash"] != prev:
                return False, e["seq"], "prev_hash 链接断裂"
            unsigned = {k: e[k] for k in
                        ("seq", "ts", "type", "payload", "prev_hash", "signer_fp", "signer_pub")}
            if self._entry_hash(unsigned) != e["hash"]:
                return False, e["seq"], "条目哈希不符 (内容被改)"
            if fingerprint_of(e["signer_pub"]) != e["signer_fp"]:
                return False, e["seq"], "签名者指纹与公钥不符"
            if not verify_signature(e["signer_pub"], bytes.fromhex(e["hash"]), e["sig"]):
                return False, e["seq"], "签名无效"
            prev = e["hash"]
        return True, None, ""

    # -- 查询
    def by_type(self, entry_type: str) -> list[dict]:
        return [e for e in self.entries if e["type"] == entry_type]

    def find_registration(self, cert_id: str) -> dict | None:
        for e in self.entries:
            if e["type"] == "registration" and e["payload"].get("cert_id") == cert_id:
                return e
        return None
