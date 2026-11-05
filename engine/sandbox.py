# -*- coding: utf-8 -*-
"""
数玺 · 红蓝对抗现场攻防变异生成器 (Red-Blue Adversarial Mutation Engine)
从所选登记母本原文现场动态生成具有针对性的攻击样本变异件：
- 策略 A: 仅做格式与空白变换不改内容 (结果: 乙级)
- 策略 B: 改一个数值字段并同步改合计字段做平 (结果: 丁级)
- 策略 C: 只改数值字段不改合计，注入勾稽逻辑穿帮 (结果: 丙级)
母本缺失相关字段时置灰并如实说明原因。
"""
import re
from typing import Dict, Any, Tuple, Optional


def analyze_base_document(text: str) -> Dict[str, Any]:
    """分析母本文本结构，检测是否具备表格明细项与合计项"""
    has_text = bool(text and text.strip())
    if not has_text:
        return {
            "has_text": False,
            "has_table_total": False,
            "table_items": [],
            "total_line_idx": None,
            "total_val": None
        }

    lines = text.splitlines()
    total_line_idx = None
    total_val = None

    # 第一轮: 优先寻找属于同一个表格的明细项和合计行 (例如 | 分隔的表格)
    table_items = []
    for idx, line in enumerate(lines):
        if ("合计" in line or "总计" in line) and ("|" in line or "｜" in line or ":" in line or "：" in line):
            m_tot = re.search(r"([0-9][0-9,.]*)", line)
            if m_tot:
                try:
                    total_val = float(m_tot.group(1).replace(",", ""))
                    total_line_idx = idx
                    break
                except ValueError:
                    pass

    if total_line_idx is not None:
        # 在合计行上方寻找同属于表格的明细项
        for idx in range(total_line_idx):
            line = lines[idx]
            m_pipe = re.search(r"([^|：:\n]+?)\s*[|｜]\s*([0-9][0-9,.]*)", line)
            if m_pipe:
                label = m_pipe.group(1).strip()
                val_str = m_pipe.group(2).replace(",", "").strip()
                try:
                    val_float = float(val_str)
                    table_items.append((idx, label, val_float, val_str, line))
                except ValueError:
                    continue

    has_table_total = (total_line_idx is not None and len(table_items) >= 1)
    return {
        "has_text": has_text,
        "has_table_total": has_table_total,
        "table_items": table_items,
        "total_line_idx": total_line_idx,
        "total_val": total_val
    }


def get_strategies_status(text: str) -> Dict[str, Dict[str, Any]]:
    """获取三种策略在当前母本上的可用状态及原因"""
    analysis = analyze_base_document(text)
    if not analysis["has_text"]:
        return {
            "A": {"available": False, "reason": "所选母本无可用纯文本，无法执行格式变换"},
            "B": {"available": False, "reason": "所选母本缺少文本字段结构，无法执行做平篡改"},
            "C": {"available": False, "reason": "所选母本缺少文本字段结构，无法注入勾稽矛盾"}
        }

    res = {
        "A": {"available": True, "reason": "可对母本执行日期空隙与全角字符格式归一变换 (内容等价)"}
    }

    if analysis["has_table_total"]:
        res["B"] = {"available": True, "reason": "母本包含明细项与合计项，可篡改明细并同步调整合计以做平账目"}
        res["C"] = {"available": True, "reason": "母本包含合计校验结构，可单改明细而不动合计制造勾稽矛盾"}
    else:
        res["B"] = {"available": False, "reason": "所选母本缺少「明细项与合计项」表格结构，无法实施做平篡改"}
        res["C"] = {"available": False, "reason": "所选母本缺少「合计」勾稽校验结构，无法注入穿帮矛盾"}

    return res


def generate_variant(text: str, strategy: str) -> Tuple[Optional[bytes], str]:
    """
    现场生成变异样本:
    - strategy: 'A' | 'B' | 'C'
    返回 (mutated_bytes, summary_msg)
    """
    analysis = analyze_base_document(text)
    if not analysis["has_text"]:
        return None, "母本文本为空，无法生成变异件"

    lines = text.splitlines()

    if strategy == "A":
        # 策略 A: 仅做格式与空白变换不改内容
        mut_lines = []
        for line in lines:
            # 日期字符间添加空白 (2026年9月30日 -> 2026 年 9 月 30 日)
            line_mod = re.sub(r"(\d{4})年(\d{1,2})月(\d{1,2})日", r"\1 年 \2 月 \3 日", line)
            # 对纯数值字段做全角微调 (例如 4200000 -> ４２０００００)
            if "净利润" in line_mod or "利润" in line_mod:
                line_mod = line_mod.replace("4200000", "４２０００００")
            mut_lines.append(line_mod)
        # 添加结尾冗余空行与制表空白
        res_text = "\n".join(mut_lines) + "\n\n"
        return res_text.encode("utf-8"), "已生成格式与空白变异件 (原意保持不变)"

    if not analysis["has_table_total"]:
        return None, "母本缺少明细与合计结构，无法生成该策略变异件"

    # 选择倒数第一个表格明细项 (例如: 服务收入 | 3500000)
    target_idx, target_label, target_val, target_val_str, orig_line = analysis["table_items"][-1]
    delta = 1000000.0  # 篡改增加 100 万元
    new_val = target_val + delta
    new_val_str = f"{int(new_val)}" if new_val.is_integer() else f"{new_val:.2f}"

    if strategy == "B":
        # 策略 B: 改一个数值字段并同步改合计字段做平
        mut_lines = list(lines)
        # 1. 替换明细项
        mut_lines[target_idx] = orig_line.replace(target_val_str, new_val_str)

        # 2. 替换合计项
        total_idx = analysis["total_line_idx"]
        orig_total_line = lines[total_idx]
        new_total = analysis["total_val"] + delta
        new_total_str = f"{int(new_total)}" if new_total.is_integer() else f"{new_total:.2f}"
        old_total_str = f"{int(analysis['total_val'])}" if analysis['total_val'].is_integer() else f"{analysis['total_val']:.2f}"
        mut_lines[total_idx] = orig_total_line.replace(old_total_str, new_total_str)

        # 3. 如果有营业收入也同步做平
        for idx, line in enumerate(mut_lines):
            if "营业收入" in line and old_total_str in line:
                mut_lines[idx] = line.replace(old_total_str, new_total_str)

        res_text = "\n".join(mut_lines)
        return res_text.encode("utf-8"), f"已篡改字段「{target_label}」(+{int(delta):,} 元) 并同步修正合计项做平账目"

    elif strategy == "C":
        # 策略 C: 只改数值字段不改合计 (制造内部勾稽不平)
        mut_lines = list(lines)
        mut_lines[target_idx] = orig_line.replace(target_val_str, new_val_str)
        res_text = "\n".join(mut_lines)
        return res_text.encode("utf-8"), f"已篡改字段「{target_label}」(+{int(delta):,} 元)，故意保留原合计以产生勾稽矛盾"

    return None, f"未知策略: {strategy}"
