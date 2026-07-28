import streamlit as st
import pandas as pd
import math
import os
from io import BytesIO
from datetime import datetime

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

def calculate_distances_full(base_df, query_df):
    """计算查询点与门店距离，返回完整结果（包含店中店和独立店分别检查）"""
    results = []
    
    dianzhongdian = base_df[base_df['门店类型'] == '店中店']
    dulidian = base_df[base_df['门店类型'] == '独立店']
    
    for _, q_row in query_df.iterrows():
        q_lat = q_row['纬度']
        q_lon = q_row['经度']
        q_name = q_row.get('名称/备注', f"查询点{len(results)+1}")

        # 店中店检查
        dzd_dist = float('inf')
        dzd_name = None
        for _, s_row in dianzhongdian.iterrows():
            dist = haversine_distance(q_lat, q_lon, s_row['纬度'], s_row['经度'])
            if dist < dzd_dist:
                dzd_dist = dist
                dzd_name = s_row['门店名称']
        
        dzd_pass = dzd_dist >= 500 if len(dianzhongdian) > 0 else True
        if len(dianzhongdian) == 0:
            dzd_dist = None
            dzd_name = '无店中店数据'

        # 独立店检查
        dld_dist = float('inf')
        dld_name = None
        for _, s_row in dulidian.iterrows():
            dist = haversine_distance(q_lat, q_lon, s_row['纬度'], s_row['经度'])
            if dist < dld_dist:
                dld_dist = dist
                dld_name = s_row['门店名称']
        
        dld_pass = dld_dist >= 1000 if len(dulidian) > 0 else True
        if len(dulidian) == 0:
            dld_dist = None
            dld_name = '无独立店数据'

        # 总体结论
        overall_pass = dzd_pass and dld_pass
        
        results.append({
            '查询点': q_name,
            '查询经度': q_lon,
            '查询纬度': q_lat,
            '最近店中店': dzd_name,
            '店中店距离(米)': round(dzd_dist, 2) if dzd_dist else None,
            '店中店≥500m': '✅ 是' if dzd_pass else '❌ 否' if dzd_dist else '⚠️ 无数据',
            '最近独立店': dld_name,
            '独立店距离(米)': round(dld_dist, 2) if dld_dist else None,
            '独立店≥1km': '✅ 是' if dld_pass else '❌ 否' if dld_dist else '⚠️ 无数据',
            '总体结论': '✅ 通过' if overall_pass else '❌ 不通过'
        })
    
    return pd.DataFrame(results)

# ========== 主应用 ==========
def main():
    st.title("📍 门店距离查询工具")
    st.markdown("计算查询点与门店之间的直线距离，判断是否符合开店距离要求")
    st.caption("规则：与店中店距离需 ≥ 500米，与独立店距离需 ≥ 1000米")

    if 'base_df' not in st.session_state:
        st.session_state.base_df = None
    if 'is_admin' not in st.session_state:
        st.session_state.is_admin = False

    default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stores_base.xlsx")

    # ===== 侧边栏 =====
    with st.sidebar:
        st.header("🏪 门店基础数据")

        # 加载门店数据
        if st.session_state.base_df is None and os.path.exists(default_path):
            try:
                raw_df = pd.read_excel(default_path)
                st.session_state.base_df = load_and_clean_store_data(raw_df)
            except Exception as e:
                st.error(f"读取门店数据失败: {e}")

        if st.session_state.base_df is not None:
            df = st.session_state.base_df
            type_counts = df['门店类型'].value_counts() if '门店类型' in df.columns else pd.Series()
            info_parts = [f"共 {len(df)} 家"]
            for t, c in type_counts.items():
                info_parts.append(f"{t}: {c}家")
            st.info(" | ".join(info_parts))

            with st.expander("📋 查看门店列表"):
                st.dataframe(st.session_state.base_df, use_container_width=True, height=300)

        # 管理员入口
        with st.expander("🔧 修改门店列表"):
            if st.session_state.is_admin:
                st.success("已进入管理模式")
                
                # 管理员可以上传新的门店文件
                st.markdown("**上传新门店数据**")
                admin_upload = st.file_uploader("上传门店Excel", type=['xlsx', 'xls'], key="admin_upload")
                if admin_upload:
                    try:
                        raw_df = pd.read_excel(admin_upload)
                        st.session_state.base_df = load_and_clean_store_data(raw_df)
                        st.session_state.base_df.to_excel(default_path, index=False)
                        st.success(f"已更新 {len(st.session_state.base_df)} 家门店")
                    except Exception as e:
                        st.error(f"读取失败: {e}")

                st.divider()
                
                # 编辑现有数据
                st.markdown("**编辑现有数据**")
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
                    if st.button("💾 保存修改"):
                        try:
                            st.session_state.base_df.to_excel(default_path, index=False)
                            st.success("已保存")
                        except Exception as e:
                            st.error(f"保存失败: {e}")
                with col2:
                    if st.button("🔄 重新加载"):
                        if os.path.exists(default_path):
                            raw_df = pd.read_excel(default_path)
                            st.session_state.base_df = load_and_clean_store_data(raw_df)
                            st.success("已重新加载")

                if st.button("退出管理模式"):
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

        st.divider()
        
        # 下载模板（直接显示按钮）
        st.markdown("**下载查询模板**")
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

    # ===== 主区域 =====
    tab1, tab2 = st.tabs(["✏️ 手动输入", "📁 文件输入"])

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
                st.error("请先加载门店基础数据")
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
                        result_df = calculate_distances_full(st.session_state.base_df, query_df)
                        st.session_state.result_df = result_df
                    st.success(f"已计算 {len(result_df)} 个查询点")
                else:
                    st.error("请输入有效的查询数据")

    # ----- Tab 2: 文件输入 -----
    with tab2:
        st.subheader("文件输入")
        st.markdown("上传包含一个或多个查询点的Excel文件，批量计算距离")

        with st.expander("📋 文件格式要求"):
            st.markdown("""
            Excel 文件必须包含以下列：
            - **经度**（必填）
            - **纬度**（必填）
            - **名称/备注**（可选，用于标识查询点）
            
            示例：
            | 名称/备注 | 经度 | 纬度 |
            |----------|------|------|
            | 查询点1 | 116.504885 | 39.885358 |
            | 查询点2 | 121.473701 | 31.230416 |
            """)
            buffer2 = BytesIO()
            template_df.to_excel(buffer2, index=False)
            buffer2.seek(0)
            st.download_button(
                label="📥 下载查询模板",
                data=buffer2,
                file_name="query_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        uploaded_file = st.file_uploader("上传查询Excel文件", type=['xlsx', 'xls'], key="file_upload")

        if uploaded_file:
            try:
                query_df = pd.read_excel(uploaded_file)
                required = {'经度', '纬度'}
                if not required.issubset(set(query_df.columns)):
                    st.error(f"缺少必要列: {required}")
                else:
                    st.info(f"已加载 {len(query_df)} 个查询点")
                    st.dataframe(query_df.head(10), use_container_width=True)

                    if st.button("🚀 开始计算", type="primary"):
                        if st.session_state.base_df is None:
                            st.error("请先加载门店基础数据")
                        else:
                            with st.spinner("计算中..."):
                                result_df = calculate_distances_full(st.session_state.base_df, query_df)
                                st.session_state.result_df = result_df
                            st.success(f"计算完成！共 {len(result_df)} 条结果")
            except Exception as e:
                st.error(f"读取失败: {e}")

    # ===== 结果展示 =====
    if 'result_df' in st.session_state and st.session_state.result_df is not None:
        st.markdown("---")
        st.header("📊 计算结果")

        result_df = st.session_state.result_df

        # 统计信息
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("查询点数量", len(result_df))
        with col2:
            pass_dzd = len(result_df[result_df['店中店≥500m'].str.contains('是')])
            st.metric("店中店≥500m", pass_dzd)
        with col3:
            pass_dld = len(result_df[result_df['独立店≥1km'].str.contains('是')])
            st.metric("独立店≥1km", pass_dld)
        with col4:
            total_pass = len(result_df[result_df['总体结论'].str.contains('通过')])
            st.metric("总体通过", total_pass)

        # 结果表格
        st.dataframe(
            result_df,
            use_container_width=True,
            column_config={
                '查询经度': st.column_config.NumberColumn(format='%.6f'),
                '查询纬度': st.column_config.NumberColumn(format='%.6f'),
                '店中店距离(米)': st.column_config.NumberColumn(format='%.2f'),
                '独立店距离(米)': st.column_config.NumberColumn(format='%.2f')
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
                file_name=f"distance_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with col2:
            csv_buffer = result_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 导出CSV结果",
                data=csv_buffer,
                file_name=f"distance_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
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