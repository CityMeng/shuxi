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

import base64
import html
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
from engine import anchor as anchor_mod  # noqa: E402
from engine import bundle as bundle_mod  # noqa: E402
from engine import report_pdf as report_pdf_mod  # noqa: E402
from engine.ledger import KeyPair, Ledger  # noqa: E402

DATA_DIR = os.environ.get("SHUXI_DATA_DIR", os.path.join(BASE_DIR, "data"))
DEMO_PASS = os.environ.get("SHUXI_DEMO_PASS", "shuxi-demo")
REGISTRAR_NAME = "望舒新能源科技有限公司 · 财务部出纳"
VERIFIER_NAME = "临溪商业银行 · 风控部核验员"

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
  --ink: #111827;            /* 徽墨浓黑主字 (路演投影高对比强化) */
  --ink-2: #374151;          /* 次级正文墨色 */
  --ink-3: #6B7280;          /* 辅助弱字/标签 */
  --line: #DED8CA;           /* 宣纸金石界线 (强化投影可辨识度) */
  --line-strong: #CFC7B6;    /* 强分界线 */
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
    radial-gradient(circle at 15% 10%, rgba(194,53,49,.028) 0%, rgba(0,0,0,0) 42%),
    radial-gradient(circle at 85% 15%, rgba(217,119,6,.028) 0%, rgba(0,0,0,0) 42%),
    linear-gradient(rgba(120,113,108,.045) 1px, rgba(0,0,0,0) 1px),
    linear-gradient(90deg, rgba(120,113,108,.045) 1px, rgba(0,0,0,0) 1px);
  background-size: 100% 100%, 100% 100%, 32px 32px, 32px 32px;
  background-attachment: fixed;
}
::selection { background: rgba(194,53,49,.22); }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #CFC7B6; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #B5AA96; }
#MainMenu, footer, [data-testid="stDecoration"] { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent !important; height: 1.5rem !important; }
.block-container { max-width: 1580px; padding: 2.8rem 2.2rem 2.0rem; }
h1 { font-size: 26px !important; }
h2 { font-size: 20px !important; }
h3 { font-size: 16px !important; }
h1, h2, h3 { font-family: var(--serif); letter-spacing: .01em;
  font-weight: 700; color: var(--ink); }
p, li, label, .stMarkdown { font-size: 14.5px; line-height: 1.55; }
[data-testid="stCaptionContainer"] p { font-size: 13px !important;
  color: var(--ink-2) !important; }
hr { margin: 0.9rem 0 !important; border-color: var(--line) !important; }

/* 侧栏: 深一号宣纸 + 发丝金界 + 印章式品牌 */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #F5F1E8, #EFEAE0);
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
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top: 1.3rem; }
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
  box-shadow: 0 3px 10px -2px rgba(24,24,27,.05), inset 0 0 0 1px rgba(255,255,255,.7); }
.sx-side-card .sx-sc-label { font-size: 12.5px; letter-spacing: .1em; color: var(--ink-3);
  font-weight: 700; margin-bottom: 5px; }
.sx-side-card .sx-sc-value { font-family: var(--mono);
  font-size: 17px; font-weight: 700; color: var(--ink); }
.sx-side-foot { font-size: 13.5px; color: var(--ink-3); line-height: 1.65; margin-top: 14px; }
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
  font-size: 13.5px !important; line-height: 1.65 !important; }
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 1.0rem; }
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
  color: var(--ink-2); background: rgba(255,253,246,.85);
  border: 1px solid var(--line); border-radius: 6px; padding: 2px 8px; }
.sx-top-chip { font-family: var(--mono); font-size: 12.5px;
  color: var(--ink); background: var(--card);
  border: 1px solid var(--line); border-radius: 8px; padding: 4px 12px;
  box-shadow: 0 2px 6px -1px rgba(24,24,27,.04); }

/* 控件与公文分段切换器 (Segmented Tabs) */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  border-radius: 10px; padding: 0.42rem 1.3rem; font-weight: 600;
  font-size: 14.5px; border: 1px solid var(--line-strong);
  background: #FFFFFF; color: var(--ink-2);
  box-shadow: 0 1px 3px rgba(24,24,27,.05);
  transition: all .18s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover,
.stFormSubmitButton > button:hover { border-color: #B8AF9E; color: var(--ink);
  background: #FAF8F3; }
button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-primaryFormSubmit"] {
  background: #C23531 !important;
  border: 1px solid #B91C1C !important; color: #FFFFFF !important;
  border-radius: 12px !important;
  box-shadow: 0 3px 10px rgba(194,53,49,.22);
}
button[data-testid="stBaseButton-primary"]:hover,
button[data-testid="stBaseButton-primaryFormSubmit"]:hover {
  background: #B91C1C !important; border-color: #991B1B !important;
}
div[data-testid="stTabs"] [data-baseweb="tab-list"] {
  background: #F2EDE2;
  border: 1px solid var(--line-strong);
  border-radius: 12px;
  padding: 4px 6px;
  gap: 6px;
  margin-bottom: 10px;
}
div[data-testid="stTabs"] button[data-baseweb="tab"] {
  border-radius: 9px !important;
  padding: 7px 18px !important;
  font-weight: 700 !important;
  font-size: 14.5px !important;
  color: var(--ink-2) !important;
  background: transparent !important;
  border: none !important;
  transition: all .16s ease;
}
div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
  background: #FFFFFF !important;
  color: var(--seal-deep) !important;
  box-shadow: 0 2px 8px rgba(24,24,27,.08), 0 0 0 1px var(--line) !important;
}
div[data-testid="stTabs"] [data-baseweb="tab-highlight"],
div[data-testid="stTabs"] [data-baseweb="tab-border"] {
  display: none !important;
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
  border-radius: 12px;
  box-shadow: 0 2px 8px -2px rgba(24,24,27,.04);
}
div[data-testid="stExpander"] summary { font-size: 14.5px; font-weight: 600; color: var(--ink); }
.stDataFrame { border-radius: 10px; overflow: hidden;
  border: 1px solid var(--line); }
div[data-testid="stAlert"] { border-radius: 10px; font-size: 14.5px; }

/* 公文纸面板: 近白纸面 + 清晰金石界线 + 多层立体微投影 */
.sx-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 16px; padding: 18px 22px; margin: 8px 0;
  box-shadow: 0 6px 22px -4px rgba(24,24,27,.06), 0 2px 6px -1px rgba(24,24,27,.04);
}
.sx-card .sx-label {
  border-bottom: 1px solid var(--line);
  padding-bottom: 8px; margin-bottom: 10px;
}
.sx-hero-card { display: flex; justify-content: space-between;
  align-items: center; gap: 18px; }
.sx-grade { font-family: var(--serif); font-size: 42px; font-weight: 900;
  letter-spacing: .02em; line-height: 1.25; padding: 2px 0; }
.sx-conf { font-size: 14.5px; color: var(--ink-2); margin-top: 2px; font-weight: 500; }
.sx-cert-id { font-family: var(--mono);
  font-size: 24px; font-weight: 700; letter-spacing: .02em; color: var(--ink);
  line-height: 1.4; padding: 2px 0; }
.sx-diffbox { background:#FDF2F2; border:1px solid #F0C6C6;
  border-left:5px solid #C23531; border-radius:12px; padding:12px 16px;
  margin:8px 0 6px; font-size:14.5px; color:var(--ink); line-height:1.9;
  box-shadow: 0 3px 10px -2px rgba(194,53,49,.08); }
.sx-diffbox .sx-diff-title { font-weight:700; color:#991B1B;
  font-size:13px; letter-spacing:.08em; margin-bottom:2px; }
.sx-diff-old { background:#EDEAE2; color:#4B5563; text-decoration:line-through;
  padding:1px 6px; border-radius:4px; font-family:var(--mono); }
.sx-diff-new { background:#FDE8E8; color:#B91C1C; font-weight:700;
  padding:1px 6px; border-radius:4px; font-family:var(--mono); }
.sx-diff-delta { color:#B91C1C; font-weight:700; font-family:var(--mono); }
.sx-stamp-mini { display:inline-block; border:1.5px solid #C23531;
  color:#C23531; border-radius:4px; padding:0 5px; font-size:11.5px;
  font-weight:700; transform:rotate(-6deg); letter-spacing:.15em;
  margin-left:6px; background:#FFF5F5; }
table.sx-ftable { width:100%; border-collapse:collapse; font-size:13.5px; }
table.sx-ftable th { text-align:left; color:var(--ink-3); font-weight:700;
  border-bottom:1px solid var(--line-strong); padding:6px 8px; }
table.sx-ftable td { border-bottom:1px solid var(--line); padding:6px 8px;
  color:var(--ink); }
td.sx-f-old { background:#F5F1E8; color:#4B5563;
  text-decoration:line-through; font-family:var(--mono); }
td.sx-f-new { background:#FDE8E8; color:#B91C1C; font-weight:700;
  font-family:var(--mono); }
td.sx-f-mono { font-family:var(--mono); }
.sx-mono { font-family: var(--mono);
  font-size: 12.5px; line-height: 1.65; word-break: break-all; color: var(--ink-2); }
.sx-mono-box { background: #FAF8F3; border: 1px solid var(--line);
  border-radius: 10px; padding: 11px 14px; margin-top: 8px; }
.sx-hash-tag { display: inline-block; font-family: var(--mono); font-size: 11px;
  font-weight: 700; color: var(--ink-2); background: #EFECE4;
  border: 1px solid var(--line-strong); border-radius: 5px;
  padding: 1px 6px; margin-right: 6px; letter-spacing: .04em; }
.sx-label { font-size: 12.5px; font-weight: 700; color: var(--ink-3);
  letter-spacing: .08em; margin-bottom: 4px; }
.sx-chip { display: inline-block; background: #F5F2EB;
  border: 1px solid var(--line); border-radius: 7px;
  padding: 2px 9px; margin: 2px 5px 2px 0; font-size: 12.5px;
  font-weight: 500; color: var(--ink-2); }
.sx-hero-title { font-family: var(--serif); font-size: 27px; font-weight: 900;
  letter-spacing: .03em; line-height: 1.45; padding: 2px 0 0; margin: 0; color: var(--ink); }
.sx-sub { color: var(--ink-2); font-size: 14.5px; margin: 2px 0 10px; line-height: 1.55; }
.sx-ledger-head { font-size: 18px; font-weight: 700; letter-spacing: .01em;
  color: var(--ink); line-height: 1.5; padding: 2px 0; }
.sx-sec { font-family: var(--serif); font-size: 17.5px; font-weight: 700;
  letter-spacing: .02em;
  line-height: 1.5; padding: 2px 0 2px 14px;
  margin: 12px 0 4px; color: var(--ink); position: relative; }
.sx-sec::before { content: ""; position: absolute; left: 0; top: 4px; bottom: 4px;
  width: 4px; border-radius: 2px;
  background: linear-gradient(180deg, var(--seal), var(--gold)); }
.sx-sec-sub { font-size: 13px; color: var(--ink-2); margin-bottom: 8px; padding-left: 14px; }
.sx-empty {
  background: rgba(255,253,246,.72); border: 1.5px dashed var(--line-strong);
  border-radius: 12px; padding: 22px 24px; margin: 8px 0 6px;
  color: var(--ink-2); font-size: 14px; line-height: 1.65; text-align: center;
}
.sx-reasons { background: var(--card); border: 1px solid var(--line);
  border-radius: 12px; padding: 12px 20px; margin: 4px 0 10px;
  box-shadow: 0 2px 8px -2px rgba(24,24,27,.04); }
.sx-reasons ul { margin: 0; padding-left: 20px; }
.sx-reasons li { font-size: 14.5px; line-height: 1.6; margin: 3px 0; color: var(--ink); }

/* 顶部状态条: 一行压紧的公文抬头, 图标砖 + 等宽数字 */
.sx-strip { display: flex; gap: 0; flex-wrap: wrap;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 16px; padding: 10px 8px; margin: 0 0 14px;
  box-shadow: 0 4px 14px -3px rgba(24,24,27,.05); }
.sx-stat { flex: 1 1 140px; padding: 3px 14px; display: flex; align-items: center;
  gap: 10px; border-left: 1px solid var(--line); }
.sx-stat:first-child { border-left: none; }
.sx-stat-ico { width: 34px; height: 34px; border-radius: 8px; flex: none;
  display: flex; align-items: center; justify-content: center; border: 1px solid; }
a.sx-stat { text-decoration: none; color: inherit; cursor: pointer;
  border-radius: 10px; transition: background .15s ease; }
a.sx-stat:hover { background: #F5F1E8; }
a.sx-stat:hover .sx-stat-num { color: var(--seal-deep); }
a.sx-stat:active { background: #F0EBE0; }
.sx-stat-num { font-family: var(--mono);
  font-size: 17.5px; font-weight: 700; color: var(--ink); }
.sx-stat-label { font-size: 12px; color: var(--ink-2); letter-spacing: .05em; margin-bottom: 1px; font-weight: 600; }
.sx-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  margin-right: 6px; vertical-align: 1px;
  animation: sx-pulse 2.2s ease-in-out infinite; }
@keyframes sx-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(16,185,129,.40); }
  50% { box-shadow: 0 0 0 5px rgba(16,185,129,0); }
}

/* 三层指纹核验矩阵 (建议 3: 硬核技术可视化 Layer Stack) */
.sx-layer-stack {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 14px 18px;
  margin: 8px 0 10px;
  box-shadow: 0 4px 16px -3px rgba(24,24,27,.05);
}
.sx-layer-head {
  display: flex; justify-content: space-between; align-items: center;
  border-bottom: 1px solid var(--line); padding-bottom: 8px; margin-bottom: 10px;
}
.sx-layer-title {
  font-family: var(--serif); font-size: 15px; font-weight: 700;
  color: var(--ink); letter-spacing: .03em;
}
.sx-layer-sub { font-size: 12px; color: var(--ink-3); font-family: var(--mono); }
.sx-layer-row {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; padding: 9px 12px; margin: 6px 0;
  background: #FAF8F3; border: 1px solid var(--line);
  border-radius: 10px; border-left: 4px solid var(--line-strong);
}
.sx-layer-left { flex: 1; min-width: 0; }
.sx-layer-name { font-size: 13.5px; font-weight: 700; color: var(--ink);
  display: flex; align-items: center; gap: 8px; }
.sx-layer-tag { font-family: var(--mono); font-size: 11px; font-weight: 700;
  padding: 1px 6px; border-radius: 4px; background: #EFECE4; color: var(--ink-2);
  border: 1px solid var(--line-strong); }
.sx-layer-detail { font-family: var(--mono); font-size: 12px; color: var(--ink-2);
  margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sx-layer-badge { flex: none; font-size: 12px; font-weight: 700;
  padding: 3px 10px; border-radius: 999px; border: 1px solid; white-space: nowrap; }
.sx-meter-wrap { display: flex; align-items: center; gap: 10px; margin-top: 5px; }
.sx-meter-track { flex: 1; height: 7px; background: #E6E0D3; border-radius: 999px;
  overflow: hidden; position: relative; max-width: 240px; }
.sx-meter-fill { height: 100%; border-radius: 999px; }

/* 账本三阶时间锚定流水线 (建议 4: 时间锚定仪式感设计) */
.sx-pipeline {
  display: flex; align-items: stretch; gap: 10px; flex-wrap: wrap;
  margin: 12px 0 8px; padding-top: 12px; border-top: 1px solid var(--line);
}
.sx-pipe-step {
  flex: 1 1 200px; background: #FAF8F3; border: 1px solid var(--line);
  border-radius: 11px; padding: 10px 14px; position: relative;
}
.sx-pipe-step.sx-pipe-active {
  background: #FFFDFA; border-color: rgba(217,119,6,.45);
  box-shadow: inset 0 0 0 1px rgba(217,119,6,.15);
}
.sx-pipe-kicker { font-family: var(--mono); font-size: 11px; font-weight: 700;
  color: var(--ink-3); letter-spacing: .06em; display: flex;
  justify-content: space-between; align-items: center; }
.sx-pipe-title { font-family: var(--serif); font-size: 14.5px; font-weight: 700;
  color: var(--ink); margin: 3px 0 2px; }
.sx-pipe-meta { font-family: var(--mono); font-size: 12px; color: var(--ink-2); }
.sx-pipe-arrow { display: flex; align-items: center; color: var(--gold);
  font-weight: 700; font-size: 16px; padding: 0 2px; }

/* 账本区块流: 墨方块递进, 链头是盖着的朱砂印 */
.sx-chain { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; margin-top: 10px; }
.sx-block { width: 17px; height: 17px; border-radius: 4px;
  background: #DFD8CA; border: 1px solid #CFC7B6;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.6); }
.sx-block-mid { background: #9CA3AF; border-color: #6B7280; }
.sx-block-head { background: radial-gradient(circle at 35% 30%, #DC2626, #C23531 55%, #991B1B);
  border-color: #FEF3C7;
  box-shadow: 0 0 0 1.5px #FEF3C7, 0 0 0 3px #D97706, 0 3px 8px rgba(153,27,27,.35); }
.sx-chain-note { font-size: 12.5px; color: var(--ink-2); margin-left: 8px; font-family: var(--mono); }
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
.sx-doc { position: relative; border-color: #D5CBB8;
  background: linear-gradient(180deg, #FFFFFF 0%, #FFFDFA 100%);
  box-shadow: 0 8px 26px -4px rgba(55,42,28,.09), 0 2px 6px rgba(24,24,27,.04); }
.sx-doc::after { content: ""; position: absolute; top: 5px; left: 5px;
  right: 5px; bottom: 5px; border: 1px solid rgba(217,119,6,.38);
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
    raw = {}
    if os.path.exists(actors_path):
        raw = json.load(open(actors_path, encoding="utf-8"))
        for name, rec in raw.items():
            actors[name] = KeyPair.from_encrypted_pem(rec["privkey_pem"], DEMO_PASS)
    # 当前主体名缺失时补齐并写回 (改名后旧实例不再 KeyError);
    # 旧条目保留, 历史登记与回执的签名依旧可验。
    missing = [n for n in (REGISTRAR_NAME, VERIFIER_NAME) if n not in actors]
    if missing:
        for name in missing:
            kp = KeyPair.generate()
            actors[name] = kp
            raw[name] = {"privkey_pem": kp.private_pem_encrypted(DEMO_PASS),
                         "pub": kp.public_b64, "fp": kp.fingerprint}
        with open(actors_path, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=1)
    return ledger, packages, actors


def wipe_data_dir(data_dir: str):
    """演示重置: 清空数据目录内的账本/登记包/主体密钥, 目录本身保留。
    只动该目录第一层, 并拒绝可疑路径 (根目录/用户主目录)。"""
    ap = os.path.abspath(data_dir)
    if ap in ("/", os.path.expanduser("~")) or len(ap) < 4:
        raise ValueError(f"拒绝清空可疑路径: {ap}")
    if not os.path.isdir(ap):
        return
    import shutil
    for name in os.listdir(ap):
        p = os.path.join(ap, name)
        if os.path.isdir(p) and not os.path.islink(p):
            shutil.rmtree(p)
        else:
            os.remove(p)


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
    pkg = packages.get(cert_id)
    comp = fp.compute_all(data, ext_of(filename), pkg["salts"] if pkg else None)
    reg = ledger.find_registration(cert_id)
    return {"report": report, "comp": comp, "reg": reg, "data": data,
            "filename": filename, "elapsed_ms": elapsed_ms}


def run_tour(ledger, packages, actors):
    """评委导览: 用真实服务调用连跑四步, 结果在登记页整屏呈现。"""
    seed_demo(ledger, packages, actors[REGISTRAR_NAME])
    regs = {}
    for e in ledger.by_type("registration"):
        pkg = packages.get(e["payload"]["cert_id"])
        if pkg and svc.resolve_status(
                ledger, e["payload"]["cert_id"])["status"] == "有效":
            regs[pkg["filename"]] = e["payload"]["cert_id"]
    sample_dir = os.path.join(BASE_DIR, "vectors", "samples")

    def _load(n):
        with open(os.path.join(sample_dir, n), "rb") as f:
            return f.read()

    steps = [{"kind": "seed",
              "title": "第一步 · 存证母本（演示三件套已入账）", "regs": regs}]
    cert = regs.get("report.txt")
    res = do_verify(ledger, packages, actors[VERIFIER_NAME], cert,
                    "report_tampered.txt", _load("report_tampered.txt"))
    steps.append({"kind": "verify",
                  "title": "第二步 · 篡改件验真（净利润被改大）", "res": res})
    sa = svc.standalone_check(ledger, _load("fake.txt"), "txt", "fake.txt")
    steps.append({"kind": "standalone",
                  "title": "第三步 · 随手查穿透（未登记文件初判）", "sa": sa})
    made_cp = False
    if not ledger.by_type("checkpoint"):
        anch = anchor_mod.stamp_digest(ledger.head_hash())
        svc.checkpoint(ledger, actors[REGISTRAR_NAME], anchor=anch)
        made_cp = True
    bundle = bundle_mod.build_bundle(ledger, packages, cert,
                                     report=res["report"])
    steps.append({"kind": "bundle",
                  "title": "第四步 · 离线证据包（可断网复核）",
                  "bundle": bundle, "made_cp": made_cp,
                  "anchor_line": anchor_mod.latest_anchor_summary(
                      ledger, DATA_DIR)})
    return steps


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
      </div>
      <div class="sx-top-chip"><span class="sx-dot" style="background:{dot}"></span>{state} · 高度 {len(ledger.entries)}</div>
    </div>""", unsafe_allow_html=True)


def status_strip(ledger):
    """全局状态条: 图标砖 + 标签 + 等宽数字 (全部真实数据, 三页通栏)。"""
    ok, _, _ = ledger.verify_chain()
    dot = "#059669" if ok else "#C23531"
    state = "全链可验" if ok else "链异常"
    # 四格整格可点 (下钻): 链接带 goto 参数, main() 据此切换导航页
    cells = [
        ("#FAF8F3", "#E7E2D6", "#78716C",
         _SVG_LAYERS, "账本高度", str(len(ledger.entries)),
         "ledger", "查看账本状态"),
        ("#FAF8F3", "#E7E2D6", "#78716C",
         _SVG_FILECHECK, "已登记凭证", str(len(ledger.by_type('registration'))),
         "register", "查看已登记凭证"),
        ("#FAF8F3", "#E7E2D6", "#78716C",
         _SVG_RECEIPT, "验真回执", str(len(ledger.by_type('receipt'))),
         "receipts", "查看验真回执"),
        ("rgba(5,150,105,.07)", "rgba(5,150,105,.30)", "#059669",
         _SVG_LINK, "链状态",
         f'<span class="sx-dot" style="background:{dot}"></span>{state}',
         "chain", "查看账本状态"),
    ]
    html = ['<div class="sx-strip">']
    for bg, bd, fg, icon, label, value, goto, hint in cells:
        html.append(
            f'<a class="sx-stat" href="?goto={goto}" target="_self" '
            f'title="{hint}"><div class="sx-stat-ico" '
            f'style="background:{bg};border-color:{bd};color:{fg}">{icon}</div>'
            f'<div><div class="sx-stat-label">{label}</div>'
            f'<div class="sx-stat-num">{value}</div></div></a>')
    html.append('</div>')
    st.markdown("".join(html), unsafe_allow_html=True)


def fmt_field_value(v):
    if v is None:
        return "（无）"
    try:
        f = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return str(v)
    return f"{f:,.2f}".rstrip("0").rstrip(".")


def diff_strip_html(report):
    """丁级差异条: 原值删除线 → 篡改值红底 + 涨跌幅 + 篡改小戳。"""
    diffs = (report.get("field_diffs")
             or (report.get("evidence") or {}).get("field_diffs") or [])
    if not diffs:
        return ""
    rows = []
    for d in diffs:
        old = fmt_field_value(d.get("registered"))
        new = fmt_field_value(d.get("candidate"))
        delta = ""
        try:
            r = float(str(d.get("registered")).replace(",", ""))
            c = float(str(d.get("candidate")).replace(",", ""))
            if r != 0:
                pct = (c - r) / abs(r) * 100
                delta = (f' <span class="sx-diff-delta">'
                         f'({pct:+.1f}%)</span>')
        except (TypeError, ValueError):
            pass
        rows.append(
            f'<div>{html.escape(str(d.get("field")))}：'
            f'<span class="sx-diff-old">{html.escape(old)}</span> → '
            f'<span class="sx-diff-new">{html.escape(new)}</span>{delta}'
            f'<span class="sx-stamp-mini">篡改</span></div>')
    return ('<div class="sx-diffbox"><div class="sx-diff-title">'
            '关键字段被改动</div>' + "".join(rows) + "</div>")


def fields_table_html(reg_fields, cand_fields):
    """语义字段对比表: 不同行原值删除线、待验值红底、状态盖篡改戳。"""
    keys = sorted(set(reg_fields or {}) | set(cand_fields or {}),
                  key=lambda k: k.encode("utf-8"))
    if not keys:
        return ""
    trs = []
    for k in keys:
        rv = (reg_fields or {}).get(k)
        cv = (cand_fields or {}).get(k)
        if rv == cv:
            trs.append(
                f"<tr><td>{html.escape(str(k))}</td>"
                f"<td class='sx-f-mono'>"
                f"{html.escape(fmt_field_value(rv))}</td>"
                f"<td class='sx-f-mono'>"
                f"{html.escape(fmt_field_value(cv))}</td>"
                f"<td style='color:#059669'>一致</td></tr>")
        else:
            trs.append(
                f"<tr><td>{html.escape(str(k))}</td>"
                f"<td class='sx-f-old'>"
                f"{html.escape(fmt_field_value(rv))}</td>"
                f"<td class='sx-f-new'>"
                f"{html.escape(fmt_field_value(cv))}</td>"
                f"<td><span class='sx-stamp-mini'>篡改</span></td></tr>")
    return ("<table class='sx-ftable'><tr><th>字段</th><th>登记值</th>"
            "<th>待验值</th><th>状态</th></tr>" + "".join(trs) + "</table>")


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


def layer_stack_html(rp, comp, report=None, reg_fields=None, sim=None):
    """三层指纹核验矩阵 (建议 3: 硬核技术可视化 Layer Stack)。"""
    # L1: 精确层 (SHA-256 / SM3 双根一致性)
    l1_match = (rp["exact"]["sha256_root"] == comp["exact"]["sha256_root"]
                and rp["exact"]["sm3_root"] == comp["exact"]["sm3_root"])
    l1_color = "#059669" if l1_match else "#C23531"
    l1_bg = "rgba(5,150,105,.08)" if l1_match else "rgba(194,53,49,.08)"
    l1_border = "rgba(5,150,105,.3)" if l1_match else "rgba(194,53,49,.3)"
    l1_badge = "双根锁定 · 逐字节吻合" if l1_match else "双根失锁 · 原文已变"

    # L2: 感知层 (pHash 与 3-gram 相似度)
    rp_h = rp.get("phashes") or []
    cp_h = (comp.get("perceptual") or {}).get("phashes") or []
    if rp_h and cp_h and len(rp_h) == len(cp_h):
        dists = [fp.hamming_hex(a, b) for a, b in zip(rp_h, cp_h)]
        avg_dist = sum(dists) / len(dists)
        ph_match = (avg_dist <= 8)
        ph_desc = f"逐页汉明距 {dists}（均值 {avg_dist:.1f}，阈值 ≤ 8）"
    else:
        ph_match = None
        ph_desc = f"登记 {len(rp_h)} 页 / 待验 {len(cp_h)} 页（跨页型）"

    if sim is not None:
        sim_val = float(sim)
        sim_pct = max(0, min(100, int(sim_val * 100)))
        sim_desc = f"文本 3-gram 相似度 {sim_val:.2%}（阈值 ≥ 90%）"
        sim_match = (sim_val >= 0.90)
    else:
        sim_pct = 0
        sim_desc = "文本相似度：不可用（纯图或无文本流）"
        sim_match = None

    l2_ok = (ph_match is True or ph_match is None) and (sim_match is True or sim_match is None)
    l2_color = "#059669" if l2_ok else "#D97706"
    l2_bg = "rgba(5,150,105,.08)" if l2_ok else "rgba(217,119,6,.08)"
    l2_border = "rgba(5,150,105,.3)" if l2_ok else "rgba(217,119,6,.3)"
    l2_badge = "排版/文本骨架一致" if l2_ok else "排版或文本骨架差异"

    # L3: 语义层 (加盐 Merkle 根与字段差异)
    cand_root = (comp.get("semantic") or {}).get("root")
    reg_root = rp.get("semantic_root")
    diffs = (report.get("field_diffs")
             or (report.get("evidence") or {}).get("field_diffs") or []) if report else []
    l3_match = (reg_root == cand_root and not diffs)
    l3_color = "#059669" if l3_match else "#C23531"
    l3_bg = "rgba(5,150,105,.08)" if l3_match else "rgba(194,53,49,.08)"
    l3_border = "rgba(5,150,105,.3)" if l3_match else "rgba(194,53,49,.3)"
    n_fields = len(comp.get("fields") or {})
    l3_badge = f"语义根吻合 · {n_fields} 项一致" if l3_match else f"语义根异常 · 检出 {len(diffs)} 处异动"

    return f"""
    <div class="sx-layer-stack">
      <div class="sx-layer-head">
        <span class="sx-layer-title">三层指纹核验矩阵</span>
        <span class="sx-layer-sub">L1 精确层 ──► L2 感知层 ──► L3 语义层</span>
      </div>
      <!-- L1 精确层 -->
      <div class="sx-layer-row" style="border-left-color:{l1_color}">
        <div class="sx-layer-left">
          <div class="sx-layer-name">
            <span>第一层 · 精确指纹</span>
            <span class="sx-layer-tag">SHA-256 + SM3 双重哈希</span>
          </div>
          <div class="sx-layer-detail">
            <span class="sx-hash-tag">SHA-256</span>{comp['exact']['sha256_root'][:18]}…　
            <span class="sx-hash-tag">SM3</span>{comp['exact']['sm3_root'][:18]}…
          </div>
        </div>
        <div class="sx-layer-badge" style="color:{l1_color};background:{l1_bg};border-color:{l1_border}">
          {l1_badge}
        </div>
      </div>
      <!-- L2 感知层 -->
      <div class="sx-layer-row" style="border-left-color:{l2_color}">
        <div class="sx-layer-left">
          <div class="sx-layer-name">
            <span>第二层 · 感知指纹</span>
            <span class="sx-layer-tag">pHash 均值距 + 3-gram 标尺</span>
          </div>
          <div class="sx-meter-wrap">
            <div class="sx-meter-track">
              <div class="sx-meter-fill" style="width:{sim_pct}%;background:{l2_color}"></div>
            </div>
            <span style="font-family:var(--mono);font-size:12px;font-weight:700;color:{l2_color}">{sim_pct}%</span>
            <span style="font-size:12px;color:var(--ink-2);">{ph_desc}</span>
          </div>
        </div>
        <div class="sx-layer-badge" style="color:{l2_color};background:{l2_bg};border-color:{l2_border}">
          {l2_badge}
        </div>
      </div>
      <!-- L3 语义层 -->
      <div class="sx-layer-row" style="border-left-color:{l3_color}">
        <div class="sx-layer-left">
          <div class="sx-layer-name">
            <span>第三层 · 语义指纹</span>
            <span class="sx-layer-tag">加盐 Merkle 根 · 防撞库</span>
          </div>
          <div class="sx-layer-detail">
            <span class="sx-hash-tag">待验语义根</span>{(cand_root or '—')[:24]}…
          </div>
        </div>
        <div class="sx-layer-badge" style="color:{l3_color};background:{l3_bg};border-color:{l3_border}">
          {l3_badge}
        </div>
      </div>
    </div>
    """


# ---------------------------------------------------------------- 页面: 登记

def page_register(ledger, packages, actors):
    tour = st.session_state.get("tour")
    if tour:
        st.markdown('<div class="sx-sec">评委导览 · 核心链路一屏看完</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="sx-sec-sub">四步均为真实服务调用：母本存证、篡改件验真、'
                    '未登记随手查、离线证据包，结论与手工操作完全一致。</div>',
                    unsafe_allow_html=True)
        if st.button("关闭导览"):
            st.session_state.pop("tour", None)
            st.rerun()

        # 建议 2: 紧凑双列仪表盘，避免深垂直翻滚
        tcol1, tcol2 = st.columns([6, 6])
        for idx, step in enumerate(tour):
            target_col = tcol1 if idx % 2 == 0 else tcol2
            with target_col:
                st.markdown(f'<div class="sx-sec" style="font-size:16px;margin-top:6px">'
                            f'{step["title"]}</div>', unsafe_allow_html=True)
                if step["kind"] == "seed":
                    st.markdown("""
                    <div class="sx-card sx-doc" style="padding:14px 18px">
                      <div class="sx-label">母本已登记入账（全链可验）</div>
                    """, unsafe_allow_html=True)
                    for fn, cid in step["regs"].items():
                        st.markdown(f'<div class="sx-sub" style="margin-bottom:4px">'
                                    f'• <b>{fn}</b><br><span style="font-family:var(--mono);font-size:12.5px;color:var(--ink-2)">凭证 {cid}</span></div>',
                                    unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                elif step["kind"] == "verify":
                    grade_hero(step["res"]["report"], step["res"]["elapsed_ms"])
                    if step["res"]["report"].get("grade") == "丁级":
                        _ds = diff_strip_html(step["res"]["report"])
                        if _ds:
                            st.markdown(_ds, unsafe_allow_html=True)
                elif step["kind"] == "standalone":
                    grade_hero(step["sa"]["verdict"])
                    _comp = step["sa"].get("comp") or {}
                    st.markdown(
                        f"<div class='sx-mono-box'>"
                        f"<div class='sx-label'>初判指纹提取</div>"
                        f"<div class='sx-mono'>SHA-256: {_comp.get('exact', {}).get('sha256_root', '—')[:28]}…<br>"
                        f"抽出语义字段: {len(_comp.get('fields', {}))} 个</div></div>",
                        unsafe_allow_html=True)
                elif step["kind"] == "bundle":
                    st.markdown(f"""
                    <div class="sx-card sx-doc" style="padding:14px 18px">
                      <div class="sx-label">独立证据包与时间锚定</div>
                      <div class="sx-sub" style="margin:4px 0 10px">{step["anchor_line"]}</div>
                    </div>""", unsafe_allow_html=True)
                    st.download_button(
                        "下载独立证据包（JSON，可离线复核）",
                        json.dumps(step["bundle"], ensure_ascii=False, indent=1),
                        file_name="shuxi-tour-bundle.json",
                        mime="application/json",
                        use_container_width=True)
        st.markdown("---")
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
              <div style="margin:10px 0 4px;font-weight:600">{p['filename']} · 登记主体 {p['registrar']}</div>
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
    st.markdown('<div class="sx-sub">五步得出结论，三层指纹直观呈现，支持深挖底层证据与原件复核。</div>',
                unsafe_allow_html=True)
    regs = registrations(ledger)
    if not regs:
        st.markdown('<div class="sx-empty">尚无登记记录，验真无从谈起。<br>'
                    '先到「登记」页登记一份文件，或点左侧「一键载入演示数据」。'
                    '</div>', unsafe_allow_html=True)
        return

    # 建议 2: 顶部公文分段切换器 (Segmented Tabs)，彻底消灭长垂直翻滚
    tab_single, tab_standalone, tab_batch = st.tabs([
        "单件精密验真", "未登记文件随手查", "企业级批量排查"
    ])

    sample_dir = os.path.join(BASE_DIR, "vectors", "samples")
    quick = {}
    if os.path.isdir(sample_dir):
        quick = {n: os.path.join(sample_dir, n) for n in
                 ("report.txt", "report_tampered.txt", "report_converted.txt",
                  "scan_b.jpg") if os.path.exists(os.path.join(sample_dir, n))}

    with tab_single:
        # 左右双翼联动: 左翼操作控制台 (5) + 右翼实时核验视界 (7)
        col_ctrl, col_view = st.columns([5, 7])
        labels = {f"{p['cert_id']} · {p['filename']}": p["cert_id"] for p in regs}
        with col_ctrl:
            st.markdown('<div class="sx-sec" style="margin-top:0">选择比对母本与待验件</div>',
                        unsafe_allow_html=True)
            cert = labels[st.selectbox("选择登记凭证", list(labels), key="ver_cert_select")]
            reg = ledger.find_registration(cert)
            rp = reg["payload"]

            pick = st.selectbox("选用演示文件快速填入", ["—"] + list(quick), key="ver_quick_pick")
            up = st.file_uploader("或上传外部待验文件", key="ver_up")

            data, fname = None, None
            if up is not None:
                data, fname = up.getvalue(), up.name
            elif pick != "—":
                with open(quick[pick], "rb") as f:
                    data = f.read()
                fname = pick

            st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
            run_btn = st.button("开始验真", type="primary", use_container_width=True,
                                disabled=(data is None))
            if run_btn and data is not None:
                st.session_state["last_verify"] = do_verify(
                    ledger, packages, actors[VERIFIER_NAME], cert, fname, data)
                st.rerun()

            # 左翼底部: 母本登记信息底卡
            st.markdown(f"""
            <div class="sx-card sx-doc" style="margin-top:14px;padding:14px 18px">
              <div class="sx-label">登记母本信息基准</div>
              <div style="font-weight:700;font-size:15px;color:var(--ink)">{rp['filename']}</div>
              <div style="font-size:13px;color:var(--ink-2);margin-top:2px">主体：{rp['registrar']}</div>
              <div class="sx-mono-box" style="margin-top:8px">
                <div class="sx-label">登记 SHA-256</div>
                <div class="sx-mono" style="color:#0284C7;font-weight:600">{rp['exact']['sha256_root']}</div>
                <div class="sx-label" style="margin-top:6px">登记 SM3</div>
                <div class="sx-mono" style="color:#059669;font-weight:600">{rp['exact']['sm3_root']}</div>
                <div class="sx-label" style="margin-top:6px">登记语义根</div>
                <div class="sx-mono" style="color:#7C3AED;font-weight:600">{rp['semantic_root']}</div>
              </div>
            </div>""", unsafe_allow_html=True)

        with col_view:
            res = st.session_state.get("last_verify")
            if res and res["reg"] and res["reg"]["payload"]["cert_id"] == cert:
                report, comp = res["report"], res["comp"]
                sim = fp.text_similarity(rp_text(ledger, packages, cert), comp["text"])
                pkg = packages.get(cert)

                # 建议 1: 结论卡与玺印
                grade_hero(report, res["elapsed_ms"])

                # 丁级关键改动提示
                if report.get("grade") == "丁级":
                    _ds = diff_strip_html(report)
                    if _ds:
                        st.markdown(_ds, unsafe_allow_html=True)

                # 建议 3: 三层指纹核验矩阵 (硬核技术可视化 Layer Stack)
                st.markdown(layer_stack_html(rp, comp, report=report,
                                             reg_fields=pkg["fields"] if pkg else {},
                                             sim=sim),
                            unsafe_allow_html=True)

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
                        sim_txt = f"{sim:.4f}" if sim is not None else "不可用"
                        st.write(f"文本相似度（3-gram Jaccard）：{sim_txt}（阈值 ≥ 0.90）")
                        st.markdown("**第三层 · 语义字段**")
                        _ft = fields_table_html(pkg["fields"] if pkg else {},
                                                comp["fields"])
                        if _ft:
                            st.markdown(_ft, unsafe_allow_html=True)
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
                        st.markdown("**判定标定依据**")
                        st.write("本判定规则经合成语料 308 例盲测标定，四级判定准确率 "
                                 "95.13%，篡改检出率 100%（单哈希二值基线 50.65%）；"
                                 "又经真实法定披露文件验证，6 份定期报告摘要共 24 例，"
                                 "23 例与期望一致（基线 50%），未命中的 1 例已在验证"
                                 "报告中如实列明原因。")
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
                                mime="application/json",
                                use_container_width=True)
                        with c2:
                            if st.button("复核这份报告", use_container_width=True):
                                st.session_state["review_ok"] = svc.verify_report(
                                    ledger, report)
                        if "review_ok" in st.session_state:
                            if st.session_state.pop("review_ok"):
                                st.success("复核通过：报告未被篡改，且与账本回执一致。")
                            else:
                                st.error("复核不通过：报告与账本不一致。")

                    # 下载按钮矩阵
                    c_b1, c_b2 = st.columns(2)
                    with c_b1:
                        try:
                            _bundle = bundle_mod.build_bundle(ledger, packages, cert,
                                                              report=report)
                            st.download_button(
                                "下载独立证据包（JSON）",
                                json.dumps(_bundle, ensure_ascii=False, indent=1),
                                file_name=f"shuxi-bundle-{cert}.json",
                                mime="application/json",
                                use_container_width=True)
                        except ValueError:
                            pass
                    with c_b2:
                        try:
                            _pdf = report_pdf_mod.build_report_pdf(
                                ledger, packages, cert, report,
                                anchor_mod.latest_anchor_summary(ledger, DATA_DIR),
                                comp=comp)
                            st.download_button(
                                "下载验真报告 PDF（打印版）", _pdf,
                                file_name=f"shuxi-report-{cert}.pdf",
                                mime="application/pdf",
                                use_container_width=True)
                        except Exception:
                            st.caption("（PDF 报告生成不可用）")
            else:
                st.markdown("""
                <div class="sx-empty" style="padding:48px 24px">
                  <div style="font-family:var(--serif);font-size:18px;font-weight:700;color:var(--ink);margin-bottom:6px">
                    等待验真操作
                  </div>
                  <div>在左侧选择登记凭证并载入或上传待验文件，点击「开始验真」。</div>
                  <div style="margin-top:10px;font-size:13px;color:var(--ink-3)">
                    右翼将实时呈现：四级验真结论与玺印 · 三层指纹核验矩阵 · 字段级 Diff 与可追溯证据链
                  </div>
                </div>""", unsafe_allow_html=True)

    with tab_standalone:
        st.markdown('<div class="sx-sec">随手查 · 未登记文件初判</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="sx-sec-sub">不选凭证，任何文件先过一遍：'
                    '反查是否与已登记原件逐字节一致，再查内部勾稽。'
                    '初判不入账，不替代正式验真。</div>',
                    unsafe_allow_html=True)
        sa_c1, sa_c2 = st.columns([5, 7])
        with sa_c1:
            sa_up = st.file_uploader("上传任意待判文件", key="sa_up")
            sa_pick = st.selectbox("或选用演示文件", ["—"] + list(quick),
                                   key="sa_pick")
            sa_data, sa_name = None, None
            if sa_up is not None:
                sa_data, sa_name = sa_up.getvalue(), sa_up.name
            elif sa_pick != "—":
                with open(quick[sa_pick], "rb") as f:
                    sa_data = f.read()
                sa_name = sa_pick
            if sa_data is not None and st.button("开始初判", type="primary", use_container_width=True):
                try:
                    st.session_state["last_standalone"] = svc.standalone_check(
                        ledger, sa_data, ext_of(sa_name), sa_name)
                except ValueError as e:
                    st.error(str(e))
                st.rerun()

        with sa_c2:
            sa = st.session_state.get("last_standalone")
            if sa:
                grade_hero(sa["verdict"])
                _comp = sa["comp"]
                st.markdown(
                    f"<div class='sx-card sx-doc' style='padding:14px 18px'>"
                    f"<div class='sx-label'>独立提取特征</div>"
                    f"<div class='sx-mono'>"
                    f"<span class='sx-hash-tag'>SHA-256</span>{_comp['exact']['sha256_root']}<br>"
                    f"<span class='sx-hash-tag'>SM3</span>{_comp['exact']['sm3_root']}<br>"
                    f"抽出字段数：<b>{len(_comp['fields'])}</b> 个</div></div>",
                    unsafe_allow_html=True)
                if sa["matched_cert"]:
                    st.info(f"已自动定位母本凭证 {sa['matched_cert']}：可切回「单件精密验真」选好该凭证生成正式验真回执。")
            else:
                st.markdown('<div class="sx-empty">请在左侧上传文件以开始初判分析。</div>',
                            unsafe_allow_html=True)

    with tab_batch:
        st.markdown('<div class="sx-sec">批量验真</div>', unsafe_allow_html=True)
        st.markdown('<div class="sx-sec-sub">一次上传多份文件：按文件名自动匹配凭证，五十份也是一张表。</div>',
                    unsafe_allow_html=True)
        ups = st.file_uploader("批量上传待验文件", key="batch_up", accept_multiple_files=True)
        if ups and st.button("开始批量验真", type="primary"):
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


def anchor_pipeline_html(ledger, data_dir):
    """账本三阶时间锚定流水线 (建议 4: 时间锚定仪式感设计)。"""
    cps = ledger.by_type("checkpoint")
    has_cp = bool(cps)
    cp_seq = str(cps[-1]["seq"]) if has_cp else "—"

    # 外部锚定状态
    anch_status = "disabled"
    anch_desc = "离线保护模式"
    ots_proof = None
    if has_cp:
        cp_payload = cps[-1]["payload"]
        anch = cp_payload.get("anchor") or {}
        astore = anchor_mod.AnchorStore(os.path.join(data_dir, "anchors.json"))
        ots_proof = astore.get(cps[-1]["seq"]) or anch.get("ots_b64")
        if anch.get("type") == "opentimestamps" and ots_proof:
            pst = anchor_mod.proof_status(ots_proof)
            if pst["status"] == "bitcoin":
                anch_status = "bitcoin"
                anch_desc = f"比特币高度 #{pst['height']}"
            elif pst["status"] == "pending":
                anch_status = "pending"
                anch_desc = "已提交日历·待出块"
            else:
                anch_status = "error"
                anch_desc = "证明解析异常"
        elif anch.get("status") == "failed":
            anch_status = "failed"
            anch_desc = "日历提交未成功"
        elif anch.get("status") == "disabled":
            anch_status = "disabled"
            anch_desc = "已停用 (离线)"

    s1_badge = f'<span class="sx-layer-badge" style="color:#059669;background:rgba(5,150,105,.08);border-color:rgba(5,150,105,.3)">高度 {len(ledger.entries)}</span>'
    s2_color = "#059669" if has_cp else "#6B7280"
    s2_bg = "rgba(5,150,105,.08)" if has_cp else "#FAF8F3"
    s2_border = "rgba(5,150,105,.3)" if has_cp else "#DED8CA"
    s2_badge = f'<span class="sx-layer-badge" style="color:{s2_color};background:{s2_bg};border-color:{s2_border}">{"序号 #" + cp_seq if has_cp else "未封印"}</span>'

    if anch_status == "bitcoin":
        s3_color, s3_bg, s3_bd, s3_badge_txt = "#059669", "rgba(5,150,105,.08)", "rgba(5,150,105,.3)", anch_desc
    elif anch_status == "pending":
        s3_color, s3_bg, s3_bd, s3_badge_txt = "#D97706", "rgba(217,119,6,.08)", "rgba(217,119,6,.3)", anch_desc
    else:
        s3_color, s3_bg, s3_bd, s3_badge_txt = "#6B7280", "rgba(107,114,128,.08)", "rgba(107,114,128,.3)", anch_desc
    s3_badge = f'<span class="sx-layer-badge" style="color:{s3_color};background:{s3_bg};border-color:{s3_bd}">{s3_badge_txt}</span>'

    return f"""
    <div class="sx-pipeline">
      <!-- 阶段 I -->
      <div class="sx-pipe-step sx-pipe-active">
        <div class="sx-pipe-kicker"><span>阶段 I · 链上存证</span>{s1_badge}</div>
        <div class="sx-pipe-title">本地哈希链账本</div>
        <div class="sx-pipe-meta">SHA-256 前向链接 · 仅追加防篡改</div>
      </div>
      <div class="sx-pipe-arrow">──►</div>
      <!-- 阶段 II -->
      <div class="sx-pipe-step {'sx-pipe-active' if has_cp else ''}">
        <div class="sx-pipe-kicker"><span>阶段 II · 链头封印</span>{s2_badge}</div>
        <div class="sx-pipe-title">检查点定期锁止</div>
        <div class="sx-pipe-meta">登记方私钥数字签名 · 固化历史状态</div>
      </div>
      <div class="sx-pipe-arrow">──►</div>
      <!-- 阶段 III -->
      <div class="sx-pipe-step {'sx-pipe-active' if anch_status in ('bitcoin', 'pending') else ''}">
        <div class="sx-pipe-kicker"><span>阶段 III · 物理时间锚</span>{s3_badge}</div>
        <div class="sx-pipe-title">OpenTimestamps 外部锚定</div>
        <div class="sx-pipe-meta">全球公认区块链授时 · 抵御追溯倒签</div>
      </div>
    </div>
    """


# ---------------------------------------------------------------- 页面: 授权与账本

def page_ledger(ledger, packages, actors):
    st.markdown('<div class="sx-hero-title">授权与账本</div>', unsafe_allow_html=True)
    st.markdown('<div class="sx-sub">授权有期限、有次数，每次查验都留回执；账本全链可验，链头支持外部不可逆时间锚定。</div>',
                unsafe_allow_html=True)
    ok, broken, reason = ledger.verify_chain()
    head = ledger.head_hash()
    status_text = ('全链校验通过 · 零断裂零篡改' if ok else
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
                         ' · 最右为当前链头</span></div>')
    else:
        blocks_html = ''

    # 建议 4: 账本状态公文卡 + 三阶时间锚定流水线
    st.markdown(f"""
    <div class="sx-card sx-doc">
      <div class="sx-label">全链状态与不可逆时间锚定体系</div>
      <div class="sx-ledger-head">{status_text}</div>
      <div class="sx-mono" style="margin-top:6px">
        <span class="sx-hash-tag">账本高度</span>{n_entries}　
        <span class="sx-hash-tag">当前链头</span>{head}
      </div>
      {blocks_html}
      {hint_html}
      {anchor_pipeline_html(ledger, DATA_DIR)}
    </div>""", unsafe_allow_html=True)

    _cpf = st.session_state.pop("cp_flash", None)
    if _cpf:
        st.success(_cpf)

    c_btn1, c_btn2 = st.columns([6, 6])
    with c_btn1:
        if st.button("写入检查点（封印当前链头）", type="primary", use_container_width=True):
            with st.spinner("正在把链头哈希提交到公共时间戳日历…"):
                anch = anchor_mod.stamp_digest(ledger.head_hash())
            svc.checkpoint(ledger, actors[REGISTRAR_NAME], anchor=anch)
            if anch.get("status") == "pending":
                st.session_state["cp_flash"] = (
                    "检查点已入账，链头已提交 OpenTimestamps 公共日历"
                    "（待比特币网络确认）。")
            elif anch.get("status") == "failed":
                st.session_state["cp_flash"] = (
                    "检查点已入账。外部锚定提交失败，已如实标注未锚定。")
            else:
                st.session_state["cp_flash"] = "检查点已入账（外部锚定已停用）。"
            st.rerun()

    # 外部锚定状态 (最近一个检查点)
    _cps = ledger.by_type("checkpoint")
    if _cps:
        _cp = _cps[-1]
        _anch = (_cp["payload"].get("anchor") or {})
        _astore = anchor_mod.AnchorStore(os.path.join(DATA_DIR, "anchors.json"))
        _proof = _astore.get(_cp["seq"]) or _anch.get("ots_b64")
        if _anch.get("type") == "opentimestamps" and _proof:
            _pst = anchor_mod.proof_status(_proof)
            if _pst["status"] == "bitcoin":
                _atext = (f"外部锚定 · 已获比特币区块链确认（区块高度 "
                          f"{_pst['height']}），证明封存在检查点内，"
                          "任何人可独立核验。")
            elif _pst["status"] == "pending":
                _atext = ("外部锚定 · 链头已提交 OpenTimestamps 公共日历，"
                          "待比特币网络确认（通常数小时），证明封存在检查点内。")
            else:
                _atext = "外部锚定 · 证明文件解析异常。"
            st.markdown(f'<div class="sx-sub" style="margin-top:6px">{_atext}</div>',
                        unsafe_allow_html=True)
            _ac1, _ac2 = st.columns(2)
            with _ac1:
                if _pst["status"] == "pending" and st.button(
                        "刷新锚定状态", use_container_width=True):
                    _new, _changed = anchor_mod.upgrade_proof(_proof)
                    if _changed:
                        _astore.put(_cp["seq"], _new)
                        st.session_state["cp_flash"] = "锚定证明已更新。"
                    else:
                        st.session_state["cp_flash"] = (
                            "暂未查到比特币确认，稍后再刷新。")
                    st.rerun()
            with _ac2:
                st.download_button(
                    "下载 .ots 证明", data=base64.b64decode(_proof),
                    file_name=f"shuxi-checkpoint-{_cp['seq']}.ots",
                    use_container_width=True)
        elif _anch.get("status") == "failed":
            st.markdown('<div class="sx-sub" style="margin-top:6px">外部锚定 · 提交公共日历失败，'
                        '本检查点未锚定（已如实入账标注）。</div>',
                        unsafe_allow_html=True)
        elif _anch.get("status") == "disabled":
            st.markdown('<div class="sx-sub" style="margin-top:6px">外部锚定 · 已停用（离线模式），'
                        '本检查点未锚定。</div>', unsafe_allow_html=True)

    regs = registrations(ledger)
    labels = {f"{p['cert_id']} · {p['filename']}": p["cert_id"] for p in regs}

    # 左右双列并排: 新建授权 (6) + 作废与密钥公告 (6)
    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
    c_auth, c_rev = st.columns([6, 6])
    with c_auth:
        st.markdown('<div class="sx-sec" style="margin-top:0">新建授权</div>', unsafe_allow_html=True)
        st.markdown('<div class="sx-sec-sub">限期、限次、全程留痕，授权查验凭证。</div>',
                    unsafe_allow_html=True)
        if labels:
            with st.form("auth_form"):
                cert = labels[st.selectbox("凭证", list(labels))]
                grantee = st.text_input("被授权方", VERIFIER_NAME)
                c1, c2 = st.columns(2)
                days = c1.number_input("有效天数", 1, 365, 7)
                maxc = c2.number_input("最多查验次数", 1, 100, 2)
                if st.form_submit_button("创建授权", type="primary", use_container_width=True):
                    au = svc.create_authorization(
                        ledger, actors[REGISTRAR_NAME], cert, grantee,
                        actors[VERIFIER_NAME].fingerprint, int(days), int(maxc))
                    st.success(f"授权已入账：{au}")
                    st.rerun()
        else:
            st.markdown('<div class="sx-empty">暂无可授权的凭证。<br>'
                        '先到「登记」页登记一份文件，或在左侧一键载入演示数据。</div>',
                        unsafe_allow_html=True)

    with c_rev:
        st.markdown('<div class="sx-sec" style="margin-top:0">作废与密钥公告</div>', unsafe_allow_html=True)
        st.markdown('<div class="sx-sec-sub">登记方私钥数字签名，作废凭证不可逆入账。</div>',
                    unsafe_allow_html=True)
        if labels:
            cert = labels[st.selectbox("选择凭证", list(labels), key="revoke_cert")]
            state = svc.resolve_status(ledger, cert)
            st.caption(f"当前状态：{state['status']}"
                       + ("；".join(state["annotations"]) if state["annotations"] else ""))
            if st.button("作废这张凭证（登记方签名，不可逆）", use_container_width=True):
                svc.revoke(ledger, actors[REGISTRAR_NAME], cert)
                st.success("已作废并入账。")
                st.rerun()
        else:
            st.markdown('<div class="sx-empty">暂无可作废的凭证。</div>',
                        unsafe_allow_html=True)

    auths = ledger.by_type("authorization")
    if auths:
        st.markdown('<div class="sx-sec">已发放授权记录</div>', unsafe_allow_html=True)
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
    st.markdown('<div class="sx-sec">验真回执全账</div>', unsafe_allow_html=True)
    if receipts:
        rows = [{"回执": e["payload"]["receipt_id"], "凭证": e["payload"]["cert_id"],
                 "验真方": e["payload"]["verifier"], "结论": e["payload"]["grade"],
                 "时间": e["ts"]} for e in receipts]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.markdown('<div class="sx-empty">暂无回执。<br>'
                    '在「验真」页完成一次验真后，回执会自动入账到这里。</div>',
                    unsafe_allow_html=True)


# ---------------------------------------------------------------- 主入口

def main():
    st.set_page_config(page_title="数玺", page_icon="玺", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    # 状态条下钻: ?goto= 链接落点 (须在导航单选实例化之前处理)
    _goto = st.query_params.get("goto")
    if _goto:
        if isinstance(_goto, list):
            _goto = _goto[0] if _goto else None
        _target = {"ledger": "授权与账本", "register": "登记",
                   "receipts": "授权与账本", "chain": "授权与账本"}.get(_goto)
        if _target:
            st.session_state["nav_page"] = _target
        try:
            del st.query_params["goto"]
        except Exception:
            pass
    if st.session_state.pop("tour_goto", False):
        # 导览按钮在侧栏 (单选已实例化) 里改不了 nav_page, 用标志在此消费
        st.session_state["nav_page"] = "登记"
    ledger, packages, actors = init_stores(DATA_DIR)
    if st.session_state.pop("do_seed_after_reset", False):
        # 演示重置后半程: 账本刚清空重建, 在此补齐演示三件套并给出提示
        try:
            _certs = seed_demo(ledger, packages, actors[REGISTRAR_NAME])
            st.session_state["seed_flash"] = (
                "success", f"演示已重置：账本清空，{len(_certs)} 张演示凭证已重新载入")
        except Exception as e:
            st.session_state["seed_flash"] = (
                "error", f"账本已清空，但演示数据重载失败：{e}。请点一键载入演示数据重试。")
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
""",
                    unsafe_allow_html=True)
        page = st.radio("导航", ["登记", "验真", "授权与账本"], key="nav_page")
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
        if st.button("评委导览 · 一键连跑", type="primary"):
            try:
                st.session_state["tour"] = run_tour(ledger, packages, actors)
                st.session_state["tour_goto"] = True
            except Exception as e:
                st.session_state["seed_flash"] = (
                    "error", f"导览运行失败：{e}。请把这条提示截图发给维护者。")
            st.rerun()
        _armed = st.session_state.get("reset_armed", False)
        if st.button("确认重置（清空账本）" if _armed else "重置演示数据"):
            if not _armed:
                st.session_state["reset_armed"] = True
            else:
                st.session_state["reset_armed"] = False
                try:
                    wipe_data_dir(DATA_DIR)
                except Exception as e:
                    st.session_state["seed_flash"] = ("error", f"重置失败：{e}")
                else:
                    st.session_state.clear()
                    st.session_state["do_seed_after_reset"] = True
            st.rerun()
        if _armed:
            st.warning("将清空当前账本的全部记录（登记、验真回执、授权、检查点），"
                       "回到初始演示状态。再点一次按钮确认重置。")
        st.markdown(f"""
        <div class="sx-side-card">
          <div class="sx-sc-label">演示说明</div>
          <div class="sx-actor"><span>登记方</span>{REGISTRAR_NAME}</div>
          <div class="sx-actor"><span>验真方</span>{VERIFIER_NAME}</div>
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
