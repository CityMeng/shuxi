# -*- coding: utf-8 -*-
"""
数玺独立证据包离线复核脚本。

用法:
  python verify_bundle.py 证据包.json 待验文件

断网可运行: 在本仓库目录下执行, 独立重算三层指纹、复验账本
全链签名与外部锚定绑定, 输出与平台一致的验真结论。
退出码: 0 = 证据包完整且复核完成; 1 = 链断裂/格式不符/结论不一致。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import bundle as bundle_mod  # noqa: E402


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        bundle = json.load(f)
    with open(argv[2], "rb") as f:
        data = f.read()
    filename = os.path.basename(argv[2])
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    try:
        res = bundle_mod.verify_bundle(bundle, data, ext, filename)
    except Exception as e:
        print(f"复核失败: {e}")
        return 1
    print(f"凭证: {bundle['cert_id']}")
    print(f"账本全链验签: {'通过' if res['chain_ok'] else '失败 ' + str(res['chain_detail'])}")
    anch = res["anchor_status"]
    if anch.get("status") not in (None, "none"):
        extra = ""
        if anch["status"] == "bitcoin":
            extra = f" (区块高度 {anch.get('height')})"
        print(f"外部锚定: {anch['status']}{extra}, "
              f"与检查点绑定 {'一致' if anch.get('binding_ok') else '不一致'}")
    rep = res["report"]
    if rep is None:
        print("未能复核待验文件 (账本校验未过)。")
        return 1
    if "error" in rep:
        print(f"复核结论: {rep['error']}")
        return 1
    print(f"复核结论: {rep['grade']} (把握度 {rep['confidence']})")
    for r in rep.get("reasons", []):
        print(f"  - {r}")
    if res["grade_matches"] is not None:
        print(f"与证据包内报告结论一致: {'是' if res['grade_matches'] else '否'}")
        return 0 if res["grade_matches"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
