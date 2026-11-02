# -*- coding: utf-8 -*-
"""
外部时间锚定 (协议规范 §12 的落地实现)。

把检查点的链头哈希提交到 OpenTimestamps 公共日历, 日历聚合后锚入
比特币区块链。由此账本不再是「自链自证」: 任何人拿到 .ots 证明文件,
都能用公开工具 (opentimestamps.org 等) 独立核验该链头在某一时刻
已经存在, 不依赖数玺平台本身。

诚实边界:
- 提交成功只代表公共日历已受理 (待确认), 比特币确认通常需数小时;
  状态如实区分 pending / bitcoin, 不把待确认说成已确认。
- 本模块的 verify_binding 只校验「证明文件与摘要的绑定关系完好」;
  比特币侧的最终确认以公开校验器为准。
- 锚定是增强项, 不是核心流程的前置条件: stamp_digest 永不抛错,
  全部日历不可达时返回 failed, 检查点照常入账并如实标注未锚定。
- 环境变量 SHUXI_ANCHOR=off 可停用锚定 (离线演示/测试用)。
"""
import base64
import io
import json
import os
import time

DEFAULT_CALENDARS = (
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
)
SUBMIT_TIMEOUT = 20


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def stamp_digest(digest_hex: str) -> dict:
    """把 64 位十六进制摘要提交到公共日历; 返回可入账的锚点字典。"""
    base = {"type": "opentimestamps", "digest": digest_hex,
            "submitted_at": _now_iso()}
    if os.environ.get("SHUXI_ANCHOR") == "off":
        return {**base, "status": "disabled", "ots_b64": None,
                "calendars": [], "error": "SHUXI_ANCHOR=off"}
    try:
        from opentimestamps.calendar import RemoteCalendar
        from opentimestamps.core.op import OpSHA256
        from opentimestamps.core.serialize import StreamSerializationContext
        from opentimestamps.core.timestamp import (DetachedTimestampFile,
                                                   Timestamp)
        digest = bytes.fromhex(digest_hex)
        ts = Timestamp(digest)
        accepted, errors = [], []
        for url in DEFAULT_CALENDARS:
            try:
                ts.merge(RemoteCalendar(url).submit(digest,
                                                    timeout=SUBMIT_TIMEOUT))
                accepted.append(url)
            except Exception as e:  # 单个日历失败不影响其他日历
                errors.append(f"{url}: {type(e).__name__}")
        if not accepted:
            return {**base, "status": "failed", "ots_b64": None,
                    "calendars": [], "error": "; ".join(errors)[:200]}
        dtf = DetachedTimestampFile(OpSHA256(), ts)
        buf = io.BytesIO()
        dtf.serialize(StreamSerializationContext(buf))
        return {**base, "status": "pending",
                "ots_b64": base64.b64encode(buf.getvalue()).decode(),
                "calendars": accepted, "error": None}
    except Exception as e:  # 库缺失/协议异常: 降级, 不阻断检查点
        return {**base, "status": "failed", "ots_b64": None,
                "calendars": [], "error": f"{type(e).__name__}: {e}"[:200]}


def _load(ots_b64: str):
    from opentimestamps.core.serialize import StreamDeserializationContext
    from opentimestamps.core.timestamp import DetachedTimestampFile
    raw = base64.b64decode(ots_b64)
    return DetachedTimestampFile.deserialize(
        StreamDeserializationContext(io.BytesIO(raw)))


def proof_status(ots_b64: str | None) -> dict:
    """解析证明文件的当前状态: bitcoin (含区块高度) / pending / invalid。"""
    if not ots_b64:
        return {"status": "none"}
    try:
        from opentimestamps.core.notary import (BitcoinBlockHeaderAttestation,
                                                PendingAttestation)
        dtf = _load(ots_b64)
        heights, pending = [], 0
        for _msg, att in dtf.timestamp.all_attestations():
            if isinstance(att, BitcoinBlockHeaderAttestation):
                heights.append(att.height)
            elif isinstance(att, PendingAttestation):
                pending += 1
        if heights:
            return {"status": "bitcoin", "height": min(heights),
                    "pending_calendars": pending}
        return {"status": "pending", "pending_calendars": pending}
    except Exception as e:
        return {"status": "invalid", "error": f"{type(e).__name__}: {e}"[:120]}


def verify_binding(ots_b64: str, digest_hex: str) -> bool:
    """证明文件绑定的摘要与给定摘要一致且结构完好。"""
    try:
        dtf = _load(ots_b64)
        fh = getattr(dtf, "file_digest", None) or dtf.timestamp.msg
        return fh.hex() == digest_hex.lower()
    except Exception:
        return False


def upgrade_proof(ots_b64: str) -> tuple[str, bool]:
    """向日历追问待确认承诺的完成状态; 有比特币证明时返回新证明。

    返回 (可能更新的 ots_b64, 是否发生变化)。网络失败时原样返回。
    """
    try:
        from opentimestamps.calendar import RemoteCalendar
        from opentimestamps.core.notary import PendingAttestation
        from opentimestamps.core.serialize import StreamSerializationContext
        dtf = _load(ots_b64)
        changed = False

        def walk(node):
            nonlocal changed
            for att in list(node.attestations):
                if isinstance(att, PendingAttestation):
                    try:
                        fetched = RemoteCalendar(att.uri).get_timestamp(
                            node.msg, timeout=SUBMIT_TIMEOUT)
                        node.merge(fetched)
                        changed = True
                    except Exception:
                        pass
            for sub in node.ops.values():
                walk(sub)

        walk(dtf.timestamp)
        if not changed:
            return ots_b64, False
        buf = io.BytesIO()
        dtf.serialize(StreamSerializationContext(buf))
        return base64.b64encode(buf.getvalue()).decode(), True
    except Exception:
        return ots_b64, False


class AnchorStore:
    """升级后证明的旁路存储: 账本条目不可变, 新证明按检查点序号存这里。

    文件格式 {序号: ots_b64}; 与 packages.json 同级的 anchors.json。
    """

    def __init__(self, path: str):
        self.path = path
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            self._data = {}

    def get(self, seq: int) -> str | None:
        return self._data.get(str(seq))

    def put(self, seq: int, ots_b64: str) -> None:
        self._data[str(seq)] = ots_b64
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f)


def latest_anchor_summary(ledger, data_dir: str) -> str:
    """最近检查点的外部锚定状态一句话 (供验真报告与导览引用)。"""
    cps = ledger.by_type("checkpoint")
    if not cps:
        return "账本暂无检查点，链头尚未对外锚定"
    cp = cps[-1]
    anch = (cp["payload"].get("anchor") or {})
    if anch.get("type") != "opentimestamps":
        return f"检查点 #{cp['seq']} 未附外部时间锚定"
    if anch.get("status") == "disabled":
        return f"检查点 #{cp['seq']} 外部锚定已停用（演示配置）"
    store = AnchorStore(os.path.join(data_dir, "anchors.json"))
    proof = store.get(cp["seq"]) or anch.get("ots_b64")
    if not proof:
        return f"检查点 #{cp['seq']} 锚定证明缺失"
    pst = proof_status(proof)
    if pst["status"] == "bitcoin":
        return (f"检查点 #{cp['seq']} 已获比特币区块链确认"
                f"（区块高度 {pst['height']}），时间锚定可独立核验")
    if pst["status"] == "pending":
        return (f"检查点 #{cp['seq']} 已提交 OpenTimestamps 公共日历，"
                "待比特币网络确认")
    return f"检查点 #{cp['seq']} 锚定证明解析异常"
