import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from database import fetch_view_data

def render_cso_dashboard(date_range, selected_markets, selected_pipelines, selected_managers=None):
    st.title("🎯 CSO Operations Dashboard")

    with st.spinner("Analyzing call metadata..."):
        df = fetch_view_data("Algonova_Calls_Raw")
        if df.empty:
            df = fetch_view_data("v_analytics_calls_enhanced")

    if df.empty:
        st.warning("No data available. Please check database connection.")
        return

    total_raw_rows = len(df)
    total_raw_exact = df.attrs.get("supabase_exact_count", None)

    if "call_datetime" in df.columns:
        df["call_datetime"] = pd.to_datetime(df["call_datetime"], errors="coerce", utc=True)
    else:
        df["call_datetime"] = pd.NaT

    df["call_date"] = df["call_datetime"].dt.date

    def determine_market(pipeline):
        p = str(pipeline).upper()
        if p.startswith('CZ'):
            return 'CZ'
        elif p.startswith('SK'):
            return 'SK'
        elif p.startswith('RUK'):
            return 'RUK'
        return 'Others'

    if 'pipeline_name' in df.columns:
        df['computed_market'] = df['pipeline_name'].apply(determine_market)
    else:
        df['computed_market'] = df.get('market', 'Others')

    mask = pd.Series([True] * len(df))
    
    mask_date = pd.Series([True] * len(df))
    if len(date_range) == 2:
        mask_date = (df["call_date"] >= date_range[0]) & (df["call_date"] <= date_range[1])
    mask = mask & mask_date
    
    mask_pipeline = pd.Series([True] * len(df))
    if selected_pipelines:
        mask_pipeline = df['pipeline_name'].isin(selected_pipelines)
    mask = mask & mask_pipeline
    
    mask_market = pd.Series([True] * len(df))
    if selected_markets:
        mask_market = (df['computed_market'].isin(selected_markets) | df['market'].isin(selected_markets))
    mask = mask & mask_market
         
    mask_manager = pd.Series([True] * len(df))
    if selected_managers:
        mask_manager = df['manager'].isin(selected_managers)
    mask = mask & mask_manager

    df = df[mask].copy()

    if df.empty:
        st.warning(f"No data found for the current selection (Filtered from {total_raw_rows} raw records).")
        return

    with st.expander("📊 Data Health & Volume", expanded=False):
        dates = df["call_date"].dropna()
        st.write(f"**Total Records Loaded from DB:** {total_raw_rows}")
        if total_raw_exact is not None:
            st.write(f"**Supabase Exact Count (server):** {total_raw_exact}")
        st.write(f"**Records Shown (after filters):** {len(df)}")
        if len(dates) > 0:
            st.write(f"**Date Range in Result:** {dates.min()} → {dates.max()}")

        rows_after_date = int(mask_date.sum())
        rows_after_market = int((mask_date & mask_market).sum())
        rows_after_pipeline = int((mask_date & mask_market & mask_pipeline).sum())
        rows_after_manager = int((mask_date & mask_market & mask_pipeline & mask_manager).sum())

        st.write(f"**Rows After Date Filter:** {rows_after_date}")
        st.write(f"**Rows After Market Filter:** {rows_after_market}")
        st.write(f"**Rows After Pipeline Filter:** {rows_after_pipeline}")
        st.write(f"**Rows After Manager Filter:** {rows_after_manager}")

        if total_raw_rows > 0:
            st.progress(len(df) / total_raw_rows, text=f"Showing {len(df)} / {total_raw_rows} calls")

    # Define Outcome Logic
    def get_outcome(row):
        ns = str(row.get('next_step_type', '')).lower()
        if any(x in ns for x in ['lesson_scheduled', 'callback_scheduled', 'payment_pending', 'sold']):
            return 'Defined'
        if 'vague' in ns:
            return 'Vague'
        return 'Other'

    df['outcome_category'] = df.apply(get_outcome, axis=1)

    # BLOCK 1: Clarity & Commitment
    st.header("1. Clarity & Commitment (Manager Discipline)")
    col_v1, col_v2 = st.columns([3, 2])
    
    mgr_stats = df.groupby('manager').agg({
        'call_id': 'count',
        'Average_quality': 'mean'
    }).reset_index()
    
    # Count Defined/Vague
    outcome_counts = df.groupby(['manager', 'outcome_category']).size().reset_index(name='count')
    
    # Calculate Rates
    defined_counts = df[df['outcome_category'] == 'Defined'].groupby('manager').size()
    mgr_stats['defined_count'] = mgr_stats['manager'].map(defined_counts).fillna(0)
    mgr_stats['defined_rate'] = (mgr_stats['defined_count'] / mgr_stats['call_id']).fillna(0)
    
    with col_v1:
        st.subheader("Manager Commitment Discipline")
        if not outcome_counts.empty:
            data_chart = outcome_counts[outcome_counts['outcome_category'].isin(['Defined', 'Vague'])]
            
            # Add total calls per manager for tooltip
            mgr_totals = df.groupby('manager')['call_id'].count().to_dict()
            data_chart['total_calls'] = data_chart['manager'].map(mgr_totals)
            
            fig_vague = px.bar(
                data_chart,
                x='manager',
                y='count',
                color='outcome_category',
                title="Clarity (Defined) vs. Chaos (Vague)",
                barmode='relative',
                color_discrete_map={'Defined': '#2ecc71', 'Vague': '#e74c3c'},
                labels={'outcome_category': 'Category', 'count': 'Percentage'}, # Renamed Y axis label
                hover_data=['total_calls'] # Added total calls to tooltip
            )
            fig_vague.update_layout(barnorm='percent', yaxis_title="Percentage (%)") # Explicitly set axis title
            st.plotly_chart(fig_vague, use_container_width=True)

    with col_v2:
        st.subheader("Leaderboard (% Defined Calls)")
        lb_df = mgr_stats.sort_values('defined_rate', ascending=False)
        lb_df['defined_rate_pct'] = (lb_df['defined_rate'] * 100).round(2).astype(str) + '%' # Round to 2
        lb_df['Avg Quality'] = lb_df['Average_quality'].round(2)
        lb_df = lb_df[['manager', 'defined_rate_pct', 'call_id', 'Avg Quality']]
        lb_df.columns = ['Manager', 'Defined %', 'Calls', 'Avg Quality']
        st.dataframe(lb_df, hide_index=True, use_container_width=True)

    st.markdown("---")

    # BLOCK 2: Process Rhythm
    st.header("2. Process Rhythm (Friction & Resistance)")
    
    # Group by Pipeline
    # Intro
    intro_prim = df[df['call_type'] == 'intro_call'].groupby('pipeline_name').size()
    intro_fu = df[df['call_type'] == 'intro_followup'].groupby('pipeline_name').size()
    # Sales
    sales_prim = df[df['call_type'] == 'sales_call'].groupby('pipeline_name').size()
    sales_fu = df[df['call_type'] == 'sales_followup'].groupby('pipeline_name').size()
    
    pipelines = df['pipeline_name'].unique()
    friction_data = []
    
    for p in pipelines:
        ip = intro_prim.get(p, 0)
        ifu = intro_fu.get(p, 0)
        sp = sales_prim.get(p, 0)
        sfu = sales_fu.get(p, 0)
        
        i_fric = ifu / ip if ip > 0 else 0
        s_fric = sfu / sp if sp > 0 else 0
        
        friction_data.append({'Pipeline': p, 'Type': 'Intro Friction', 'Value': round(i_fric, 2), 'Total Calls': ip + ifu})
        friction_data.append({'Pipeline': p, 'Type': 'Sales Friction', 'Value': round(s_fric, 2), 'Total Calls': sp + sfu})
        
    if friction_data:
        df_fric = pd.DataFrame(friction_data)
        col1, col2 = st.columns([2, 1])
        with col1:
            fig_friction = px.bar(
                df_fric, 
                x='Pipeline', 
                y='Value', 
                color='Type', 
                barmode='group',
                title="Friction Index by Pipeline",
                color_discrete_map={'Intro Friction': '#3498db', 'Sales Friction': '#e67e22'},
                hover_data=['Total Calls'] # Added to tooltip
            )
            fig_friction.update_layout(yaxis_title="Friction Index (Follow-ups / Primary)")
            st.plotly_chart(fig_friction, use_container_width=True)
            
        with col2:
            st.metric(
                "Avg Intro Friction",
                f"{df_fric[df_fric['Type']=='Intro Friction']['Value'].mean():.2f}",
                help=r"$Intro\ Friction=\frac{Intro\ Followups}{Intro\ Primaries}$",
            )
            st.metric(
                "Avg Sales Friction",
                f"{df_fric[df_fric['Type']=='Sales Friction']['Value'].mean():.2f}",
                help=r"$Friction=\frac{Followups}{Primaries}$",
            )

    st.markdown("---")

    st.subheader("Friction vs. Defined Rate")
    
    # Prepare Bubble Data
    bubble_stats = df.groupby(['manager', 'pipeline_name', 'computed_market']).agg({
        'Average_quality': 'mean',
        'call_id': 'count'
    }).reset_index()
    bubble_stats = bubble_stats.rename(columns={'call_id': 'total_calls'})
    
    def get_mgr_pipe_defined(row):
        sub = df[(df["manager"] == row["manager"]) & (df["pipeline_name"] == row["pipeline_name"])].copy()
        prim = sub[sub["call_type"].isin(["intro_call", "sales_call"])]
        if len(prim) == 0:
            return 0
        non_vague = prim[prim["outcome_category"] != "Vague"]
        return len(non_vague) / len(prim)
        
    bubble_stats["defined_rate_pct"] = (bubble_stats.apply(get_mgr_pipe_defined, axis=1) * 100).round(2)
    bubble_stats["Average_quality"] = bubble_stats["Average_quality"].round(2)
    
    def get_mgr_pipe_friction(row):
        sub = df[(df['manager'] == row['manager']) & (df['pipeline_name'] == row['pipeline_name'])]
        prim = len(sub[sub['call_type'].isin(['intro_call', 'sales_call'])])
        fu = len(sub[sub['call_type'].isin(['intro_followup', 'sales_followup'])])
        return fu / prim if prim > 0 else 0
        
    bubble_stats["friction_index"] = bubble_stats.apply(get_mgr_pipe_friction, axis=1).round(2)

    if not bubble_stats.empty:
        market_color_map = {
            "CZ": "#1f77b4",
            "SK": "#d62728",
            "RUK": "#2ca02c",
            "Others": "#9467bd",
        }

        fig_bubble = px.scatter(
            bubble_stats,
            x="defined_rate_pct",
            y="friction_index",
            size="total_calls",
            color="computed_market",
            hover_name="manager",
            template="plotly_white",
            size_max=60,
            color_discrete_map=market_color_map,
            labels={
                "defined_rate_pct": "Defined Rate (%)",
                "friction_index": "Friction Index (FU / Primary)",
                "total_calls": "Calls",
                "computed_market": "Market",
            },
            hover_data=["pipeline_name", "total_calls", "Average_quality", "defined_rate_pct", "friction_index"],
        )

        fig_bubble.add_vline(x=bubble_stats["defined_rate_pct"].mean(), line_dash="dot", annotation_text="Avg Defined")
        fig_bubble.add_hline(y=bubble_stats["friction_index"].mean(), line_dash="dot", annotation_text="Avg Friction")
        st.plotly_chart(fig_bubble, use_container_width=True)

    st.markdown("---")

    # BLOCK 4: Silent Lead Ratio
    st.header("4. Silent Lead Ratio")
    
    silence_df = df[df['call_type'].isin(['intro_call', 'sales_call'])].copy()
    if not silence_df.empty:
        silence_df['is_sterile'] = silence_df['main_objection_type'].fillna('None').apply(
            lambda x: str(x).lower() in ['none', '', 'nan']
        )
        
        mgr_silence = silence_df.groupby('manager').agg({
            'call_id': 'count',
            'is_sterile': 'sum'
        }).reset_index()
        mgr_silence['sterile_rate'] = (mgr_silence['is_sterile'] / mgr_silence['call_id'] * 100).round(2) # Round
        
        total_calls = mgr_silence['call_id'].sum()
        total_sterile = mgr_silence['is_sterile'].sum()
        
        fig_waterfall = go.Figure(go.Waterfall(
            name = "Silent Leads", orientation = "v",
            measure = ["relative", "relative"],
            x = ["Total Calls", "Sterile (No Obj)"],
            textposition = "outside",
            text = [f"{total_calls}", f"{total_sterile}"],
            y = [total_calls, -total_sterile],
            connector = {"line":{"color":"rgb(63, 63, 63)"}},
        ))
        fig_waterfall.update_layout(title="Silent Calls Volume", showlegend=False)
        st.plotly_chart(fig_waterfall, use_container_width=True)
        
        st.subheader("Manager Silent Ratio Leaderboard")
        silent_lb = mgr_silence.sort_values('sterile_rate', ascending=False)
        silent_lb.columns = ['Manager', 'Total Calls', 'Sterile Calls', 'Silent Rate %']
        st.dataframe(silent_lb, hide_index=True, use_container_width=True)

    st.markdown("---")
    
    # BLOCK 5: Details
    st.header("5. Operational Waste & Feed")
    tab1, tab2 = st.tabs(["⚠️ Operational Waste", "🔎 Call Inspector"])
    
    with tab1:
        if 'call_duration_sec' in df.columns:
            anomalies = df[
                (df['call_duration_sec'] > 900) & 
                (df['outcome_category'] == 'Vague')
            ].sort_values('call_duration_sec', ascending=False)
            
            if not anomalies.empty:
                st.error(f"Found {len(anomalies)} calls > 15m with Vague outcome.")
                st.dataframe(
                    anomalies[['date', 'manager', 'call_duration_sec', 'next_step_type', 'kommo_link']],
                    use_container_width=True, hide_index=True
                )
            else:
                st.success("No operational waste detected.")

    with tab2:
        call_options = df.sort_values('call_datetime', ascending=False).head(50)[['call_id', 'manager', 'call_date', 'next_step_type']]
        call_options['label'] = call_options.apply(lambda x: f"{x['call_date']} | {x['manager']} | {x['next_step_type']}", axis=1)
        
        selected_label = st.selectbox("Select a call:", options=call_options['label'])
        if selected_label:
            idx = call_options[call_options['label'] == selected_label].index[0]
            cid = call_options.loc[idx, 'call_id']
            row = df[df['call_id'] == cid].iloc[0]
            
            st.write(f"**Manager:** {row['manager']}")
            st.write(f"**Outcome:** {row['next_step_type']}")
            if row.get('kommo_link'):
                st.markdown(f"[🔗 Open in Kommo]({row['kommo_link']})")
            
            st.info(f"**Mistakes:** {row.get('mistakes_summary')}")
            st.success(f"**Best Phrases:** {row.get('best_phrases')}")

if __name__ == "__main__":
    pass
