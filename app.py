import streamlit as st
import pandas as pd
import os
import json
import datetime
import streamlit.components.v1 as components

# ==========================================
# BLOCK 1: 基础配置 (事项 2)
# ==========================================
# ==========================================
# BLOCK 1: 基础配置 (事项 2 - 增强修复版)
# ==========================================
CONFIG_FILE = "config_v2.json"

def load_config():
    """读取配置文件，并自动补全缺失的标签"""
    defaults = {
        "admin_password": "199266", 
        "user_password": "a123456",
        "app_title": "AI课堂教学数据分析工具",  # 报错就是因为旧文件缺这一行
        "upload_hint": "⬆️ 请上传班级教学数据 Excel 原文件"
    }
    
    # 如果文件不存在，直接创建默认的
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(defaults, f, ensure_ascii=False)
        return defaults

    # 如果文件存在，我们要读取它，并检查是否少了新标签
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            current_conf = json.load(f)
        
        # 【核心修复逻辑】：如果旧文件少了某个标签（比如 app_title），自动补上去
        updated = False
        for key, value in defaults.items():
            if key not in current_conf:
                current_conf[key] = value
                updated = True
        
        # 如果补了新标签，把新的存回去，下次就不会报错了
        if updated:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(current_conf, f, ensure_ascii=False)
        
        return current_conf
    except:
        # 如果文件损坏了，直接返回默认值，确保不崩溃
        return defaults

conf = load_config()

# 这一行就是之前报错的地方，现在我们确保 conf 里面一定有 "app_title" 了
st.set_page_config(page_title=conf.get("app_title", "教学分析工具"), layout="wide")

# ==========================================
# BLOCK 3: 数据处理大脑 (事项 1 - 深度逻辑修复)
# ==========================================
import re

def natural_sort_key(s):
    """自定义排序：处理‘七八九’汉字与数字混合排序"""
    char_map = {'七': 7, '八': 8, '九': 9, '十': 10}
    # 优先提取年级汉字
    for char, val in char_map.items():
        if char in s: return (val, [int(text) if text.isdigit() else text for text in re.split('([0-9]+)', s)])
    return (99, [int(text) if text.isdigit() else text for text in re.split('([0-9]+)', s)])

def process_full_dimensions(df):
    try:
        df['周'] = pd.to_datetime(df['周'], errors='coerce')
        df = df.dropna(subset=['周']).fillna(0)
        
        # 字段兼容性定义
        col_t = "老师布置课时总时长（分钟）"
        col_s = "学生观看AI课堂课时微课总时长(分钟)"
        col_comp = "微课完成率" # 补全完课率
        
        for col in [col_t, col_s, col_comp]:
            if col not in df.columns: df[col] = 0

        all_weeks = sorted(df['周'].unique())
        target_week = all_weeks[-1]
        curr_df = df[df['周'] == target_week].copy()
        
        # --- KPI核算 ---
        m_curr = {
            'hours': int(curr_df['课时数'].sum()), 
            'att': curr_df['课时平均出勤率'].mean(), 
            'corr': curr_df['题目正确率（自学+快背）'].mean(),
            't_assign_sum': int(curr_df[col_t].sum()), 
            's_watch_sum': int(curr_df[col_s].sum())
        }
        
        # --- 维度 2 & 3：班级效能（含汉字数字混合排序） ---
        class_stats = curr_df.groupby('班级名称').agg({
            '课时数':'sum', '课时平均出勤率':'mean', 
            '题目正确率（自学+快背）':'mean', col_t:'sum', col_s:'sum'
        }).reset_index()
        
        # 维度 2 的排序：年级汉字+班级数字
        class_stats['sort_key'] = class_stats['班级名称'].apply(natural_sort_key)
        c_stats_sorted_by_name = class_stats.sort_values('sort_key')
        
        # 维度 3 的排序：课时数从大到小
        c_stats_sorted_by_hours = class_stats.sort_values('课时数', ascending=False)

        # --- 生成维度 3 表格 HTML ---
        table_rows = ""
        avg_att = m_curr['att']
        for _, row in c_stats_sorted_by_hours.iterrows():
            style = "style='color:red;font-weight:bold;'" if row['课时平均出勤率'] < avg_att else ""
            table_rows += f"<tr><td>{row['班级名称']}</td><td>{row['课时数']}</td><td {style}>{row['课时平均出勤率']*100:.1f}%</td><td>{int(row[col_t])}</td><td>{int(row[col_s])}</td></tr>"

        # --- 历史趋势聚合 ---
        trend = df.groupby('周').agg({
            '课时数':'sum', '课时平均出勤率':'mean', 
            '题目正确率（自学+快背）':'mean', col_comp:'mean',
            col_t:'sum', col_s:'sum' # 维度 5 改为合计
        }).reset_index()
        
        return {
            "target_week": target_week.strftime('%Y-%m-%d'),
            "m_curr": m_curr, "tables_html": table_rows,
            "c_cats": c_stats_sorted_by_name['班级名称'].tolist(), 
            "c_hours": c_stats_sorted_by_name['课时数'].tolist(),
            "c_att": (c_stats_sorted_by_name['课时平均出勤率']*100).round(1).tolist(),
            "c_corr": (c_stats_sorted_by_name['题目正确率（自学+快背）']*100).round(1).tolist(),
            "t_dates": trend['周'].dt.strftime('%m-%d').tolist(), 
            "t_hours": trend['课时数'].tolist(),
            "t_att": (trend['课时平均出勤率']*100).round(1).tolist(),
            "t_corr": (trend['题目正确率（自学+快背）']*100).round(1).tolist(),
            "t_comp": (trend[col_comp]*100).round(1).tolist(),
            "t_assign_sum": trend[col_t].tolist(),
            "t_watch_sum": trend[col_s].tolist()
        }
    except Exception as e:
        st.error(f"分析逻辑出错: {e}"); return None

# ==========================================
# BLOCK 4: HTML 报表生成 (事项 3 - 维度补全)
# ==========================================
def get_full_report_html(d):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8">
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        body {{ font-family: "Microsoft YaHei", sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; background: #f4f6f9; }}
        .card {{ background: #fff; padding: 20px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
        .kpi {{ display: flex; justify-content: space-around; text-align: center; flex-wrap: wrap; }}
        .kpi div {{ min-width: 200px; margin: 10px 0; }}
        .kpi div strong {{ font-size: 28px; color: #2980b9; display: block; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }}
        th {{ background: #eee; padding: 10px; border-bottom: 2px solid #ddd; }} 
        td {{ padding: 10px; border-bottom: 1px solid #eee; text-align: center; }}
        .chart {{ height: 420px; width: 100%; }}
    </style>
    </head>
    <body>
        <h2 style="text-align:center">AI课堂教学数据分析周报</h2>
        <div style="text-align:center;color:#666;margin-bottom:20px">统计周期: <b>{d['target_week']}</b></div>
        
        <div class="card">
            <h3>📊 维度 1：本周核心指标</h3>
            <div class="kpi">
                <div><strong>{d['m_curr']['hours']}</strong>总课时</div>
                <div><strong>{d['m_curr']['att']*100:.1f}%</strong>平均出勤率</div>
                <div><strong>{d['m_curr']['t_assign_sum']}</strong>老师布置总时长(分)</div>
                <div><strong>{d['m_curr']['s_watch_sum']}</strong>学生观看总时长(分)</div>
            </div>
        </div>

        <div class="card"><h3>📊 维度 2：班级效能分析 (班级序)</h3><div id="c1" class="chart"></div></div>
        
        <div class="card"><h3>📊 维度 3：本周详细数据 (按课时排序)</h3>
            {d['tables_html']}
        </div>
        
        <div class="card"><h3>📊 维度 4：全周期历史趋势 (课时/出勤/正确/完课)</h3><div id="c2" class="chart"></div></div>
        
        <div class="card"><h3>📊 维度 5：历史趋势 - 老师布置时长与观看时长</h3><div id="c3" class="chart"></div></div>

        <script>
            var c1 = echarts.init(document.getElementById('c1'));
            c1.setOption({{
                tooltip: {{trigger:'axis'}}, legend: {{bottom:0}},
                xAxis: {{type:'category', data:{json.dumps(d['c_cats'])}, axisLabel:{{rotate:30, interval:0}} }},
                yAxis: [{{type:'value', name:'课时'}}, {{type:'value', name:'%', max:100}}],
                series: [
                    {{type:'bar', name:'课时', data:{json.dumps(d['c_hours'])}, itemStyle:{{color:'#3498db'}} }},
                    {{type:'line', yAxisIndex:1, name:'出勤率', data:{json.dumps(d['c_att'])}, itemStyle:{{color:'#2ecc71'}} }},
                    {{type:'line', yAxisIndex:1, name:'正确率', data:{json.dumps(d['c_corr'])}, itemStyle:{{color:'#e74c3c'}} }}
                ]
            }});

            var c2 = echarts.init(document.getElementById('c2'));
            c2.setOption({{
                tooltip: {{trigger:'axis'}}, legend: {{bottom:0}},
                xAxis: {{type:'category', data:{json.dumps(d['t_dates'])} }},
                yAxis: [{{type:'value', name:'总课时'}}, {{type:'value', name:'%', max:100}}],
                series: [
                    {{type:'bar', name:'总课时', data:{json.dumps(d['t_hours'])}, itemStyle:{{color:'#9b59b6'}} }},
                    {{type:'line', yAxisIndex:1, name:'平均出勤', data:{json.dumps(d['t_att'])}, itemStyle:{{color:'#2ecc71'}} }},
                    {{type:'line', yAxisIndex:1, name:'正确率', data:{json.dumps(d['t_corr'])}, itemStyle:{{color:'#e74c3c'}} }},
                    {{type:'line', yAxisIndex:1, name:'完课率', data:{json.dumps(d['t_comp'])}, itemStyle:{{color:'#f1c40f'}} }}
                ]
            }});

            var c3 = echarts.init(document.getElementById('c3'));
            c3.setOption({{
                tooltip: {{trigger:'axis'}}, legend: {{bottom:0}},
                xAxis: {{type:'category', data:{json.dumps(d['t_dates'])} }},
                yAxis: {{type:'value', name:'合计时长(分钟)'}},
                series: [
                    {{type:'line', name:'老师布置合计', data:{json.dumps(d['t_assign_sum'])}, itemStyle:{{color:'#3498db'}}, smooth:true }},
                    {{type:'line', name:'学生观看合计', data:{json.dumps(d['t_watch_sum'])}, itemStyle:{{color:'#e67e22'}}, smooth:true }}
                ]
            }});
        </script>
    </body></html>
    \"\"\"
    return html

# ==========================================
# BLOCK 6: 交互界面 (事项 3 - 登录增强)
# ==========================================
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

if not st.session_state.logged_in:
    # 事项 3：增加软件名称显示
    st.markdown(f"<h1 style='text-align: center; color: #2c3e50;'>{conf['app_title']}</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #7f8c8d;'>智慧教学数据闭环管理系统</p>", unsafe_allow_html=True)
    
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.write("---")
            pwd = st.text_input("🔑 请输入系统准入密码", type="password")
            if st.button("立即进入系统", use_container_width=True):
                if pwd == conf["admin_password"] or pwd == conf["user_password"]:
                    st.session_state.logged_in = True; st.rerun()
                else: st.error("❌ 密码验证失败，请重新输入")
else:
    st.sidebar.title("🚀 数据中心")
    file = st.file_uploader("导入 Excel 文件", type=["xlsx"])
    if file:
        data_packet = process_full_dimensions(pd.read_excel(file))
        if data_packet:
            full_html = get_full_report_html(data_packet)
            st.download_button("📥 下载完整版 HTML 报表", full_html, "完整教学分析报告.html", "text/html")
            st.subheader("👁️ 实时预览")
            components.html(full_html, height=1200, scrolling=True)
