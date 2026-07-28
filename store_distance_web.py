import streamlit as st
import pandas as pd
import math
import os
from io import BytesIO

# ========== 配置 ==========
st.set_page_config(
    page_title="门店距离查询工具",
    page_icon="📍",
    layout="wide"
)

# ========== 距离计算函数 ==========
def haversine_distance(lat1, lon1, lat2, lon2):
    """Haversine公式计算两点直线距离（米）"""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_distances(base_df, query_df):
    """计算查询点与所有门店距离，返回结果DataFrame"""
    results = []
    for _, q_row in query_df.iterrows():
        q_lat = q_row['纬度']
        q_lon = q_row['经度']
        q_name = q_row.get('名称/备注', f"查询点{len(results)+1}")

        min_dist = float('inf')
        nearest_store = None
        nearest_lat = None
        nearest_lon = None

        for _, s_row in base_df.iterrows():
            dist = haversine_distance(q_lat, q_lon, s_row['纬度'], s_row['经度'])
            if dist < min_dist:
                min_dist = dist
                nearest_store = s_row['门店名称']
                nearest_lat = s_row['纬度']
                nearest_lon = s_row['经度']

        results.append({
            '查询点': q_name,
            '查询经度': q_lon,
            '查询纬度': q_lat,
            '最近门店': nearest_store,
            '门店经度': nearest_lon,
            '门店纬度': nearest_lat,
            '最小距离(米)': round(min_dist, 2),
            '是否小于500米': '✅ 是' if min_dist < 500 else '❌ 否'
        })
    return pd.DataFrame(results)

# ========== 主应用 ==========
def main():
    # 标题
    st.title("📍 门店距离查询工具")
    st.markdown("计算查询点与门店之间的直线距离，找出最近的门店")

    # 初始化session state
    if 'base_df' not in st.session_state:
        st.session_state.base_df = None
    if 'base_file_path' not in st.session_state:
        st.session_state.base_file_path = None

    # ===== 侧边栏：门店管理 =====
    with st.sidebar:
        st.header("🏪 门店基础数据")

        default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stores_base.xlsx")

        uploaded_base = st.file_uploader("上传门店Excel", type=['xlsx', 'xls'], key="base_upload")

        if uploaded_base:
            try:
                st.session_state.base_df = pd.read_excel(uploaded_base)
                st.session_state.base_file_path = uploaded_base.name
            except Exception as e:
                st.error(f"读取失败: {e}")
        elif os.path.exists(default_path) and st.session_state.base_df is None:
            st.session_state.base_df = pd.read_excel(default_path)
            st.session_state.base_file_path = default_path

        if st.session_state.base_df is not None:
            st.success(f"已加载 {len(st.session_state.base_df)} 家门店")

            with st.expander("📝 编辑门店数据", expanded=False):
                edited_df = st.data_editor(
                    st.session_state.base_df,
                    num_rows="dynamic",
                    use_container_width=True,
                    key="base_data_editor"
                )
                if edited_df is not None:
                    st.session_state.base_df = edited_df

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 保存到文件"):
                        try:
                            st.session_state.base_df.to_excel(default_path, index=False)
                            st.success(f"已保存到 {default_path}")
                        except Exception as e:
                            st.error(f"保存失败: {e}")
                with col2:
                    if st.button("🔄 重新加载"):
                        if os.path.exists(default_path):
                            st.session_state.base_df = pd.read_excel(default_path)
                            st.success("已重新加载")
                        else:
                            st.error("文件不存在")

            with st.expander("📋 查看门店列表"):
                st.dataframe(st.session_state.base_df, use_container_width=True)

            buffer = BytesIO()
            st.session_state.base_df.to_excel(buffer, index=False)
            buffer.seek(0)
            st.download_button(
                label="📥 下载门店数据模板",
                data=buffer,
                file_name="stores_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # ===== 主区域 =====
    tab1, tab2, tab3 = st.tabs(["🔍 距离查询", "✏️ 手动输入", "📊 批量查询"])

    # ----- Tab 1: 上传查询 -----
    with tab1:
        st.subheader("上传查询文件")

        # 查询文件格式说明
        with st.expander("📋 文件格式要求"):
            st.markdown("""
            Excel 文件必须包含以下列：
            - **经度**（必填）
            - **纬度**（必填）
            - **名称/备注**（可选，用于标识查询点）
            """)

        uploaded_query = st.file_uploader("上传查询Excel", type=['xlsx', 'xls'], key="query_upload")

        if uploaded_query:
            try:
                query_df = pd.read_excel(uploaded_query)
                required = {'经度', '纬度'}
                if not required.issubset(set(query_df.columns)):
                    st.error(f"缺少必要列: {required}")
                else:
                    st.info(f"已加载 {len(query_df)} 个查询点")
                    st.dataframe(query_df.head(10), use_container_width=True)

                    if st.button("🚀 开始计算", type="primary"):
                        if st.session_state.base_df is None:
                            st.error("请先上传门店基础数据")
                        else:
                            with st.spinner("计算中..."):
                                result_df = calculate_distances(st.session_state.base_df, query_df)
                                st.session_state.result_df = result_df
                            st.success("计算完成！")
            except Exception as e:
                st.error(f"读取失败: {e}")

    # ----- Tab 2: 手动输入 -----
    with tab2:
        st.subheader("手动输入经纬度")

        col1, col2, col3 = st.columns(3)
        with col1:
            input_name = st.text_input("名称/备注", value="查询点1")
        with col2:
            input_lon = st.text_input("经度", value="", placeholder="116.504885")
        with col3:
            input_lat = st.text_input("纬度", value="", placeholder="39.885358")

        # 批量输入区
        st.markdown("---")
        st.markdown("**或批量输入**（支持两种格式）")
        st.caption("格式1: 名称, 经度, 纬度　｜　格式2: 经度, 纬度（自动命名）")
        batch_input = st.text_area(
            "批量输入",
            placeholder="名称1, 116.504885, 39.885358\n116.40, 39.90\n名称3, 121.50, 31.20",
            height=120
        )

        if st.button("🔍 计算手动输入", type="primary"):
            if st.session_state.base_df is None:
                st.error("请先上传门店基础数据")
            else:
                # 处理单个输入
                query_data = []
                if input_lon.strip() and input_lat.strip():
                    try:
                        lon = float(input_lon)
                        lat = float(input_lat)
                        query_data.append({'名称/备注': input_name, '经度': lon, '纬度': lat})
                    except ValueError:
                        st.warning("单个输入的经纬度格式不正确，已跳过")

                # 处理批量输入
                if batch_input.strip():
                    for i, line in enumerate(batch_input.strip().split('\n'), 1):
                        parts = [p.strip() for p in line.split(',')]
                        try:
                            if len(parts) == 3:
                                query_data.append({
                                    '名称/备注': parts[0],
                                    '经度': float(parts[1]),
                                    '纬度': float(parts[2])
                                })
                            elif len(parts) == 2:
                                query_data.append({
                                    '名称/备注': f'查询点{len(query_data)+1}',
                                    '经度': float(parts[0]),
                                    '纬度': float(parts[1])
                                })
                            else:
                                st.warning(f"第{i}行格式错误: {line}")
                        except ValueError:
                            st.warning(f"第{i}行经纬度格式错误: {line}")

                if query_data:
                    query_df = pd.DataFrame(query_data)
                    with st.spinner("计算中..."):
                        result_df = calculate_distances(st.session_state.base_df, query_df)
                        st.session_state.result_df = result_df
                    st.success(f"已计算 {len(result_df)} 个查询点")
                else:
                    st.error("请输入有效的查询数据")

    # ----- Tab 3: 批量查询 -----
    with tab3:
        st.subheader("批量查询")
        st.markdown("上传包含多个查询点的Excel文件，批量计算距离")

        uploaded_batch = st.file_uploader("上传批量查询Excel", type=['xlsx', 'xls'], key="batch_upload")

        if uploaded_batch:
            try:
                batch_df = pd.read_excel(uploaded_batch)
                st.dataframe(batch_df.head(20), use_container_width=True)

                if st.button("🚀 批量计算", type="primary"):
                    if st.session_state.base_df is None:
                        st.error("请先上传门店基础数据")
                    else:
                        required = {'经度', '纬度'}
                        if not required.issubset(set(batch_df.columns)):
                            st.error(f"缺少必要列: {required}")
                        else:
                            with st.spinner("批量计算中..."):
                                result_df = calculate_distances(st.session_state.base_df, batch_df)
                                st.session_state.result_df = result_df
                            st.success(f"批量计算完成，共 {len(result_df)} 条结果")
            except Exception as e:
                st.error(f"读取失败: {e}")

    # ===== 结果展示 =====
    if 'result_df' in st.session_state and st.session_state.result_df is not None:
        st.markdown("---")
        st.header("📊 计算结果")

        result_df = st.session_state.result_df

        # 统计信息
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("查询点数量", len(result_df))
        with col2:
            within_500 = len(result_df[result_df['是否小于500米'].str.contains('是')])
            st.metric("小于500米", within_500)
        with col3:
            avg_dist = result_df['最小距离(米)'].mean()
            st.metric("平均距离", f"{avg_dist:.0f}米")

        # 结果表格
        st.dataframe(
            result_df,
            use_container_width=True,
            column_config={
                '查询经度': st.column_config.NumberColumn(format='%.6f'),
                '查询纬度': st.column_config.NumberColumn(format='%.6f'),
                '门店经度': st.column_config.NumberColumn(format='%.6f'),
                '门店纬度': st.column_config.NumberColumn(format='%.6f'),
                '最小距离(米)': st.column_config.NumberColumn(format='%.2f 米')
            }
        )

        # 导出
        col1, col2 = st.columns(2)
        with col1:
            buffer = BytesIO()
            result_df.to_excel(buffer, index=False)
            buffer.seek(0)
            st.download_button(
                label="📥 导出Excel结果",
                data=buffer,
                file_name="distance_result.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with col2:
            csv_buffer = result_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 导出CSV结果",
                data=csv_buffer,
                file_name="distance_result.csv",
                mime="text/csv"
            )

    # ===== 页脚 =====
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: gray;'>
        💡 提示：距离计算使用 Haversine 公式，考虑地球曲率，结果为球面直线距离
    </div>
    """, unsafe_allow_html=True)

if __name__ == '__main__':
    main()