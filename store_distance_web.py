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

ADMIN_PASSWORD = "admin888"

TYPE_MAP = {
    '小店事业部': '独立店',
    '独立店': '独立店',
    '店中店': '店中店',
    '公司总部': None,
}

# ========== 距离计算函数 ==========
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def load_and_clean_store_data(df):
    if '一级门店组' in df.columns:
        df['门店类型'] = df['一级门店组'].map(TYPE_MAP)
    elif '门店类型' in df.columns:
        df['门店类型'] = df['门店类型'].map(TYPE_MAP).fillna(df['门店类型'])

    if '门店类型' in df.columns:
        df = df[df['门店类型'].notna()].copy()
        valid_types = {'独立店', '店中店'}
        df = df[df['门店类型'].isin(valid_types)].copy()
    else:
        df['门店类型'] = '未知'

    col_order = ['门店名称', '门店类型', '经度', '纬度']
    existing_cols = [c for c in col_order if c in df.columns]
    other_cols = [c for c in df.columns if c not in existing_cols]
    df = df[existing_cols + other_cols]

    return df.reset_index(drop=True)

def calculate_distances(base_df, query_df):
    results = []
    for _, q_row in query_df.iterrows():
        q_lat = q_row['纬度']
        q_lon = q_row['经度']
        q_name = q_row.get('名称/备注', f"查询点{len(results)+1}")

        min_dist = float('inf')
        nearest_store = None
        nearest_lat = None
        nearest_lon = None
        nearest_type = None

        for _, s_row in base_df.iterrows():
            dist = haversine_distance(q_lat, q_lon, s_row['纬度'], s_row['经度'])
            if dist < min_dist:
                min_dist = dist
                nearest_store = s_row['门店名称']
                nearest_lat = s_row['纬度']
                nearest_lon = s_row['经度']
                nearest_type = s_row.get('门店类型', '')

        results.append({
            '查询点': q_name,
            '查询经度': q_lon,
            '查询纬度': q_lat,
            '最近门店': nearest_store,
            '门店类型': nearest_type,
            '门店经度': nearest_lon,
            '门店纬度': nearest_lat,
            '最小距离(米)': round(min_dist, 2),
            '是否小于500米': '✅ 是' if min_dist < 500 else '❌ 否'
        })
    return pd.DataFrame(results)

def check_store_feasibility(base_df, new_lat, new_lon):
    results = {}
    thresholds = {'独立店': 1000, '店中店': 500}

    for store_type, threshold in thresholds.items():
        type_stores = base_df[base_df['门店类型'] == store_type]
        if type_stores.empty:
            results[store_type] = {'距离': None, '通过': True, '说明': f'无{store_type}门店数据'}
            continue

        min_dist = float('inf')
        nearest = None
        for _, s_row in type_stores.iterrows():
            dist = haversine_distance(new_lat, new_lon, s_row['纬度'], s_row['经度'])
            if dist < min_dist:
                min_dist = dist
                nearest = s_row['门店名称']

        passed = min_dist >= threshold
        results[store_type] = {
            '距离': round(min_dist, 2),
            '最近门店': nearest,
            '阈值': threshold,
            '通过': passed,
            '说明': f'与最近{store_type}（{nearest}）距离{min_dist:.0f}m，需≥{threshold}m'
        }

    return results

# ========== 主应用 ==========
def main():
    st.title("📍 门店距离查询工具")
    st.markdown("计算查询点与门店之间的直线距离，找出最近的门店")

    if 'base_df' not in st.session_state:
        st.session_state.base_df = None
    if 'base_file_path' not in st.session_state:
        st.session_state.base_file_path = None
    if 'is_admin' not in st.session_state:
        st.session_state.is_admin = False

    with st.sidebar:
        st.header("🏪 门店基础数据")

        default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stores_base.xlsx")

        uploaded_base = st.file_uploader("上传门店Excel", type=['xlsx', 'xls'], key="base_upload")

        if uploaded_base:
            try:
                raw_df = pd.read_excel(uploaded_base)
                st.session_state.base_df = load_and_clean_store_data(raw_df)
                st.session_state.base_file_path = uploaded_base.name
                st.success(f"已加载 {len(st.session_state.base_df)} 家门店")
            except Exception as e:
                st.error(f"读取失败: {e}")
        elif os.path.exists(default_path) and st.session_state.base_df is None:
            try:
                raw_df = pd.read_excel(default_path)
                st.session_state.base_df = load_and_clean_store_data(raw_df)
                st.session_state.base_file_path = default_path
                st.success(f"已加载 {len(st.session_state.base_df)} 家门店")
            except Exception as e:
                st.error(f"读取失败: {e}")

        if st.session_state.base_df is not None:
            df = st.session_state.base_df
            type_counts = df['门店类型'].value_counts() if '门店类型' in df.columns else pd.Series()
            info_parts = [f"共 {len(df)} 家门店"]
            for t, c in type_counts.items():
                info_parts.append(f"{t}: {c}家")
            st.info("　|　".join(info_parts))

            with st.expander("📋 查看门店列表"):
                st.dataframe(st.session_state.base_df, use_container_width=True, height=300)

            with st.expander("🔐 管理员模式"):
                if st.session_state.is_admin:
                    st.success("已进入管理员模式")
                    edited_df = st.data_editor(
                        st.session_state.base_df,
                        num_rows="dynamic",
                        use_container_width=True,
                        key="base_data_editor",
                        column_config={
                            '门店类型': st.column_config.SelectboxColumn(options=['独立店', '店中店'])
                        }
                    )
                    if edited_df is not None:
                        st.session_state.base_df = load_and_clean_store_data(edited_df)

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("💾 保存到文件"):
                            try:
                                st.session_state.base_df.to_excel(default_path, index=False)
                                st.success("保存成功")
                            except Exception as e:
                                st.error(f"保存失败: {e}")
                    with col2:
                        if st.button("🔄 重新加载"):
                            if os.path.exists(default_path):
                                raw_df = pd.read_excel(default_path)
                                st.session_state.base_df = load_and_clean_store_data(raw_df)
                                st.success("已重新加载")

                    if st.button("退出管理员模式"):
                        st.session_state.is_admin = False
                        st.rerun()
                else:
                    pwd = st.text_input("请输入管理员密码", type="password")
                    if st.button("登录"):
                        if pwd == ADMIN_PASSWORD:
                            st.session_state.is_admin = True
                            st.rerun()
                        else:
                            st.error("密码错误")

            with st.expander("📥 下载模板"):
                template_data = {
                    '名称/备注': ['示例查询点1', '示例查询点2'],
                    '经度': [116.504885, 121.473701],
                    '纬度': [39.885358, 31.230416]
                }
                template_df = pd.DataFrame(template_data)
                buffer = BytesIO()
                template_df.to_excel(buffer, index=False)
                buffer.seek(0)
                st.download_button(
                    label="📥 下载查询模板（示例数据）",
                    data=buffer,
                    file_name="query_template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                st.caption("模板包含2行示例数据，请按格式填写后上传查询")

    # ===== 主区域 =====
    tab1, tab2, tab3, tab4 = st.tabs(["✏️ 手动输入", "🔍 距离查询", "📊 批量查询", "🏪 新店可行性检查"])

    # ----- Tab 1: 手动输入 -----
    with tab1:
        st.subheader("手动输入经纬度")

        col1, col2, col3 = st.columns(3)
        with col1:
            input_name = st.text_input("名称/备注", value="查询点1")
        with col2:
            input_lon = st.text_input("经度", value="", placeholder="116.504885")
        with col3:
            input_lat = st.text_input("纬度", value="", placeholder="39.885358")

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
                query_data = []
                if input_lon.strip() and input_lat.strip():
                    try:
                        lon = float(input_lon)
                        lat = float(input_lat)
                        query_data.append({'名称/备注': input_name, '经度': lon, '纬度': lat})
                    except ValueError:
                        st.warning("单个输入的经纬度格式不正确，已跳过")

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

    # ----- Tab 2: 距离查询（上传文件） -----
    with tab2:
        st.subheader("上传查询文件")

        with st.expander("📋 文件格式要求"):
            st.markdown("""
            Excel 文件必须包含以下列：
            - **经度**（必填）
            - **纬度**（必填）
            - **名称/备注**（可选，用于标识查询点）
            """)
            template_data = {
                '名称/备注': ['示例查询点1', '示例查询点2'],
                '经度': [116.504885, 121.473701],
                '纬度': [39.885358, 31.230416]
            }
            template_df = pd.DataFrame(template_data)
            buffer = BytesIO()
            template_df.to_excel(buffer, index=False)
            buffer.seek(0)
            st.download_button(
                label="📥 下载查询模板",
                data=buffer,
                file_name="query_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

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

    # ----- Tab 4: 新店可行性检查 -----
    with tab4:
        st.subheader("🏪 新店选址可行性检查")
        st.markdown("输入新店经纬度，检查是否符合开店距离要求")
        st.markdown("""
        **规则：**
        - 与最近**独立店**距离需 ≥ **1000米**
        - 与最近**店中店**距离需 ≥ **500米**
        """)

        col1, col2 = st.columns(2)
        with col1:
            new_lon = st.text_input("新店经度", value="", placeholder="116.504885", key="new_lon")
        with col2:
            new_lat = st.text_input("新店纬度", value="", placeholder="39.885358", key="new_lat")

        if st.button("🔍 检查可行性", type="primary"):
            if st.session_state.base_df is None:
                st.error("请先上传门店基础数据")
            elif not new_lon.strip() or not new_lat.strip():
                st.error("请输入有效的经纬度")
            else:
                try:
                    lon = float(new_lon)
                    lat = float(new_lat)
                    with st.spinner("检查中..."):
                        results = check_store_feasibility(st.session_state.base_df, lat, lon)

                    st.markdown("### 检查结果")

                    all_pass = True
                    for store_type, data in results.items():
                        passed = data['通过']
                        if not passed:
                            all_pass = False

                        status = "✅ 通过" if passed else "❌ 不通过"
                        color = "green" if passed else "red"

                        with st.container():
                            st.markdown(f"**{store_type}** 距离检查: :{color}[{status}]")
                            if data.get('距离') is not None:
                                st.write(f"- 最近门店: {data.get('最近门店', '未知')}")
                                st.write(f"- 实际距离: **{data['距离']:.0f}米**")
                                st.write(f"- 要求阈值: ≥ **{data['阈值']}米**")
                                st.write(f"- {data['说明']}")
                            else:
                                st.write(f"- {data.get('说明', '无数据')}")
                            st.divider()

                    if all_pass:
                        st.success("🎉 **总体结论：通过可行性检查，可以开店！**")
                    else:
                        st.warning("⚠️ **总体结论：未通过，请查看具体不通过项**")

                except ValueError:
                    st.error("经纬度格式错误，请输入有效数字")

    # ===== 结果展示 =====
    if 'result_df' in st.session_state and st.session_state.result_df is not None:
        st.markdown("---")
        st.header("📊 计算结果")

        result_df = st.session_state.result_df

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("查询点数量", len(result_df))
        with col2:
            within_500 = len(result_df[result_df['是否小于500米'].str.contains('是')])
            st.metric("小于500米", within_500)
        with col3:
            avg_dist = result_df['最小距离(米)'].mean()
            st.metric("平均距离", f"{avg_dist:.0f}米")

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