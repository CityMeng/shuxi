# -*- coding: utf-8 -*-
"""
数玺 · 可插拔 DSL 规则引擎与抽象语法树解析 (DSL Rules Engine)
支持外部配置文件 (rules.json)、字段别名归一、基于 AST 语法树的安全公式求值 (禁止 eval) 与每规则独立容差。
DSL 评估结果仅供展示与业务审计参考，绝不干预系统四级判定核心逻辑。
"""
import ast
import json
import os
from typing import Dict, Any, List, Optional

_DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules.json")


def load_rules_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """读取外部规则配置文件 rules.json"""
    path = config_path or _DEFAULT_CONFIG_PATH
    if not os.path.exists(path):
        return {"aliases": {}, "rules": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _eval_ast(node: ast.AST, var_map: Dict[str, float]) -> float:
    """递归遍历语法树求值，严格禁止 eval，仅支持基础算数运算符"""
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body, var_map)
    elif isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"不支持的常量类型: {type(node.value)}")
    elif isinstance(node, ast.Name):
        if node.id not in var_map:
            raise KeyError(f"未识别或未提供的字段变量: {node.id}")
        return float(var_map[node.id])
    elif isinstance(node, ast.UnaryOp):
        operand = _eval_ast(node.operand, var_map)
        if isinstance(node.op, ast.UAdd):
            return operand
        elif isinstance(node.op, ast.USub):
            return -operand
        raise ValueError(f"不支持的一元操作符: {type(node.op)}")
    elif isinstance(node, ast.BinOp):
        left = _eval_ast(node.left, var_map)
        right = _eval_ast(node.right, var_map)
        if isinstance(node.op, ast.Add):
            return left + right
        elif isinstance(node.op, ast.Sub):
            return left - right
        elif isinstance(node.op, ast.Mult):
            return left * right
        elif isinstance(node.op, ast.Div):
            if abs(right) < 1e-12:
                raise ZeroDivisionError("除以零错误")
            return left / right
        raise ValueError(f"不支持的二元操作符: {type(node.op)}")
    raise ValueError(f"不支持的语法树节点: {type(node)}")


def evaluate_expression_ast(expr_str: str, var_map: Dict[str, float]) -> Optional[float]:
    """安全解析并计算算术表达式"""
    try:
        tree = ast.parse(expr_str.strip(), mode="eval")
        return _eval_ast(tree, var_map)
    except Exception:
        return None


def normalize_fields_with_aliases(fields: Dict[str, Any], aliases_config: Dict[str, List[str]]) -> Dict[str, float]:
    """基于别名表归一化输入字段，转换为数值字典"""
    # 建立 反向映射: alias -> canonical_name
    alias_to_canon = {}
    for canon, alias_list in aliases_config.items():
        for a in alias_list:
            alias_to_canon[a] = canon
        alias_to_canon[canon] = canon

    num_map: Dict[str, float] = {}

    for k, v in fields.items():
        if v is None:
            continue
        try:
            cleaned = str(v).replace(",", "").replace("¥", "").replace("元", "").strip()
            val_float = float(cleaned)
        except (ValueError, TypeError):
            continue

        # 归一到标准字段名
        canon_name = alias_to_canon.get(k, k)
        num_map[canon_name] = val_float
        # 同时保留原键名以防公式直接用原名
        if k not in num_map:
            num_map[k] = val_float

    return num_map


def evaluate_dsl_rules(fields: Dict[str, Any],
                       config_path: Optional[str] = None,
                       rules_override: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    运行可插拔 DSL 勾稽规则引擎：
    1. 动态加载 rules.json 配置文件
    2. 执行别名表字段归一
    3. 基于 AST 语法树逐条解析等式两端，比对配置自带容差
    4. 结果仅供业务审计参考展示，不参与四级判定
    """
    cfg = load_rules_config(config_path)
    aliases = cfg.get("aliases", {})
    rules = rules_override if rules_override is not None else cfg.get("rules", [])

    num_map = normalize_fields_with_aliases(fields, aliases)

    passed = []
    violated = []

    for rule in rules:
        formula = rule.get("formula", "")
        rid = rule.get("id", "UNKNOWN")
        rname = rule.get("name", "未命名规则")
        tolerance = float(rule.get("tolerance", 0.01))
        severity = rule.get("severity", "INFO")

        if "==" not in formula:
            continue

        lhs_str, rhs_str = formula.split("==", 1)
        lhs_val = evaluate_expression_ast(lhs_str, num_map)
        rhs_val = evaluate_expression_ast(rhs_str, num_map)

        if lhs_val is None or rhs_val is None:
            # 待验文件中缺少参与计算的字段，跳过该规则
            continue

        diff = abs(lhs_val - rhs_val)
        is_ok = (diff <= tolerance)

        item = {
            "id": rid,
            "name": rname,
            "formula": formula,
            "lhs": lhs_val,
            "rhs": rhs_val,
            "diff": diff,
            "tolerance": tolerance,
            "severity": severity
        }

        if is_ok:
            passed.append(item)
        else:
            violated.append(item)

    return {
        "passed": passed,
        "violated": violated,
        "is_all_passed": (len(violated) == 0)
    }
