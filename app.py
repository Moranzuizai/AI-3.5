import streamlit as st
import pandas as pd
import os
import json
import datetime
import streamlit.components.v1 as components

# ==========================================
# BLOCK 1: 基础配置 (事项 2)
# ==========================================
CONFIG_FILE = "config_v2.json"
def load_config():
    defaults = {"admin_password": "199266", "user_password": "a123456", "app_title": "AI课堂教学数据分析工具"}
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f: json.dump(defaults, f)
        return defaults
    with open(CONFIG_FILE, 'r') as f: return json.load(f)

conf = load_config()
st.set_page_config(page_title=conf["app_title"], layout="wide")

# ==========================================
# BLOCK 3: 数据处理大脑 (事项 1 - 维度扩容)
# ==========================================
def process_full_dimensions(df):
    try:
        # 1. 基础清洗
        df['周'] = pd.to_datetime(df['周'], errors='coerce')
        df = df.dropna(subset=['周']).fillna(0)
        
        # 2. 核心字段名匹配（确保兼容用户Excel）
        col_t_assign = "老师布置课时总时长（分钟）"
        col_s_watch = "学生观看AI课堂课时微课总时长(分钟)"
        
        all_weeks = sorted(df['周'].unique())
        target_week = all_weeks[-1]
        prev_week = all_weeks[-2] if len(all_weeks) > 1 else None
        
        # 3. 本周数据切片
        curr_df = df[df['周'] == target_week]
        m_curr = {
            'hours': int(curr_df['课时数'].sum()), 
            'att': curr_df['课时平均出勤率'].mean(), 
            'corr': curr_df['题目正确率（自学+快背）'].mean(),
            't_assign_sum': int(curr_df[col_t_assign].sum()), # 新增：老师布置总时长
            's_watch_sum': int(curr_df[col_s_watch].sum())    # 新增：学生观看总时长
        }
        
        # 4. 标杆与关注逻辑
        class_group = curr_df.groupby('班级名称').agg({
            '课时平均出勤率':'mean', 
            col_t_assign:'sum', 
            col_s_watch:'sum'
        }).reset_index()
        best_row = class_group.sort_values('课时平均出勤率', ascending=False).iloc[0]
        best_html = f'<div class="highlight-box success-box">🏆 <b>本周标杆班级:</b> {best_row["班级名称"]} (出勤率 {best_row["课时平均出勤率"]*100:.1f}%)</div>'

        # 5. 详细数据表格 (增加两列)
        table_rows = ""
        avg_att = m_curr['att']
        for _, row in curr_df.iterrows():
            att_style = "class='alert'" if row['课时平均出勤率'] < avg_att else ""
            table_rows += f"""
            <tr>
                <td>{row['班级名称']}</td>
                <td>{row['课时数']}</td>
                <td {att_style}>{row['课时平均出勤率']*100:.1f}%</td>
                <td>{int(row[col_t_assign])}</td>
                <td>{int(row[col_s_watch])}</td>
            </tr>"""
        tables_html = f"""
        <table>
            <thead><tr><th>班级</th><th>课时</th><th>出勤率</th><th>老师布置(分)</th><th>学生观看(分)</th></tr></thead>
            <tbody>{table_rows}</tbody>
        </table>"""

        # 6. 趋势数据 (增加时长维度趋势)
        trend = df.groupby('周').agg({
            '课时数':'sum', 
            '课时平均出勤率':'mean', 
            col_t_assign:'mean', 
            col_s_watch:'mean'
        }).reset_index()
        
        return {
            "target_week": target_week.strftime('%Y-%m-%d'),
            "m_curr": m_curr,
            "best_html": best_html, 
            "tables_html": tables_html,
            "c_cats": class_group['班级名称'].tolist(), 
            "c_hours": curr_df.groupby('班级名称')['课时数'].sum().tolist(),
            "c_att": (class_group['课时平均出勤率']*100).round(1).tolist(),
            "t_dates": trend['周'].dt.strftime('%m-%d').tolist(), 
            "t_hours": trend['课时数'].tolist(),
            "t_att": (trend['课时平均出勤率']*100).round(1).tolist(),
            "t_assign_avg": trend[col_t_assign].round(1).tolist(), # 新增趋势
            "t_watch_avg": trend[col_s_watch].round(1).tolist()    # 新增趋势
        }
    except Exception as e:
        st.error(f"数据处理失败，请确保Excel包含'老师布置课时总时长（分钟）'等列。错误: {e}"); return None

# ==========================================
# BLOCK 4: HTML 报表生成 (事项 3 - 零删减 + 维度扩容)
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
        .highlight-box {{ padding: 15px; margin: 10px 0; border-radius: 5px; font-size: 14px; }}
        .success-box {{ background: #d4edda; color: #155724; border-left: 5px solid #28a745; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }}
        th {{ background: #eee; padding: 10px; border-bottom: 2px solid #ddd; }} 
        td {{ padding: 10px; border-bottom: 1px solid #eee; text-align: center; }}
        .alert {{ color: #e74c3c; font-weight: bold; }}
        .chart {{ height: 400px; width: 100%; }}
        .footer {{ text-align:center; color:#999; font-size:12px; margin-top:20px; }}
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
            {d['best_html']}
        </div>

        <div class="card"><h3>📊 维度 2：班级效能分析</h3><div id="c1" class="chart"></div></div>
        
        <div class="card"><h3>📊 维度 3：详细数据明细</h3>
            <p style="text-align:right;color:#999;font-size:11px">* 出勤率红色表示低于均值</p>
            {d['tables_html']}
        </div>
        
        <div class="card"><h3>📊 维度 4：历史趋势 - 课时与出勤</h3><div id="c2" class="chart"></div></div>
        
        <div class="card"><h3>📊 维度 5：历史趋势 - 布置与观看时长(周平均)</h3><div id="c3" class="chart"></div></div>

        <script>
            var c1 = echarts.init(document.getElementById('c1'));
            c1.setOption({{
                tooltip: {{trigger:'axis'}}, legend: {{bottom:0}},
                xAxis: {{type:'category', data:{json.dumps(d['c_cats'])} }},
                yAxis: [{{type:'value', name:'课时'}}, {{type:'value', name:'%', max:100}}],
                series: [
                    {{type:'bar', name:'课时', data:{json.dumps(d['c_hours'])} }},
                    {{type:'line', yAxisIndex:1, name:'出勤率', data:{json.dumps(d['c_att'])} }}
                ]
            }});

            var c2 = echarts.init(document.getElementById('c2'));
            c2.setOption({{
                tooltip: {{trigger:'axis'}}, legend: {{bottom:0}},
                xAxis: {{type:'category', data:{json.dumps(d['t_dates'])} }},
                yAxis: [{{type:'value', name:'总课时'}}, {{type:'value', name:'%', max:100}}],
                series: [
                    {{type:'bar', name:'总课时', data:{json.dumps(d['t_hours'])}, itemStyle:{{color:'#9b59b6'}} }},
                    {{type:'line', yAxisIndex:1, name:'平均出勤', data:{json.dumps(d['t_att'])}, itemStyle:{{color:'#2ecc71'}} }}
                ]
            }});

            var c3 = echarts.init(document.getElementById('c3'));
            c3.setOption({{
                tooltip: {{trigger:'axis'}}, legend: {{bottom:0}},
                xAxis: {{type:'category', data:{json.dumps(d['t_dates'])} }},
                yAxis: [{{type:'value', name:'老师布置(分)'}}, {{type:'value', name:'学生观看(分)'}}],
                series: [
                    {{type:'line', name:'老师布置', data:{json.dumps(d['t_assign_avg'])}, itemStyle:{{color:'#3498db'}}, smooth:true }},
                    {{type:'line', yAxisIndex:1, name:'学生观看', data:{json.dumps(d['t_watch_avg'])}, itemStyle:{{color:'#e67e22'}}, smooth:true }}
                ]
            }});
        </script>
    </body></html>
    """
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
