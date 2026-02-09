import streamlit as st
import pandas as pd
import os
import json
import datetime
import streamlit.components.v1 as components
import qianfan
from io import BytesIO

# ==========================================
# 房间 1：【配置与中心仓库】
# 作用：存放密码、API密钥、软件名称等。
# 维护建议：小白只需改这里的引号里的字。
# ==========================================

CONFIG_FILE = "config_v2.json"
LOG_FILE = "user_behavior_log.csv"      # 详细行为日志
FEEDBACK_FILE = "user_feedback_log.csv" # 用户反馈日志

def load_system_config():
    default_conf = {
        "admin_password": "199266", 
        "user_password": "a123456",
        "baidu_api_key": "",
        "baidu_secret_key": "",
        "app_title": "AI课堂智能分析工作站",
        "welcome_hint": "⬆️ 请导入班级教学数据 Excel 文件"
    }
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f: json.dump(default_conf, f)
        return default_conf
    with open(CONFIG_FILE, 'r') as f: return json.load(f)

sys_conf = load_system_config()

# 设置网页标题
st.set_page_config(page_title=sys_conf["app_title"], layout="wide")

# ==========================================
# 房间 2：【日志与反馈引擎】
# 作用：记录用户点过什么、反馈了什么。
# 维护建议：这里负责“收集意见”，用于后续优化。
# ==========================================

def record_behavior(action, detail=""):
    """记录用户每一个关键操作"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_data = pd.DataFrame([[now, st.session_state.get('role', '未知'), action, detail]], 
                            columns=["时间", "角色", "操作", "详情"])
    if not os.path.exists(LOG_FILE):
        log_data.to_csv(LOG_FILE, index=False)
    else:
        log_data.to_csv(LOG_FILE, mode='a', header=False, index=False)

# ==========================================
# 房间 3：【数据处理大脑】
# 作用：清洗 Excel，计算出勤率、正确率、趋势。
# 维护建议：如果你想增加新的统计指标，写在这里。
# ==========================================

def process_excel_data(df):
    try:
        df['周'] = pd.to_datetime(df['周'], errors='coerce')
        df = df.dropna(subset=['周']).fillna(0)
        latest_date = df['周'].max()
        current_data = df[df['周'] == latest_date]
        
        # 计算趋势（用于 ECharts）
        trend_group = df.groupby('周').agg({'课时数':'sum', '课时平均出勤率':'mean', '题目正确率（自学+快背）':'mean'}).reset_index()
        
        return {
            "date": latest_date.strftime('%Y-%m-%d'),
            "att": current_data['课时平均出勤率'].mean(),
            "cor": current_data['题目正确率（自学+快背）'].mean(),
            "hours": current_data['课时数'].sum(),
            "js_weeks": trend_group['周'].dt.strftime('%m-%d').tolist(),
            "js_hours": trend_group['课时数'].tolist(),
            "js_att": (trend_group['课时平均出勤率']*100).round(1).tolist(),
            "js_cor": (trend_group['题目正确率（自学+快背）']*100).round(1).tolist()
        }
    except Exception as e:
        st.error(f"数据处理出错，请检查Excel格式: {e}")
        return None

# ==========================================
# 房间 4：【HTML 报表合成器】
# 作用：把数据和 AI 聊出来的文字“缝合”成最终的 HTML。
# 维护建议：想改下载后的网页样式，改这里。
# ==========================================

def build_html_report(data, ai_text):
    # 这里嵌入了你要求的 ECharts 逻辑
    html_tpl = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
        <style>
            body {{ font-family: sans-serif; padding: 20px; line-height: 1.6; background: #f8f9fa; }}
            .card {{ background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .ai-box {{ border-left: 5px solid #2ecc71; background: #f0fff4; padding: 15px; font-weight: 500; }}
        </style>
    </head>
    <body>
        <h2>📊 教学分析报告 ({data['date']})</h2>
        <div class="card">
            <p><b>本周概况：</b>出勤率 {data['att']*100:.1f}% | 正确率 {data['cor']*100:.1f}% | 总课时 {int(data['hours'])}</p>
            <div id="chart" style="width:100%;height:350px;"></div>
        </div>
        <div class="card ai-box">
            <h3>🤖 AI 协作分析建议</h3>
            <div>{ai_text.replace('\\n', '<br>')}</div>
        </div>
        <script>
            var c = echarts.init(document.getElementById('chart'));
            c.setOption({{
                tooltip: {{ trigger: 'axis' }},
                xAxis: {{ data: {json.dumps(data['js_weeks'])} }},
                yAxis: [{{type:'value'}}, {{type:'value', max:100}}],
                series: [
                    {{ name:'课时', type:'bar', data:{data['js_hours']} }},
                    {{ name:'正确率', type:'line', yAxisIndex:1, data:{data['js_cor']} }}
                ]
            }});
        </script>
    </body>
    </html>
    """
    return html_tpl

# ==========================================
# 房间 5：【网页交互主逻辑】
# 作用：处理登录、上传、聊天窗口。
# 维护建议：想改网页上的文字和按钮顺序，在这里调优。
# ==========================================

# 状态初始化
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'chat_history' not in st.session_state: st.session_state.chat_history = []
if 'analysis_res' not in st.session_state: st.session_state.analysis_res = None

# 1. 登录逻辑
if not st.session_state.logged_in:
    st.title(sys_conf["app_title"])
    pwd = st.text_input("请输入准入密码", type="password")
    if st.button("进入系统"):
        if pwd == sys_conf["admin_password"]:
            st.session_state.logged_in, st.session_state.role = True, "admin"
            record_behavior("登录", "管理员权限")
            st.rerun()
        elif pwd == sys_conf["user_password"]:
            st.session_state.logged_in, st.session_state.role = True, "user"
            record_behavior("登录", "普通用户权限")
            st.rerun()
        else: st.error("密码错误")

# 2. 登录后的内容
else:
    st.sidebar.title(f"控制台 ({st.session_state.role})")
    mode = st.sidebar.radio("请选择功能", ["数据看板", "AI 互动修正", "后台设置"])
    
    if st.sidebar.button("安全退出"):
        st.session_state.logged_in = False
        st.rerun()

    # --- 功能 A：数据看板 ---
    if mode == "数据看板":
        st.header("📈 数据自动分析")
        file = st.file_uploader(sys_conf["welcome_hint"], type=["xlsx"])
        if file:
            res = process_excel_data(pd.read_excel(file))
            if res:
                st.session_state.analysis_res = res
                st.success(f"已成功分析 {res['date']} 的数据！")
                st.info("👈 请点击侧边栏‘AI 互动修正’生成报告")
                record_behavior("上传文件", file.name)

    # --- 功能 B：AI 互动修正 ---
    elif mode == "AI 互动修正":
        st.header("🤖 AI 协作辅助生成")
        if not st.session_state.analysis_res:
            st.warning("请先在‘数据看板’上传文件。")
        else:
            # AI 逻辑 (此处接入百度/或模拟)
            for m in st.session_state.chat_history:
                with st.chat_message(m["role"]): st.write(m["content"])

            q = st.chat_input("您可以要求AI：‘字数少一点’、‘重点分析低分班级’...")
            if q:
                st.session_state.chat_history.append({"role": "user", "content": q})
                record_behavior("AI互动", q)
                # 模拟AI回复，实际可接入qianfan
                ans = f"【AI模拟回复】已根据您的要求‘{q}’对数据进行了二次分析..."
                st.session_state.chat_history.append({"role": "assistant", "content": ans})
                st.rerun()

            if st.session_state.chat_history:
                st.divider()
                # 导出按钮
                final_txt = st.session_state.chat_history[-1]["content"]
                final_html = build_html_report(st.session_state.analysis_res, final_txt)
                st.download_button("📥 下载完整 HTML 报表", final_html, "分析报告.html", "text/html")
                record_behavior("下载报表")

    # --- 功能 C：后台设置 ---
    elif mode == "后台设置" and st.session_state.role == "admin":
        st.header("⚙️ 后台管理")
        tab1, tab2, tab3 = st.tabs(["设置修改", "操作日志", "用户反馈"])
        with tab1:
            sys_conf["app_title"] = st.text_input("软件名称", sys_conf["app_title"])
            if st.button("保存设置"):
                with open(CONFIG_FILE, 'w') as f: json.dump(sys_conf, f)
                st.success("已更新，重启生效")
        with tab2:
            if os.path.exists(LOG_FILE):
                st.dataframe(pd.read_csv(LOG_FILE).sort_index(ascending=False))
        with tab3:
            st.write("待集成的反馈数据...")