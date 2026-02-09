import streamlit as st
import pandas as pd
import os
import re
import json
import datetime
import streamlit.components.v1 as components

# ==========================================
# BLOCK 1: 基础配置 (事项 2)
# ==========================================
CONFIG_FILE = "config_v3.json"

def load_config():
    defaults = {
        "admin_password": "199266", 
        "user_password": "a123456",
        "app_title": "AI课堂教学数据分析工具 (3.0 完整版)",
        "upload_hint": "⬆️ 请上传班级数据 Excel 原文件"
    }
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(defaults, f, ensure_ascii=False)
        return defaults
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            c = json.load(f)
            # 自动补全可能缺失的 key
            for k, v in defaults.items():
                if k not in c: c[k] = v
            return c
    except: return defaults

conf = load_config()

# ==========================================
# BLOCK 3: 数据处理大脑 (事项 1 - 零删减逻辑)
# ==========================================
def natural_sort_key(s):
    """汉字年级+数字班级 自然排序算法"""
    char_map = {'七': 7, '八': 8, '九': 9, '十': 10}
    grade_weight = 99
    for char, weight in char_map.items():
        if char in s:
            grade_weight = weight
            break
    parts = [int(text) if text.isdigit() else text for text in re.split('([0-9]+)', s)]
    return (grade_weight, parts)

def process_data_logic(df):
    try:
        # 1. 基础清洗
        df['周'] = pd.to_datetime(df['周'], errors='coerce')
        df = df.dropna(subset=['周']).fillna(0)
        
        # 2. 字段定义 (维度扩容)
        col_t = "老师布置课时总时长（分钟）"
        col_s = "学生观看AI课堂课时微课总时长(分钟)"
        col_comp = "微课完成率"
        col_corr = "题目正确率（自学+快背）"
        
        # 3. 兼容性补全
        for c in [col_t, col_s, col_comp, col_corr]:
            if c not in df.columns: df[c] = 0

        all_weeks = sorted(df['周'].unique())
        if not all_weeks: return None
        target_week = all_weeks[-1]
        
        # 4. 本周核心数据 (维度 1)
        curr_df = df[df['周'] == target_week].copy()
        m_curr = {
            'hours': int(curr_df['课时数'].sum()), 
            'att': curr_df['课时平均出勤率'].mean(), 
            'corr': curr_df[col_corr].mean(),
            't_assign_sum': int(curr_df[col_t].sum()), 
            's_watch_sum': int(curr_df[col_s].sum())
        }
        
        # 5. 班级排序 (维度 2)
        class_stats = curr_df.groupby('班级名称').agg({
            '课时数':'sum', '课时平均出勤率':'mean', col_corr:'mean'
        }).reset_index()
        class_stats['sort_key'] = class_stats['班级名称'].apply(natural_sort_key)
        c_sorted = class_stats.sort_values('sort_key')
        
        # 6. 表格生成 (维度 3 - 课时数降序)
        table_df = curr_df.sort_values('课时数', ascending=False)
        avg_att = m_curr['att']
        t_rows = ""
        for _, row in table_df.iterrows():
            styl = "style='color:red;font-weight:bold;'" if row['课时平均出勤率'] < avg_att else ""
            t_rows += f"<tr><td>{row['班级名称']}</td><td>{row['课时数']}</td><td {styl}>{row['课时平均出勤率']*100:.1f}%</td><td>{int(row[col_t])}</td><td>{int(row[col_s])}</td></tr>"

        # 7. 趋势聚合 (维度 4 & 5)
        trend = df.groupby('周').agg({
            '课时数':'sum', '课时平均出勤率':'mean', col_corr:'mean', col_comp:'mean',
            col_t:'sum', col_s:'sum'
        }).reset_index()
        
        return {
            "date": target_week.strftime('%Y-%m-%d'),
            "m": m_curr, "t_rows": t_rows,
            "c_n": c_sorted['班级名称'].tolist(), "c_h": c_sorted['课时数'].tolist(),
            "c_a": (c_sorted['课时平均出勤率']*100).round(1).tolist(), "c_r": (c_sorted[col_corr]*100).round(1).tolist(),
            "tr_d": trend['周'].dt.strftime('%m-%d').tolist(), "tr_h": trend['课时数'].tolist(),
            "tr_a": (trend['课时平均出勤率']*100).round(1).tolist(), "tr_r": (trend[col_corr]*100).round(1).tolist(),
            "tr_c": (trend[col_comp]*100).round(1).tolist(),
            "tr_ts": trend[col_t].tolist(), "tr_ss": trend[col_s].tolist()
        }
    except Exception as e:
        st.error(f"分析出错: {e}"); return None

# ==========================================
# BLOCK 4: HTML 报表生成 (事项 3 - 零删减 5 个维度)
# ==========================================
def get_html_template(d):
    return f"""
    <html>
    <head><meta charset="UTF-8"><script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        body {{ font-family: sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; background: #f4f6f9; }}
        .card {{ background: #fff; padding: 20px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        .kpi {{ display: flex; justify-content: space-around; text-align: center; flex-wrap: wrap; }}
        .kpi div strong {{ font-size: 28px; color: #2980b9; display: block; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th {{ background: #eee; padding: 10px; }} td {{ padding: 10px; border-bottom: 1px solid #eee; text-align: center; }}
        .chart {{ height: 400px; width: 100%; }}
    </style></head>
    <body>
        <h2 style="text-align:center">AI课堂教学数据分析周报 ({d['date']})</h2>
        <div class="card">
            <h3>📊 维度 1：核心指标</h3>
            <div class="kpi">
                <div><strong>{d['m']['hours']}</strong>总课时</div>
                <div><strong>{d['m']['att']*100:.1f}%</strong>出勤率</div>
                <div><strong>{d['m']['t_assign_sum']}</strong>布置时长(分)</div>
                <div><strong>{d['m']['s_watch_sum']}</strong>观看时长(分)</div>
            </div>
        </div>
        <div class="card"><h3>📊 维度 2：班级效能分析 (班级序)</h3><div id="c1" class="chart"></div></div>
        <div class="card"><h3>📊 维度 3：数据明细 (课时排序)</h3>
            <table><thead><tr><th>班级</th><th>课时</th><th>出勤率</th><th>布置时长</th><th>观看时长</th></tr></thead>
            <tbody>{d['t_rows']}</tbody></table>
        </div>
        <div class="card"><h3>📊 维度 4：历史趋势 (多指标)</h3><div id="c2" class="chart"></div></div>
        <div class="card"><h3>📊 维度 5：历史趋势 (时长合计)</h3><div id="c3" class="chart"></div></div>
        <script>
            var opt = {{ tooltip:{{trigger:'axis'}}, legend:{{bottom:0}} }};
            var c1 = echarts.init(document.getElementById('c1'));
            c1.setOption({{ ...opt, xAxis:{{data:{json.dumps(d['c_n'])} }}, yAxis:[{{type:'value'}},{{type:'value',max:100}}],
                series:[{{name:'课时',type:'bar',data:{json.dumps(d['c_h'])} }},{{name:'出勤',type:'line',yAxisIndex:1,data:{json.dumps(d['c_a'])} }},{{name:'正确',type:'line',yAxisIndex:1,data:{json.dumps(d['c_r'])} }}]
            }});
            var c2 = echarts.init(document.getElementById('c2'));
            c2.setOption({{ ...opt, xAxis:{{data:{json.dumps(d['tr_d'])} }}, yAxis:[{{type:'value'}},{{type:'value',max:100}}],
                series:[{{name:'课时',type:'bar',data:{json.dumps(d['tr_h'])} }},{{name:'出勤',type:'line',yAxisIndex:1,data:{json.dumps(d['tr_a'])} }},{{name:'正确',type:'line',yAxisIndex:1,data:{json.dumps(d['tr_r'])} }},{{name:'完课',type:'line',yAxisIndex:1,data:{json.dumps(d['tr_c'])} }}]
            }});
            var c3 = echarts.init(document.getElementById('c3'));
            c3.setOption({{ ...opt, xAxis:{{data:{json.dumps(d['tr_d'])} }}, yAxis:{{type:'value'}},
                series:[{{name:'布置合计',type:'line',smooth:true,data:{json.dumps(d['tr_ts'])} }},{{name:'观看合计',type:'line',smooth:true,data:{json.dumps(d['tr_ss'])} }}]
            }});
        </script>
    </body></html>
    """

# ==========================================
# BLOCK 6: 交互界面 (事项 3 - 3.0 逻辑增强)
# ==========================================
st.set_page_config(page_title=conf["app_title"], layout="wide")

if 'logged_in' not in st.session_state: st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown(f"<h1 style='text-align: center;'>{conf['app_title']}</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pwd = st.text_input("🔑 请输入系统准入密码", type="password")
        if st.button("进入系统", use_container_width=True):
            if pwd == conf["admin_password"] or pwd == conf["user_password"]:
                st.session_state.logged_in = True; st.rerun()
            else: st.error("密码错误")
else:
    st.sidebar.title("🚀 内容分析中心 (3.0)")
    # 强制要求上传文件
    uploaded_file = st.sidebar.file_uploader(conf["upload_hint"], type=["xlsx"])
    
    if uploaded_file is None:
        st.info("👋 欢迎回来！请在左侧侧边栏上传 Excel 文件以开始数据分析。")
        st.image("https://img.icons8.com/clouds/200/null/upload.png") # 增加一个图标引导
    else:
        # 只有在有文件时才运行后续逻辑
        data_p = process_data_logic(pd.read_excel(uploaded_file))
        if data_p:
            html_res = get_html_template(data_p)
            
            # 下载与提示
            c1, c2 = st.columns([1, 3])
            with c1:
                st.download_button("📥 下载完整报表", html_res, "分析周报.html", "text/html")
            with c2:
                st.markdown("<p style='padding-top:10px; color:#666;'>💡 <b>提醒：</b>下载完成后，若需分析另一份数据，请直接重新上传新文件。</p>", unsafe_allow_html=True)
            
            st.divider()
            components.html(html_res, height=1200, scrolling=True)
