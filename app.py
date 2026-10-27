# -*- coding: utf-8 -*-
"""
数玺 · 数据可信管理工具 (原型)
三页: 登记 / 验真 / 授权与账本 — 实现《数玺协议规范 v1.3》。

设计语言: 配色与按钮规范学用户自有仓库 CityMeng/shuxi-Google 的\nReact 版设计令牌 (2026-10-27 用户令学习并同步) — 宣纸 #FAF8F3 底、\n纯白卡面、朱砂 #C23531 主色 (悬停 #B91C1C)、鎏金 #D97706、墨灰字\n#1F2937; 公文纸 = 白纸渐变 + 鎏金内框, 结论卡左脊压等级色;\n主按钮纯色平涂圆角 12, 次按钮白底描边; 等级色 甲 #059669 /\n乙 #0284C7 / 丙 #D97706 / 丁 #C23531 / 复核 #6B7280; 三根分色\nSHA-256 天蓝、SM3 翠绿、语义根紫。布局与字号沿用同日修正版\n(侧栏加宽加大、登记流程卡、状态条压紧);
同日晚对标 AI Studio 复刻版后吸收其三处长处: 半透明玻璃面 (透出
底光)、玺印改玫红渐变 + 米白实环 + 金外环、状态点呼吸脉冲。

数据目录: 环境变量 SHUXI_DATA_DIR, 缺省为项目下 data/。
演示口令: 环境变量 SHUXI_DEMO_PASS, 缺省 shuxi-demo (原型演示用,
正式部署应由各主体自行保管口令)。
"""
from __future__ import annotations

import io
import json
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "vectors"))

import streamlit as st  # noqa: E402

from engine import fp, grade as gr  # noqa: E402
from engine import service as svc  # noqa: E402
from engine.ledger import KeyPair, Ledger  # noqa: E402

DATA_DIR = os.environ.get("SHUXI_DATA_DIR", os.path.join(BASE_DIR, "data"))
DEMO_PASS = os.environ.get("SHUXI_DEMO_PASS", "shuxi-demo")
REGISTRAR_NAME = "示例新能源有限公司 · 财务部"
VERIFIER_NAME = "合作银行 · 核验岗"

GRADE_COLORS = {  # 方案B 等级色 (宣纸亮底深色版, 纸面可读优先)
    "甲级": "#059669", "乙级": "#0284C7", "丙级": "#D97706",
    "丁级": "#C23531", "丁级嫌疑": "#C23531", "待人工复核": "#6B7280",
    "已作废": "#6B7280", "未登记": "#6B7280",
}

SEAL_TEXT = {  # 玺印印面文字 (竖排两字)
    "甲级": "甲级", "乙级": "乙级", "丙级": "丙级", "丁级": "丁级",
    "丁级嫌疑": "丁级", "待人工复核": "复核", "已作废": "作废",
    "未登记": "未登", "错误": "存疑",
}

CSS = """
<style>
/* 数玺界面层 v6: 方案B「宣纸公文」(用户 2026-10-27 定版) —
   骨架借 Ant Design 亮色企业规范的语义令牌纪律, 气质自创:
   宣纸米白底 + 墨色字 + 朱砂印章红主色 + 鎏金细线; 面板是
   一张张公文纸 (近白纸面/发丝金边/暖影), 标题思源宋体,
   哈希等宽, 布局加密排满不留空场; 玺印为朱砂印面米白环金圈,
   落在纸上即全站身份。令牌集中在此, 改一处全站生效。 */
:root {
  --paper: #FAF8F3;          /* 宣纸底 */
  --paper-deep: #F0EBE0;     /* 深一号纸 (侧栏/输入区) */
  --card: #FFFFFF;           /* 公文纸面 */
  --ink: #1F2937;            /* 墨色主字 */
  --ink-2: #4B5563;          /* 次字 */
  --ink-3: #78716C;          /* 弱字/标签 */
  --line: #E7E2D6;           /* 发丝线 */
  --line-strong: #DCD5C6;
  --seal: #C23531;           /* 朱砂红 (主色) */
  --seal-deep: #B91C1C;
  --seal-tint: rgba(194,53,49,.07);
  --gold: #D97706;           /* 鎏金 */
  --gold-line: #D97706;
  --ok: #059669;
  --serif: "Noto Serif SC", "Songti SC", "STSong", "SimSun", "宋体", serif;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
          "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  --mono: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
}
html, body, [class*="css"], .stApp {
  font-family: var(--sans) !important;
  color: var(--ink);
  -webkit-font-smoothing: antialiased;
}
.stApp {
  background-color: var(--paper);
  background-image:
    radial-gradient(circle at 15% 10%, rgba(194,53,49,.025) 0%, rgba(0,0,0,0) 40%),
    radial-gradient(circle at 85% 15%, rgba(217,119,6,.025) 0%, rgba(0,0,0,0) 40%),
    linear-gradient(rgba(120,113,108,.04) 1px, rgba(0,0,0,0) 1px),
    linear-gradient(90deg, rgba(120,113,108,.04) 1px, rgba(0,0,0,0) 1px);
  background-size: 100% 100%, 100% 100%, 32px 32px, 32px 32px;
  background-attachment: fixed;
}
::selection { background: rgba(194,53,49,.22); }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #D6CFC2; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #B8AF9F; }
#MainMenu, footer, [data-testid="stDecoration"] { visibility: hidden; }
.block-container { max-width: 1560px; padding: 2.7rem 2.2rem 2.2rem; }
h1 { font-size: 26px !important; }
h2 { font-size: 20px !important; }
h3 { font-size: 16px !important; }
h1, h2, h3 { font-family: var(--serif); letter-spacing: .01em;
  font-weight: 700; color: var(--ink); }
p, li, label, .stMarkdown { font-size: 14.5px; line-height: 1.55; }
[data-testid="stCaptionContainer"] p { font-size: 13px !important;
  color: var(--ink-2) !important; }
hr { margin: 1rem 0 !important; border-color: var(--line) !important; }

/* 侧栏: 深一号宣纸 + 发丝金界 + 印章式品牌 */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #F5F1E8, #F0EBE0);
  border-right: 1px solid var(--line-strong);
  min-width: 322px; max-width: 322px;
  transform: none !important;  /* 导航锁定: 禁止滑出 (见下) */
}
/* 导航做死 (用户 2026-10-27 令): Streamlit 收起侧栏只给 section 加
   translateX(-300px) 却仍占 322px 布局宽, 主区被顶到右侧、左边留
   一大条空白。演示系统导航必须常驻: 藏收起钮 + 强制 transform 归零,
   任何途径都收不起来, 主区永远从侧栏右侧正常排版。 */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top: 1.4rem; }
.sx-side-brand { display: flex; align-items: center; gap: 12px; padding: 2px 0 4px; }
.sx-logo-lg { width: 44px; height: 44px; border-radius: 12px; }
.sx-logo-lg .sx-logo-in { border-radius: 12px; font-size: 21px; }
.sx-brand { font-family: var(--serif); font-size: 31px; font-weight: 900;
  letter-spacing: .04em; color: var(--ink); line-height: 1.35; }
.sx-brand-sub { font-size: 14px; color: var(--ink-2); line-height: 1.6; margin-top: 1px; }
.sx-brand-bar { height: 3px; border-radius: 2px; margin: 12px 0 6px; position: relative;
  background: linear-gradient(90deg, var(--seal), var(--gold-line)); }
.sx-brand-bar::after { content: ""; position: absolute; right: 0; top: 0;
  width: 34px; height: 3px; border-radius: 2px; background: var(--seal); }
div[data-testid="stRadio"] > label { font-size: 13px !important; font-weight: 700;
  letter-spacing: .14em; color: var(--ink-3) !important; margin-bottom: 2px; }
div[data-testid="stRadio"] label { font-size: 17.5px; font-weight: 600; color: var(--ink); padding: 2px 0; }
div[data-testid="stRadio"] > div { gap: 12px; }
.sx-side-card {
  background: #FFFFFF;
  border: 1px solid var(--line); border-radius: 12px;
  padding: 14px 16px; margin: 4px 0 12px;
  box-shadow: 0 1px 2px rgba(0,0,0,.04), inset 0 0 0 1px rgba(255,255,255,.5); }
.sx-side-card .sx-sc-label { font-size: 12.5px; letter-spacing: .1em; color: var(--ink-3);
  font-weight: 700; margin-bottom: 5px; }
.sx-side-card .sx-sc-value { font-family: var(--mono);
  font-size: 17px; font-weight: 700; color: var(--ink); }
.sx-side-foot { font-size: 13.5px; color: var(--ink-3); line-height: 1.65; margin-top: 14px; }
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
  font-size: 13.5px !important; line-height: 1.65 !important; }
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 1.05rem; }
.sx-actor { font-size: 14px; color: var(--ink); line-height: 1.55; margin-top: 6px; }
.sx-actor span { color: var(--ink-3); font-size: 13px; font-weight: 700;
  letter-spacing: .06em; margin-right: 8px; }
.sx-actor-note { font-size: 13px; color: var(--ink-3); margin-top: 6px; }
.sx-side-sell { border-top: 1px solid var(--line); margin-top: 10px;
  padding-top: 9px; font-size: 14px; color: var(--ink-2); line-height: 1.7; }

/* 顶栏: 透明融入纸面, 一条发丝线分界 */
.sx-topbar { display: flex; justify-content: space-between; align-items: center;
  gap: 16px; flex-wrap: wrap;
  background: transparent; border: none;
  border-bottom: 1px solid var(--line-strong);
  padding: 0 2px 10px; margin-bottom: 12px; }
.sx-top-left { display: flex; align-items: center; gap: 10px; }
.sx-logo { width: 36px; height: 36px; border-radius: 10px; padding: 0; flex: none;
  background: #C23531;
  box-shadow: 0 0 0 1px rgba(217,119,6,.5), 0 2px 6px rgba(153,27,27,.25),
              inset 0 0 6px rgba(0,0,0,.18); }
.sx-logo-in { width: 100%; height: 100%; border-radius: 7px; background: transparent;
  display: flex; align-items: center; justify-content: center;
  color: #FEF3C7; font-family: "Kaiti SC", "STKaiti", KaiTi, "楷体", var(--serif);
  font-weight: 700; font-size: 18px; }
.sx-top-title { font-family: var(--serif); font-size: 20px; font-weight: 900;
  color: var(--ink); letter-spacing: .05em; }
.sx-spec-chip { font-family: var(--mono); font-size: 12px;
  color: var(--ink-2); background: rgba(255,253,246,.7);
  border: 1px solid var(--line); border-radius: 6px; padding: 2px 8px; }
.sx-top-chip { font-family: var(--mono); font-size: 12.5px;
  color: var(--ink); background: var(--card);
  border: 1px solid var(--line); border-radius: 8px; padding: 4px 10px; }

/* 控件 */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  border-radius: 10px; padding: 0.4rem 1.3rem; font-weight: 600;
  font-size: 14.5px; border: 1px solid var(--line-strong);
  background: #FFFFFF; color: #374151;
  box-shadow: 0 1px 2px rgba(0,0,0,.04);
  transition: all .18s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover,
.stFormSubmitButton > button:hover { border-color: #D1C7B7; color: var(--ink);
  background: #FAF8F3; }
button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-primaryFormSubmit"] {
  background: #C23531 !important;
  border: 1px solid #B91C1C !important; color: #FFFFFF !important;
  border-radius: 12px !important;
  box-shadow: 0 1px 2px rgba(0,0,0,.06);
}
button[data-testid="stBaseButton-primary"]:hover,
button[data-testid="stBaseButton-primaryFormSubmit"]:hover {
  background: #B91C1C !important; border-color: #991B1B !important;
}
div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input {
  background-color: #FFFFFF !important; color: var(--ink) !important;
  border: 1px solid var(--line-strong) !important; border-radius: 8px !important;
}
div[data-baseweb="select"] > div {
  background-color: #FFFFFF !important;
  border-color: var(--line-strong) !important; border-radius: 8px !important;
}
div[data-testid="stFileUploader"] section {
  background: var(--seal-tint) !important;
  border: 1.5px dashed rgba(194,53,49,.45) !important; border-radius: 10px !important;
}
div[data-testid="stExpander"] {
  background: var(--card); border: 1px solid var(--line);
  border-radius: 10px;
}
div[data-testid="stExpander"] summary { font-size: 14.5px; font-weight: 600; }
.stDataFrame { border-radius: 8px; overflow: hidden;
  border: 1px solid var(--line); }
div[data-testid="stAlert"] { border-radius: 10px; font-size: 14.5px; }

/* 公文纸面板: 近白纸面 + 发丝金边 + 一道朱砂顶线 */
.sx-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 16px; padding: 18px 22px; margin: 10px 0;
  box-shadow: 0 1px 3px rgba(0,0,0,.03), 0 1px 2px -1px rgba(0,0,0,.03);
}
.sx-card .sx-label {
  border-bottom: 1px solid var(--line);
  padding-bottom: 8px; margin-bottom: 10px;
}
.sx-hero-card { display: flex; justify-content: space-between;
  align-items: center; gap: 18px; }
.sx-grade { font-family: var(--serif); font-size: 42px; font-weight: 900;
  letter-spacing: .02em; line-height: 1.3; padding: 3px 0; }
.sx-conf { font-size: 14.5px; color: var(--ink-2); margin-top: 2px; }
.sx-cert-id { font-family: var(--mono);
  font-size: 24px; font-weight: 700; letter-spacing: .02em; color: var(--ink);
  line-height: 1.45; padding: 2px 0; }
.sx-mono { font-family: var(--mono);
  font-size: 12px; line-height: 1.6; word-break: break-all; color: var(--ink-2); }
.sx-mono-box { background: #FAF8F3; border: 1px solid var(--line);
  border-radius: 8px; padding: 10px 12px; margin-top: 8px; }
.sx-label { font-size: 12.5px; font-weight: 600; color: var(--ink-3);
  letter-spacing: .07em; margin-bottom: 3px; }
.sx-chip { display: inline-block; background: #F4EFE6;
  border: 1px solid var(--line); border-radius: 8px;
  padding: 3px 10px; margin: 2px 4px 2px 0; font-size: 12.5px; color: var(--ink); }
.sx-hero-title { font-family: var(--serif); font-size: 27px; font-weight: 900;
  letter-spacing: .03em; line-height: 1.5; padding: 2px 0 0; margin: 0; color: var(--ink); }
.sx-sub { color: var(--ink-2); font-size: 14.5px; margin: 2px 0 12px; line-height: 1.55; }
.sx-ledger-head { font-size: 18px; font-weight: 700; letter-spacing: .01em;
  color: var(--ink); line-height: 1.55; padding: 2px 0; }
.sx-sec { font-family: var(--serif); font-size: 17.5px; font-weight: 700;
  letter-spacing: .02em;
  line-height: 1.55; padding: 2px 0 2px 14px;
  margin: 16px 0 4px; color: var(--ink); position: relative; }
.sx-sec::before { content: ""; position: absolute; left: 0; top: 4px; bottom: 4px;
  width: 4px; border-radius: 2px;
  background: linear-gradient(180deg, var(--seal), var(--gold)); }
.sx-sec-sub { font-size: 13px; color: var(--ink-2); margin-bottom: 8px; padding-left: 14px; }
.sx-empty {
  background: rgba(255,253,246,.55); border: 1.5px dashed var(--line-strong);
  border-radius: 10px; padding: 20px 24px; margin: 10px 0 6px;
  color: var(--ink-2); font-size: 14px; line-height: 1.65; text-align: center;
}
.sx-reasons { background: var(--card); border: 1px solid var(--line);
  border-radius: 10px; padding: 12px 20px; margin: 4px 0 12px; }
.sx-reasons ul { margin: 0; padding-left: 20px; }
.sx-reasons li { font-size: 14.5px; line-height: 1.6; margin: 3px 0; color: var(--ink); }

/* 顶部状态条: 一行压紧的公文抬头, 图标砖 + 等宽数字 */
.sx-strip { display: flex; gap: 0; flex-wrap: wrap;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 16px; padding: 10px 8px; margin: 0 0 14px;
  box-shadow: 0 1px 2px rgba(0,0,0,.03); }
.sx-stat { flex: 1 1 140px; padding: 2px 14px; display: flex; align-items: center;
  gap: 10px; border-left: 1px solid var(--line); }
.sx-stat:first-child { border-left: none; }
.sx-stat-ico { width: 32px; height: 32px; border-radius: 8px; flex: none;
  display: flex; align-items: center; justify-content: center; border: 1px solid; }
.sx-stat-num { font-family: var(--mono);
  font-size: 17px; font-weight: 700; color: var(--ink); }
.sx-stat-label { font-size: 12px; color: var(--ink-2); letter-spacing: .05em; margin-bottom: 1px; }
.sx-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  margin-right: 6px; vertical-align: 1px;
  animation: sx-pulse 2.2s ease-in-out infinite; }
@keyframes sx-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(16,185,129,.40); }
  50% { box-shadow: 0 0 0 5px rgba(16,185,129,0); }
}

/* 账本区块流: 墨方块递进, 链头是盖着的朱砂印 */
.sx-chain { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; margin-top: 12px; }
.sx-block { width: 16px; height: 16px; border-radius: 4px;
  background: #E2DBD0; box-shadow: inset 0 1px 0 rgba(255,255,255,.5); }
.sx-block-mid { background: #A8A29E; }
.sx-block-head { background: radial-gradient(circle at 35% 30%, #DC2626, #C23531 55%, #991B1B);
  box-shadow: 0 0 0 1.5px #FEF3C7, 0 0 0 3px #D97706, 0 3px 8px rgba(153,27,27,.35); }
.sx-chain-note { font-size: 12.5px; color: var(--ink-3); margin-left: 8px; }
/* 登记流程卡: 三步横排 + 须知行 (填左列, 与凭证卡等高对话) */
.sx-steps { display: flex; align-items: flex-start; gap: 8px; margin: 4px 0 2px; }
.sx-step { display: flex; gap: 8px; flex: 1; align-items: flex-start; }
.sx-step-n { flex: none; width: 23px; height: 23px; border-radius: 50%;
  background: var(--seal-tint); border: 1px solid rgba(194,53,49,.4);
  color: var(--seal-deep); font-family: var(--mono); font-size: 13px;
  font-weight: 700; display: flex; align-items: center; justify-content: center;
  margin-top: 1px; }
.sx-step b { font-size: 14.5px; color: var(--ink); }
.sx-step span { font-size: 13px; color: var(--ink-2); line-height: 1.5; }
.sx-step-arrow { color: var(--ink-3); font-size: 15px; padding-top: 3px; }
.sx-notes { border-top: 1px solid var(--line); margin-top: 10px; padding-top: 9px; }
.sx-notes div { font-size: 13.5px; color: var(--ink-2); line-height: 1.75; }
.sx-notes b { color: var(--seal-deep); font-weight: 700; margin-right: 6px; }

/* 正式公文纸: 白纸渐变 + 鎏金内框 (学用户 shuxi-Google 版 official-doc-paper) */
.sx-doc { position: relative; border-color: #DED7C8;
  background: linear-gradient(180deg, #FFFFFF 0%, #FFFDFA 100%);
  box-shadow: 0 4px 16px -2px rgba(78,60,42,.08), 0 1px 3px rgba(0,0,0,.04); }
.sx-doc::after { content: ""; position: absolute; top: 5px; left: 5px;
  right: 5px; bottom: 5px; border: 1px solid rgba(217,119,6,.35);
  border-radius: 11px; pointer-events: none; }

/* 批量统计语义片 */
.sx-batch-chip { display: inline-block; border-radius: 980px;
  padding: 3px 12px; margin: 2px 6px 2px 0; font-size: 13px; font-weight: 600;
  border: 1px solid; }

/* 玺印: 朱砂印面 + 米白环 + 金圈, 落在纸上 */
.sx-seal {
  flex: none; width: 96px; height: 96px; border-radius: 20px;
  display: flex; align-items: center; justify-content: center;
  background: radial-gradient(circle at 35% 30%, #DC2626 0%, #C23531 40%, #991B1B 85%, #7F1D1D 100%);
  border: 3px solid #FEF3C7;
  box-shadow: 0 0 0 1.5px #D97706, inset 0 0 10px rgba(0,0,0,.35),
              inset 0 1px 3px rgba(254,243,199,.4),
              0 8px 24px rgba(185,28,28,.28);
  color: #FFFFFF; font-family: "Kaiti SC", "STKaiti", KaiTi, "楷体", serif;
  font-size: 28px; font-weight: 700; letter-spacing: .04em;
  text-shadow: 0 1px 2px rgba(0,0,0,.45);
  writing-mode: vertical-rl; text-orientation: upright;
  transform: rotate(-6deg);
  animation: sx-sealDrop .45s cubic-bezier(.175,.885,.32,1.25) both;
}
.sx-seal-sm { width: 54px; height: 54px; border-radius: 12px;
  font-size: 22px; writing-mode: horizontal-tb; border-width: 2px;
  box-shadow: 0 0 0 1px #D97706, inset 0 0 6px rgba(0,0,0,.3),
              inset 0 1px 2px rgba(254,243,199,.4),
              0 4px 14px rgba(185,28,28,.22);
  position: absolute; top: 16px; right: 18px; }
@keyframes sx-sealDrop {
  0% { transform: scale(2.4) rotate(-22deg); opacity: 0; filter: blur(4px); }
  65% { transform: scale(.94) rotate(-5deg); opacity: 1; filter: blur(0); }
  82% { transform: scale(1.03) rotate(-8deg); }
  100% { transform: scale(1) rotate(-6deg); opacity: 1; }
}
</style>
"""


# ---------------------------------------------------------------- 数据与主体

def init_stores(data_dir: str):
    """初始化账本/登记包/主体密钥 (首次运行自动生成演示主体)。"""
    os.makedirs(data_dir, exist_ok=True)
    ledger = Ledger(os.path.join(data_dir, "ledger.jsonl"))
    packages = svc.PackageStore(os.path.join(data_dir, "packages.json"))
    actors_path = os.path.join(data_dir, "actors.json")
    actors: dict[str, KeyPair] = {}
    if os.path.exists(actors_path):
        raw = json.load(open(actors_path, encoding="utf-8"))
        for name, rec in raw.items():
            actors[name] = KeyPair.from_encrypted_pem(rec["privkey_pem"], DEMO_PASS)
    else:
        raw = {}
        for name in (REGISTRAR_NAME, VERIFIER_NAME):
            kp = KeyPair.generate()
            actors[name] = kp
            raw[name] = {"privkey_pem": kp.private_pem_encrypted(DEMO_PASS),
                         "pub": kp.public_b64, "fp": kp.fingerprint}
        with open(actors_path, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=1)
    return ledger, packages, actors


def ext_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def do_register(ledger, packages, registrar_kp, filename, data):
    return svc.register_file(ledger, packages, registrar_kp, REGISTRAR_NAME,
                             filename, data, ext_of(filename), DEMO_PASS)


def do_verify(ledger, packages, verifier_kp, cert_id, filename, data,
              auth_id=None):
    t0 = time.perf_counter()
    report = svc.verify_file(ledger, packages, verifier_kp, VERIFIER_NAME,
                             cert_id, data, ext_of(filename), filename,
                             auth_id=auth_id)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    comp = fp.compute_all(data, ext_of(filename))
    reg = ledger.find_registration(cert_id)
    return {"report": report, "comp": comp, "reg": reg, "data": data,
            "filename": filename, "elapsed_ms": elapsed_ms}


def find_cert_by_filename(ledger, filename):
    found = None
    for e in ledger.by_type("registration"):
        if e["payload"]["filename"] == filename:
            found = e["payload"]["cert_id"]
    return found


def do_batch(ledger, packages, verifier_kp, files):
    """批量验真: 按文件名匹配登记记录; 无匹配的只做勾稽审计。"""
    rows, stats = [], {}
    t0 = time.perf_counter()
    for filename, data in files:
        ts = time.perf_counter()
        cert = find_cert_by_filename(ledger, filename)
        if cert:
            rep = svc.verify_file(ledger, packages, verifier_kp, VERIFIER_NAME,
                                  cert, data, ext_of(filename), filename)
            grade, conf = rep.get("grade", "错误"), rep.get("confidence", "")
        else:
            comp = fp.compute_all(data, ext_of(filename))
            aud = gr.audit(data, ext_of(filename), comp["text"], comp["fields"])
            res = gr.grade_standalone(aud)
            grade, conf = res["grade"], str(res["confidence"])
        ms = (time.perf_counter() - ts) * 1000
        rows.append({"文件": filename, "凭证": cert or "—", "等级": grade,
                     "把握": conf, "耗时ms": round(ms, 1)})
        stats[grade] = stats.get(grade, 0) + 1
    return rows, stats, (time.perf_counter() - t0) * 1000


DEMO_FILES = ("report.txt", "contract_bad.txt", "scan_a.png")


def seed_demo(ledger, packages, registrar_kp):
    """一键载入演示数据 (虚构样本): 逐份核对演示三件套, 缺哪份补哪份;
    演示凭证被作废也算缺失, 重新登记一份, 保证演示随时能跑。
    (旧逻辑是账本里有任何登记就整体跳过, 公共实例上按钮会失效。)"""
    import gen_samples
    gen_samples.main()
    sdir = os.path.join(BASE_DIR, "vectors", "samples")
    have = set()
    for e in ledger.by_type("registration"):
        p = e["payload"]
        if p.get("registrar") != REGISTRAR_NAME:
            continue
        if svc.resolve_status(ledger, p["cert_id"])["status"] == "有效":
            have.add(p["filename"])
    certs = []
    for name in DEMO_FILES:
        if name in have:
            continue
        with open(os.path.join(sdir, name), "rb") as f:
            certs.append(do_register(ledger, packages, registrar_kp, name, f.read()))
    return certs


def cert_qr_png(cert_id, payload):
    import qrcode
    text = json.dumps({
        "cert_id": cert_id, "filename": payload["filename"],
        "sha256_root": payload["exact"]["sha256_root"],
        "sm3_root": payload["exact"]["sm3_root"],
        "semantic_root": payload["semantic_root"],
    }, ensure_ascii=False)
    img = qrcode.make(text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- 通用渲染

def registrations(ledger):
    return [e["payload"] for e in ledger.by_type("registration")]


def _svg(paths: str) -> str:
    return ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round">{paths}</svg>')


_SVG_LAYERS = _svg('<path d="M12 2 2 7l10 5 10-5-10-5Z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>')
_SVG_FILECHECK = _svg('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="m9 15 2 2 4-4"/>')
_SVG_RECEIPT = _svg('<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M8 7h8"/><path d="M8 11h8"/>')
_SVG_LINK = _svg('<path d="M9 17H7A5 5 0 0 1 7 7h2"/><path d="M15 7h2a5 5 0 1 1 0 10h-2"/><path d="M8 12h8"/>')


def top_bar(ledger):
    """顶栏 (移植 AI Studio 版 Sticky Top Bar 的品牌区 + 状态片)。"""
    ok, _, _ = ledger.verify_chain()
    dot = "#10B981" if ok else "#C23531"
    state = "全链可验" if ok else "链异常"
    st.markdown(f"""
    <div class="sx-topbar">
      <div class="sx-top-left">
        <div class="sx-logo"><div class="sx-logo-in">玺</div></div>
        <span class="sx-top-title">数玺</span>
        <span class="sx-spec-chip">规范 v1.3 · 套件 SXA1</span>
      </div>
      <div class="sx-top-chip"><span class="sx-dot" style="background:{dot}"></span>{state} · 高度 {len(ledger.entries)}</div>
    </div>""", unsafe_allow_html=True)


def status_strip(ledger):
    """全局状态条: 图标砖 + 标签 + 等宽数字 (全部真实数据, 三页通栏)。"""
    ok, _, _ = ledger.verify_chain()
    dot = "#059669" if ok else "#C23531"
    state = "全链可验" if ok else "链异常"
    cells = [
        ("#FAF8F3", "#E7E2D6", "#78716C",
         _SVG_LAYERS, "账本高度", str(len(ledger.entries))),
        ("#FAF8F3", "#E7E2D6", "#78716C",
         _SVG_FILECHECK, "已登记凭证", str(len(ledger.by_type('registration')))),
        ("#FAF8F3", "#E7E2D6", "#78716C",
         _SVG_RECEIPT, "验真回执", str(len(ledger.by_type('receipt')))),
        ("rgba(5,150,105,.07)", "rgba(5,150,105,.30)", "#059669",
         _SVG_LINK, "链状态",
         f'<span class="sx-dot" style="background:{dot}"></span>{state}'),
    ]
    html = ['<div class="sx-strip">']
    for bg, bd, fg, icon, label, value in cells:
        html.append(
            f'<div class="sx-stat"><div class="sx-stat-ico" '
            f'style="background:{bg};border-color:{bd};color:{fg}">{icon}</div>'
            f'<div><div class="sx-stat-label">{label}</div>'
            f'<div class="sx-stat-num">{value}</div></div></div>')
    html.append('</div>')
    st.markdown("".join(html), unsafe_allow_html=True)


def grade_hero(report, elapsed_ms=None):
    g = report.get("grade", "错误")
    color = GRADE_COLORS.get(g, "#C23531")
    conf = report.get("confidence", "")
    try:
        conf_pct = f"{float(conf) * 100:.0f}%"
    except (TypeError, ValueError):
        conf_pct = conf
    extra = f" · 本次验真耗时 {elapsed_ms:.0f} ms" if elapsed_ms is not None else ""
    st.markdown(f"""
    <div class="sx-card sx-hero-card sx-doc" style="border-left:5px solid {color}">
      <div>
        <div class="sx-label">验真结论</div>
        <div class="sx-grade" style="color:{color}">{g}</div>
        <div class="sx-conf">把握 {conf_pct}{extra}</div>
      </div>
      <div class="sx-seal">{SEAL_TEXT.get(g, g[:2])}</div>
    </div>""", unsafe_allow_html=True)
    if report.get("error"):
        st.error(report["error"])
    reasons = report.get("reasons", [])
    if reasons:
        items = "".join(f"<li>{r}</li>" for r in reasons)
        st.markdown(f'<div class="sx-reasons"><ul>{items}</ul></div>',
                    unsafe_allow_html=True)


# ---------------------------------------------------------------- 页面: 登记

def page_register(ledger, packages, actors):
    st.markdown('<div class="sx-hero-title">登记</div>', unsafe_allow_html=True)
    st.markdown('<div class="sx-sub">为文件计算三层指纹并写入账本，领取防伪凭证。原件与字段明文不进账本。</div>',
                unsafe_allow_html=True)
    colL, colR = st.columns([6, 6])
    with colL:
        up = st.file_uploader("选择要登记的文件", key="reg_up",
                              type=["pdf", "docx", "xlsx", "txt", "csv", "md",
                                    "png", "jpg", "jpeg"])
        if up is not None:
            data = up.getvalue()
            st.caption(f"{up.name} · {len(data)} 字节")
            if st.button("开始登记", type="primary"):
                try:
                    cert = do_register(ledger, packages, actors[REGISTRAR_NAME],
                                       up.name, data)
                    st.session_state["last_cert"] = cert
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        st.markdown("""
        <div class="sx-card" style="margin-top:14px">
          <div class="sx-label">登记流程</div>
          <div class="sx-steps">
            <div class="sx-step"><div class="sx-step-n">1</div>
              <div><b>选择文件</b><br><span>报表、合同、报告</span></div></div>
            <div class="sx-step-arrow">→</div>
            <div class="sx-step"><div class="sx-step-n">2</div>
              <div><b>计算三层指纹</b><br><span>精确字节 / 页面长相 / 字段事实</span></div></div>
            <div class="sx-step-arrow">→</div>
            <div class="sx-step"><div class="sx-step-n">3</div>
              <div><b>写入账本</b><br><span>领防伪凭证</span></div></div>
          </div>
          <div class="sx-notes">
            <div><b>格式</b>PDF、Word、Excel、图片与文本，单文件上限 500MB</div>
            <div><b>隐私</b>原件与字段明文不进账本，只存指纹与字段名</div>
            <div><b>版本</b>同一文件再次登记生成新凭证，历史记录保留可查</div>
          </div>
        </div>""", unsafe_allow_html=True)
    with colR:
        cert = st.session_state.get("last_cert")
        reg = ledger.find_registration(cert) if cert else None
        if reg:
            p = reg["payload"]
            chips = "".join(f'<span class="sx-chip">{k}</span>' for k in p["field_keys"])
            st.markdown(f"""
            <div class="sx-card sx-doc" style="position:relative;margin-top:0">
              <div class="sx-seal sx-seal-sm">玺</div>
              <div class="sx-label">数玺凭证 · 登记成功</div>
              <div class="sx-cert-id">{cert}</div>
              <div style="margin:10px 0 4px">{p['filename']} · 登记主体 {p['registrar']}</div>
              <div class="sx-mono-box">
                <div class="sx-label">精确根 SHA-256</div><div class="sx-mono" style="color:#0284C7;font-weight:600">{p['exact']['sha256_root']}</div>
                <div class="sx-label" style="margin-top:6px">精确根 SM3</div><div class="sx-mono" style="color:#059669;font-weight:600">{p['exact']['sm3_root']}</div>
                <div class="sx-label" style="margin-top:6px">语义根</div><div class="sx-mono" style="color:#7C3AED;font-weight:600">{p['semantic_root']}</div>
              </div>
              <div class="sx-label" style="margin-top:10px">已登记字段（仅名）</div><div>{chips or '无'}</div>
            </div>""", unsafe_allow_html=True)
            if p["degraded"]:
                st.warning("降级登记：" + "、".join(p["degraded"])
                           + "（已按规范第 14 节注明）")
            if p["reg_audit"]:
                st.info("登记时勾稽提示（老问题，只记录不判罪）："
                        + "；".join(i["msg"] for i in p["reg_audit"]))
            st.image(cert_qr_png(cert, p), caption="凭证二维码", width=150)
        else:
            st.markdown('<div class="sx-empty" style="margin-top:0">凭证出示区<br>'
                        '登记成功后，带玺印的凭证卡将在此处出示，'
                        '含精确双根、语义根与二维码。</div>',
                        unsafe_allow_html=True)
    regs = registrations(ledger)
    if regs:
        st.markdown('<div class="sx-sec">已登记凭证</div>',
                    unsafe_allow_html=True)
        rows = [{"凭证": p["cert_id"], "文件": p["filename"],
                 "登记主体": p["registrar"], "字段数": len(p["field_keys"])}
                for p in regs]
        st.dataframe(rows, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- 页面: 验真

def page_verify(ledger, packages, actors):
    st.markdown('<div class="sx-hero-title">验真</div>', unsafe_allow_html=True)
    st.markdown('<div class="sx-sub">五步得出结论，每一步都可点开深挖底层证据。</div>',
                unsafe_allow_html=True)
    regs = registrations(ledger)
    if not regs:
        st.markdown('<div class="sx-empty">尚无登记记录，验真无从谈起。<br>'
                    '先到「登记」页登记一份文件，或点左侧「一键载入演示数据」。'
                    '</div>', unsafe_allow_html=True)
        return
    labels = {f"{p['cert_id']} · {p['filename']}": p["cert_id"] for p in regs}
    row1a, row1b = st.columns([7, 5])
    with row1a:
        cert = labels[st.selectbox("选择凭证", list(labels))]
    reg = ledger.find_registration(cert)
    rp = reg["payload"]

    sample_dir = os.path.join(BASE_DIR, "vectors", "samples")
    quick = {}
    if os.path.isdir(sample_dir):
        quick = {n: os.path.join(sample_dir, n) for n in
                 ("report.txt", "report_tampered.txt", "report_converted.txt",
                  "scan_b.jpg") if os.path.exists(os.path.join(sample_dir, n))}
    with row1b:
        pick = st.selectbox("或选用演示文件", ["—"] + list(quick))
    row2a, row2b = st.columns([7, 5])
    with row2a:
        up = st.file_uploader("上传待验文件", key="ver_up")

    data, fname = None, None
    if up is not None:
        data, fname = up.getvalue(), up.name
    elif pick != "—":
        with open(quick[pick], "rb") as f:
            data = f.read()
        fname = pick
    with row2b:
        st.markdown('<div style="height:30px"></div>', unsafe_allow_html=True)
        if data is not None and st.button("开始验真", type="primary",
                                          use_container_width=True):
            st.session_state["last_verify"] = do_verify(
                ledger, packages, actors[VERIFIER_NAME], cert, fname, data)
            st.rerun()

    res = st.session_state.get("last_verify")
    if res and res["reg"] and res["reg"]["payload"]["cert_id"] == cert:
        report, comp = res["report"], res["comp"]
        grade_hero(report, res["elapsed_ms"])
        if "error" not in report:
            with st.expander("深挖证据 · 三层指纹 / 勾稽 / 报告凭证"):
                st.markdown("**第一层 · 精确指纹**")
                st.markdown(
                    f"<div class='sx-mono'>登记 SHA-256　{rp['exact']['sha256_root']}<br>"
                    f"待验 SHA-256　{comp['exact']['sha256_root']}<br>"
                    f"登记 SM3　　　{rp['exact']['sm3_root']}<br>"
                    f"待验 SM3　　　{comp['exact']['sm3_root']}</div>",
                    unsafe_allow_html=True)
                st.markdown("**第二层 · 感知指纹**")
                rp_h, cp_h = rp["phashes"], comp["perceptual"]["phashes"]
                if rp_h and cp_h and len(rp_h) == len(cp_h):
                    dists = [fp.hamming_hex(a, b) for a, b in zip(rp_h, cp_h)]
                    st.write(f"逐页汉明距离：{dists}（均值 "
                             f"{sum(dists) / len(dists):.2f}，阈值 ≤ 8）")
                else:
                    st.write(f"登记 {len(rp_h)} 页 / 待验 {len(cp_h)} 页"
                             "（页数不一致时感知哈希不参与判定）")
                sim = fp.text_similarity(rp_text(ledger, packages, cert), comp["text"])
                sim_txt = f"{sim:.4f}" if sim is not None else "不可用"
                st.write(f"文本相似度（3-gram Jaccard）：{sim_txt}（阈值 ≥ 0.90）")
                st.markdown("**第三层 · 语义字段**")
                pkg = packages.get(cert)
                rows = []
                keys = sorted(set((pkg["fields"] if pkg else {})) | set(comp["fields"]),
                              key=lambda k: k.encode("utf-8"))
                for k in keys:
                    rv = pkg["fields"].get(k) if pkg else None
                    cv = comp["fields"].get(k)
                    rows.append({"字段": k, "登记值": rv, "待验值": cv,
                                 "状态": "一致" if rv == cv else "不同"})
                if rows:
                    st.dataframe(rows, use_container_width=True, hide_index=True)
                else:
                    st.write("无语义字段（纯图像或无标签内容）")
                st.markdown(f"<div class='sx-mono'>登记语义根　{rp['semantic_root']}<br>"
                            f"待验语义根　{comp['semantic']['root']}</div>",
                            unsafe_allow_html=True)
                aud = gr.audit(res["data"], ext_of(res["filename"]),
                               comp["text"], comp["fields"])
                st.markdown("**勾稽复算**")
                if aud["issues"]:
                    for i in aud["issues"]:
                        st.write(f"- {i['code']}：{i['msg']}")
                else:
                    st.write("G1/G2 未见异常")
                for h in aud["hints"]:
                    st.write(f"- {h}")
                st.markdown("**验真报告凭证**")
                st.markdown(f"<div class='sx-mono'>回执编号　{report.get('receipt_id')}<br>"
                            f"报告哈希　{report.get('report_hash')}<br>"
                            f"回执入账　{report.get('receipt_entry_hash')}</div>",
                            unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                with c1:
                    st.download_button(
                        "下载验真报告 JSON",
                        json.dumps(report, ensure_ascii=False, indent=1),
                        file_name=f"shuxi-report-{cert}.json",
                        mime="application/json")
                with c2:
                    if st.button("复核这份报告"):
                        st.session_state["review_ok"] = svc.verify_report(
                            ledger, report)
                if "review_ok" in st.session_state:
                    if st.session_state.pop("review_ok"):
                        st.success("复核通过：报告未被篡改，且与账本回执一致。")
                    else:
                        st.error("复核不通过：报告与账本不一致。")

    st.markdown('<div class="sx-sec">批量验真</div>', unsafe_allow_html=True)
    st.markdown('<div class="sx-sec-sub">一次上传多份文件：按文件名自动匹配凭证，五十份也是一张表。</div>',
                unsafe_allow_html=True)
    ups = st.file_uploader("批量上传", key="batch_up", accept_multiple_files=True)
    if ups and st.button("开始批量验真"):
        files = [(u.name, u.getvalue()) for u in ups]
        rows, stats, total = do_batch(ledger, packages, actors[VERIFIER_NAME], files)
        st.markdown(f"**{len(rows)} 份 · 总耗时 {total:.0f} ms**")
        chips = "".join(
            f'<span class="sx-batch-chip" style="color:{c};background:{c}1A;'
            f'border-color:{c}59">{g} × {n}</span>'
            for g, n in stats.items()
            for c in [GRADE_COLORS.get(g, "#6B7280")])
        st.markdown(chips, unsafe_allow_html=True)
        st.dataframe(rows, use_container_width=True, hide_index=True)


def rp_text(ledger, packages, cert):
    pkg = packages.get(cert)
    return pkg["text"] if pkg else ""


# ---------------------------------------------------------------- 页面: 授权与账本

def page_ledger(ledger, packages, actors):
    st.markdown('<div class="sx-hero-title">授权与账本</div>', unsafe_allow_html=True)
    st.markdown('<div class="sx-sub">授权有期限、有次数，每次查验都留回执；账本全链可验。</div>',
                unsafe_allow_html=True)
    ok, broken, reason = ledger.verify_chain()
    head = ledger.head_hash()
    status_text = ('全链校验通过' if ok else
                   '链已断裂 @ ' + str(broken) + '：' + reason)
    hint_html = ('<div class="sx-sec-sub" style="margin:8px 0 0;padding-left:0">账本为空：'
                 '先登记一份文件，或在左侧一键载入演示数据。</div>'
                 if len(ledger.entries) == 0 else '')
    n_entries = len(ledger.entries)
    if n_entries:
        shown = ledger.entries[-28:]  # 取最新 28 条, 末块即真链头 (学 AI Studio 版)
        squares = []
        for i in range(len(shown)):
            cls = "sx-block"
            if i == len(shown) - 1:
                cls += " sx-block-head"
            elif i >= len(shown) // 2:
                cls += " sx-block-mid"
            squares.append(f'<span class="{cls}"></span>')
        blocks_html = ('<div class="sx-chain">' + "".join(squares)
                       + f'<span class="sx-chain-note">区块 × {n_entries}'
                         ' · 最右为链头</span></div>')
    else:
        blocks_html = ''
    st.markdown(f"""
    <div class="sx-card">
      <div class="sx-label">账本状态</div>
      <div class="sx-ledger-head">{status_text}</div>
      <div class="sx-mono" style="margin-top:6px">高度 {n_entries} · 链头 {head}</div>
      {blocks_html}
      {hint_html}
    </div>""", unsafe_allow_html=True)
    if st.button("写入检查点（封印当前链头）"):
        svc.checkpoint(ledger, actors[REGISTRAR_NAME])
        st.success("检查点已入账。")
        st.rerun()

    regs = registrations(ledger)
    labels = {f"{p['cert_id']} · {p['filename']}": p["cert_id"] for p in regs}
    st.markdown('<div class="sx-sec">新建授权</div>', unsafe_allow_html=True)
    st.markdown('<div class="sx-sec-sub">把指定凭证的查验权授予验真方，限期、限次、全程留痕。</div>',
                unsafe_allow_html=True)
    if labels:
        with st.form("auth_form"):
            cert = labels[st.selectbox("凭证", list(labels))]
            grantee = st.text_input("被授权方", VERIFIER_NAME)
            c1, c2 = st.columns(2)
            days = c1.number_input("有效天数", 1, 365, 7)
            maxc = c2.number_input("最多查验次数", 1, 100, 2)
            if st.form_submit_button("创建授权", type="primary"):
                au = svc.create_authorization(
                    ledger, actors[REGISTRAR_NAME], cert, grantee,
                    actors[VERIFIER_NAME].fingerprint, int(days), int(maxc))
                st.success(f"授权已入账：{au}")
                st.rerun()
    else:
        st.markdown('<div class="sx-empty">暂无可授权的凭证。<br>'
                    '先到「登记」页登记一份文件，或在左侧一键载入演示数据。</div>',
                    unsafe_allow_html=True)
    auths = ledger.by_type("authorization")
    if auths:
        rows = []
        for e in auths:
            p = e["payload"]
            chk = svc.check_authorization(ledger, p["auth_id"])
            rows.append({"授权号": p["auth_id"], "凭证": p["cert_id"],
                         "被授权方": p["grantee"], "已用/上限":
                         f"{chk['used']}/{p['max_count']}",
                         "状态": "有效" if chk["valid"] else chk["reason"]})
        st.dataframe(rows, use_container_width=True, hide_index=True)

    receipts = ledger.by_type("receipt")
    st.markdown('<div class="sx-sec">验真回执</div>', unsafe_allow_html=True)
    if receipts:
        rows = [{"回执": e["payload"]["receipt_id"], "凭证": e["payload"]["cert_id"],
                 "验真方": e["payload"]["verifier"], "结论": e["payload"]["grade"],
                 "时间": e["ts"]} for e in receipts]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.markdown('<div class="sx-empty">暂无回执。<br>'
                    '在「验真」页完成一次验真后，回执会自动入账到这里。</div>',
                    unsafe_allow_html=True)

    st.markdown('<div class="sx-sec">作废与密钥公告</div>', unsafe_allow_html=True)
    if labels:
        cert = labels[st.selectbox("选择凭证", list(labels), key="revoke_cert")]
        state = svc.resolve_status(ledger, cert)
        st.caption(f"当前状态：{state['status']}"
                   + ("；".join(state["annotations"]) if state["annotations"] else ""))
        if st.button("作废这张凭证（登记方签名，不可逆）"):
            svc.revoke(ledger, actors[REGISTRAR_NAME], cert)
            st.success("已作废并入账。")
            st.rerun()
    else:
        st.markdown('<div class="sx-empty">暂无可作废的凭证。</div>',
                    unsafe_allow_html=True)


# ---------------------------------------------------------------- 主入口

def main():
    st.set_page_config(page_title="数玺", page_icon="玺", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    ledger, packages, actors = init_stores(DATA_DIR)
    with st.sidebar:
        st.markdown("""
        <div class="sx-side-brand">
          <div class="sx-logo sx-logo-lg"><div class="sx-logo-in">玺</div></div>
          <div>
            <div class="sx-brand">数玺</div>
            <div class="sx-brand-sub">数据可信管理工具</div>
          </div>
        </div>
        <div class="sx-brand-bar"></div>
        <div class="sx-brand-sub">规范 v1.3 · 套件 SXA1 · 原型</div>""",
                    unsafe_allow_html=True)
        page = st.radio("导航", ["登记", "验真", "授权与账本"])
        ok_sb, _, _ = ledger.verify_chain()
        dot_sb = "#10B981" if ok_sb else "#C23531"
        state_sb = "全链可验" if ok_sb else "链异常"
        st.markdown(f"""
        <div class="sx-side-card">
          <div class="sx-sc-label">账本状态</div>
          <div class="sx-sc-value"><span class="sx-dot" style="background:{dot_sb}"></span>{state_sb}</div>
          <div class="sx-brand-sub" style="margin-top:4px">高度 {len(ledger.entries)} · 登记 {len(ledger.by_type('registration'))} · 回执 {len(ledger.by_type('receipt'))}</div>
          <div class="sx-brand-sub" style="margin-top:3px">检查点 {len(ledger.by_type('checkpoint'))} · 链头 <span style="font-family:var(--mono)">{ledger.head_hash()[:10]}…</span></div>
        </div>""", unsafe_allow_html=True)
        if st.button("一键载入演示数据"):
            # 提示先存会话再刷新: 直接 success 后接 rerun, 提示会被刷新冲掉,
            # 人眼看不见, 按钮看着像死的 (2026-10-27 用户实测抓到)。
            try:
                certs = seed_demo(ledger, packages, actors[REGISTRAR_NAME])
            except Exception as e:  # 环境异常不许把英文堆栈露给用户
                st.session_state["seed_flash"] = (
                    "error", f"演示数据载入失败：{e}。请把这条提示截图发给维护者。")
            else:
                st.session_state["seed_flash"] = (
                    "success",
                    f"已补齐演示数据：新增 {len(certs)} 张演示凭证" if certs
                    else "演示数据已齐全（3 张演示凭证都在，可直接去验真页试）")
            st.rerun()
        _flash = st.session_state.pop("seed_flash", None)
        if _flash:
            (st.success if _flash[0] == "success" else st.error)(_flash[1])
        st.markdown("""
        <div class="sx-side-card">
          <div class="sx-sc-label">演示说明</div>
          <div class="sx-actor"><span>登记方</span>示例新能源有限公司 · 财务部</div>
          <div class="sx-actor"><span>验真方</span>合作银行 · 核验岗</div>
          <div class="sx-actor-note">出场主体均为虚构，仅用于演示</div>
          <div class="sx-side-sell">三层指纹 · 四级验真<br>哈希存证 / 一键验真 / 授权留痕</div>
        </div>""", unsafe_allow_html=True)
    top_bar(ledger)
    status_strip(ledger)
    if page == "登记":
        page_register(ledger, packages, actors)
    elif page == "验真":
        page_verify(ledger, packages, actors)
    else:
        page_ledger(ledger, packages, actors)


if __name__ == "__main__":
    main()
