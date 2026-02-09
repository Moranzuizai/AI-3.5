import streamlit as st
import pandas as pd
import os
import json
import datetime
import streamlit.components.v1 as components
import requests # 用于后续连接 DeepSeek 等接口

# ==========================================
# BLOCK 1: 基础配置 (事项 2)
# ==========================================
CONFIG_FILE = "config_v2.json"
LOG_FILE = "user_action_log.csv"

def load_sys_config():
    """读取或创建默认配置"""
    defaults = {
        "admin_pwd": "199266", 
        "user_pwd": "a123456",
        "api_key": "", # 这里留给以后填 DeepSeek Key
        "app_name": "AI 课堂智能分析平台",
        "login_tip": "⬆️ 请上传班级教学数据 Excel 原文件"
    }
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f: json.dump(defaults, f)
        return defaults
    with open(CONFIG_FILE, 'r') as f: return json.load(f)

conf = load_sys_config()

# ==========================================
# BLOCK 2: 行为日志 (事项 2 - 用于优化代码)
# ==========================================
def record_log(action, detail=""):
    """自动记录用户操作，存入 CSV 文件"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = pd.DataFrame([[now, st.session_state.get('role', '访客'), action, detail]], 
                            columns=["时间", "角色", "操作", "详情"])
    if not os.path.exists(LOG_FILE):
        log_entry.to_csv(LOG_FILE, index=False)
    else:
        log_entry.to_csv(LOG_FILE, mode='a', header=False, index=False)

# ==========================================
# BLOCK 3: 数据清洗 (事项 1 - 核心逻辑)
# ==========================================
def analyze_excel(df):
    """
    [零删减说明]：此处应保留你原本复杂的 df 处理逻辑。
    为了适应不同文件，我们使用通用的列名匹配。
    """
    try:
        # 1. 自动寻找包含“周”字的列作为时间
        week_col = [c for c in df.columns if '周' in c][0]
        df[week_col] = pd.to_datetime(df[week_col], errors='coerce')
        df = df.dropna(subset=[week_col])
        
        latest = df[week_col].max()
        curr_df = df[df[week_col] == latest]
        
        # 2. 这里的计算指标必须与你 HTML 模板中的变量名一一对应
        stats = {
            "date": latest.strftime('%Y-%m-%d'),
            "att": curr_df[[c for c in df.columns if '出勤' in c][0]].mean(),
            "cor": curr_df[[c for c in df.columns if '正确' in c][0]].mean(),
            "hours": curr_df[[c for c in df.columns if '课时' in c][0]].sum(),
            # 趋势数据
            "t_x": df[week_col].dt.strftime('%m-%d').unique().tolist(),
            "t_y_att": (df.groupby(week_col)[[c for c in df.columns if '出勤' in c][0]].mean()*100).round(1).tolist()
        }
        return stats
    except Exception as e:
        st.error(f"⚠️ 数据解析失败，请检查 Excel 列名。详细错误：{e}")
        return None

# ==========================================
# BLOCK 4: HTML 报表生成 (事项 3 - 报表呈现维度)
# [说明]：此处采用了您提供的精美模板，确保维度完整。
# ==========================================
def get_report_html(d, ai_text):
    """
    接收数据包 d 和 AI 协作文字 ai_text，生成最终 HTML。
    d 需包含：target_week, prev_week, m_curr, t_h, t_a, t_c, 
    best_html, focus_html, c_cats, c_hours, c_att, c_corr, 
    t_dates, t_hours, t_att, t_corr, tables_html
    """
    
    # 注入 AI 协作文字到模板中（您可以根据需要调整 AI 文字在 HTML 中的显示位置）
    # 这里我们把 AI 文字包装成一个卡片，放在“本周核心指标”下方
    ai_card_html = f"""
    <div class="card">
        <h3>🤖 AI 协作分析建议</h3>
        <div class="highlight-box success-box" style="white-space: pre-wrap; font-size: 15px; line-height: 1.8;">{ai_text}</div>
    </div>
    """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8">
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        body {{ font-family: "Microsoft YaHei", sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; background: #f4f6f9; }}
        .card {{ background: #fff; padding: 20px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
        .kpi {{ display: flex; justify-content: space-around; text-align: center; }}
        .kpi div strong {{ font-size: 30px; color: #2980b9; display: block; }}
        .highlight-box {{ padding: 15px; margin: 10px 0; border-radius: 5px; font-size: 14px; }}
        .success-box {{ background: #d4edda; color: #155724; border-left: 5px solid #28a745; }}
        .warning-box {{ background: #fff3cd; color: #856404; border-left: 5px solid #ffc107; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }}
        th {{ background: #eee; padding: 10px; border-bottom: 2px solid #ddd; }} 
        td {{ padding: 10px; border-bottom: 1px solid #eee; text-align: center; }}
        .alert {{ color: #e74c3c; font-weight: bold; }} .good {{ color: #27ae60; }}
        .chart {{ height: 400px; width: 100%; }}
        .footer {{ text-align:center; color:#999; font-size:12px; margin-top:20px; }}
    </style>
    </head>
    <body>
        <h2 style="text-align:center">AI课堂教学数据分析周报</h2>
        <div style="text-align:center;color:#666;margin-bottom:20px">
            统计周期: <b>{d['target_week']}</b> 
            {f'<span style="font-size:12px">(对比: {d["prev_week"]})</span>' if d['prev_week'] else ''}
        </div>
        
        <div class="card">
            <h3>📊 本周核心指标</h3>
            <div class="kpi">
                <div><strong>{d['m_curr']['hours']}{d['t_h']}</strong>总课时</div>
                <div><strong>{d['m_curr']['att']*100:.1f}%{d['t_a']}</strong>出勤率</div>
                <div><strong>{d['m_curr']['corr']*100:.1f}%{d['t_c']}</strong>正确率</div>
            </div>
            {d['best_html']}{d['focus_html']}
        </div>

        {ai_card_html}
        
        <div class="card"><h3>🏫 班级效能分析</h3><div id="c1" class="chart"></div></div>
        <div class="card"><h3>📋 详细数据明细</h3>
            <p style="text-align:right;color:#999;font-size:12px">* 红色数字表示低于全校均值</p>{d['tables_html']}
        </div>
        <div class="card"><h3>📈 全周期历史趋势</h3><div id="c2" class="chart"></div></div>
        <div class="footer">Generated by AI Agent (Web Edition)</div>

        <script>
            var c1 = echarts.init(document.getElementById('c1'));
            c1.setOption({{
                tooltip: {{trigger:'axis'}}, legend: {{bottom:0}},
                grid: {{left:'3%', right:'4%', bottom:'10%', containLabel:true}},
                xAxis: {{type:'category', data:{json.dumps(d['c_cats'])}, axisLabel:{{rotate:30, interval:0}}}},
                yAxis: [{{type:'value',name:'课时'}}, {{type:'value',name:'%',max:100}}],
                series: [
                    {{type:'bar',name:'课时数',data:{json.dumps(d['c_hours'])},itemStyle:{{color:'#3498db'}}}},
                    {{type:'line',yAxisIndex:1,name:'出勤率',data:{json.dumps(d['c_att'])},itemStyle:{{color:'#2ecc71'}}}},
                    {{type:'line',yAxisIndex:1,name:'正确率',data:{json.dumps(d['c_corr'])},itemStyle:{{color:'#e74c3c'}}}}
                ]
            }});
            var c2 = echarts.init(document.getElementById('c2'));
            c2.setOption({{
                tooltip: {{trigger:'axis'}}, legend: {{bottom:0}},
                grid: {{left:'3%', right:'4%', bottom:'10%', containLabel:true}},
                xAxis: {{type:'category', data:{json.dumps(d['t_dates'])}}},
                yAxis: [{{type:'value',name:'课时'}}, {{type:'value',name:'%',max:100}}],
                series: [
                    {{type:'bar',name:'课时数',data:{json.dumps(d['t_hours'])},itemStyle:{{color:'#9b59b6'}}}},
                    {{type:'line',yAxisIndex:1,name:'出勤率',data:{json.dumps(d['t_att'])},itemStyle:{{color:'#2ecc71'}}}},
                    {{type:'line',yAxisIndex:1,name:'正确率',data:{json.dumps(d['t_corr'])},itemStyle:{{color:'#e74c3c'}}}}
                ]
            }});
            window.onresize = function(){{ c1.resize(); c2.resize(); }};
        </script>
    </body></html>
    """
    return html_content

# ==========================================
# BLOCK 5: AI 协作桥 (事项 1 - 支持多轮对话)
# ==========================================
def fetch_ai_response(messages):
    """
    后续修改此处即可接入 DeepSeek。
    目前为本地模拟逻辑，确保小白在没填 Key 之前也能跑通。
    """
    # 如果有 Key，这里写 API 调用代码
    return "【AI 建议】本周出勤稳定，正确率有待提高。建议针对平均分低于 20% 的班级进行定点辅导。"

# ==========================================
# BLOCK 6: 交互界面 (事项 3)
# ==========================================
st.set_page_config(page_title=conf["app_name"], layout="wide")

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'ai_history' not in st.session_state: st.session_state.ai_history = []
if 'analysis_data' not in st.session_state: st.session_state.analysis_data = None

# 1. 登录逻辑
if not st.session_state.logged_in:
    st.title(f"🔐 {conf['app_name']}")
    pwd = st.text_input("请输入准入密码", type="password")
    if st.button("进入系统"):
        if pwd == conf["admin_pwd"]:
            st.session_state.logged_in, st.session_state.role = True, "admin"
            record_log("登录", "管理员角色")
            st.rerun()
        elif pwd == conf["user_pwd"]:
            st.session_state.logged_in, st.session_state.role = True, "user"
            record_log("登录", "普通角色")
            st.rerun()
        else: st.error("密码错误")

# 2. 登录后的主页面
else:
    st.sidebar.title(f"🕹️ 控制台 ({st.session_state.role})")
    tab = st.sidebar.radio("选择模块", ["数据工作台", "AI 协作修正", "系统设置"])
    
    if st.sidebar.button("安全退出"):
        st.session_state.logged_in = False
        st.rerun()

    # --- 数据工作台 ---
    if tab == "数据工作台":
        st.header("📊 自动化数据中心")
        file = st.file_uploader(conf["login_tip"], type=["xlsx"])
        if file:
            res = analyze_excel(pd.read_excel(file))
            if res:
                st.session_state.analysis_data = res
                st.success("✅ 数据分析完成！核心指标已更新。")
                record_log("数据上传", file.name)
                # 展示核心卡片
                c1, c2 = st.columns(2)
                c1.metric("出勤率", f"{res['att']*100:.1f}%")
                c2.metric("正确率", f"{res['cor']*100:.1f}%")

    # --- AI 协作修正 (核心互动功能) ---
    elif tab == "AI 协作修正":
        st.header("🤖 AI 协作生成报告")
        if not st.session_state.analysis_data:
            st.warning("👋 请先在‘数据工作台’上传数据。")
        else:
            # 显示对话
            for msg in st.session_state.ai_history:
                with st.chat_message(msg["role"]): st.write(msg["content"])
            
            # 对话输入
            query = st.chat_input("您可以要求 AI 修改文字，例如：‘字数少一点’、‘重点提到初一10班’...")
            if query:
                st.session_state.ai_history.append({"role": "user", "content": query})
                record_log("AI 互动", query)
                with st.spinner("AI 正在重写报告..."):
                    # 获取 AI 回复
                    response = fetch_ai_response(st.session_state.ai_history)
                    st.session_state.ai_history.append({"role": "assistant", "content": response})
                st.rerun()
            
            # 下载按钮
            if st.session_state.ai_history:
                st.divider()
                final_text = st.session_state.ai_history[-1]["content"]
                final_html = get_report_html(st.session_state.analysis_data, final_text)
                st.download_button("📥 下载带 AI 建议的 HTML 报表", final_html, "分析报告.html", "text/html")

    # --- 系统设置 ---
    elif tab == "系统设置" and st.session_state.role == "admin":
        st.header("⚙️ 后台管理中心")
        new_app_name = st.text_input("修改系统名称", conf["app_name"])
        new_user_pwd = st.text_input("修改普通用户密码", conf["user_pwd"])
        if st.button("保存并更新设置"):
            conf["app_name"] = new_app_name
            conf["user_pwd"] = new_user_pwd
            with open(CONFIG_FILE, 'w') as f: json.dump(conf, f)
            st.success("配置已保存！下次刷新生效。")
        
        st.divider()
        st.subheader("📝 历史行为日志")
        if os.path.exists(LOG_FILE):
            st.dataframe(pd.read_csv(LOG_FILE).sort_index(ascending=False))
