import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import supabase
from supabase import create_client, Client

# Supabase connection
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Page configuration
st.set_page_config(page_title="Correlli Sales Assistant", layout="wide")

# Custom CSS for better styling
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .header-section {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .warning-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = 'Dashboard'

@st.cache_data
def get_sales_data():
    """Fetch sales performance metrics from Supabase"""
    try:
        response = supabase_client.table('v_sales_performance_metrics').select('*').execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        return pd.DataFrame()

@st.cache_data
def get_sales_by_representative():
    """Fetch sales by representative"""
    try:
        response = supabase_client.table('v_sales_performance_metrics').select('*').execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            return df.groupby('sales_rep_name')['total_sales'].sum().sort_values(ascending=False)
        return pd.Series()
    except Exception as e:
        st.error(f"Error fetching representative data: {str(e)}")
        return pd.Series()

@st.cache_data
def get_pipeline_data():
    """Fetch pipeline data"""
    try:
        response = supabase_client.table('v_sales_performance_metrics').select('*').execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            return df.groupby('stage')['value'].sum().sort_values(ascending=False)
        return pd.Series()
    except Exception as e:
        st.error(f"Error fetching pipeline data: {str(e)}")
        return pd.Series()

def create_executive_dashboard():
    """Create the CEO Executive Dashboard"""
    st.markdown('<div class="header-section"><h2>📊 CEO Executive Dashboard</h2></div>', unsafe_allow_html=True)
    
    # Get data
    sales_data = get_sales_data()
    
    if sales_data.empty:
        st.warning("No sales data available. Please check your Supabase connection.")
        return
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_sales = sales_data['total_sales'].sum() if 'total_sales' in sales_data.columns else 0
        st.metric("Total Sales", f"${total_sales:,.2f}")
    
    with col2:
        total_deals = len(sales_data) if sales_data.shape[0] > 0 else 0
        st.metric("Total Deals", total_deals)
    
    with col3:
        avg_deal_size = (sales_data['total_sales'].sum() / len(sales_data)) if len(sales_data) > 0 else 0
        st.metric("Average Deal Size", f"${avg_deal_size:,.2f}")
    
    with col4:
        win_rate = (sales_data['total_sales'].sum() / 100) if 'total_sales' in sales_data.columns else 0
        st.metric("Pipeline Health", f"{win_rate:.1f}%")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Sales by Representative")
        sales_by_rep = get_sales_by_representative()
        if not sales_by_rep.empty:
            fig = px.bar(x=sales_by_rep.index, y=sales_by_rep.values, 
                        labels={'x': 'Sales Representative', 'y': 'Total Sales'},
                        color=sales_by_rep.values, color_continuous_scale='Viridis')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No sales representative data available")
    
    with col2:
        st.subheader("Pipeline by Stage")
        pipeline_data = get_pipeline_data()
        if not pipeline_data.empty:
            fig = go.Figure(data=[go.Pie(labels=pipeline_data.index, values=pipeline_data.values)])
            fig.update_layout(title="Deal Pipeline Distribution")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No pipeline data available")
    
    # Detailed table
    st.subheader("Sales Performance Details")
    st.dataframe(sales_data, use_container_width=True)

def create_cmo_dashboard():
    """Create the CMO (Chief Marketing Officer) Dashboard"""
    st.markdown('<div class="header-section"><h2>📢 CMO Dashboard - Marketing Performance</h2></div>', unsafe_allow_html=True)
    
    sales_data = get_sales_data()
    
    if sales_data.empty:
        st.warning("No marketing data available. Please check your Supabase connection.")
        return
    
    # Marketing metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_leads = len(sales_data) if sales_data.shape[0] > 0 else 0
        st.metric("Total Leads Generated", total_leads)
    
    with col2:
        conversion_rate = (len(sales_data) / max(len(sales_data), 1)) * 100
        st.metric("Conversion Rate", f"{conversion_rate:.1f}%")
    
    with col3:
        total_marketing_pipeline = sales_data['total_sales'].sum() if 'total_sales' in sales_data.columns else 0
        st.metric("Marketing Pipeline Value", f"${total_marketing_pipeline:,.2f}")
    
    with col4:
        avg_lead_value = (sales_data['total_sales'].sum() / max(len(sales_data), 1)) if len(sales_data) > 0 else 0
        st.metric("Average Lead Value", f"${avg_lead_value:,.2f}")
    
    # Marketing charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Lead Distribution by Source")
        if not sales_data.empty and 'source' in sales_data.columns:
            source_dist = sales_data['source'].value_counts()
            fig = px.pie(values=source_dist.values, names=source_dist.index, 
                        title="Lead Sources Distribution")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No source data available")
    
    with col2:
        st.subheader("Marketing Campaign Performance")
        if not sales_data.empty and 'campaign' in sales_data.columns:
            campaign_perf = sales_data.groupby('campaign')['total_sales'].sum().sort_values(ascending=False)
            fig = px.bar(x=campaign_perf.index, y=campaign_perf.values,
                        labels={'x': 'Campaign', 'y': 'Revenue'},
                        title="Revenue by Campaign")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No campaign data available")
    
    st.subheader("Lead Quality Analysis")
    st.dataframe(sales_data, use_container_width=True)

def create_cso_dashboard():
    """Create the CSO (Chief Sales Officer) Dashboard"""
    st.markdown('<div class="header-section"><h2>💼 CSO Dashboard - Sales Operations</h2></div>', unsafe_allow_html=True)
    
    sales_data = get_sales_data()
    
    if sales_data.empty:
        st.warning("No sales operations data available. Please check your Supabase connection.")
        return
    
    # Sales operations metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_revenue = sales_data['total_sales'].sum() if 'total_sales' in sales_data.columns else 0
        st.metric("Total Revenue", f"${total_revenue:,.2f}")
    
    with col2:
        active_deals = len(sales_data) if sales_data.shape[0] > 0 else 0
        st.metric("Active Deals", active_deals)
    
    with col3:
        avg_deal_size = (sales_data['total_sales'].sum() / max(len(sales_data), 1)) if len(sales_data) > 0 else 0
        st.metric("Average Deal Size", f"${avg_deal_size:,.2f}")
    
    with col4:
        sales_reps = sales_data['sales_rep_name'].nunique() if 'sales_rep_name' in sales_data.columns else 0
        st.metric("Active Sales Reps", sales_reps)
    
    # Sales operations charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Revenue by Sales Stage")
        pipeline_data = get_pipeline_data()
        if not pipeline_data.empty:
            fig = px.bar(x=pipeline_data.index, y=pipeline_data.values,
                        labels={'x': 'Pipeline Stage', 'y': 'Value'},
                        title="Deal Value by Stage",
                        color=pipeline_data.values, color_continuous_scale='Blues')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No pipeline data available")
    
    with col2:
        st.subheader("Sales Team Performance")
        sales_by_rep = get_sales_by_representative()
        if not sales_by_rep.empty:
            fig = px.bar(x=sales_by_rep.index, y=sales_by_rep.values,
                        labels={'x': 'Sales Rep', 'y': 'Total Sales'},
                        title="Individual Rep Performance",
                        color=sales_by_rep.values, color_continuous_scale='Greens')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No representative data available")
    
    st.subheader("Sales Deal Details")
    st.dataframe(sales_data, use_container_width=True)

def create_manager_lab():
    """Create the Manager Lab - Sales Manager Coaching & Development"""
    st.markdown('<div class="header-section"><h2>🎓 Manager Lab - Coaching & Development</h2></div>', unsafe_allow_html=True)
    
    sales_data = get_sales_data()
    
    if sales_data.empty:
        st.warning("No manager data available. Please check your Supabase connection.")
        return
    
    # Manager metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_team_size = sales_data['sales_rep_name'].nunique() if 'sales_rep_name' in sales_data.columns else 0
        st.metric("Team Size", total_team_size)
    
    with col2:
        team_revenue = sales_data['total_sales'].sum() if 'total_sales' in sales_data.columns else 0
        st.metric("Team Revenue", f"${team_revenue:,.2f}")
    
    with col3:
        avg_rep_revenue = (sales_data['total_sales'].sum() / max(sales_data['sales_rep_name'].nunique(), 1)) if 'sales_rep_name' in sales_data.columns else 0
        st.metric("Avg Revenue per Rep", f"${avg_rep_revenue:,.2f}")
    
    with col4:
        total_deals = len(sales_data) if sales_data.shape[0] > 0 else 0
        st.metric("Team Deals", total_deals)
    
    # Manager coaching tabs
    tab1, tab2, tab3 = st.tabs(["Team Performance", "Rep Coaching Insights", "Development Resources"])
    
    with tab1:
        st.subheader("Team Performance Overview")
        sales_by_rep = get_sales_by_representative()
        if not sales_by_rep.empty:
            fig = px.bar(x=sales_by_rep.index, y=sales_by_rep.values,
                        labels={'x': 'Sales Rep', 'y': 'Sales'},
                        title="Individual Performance Ranking",
                        color=sales_by_rep.values, color_continuous_scale='Purples')
            st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("Performance Metrics Table")
        st.dataframe(sales_data, use_container_width=True)
    
    with tab2:
        st.subheader("Rep Coaching Insights")
        st.info("📌 Use these insights for 1-on-1 coaching sessions with your team members:")
        
        if not sales_data.empty and 'sales_rep_name' in sales_data.columns:
            rep_summary = sales_data.groupby('sales_rep_name').agg({
                'total_sales': 'sum',
            }).sort_values('total_sales', ascending=False)
            
            rep_summary.columns = ['Total Sales']
            rep_summary = rep_summary.reset_index()
            rep_summary['Rank'] = range(1, len(rep_summary) + 1)
            
            st.dataframe(rep_summary, use_container_width=True)
        
        st.markdown("### Coaching Areas:")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **Top Performers:**
            - Recognition opportunities
            - Peer mentoring roles
            - Advanced training options
            """)
        with col2:
            st.markdown("""
            **Development Needed:**
            - Training resources
            - Mentoring assignments
            - Skill development focus
            """)
    
    with tab3:
        st.subheader("Development Resources & Tools")
        st.markdown("""
        #### Sales Manager Resources:
        - **Coaching Framework**: Weekly 1-on-1 templates
        - **Training Modules**: Product knowledge, objection handling
        - **Performance Tools**: Goal tracking, activity monitoring
        - **Best Practices**: Sales techniques from top performers
        
        #### Team Development:
        - Regular training schedules
        - Mentorship programs
        - Certification opportunities
        - Industry certifications
        """)
        
        # Resource download section
        st.markdown("#### Quick Access:")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button(
                label="📄 Weekly Coaching Template",
                data="Coaching Template:\n\n1. Performance Review\n2. Development Areas\n3. Action Items\n4. Next Steps",
                file_name="coaching_template.txt"
            )
        with col2:
            st.download_button(
                label="📊 Team Metrics Export",
                data=sales_data.to_csv() if not sales_data.empty else "No data available",
                file_name="team_metrics.csv"
            )
        with col3:
            st.download_button(
                label="📋 Action Plan Template",
                data="Action Plan:\n\nGoals:\n\nTimeline:\n\nSuccess Metrics:",
                file_name="action_plan.txt"
            )

def create_data_lab():
    """Create the Data Lab for advanced analytics"""
    st.markdown('<div class="header-section"><h2>🔬 Data Lab - Advanced Analytics</h2></div>', unsafe_allow_html=True)
    
    sales_data = get_sales_data()
    
    if sales_data.empty:
        st.warning("No data available for analysis. Please check your Supabase connection.")
        return
    
    tab1, tab2, tab3 = st.tabs(["Raw Data", "Custom Queries", "Analytics"])
    
    with tab1:
        st.subheader("Raw Sales Data")
        st.dataframe(sales_data, use_container_width=True)
        
        # Export options
        st.markdown("**Export Options:**")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📥 Download as CSV",
                data=sales_data.to_csv(index=False),
                file_name=f"sales_data_{datetime.now().strftime('%Y%m%d')}.csv"
            )
        with col2:
            st.download_button(
                label="📥 Download as JSON",
                data=sales_data.to_json(),
                file_name=f"sales_data_{datetime.now().strftime('%Y%m%d')}.json"
            )
    
    with tab2:
        st.subheader("Custom Query Builder")
        st.info("Filter and analyze data based on your specific needs")
        
        # Filter options
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if 'sales_rep_name' in sales_data.columns:
                selected_reps = st.multiselect(
                    "Filter by Sales Rep",
                    sales_data['sales_rep_name'].unique(),
                    default=sales_data['sales_rep_name'].unique()
                )
                filtered_data = sales_data[sales_data['sales_rep_name'].isin(selected_reps)]
            else:
                filtered_data = sales_data
        
        with col2:
            if 'stage' in sales_data.columns:
                selected_stages = st.multiselect(
                    "Filter by Stage",
                    sales_data['stage'].unique(),
                    default=sales_data['stage'].unique()
                )
                filtered_data = filtered_data[filtered_data['stage'].isin(selected_stages)]
        
        with col3:
            date_range = st.date_input(
                "Date Range",
                value=(datetime.now() - timedelta(days=30), datetime.now())
            )
        
        st.subheader("Filtered Results")
        st.dataframe(filtered_data, use_container_width=True)
    
    with tab3:
        st.subheader("Advanced Analytics")
        
        # Summary statistics
        st.markdown("**Summary Statistics:**")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Records", len(sales_data))
        with col2:
            st.metric("Total Value", f"${sales_data['total_sales'].sum():,.2f}" if 'total_sales' in sales_data.columns else "$0")
        with col3:
            st.metric("Average Value", f"${sales_data['total_sales'].mean():,.2f}" if 'total_sales' in sales_data.columns else "$0")
        
        # Distribution analysis
        if 'total_sales' in sales_data.columns:
            st.subheader("Value Distribution")
            fig = px.histogram(sales_data, x='total_sales', nbins=20, 
                             title="Distribution of Deal Sizes",
                             labels={'total_sales': 'Deal Value'})
            st.plotly_chart(fig, use_container_width=True)

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Select Dashboard:",
    ["CEO Dashboard", "CMO Dashboard", "CSO Dashboard", "Manager Lab", "Data Lab"]
)

# Main content
if page == "CEO Dashboard":
    create_executive_dashboard()
elif page == "CMO Dashboard":
    create_cmo_dashboard()
elif page == "CSO Dashboard":
    create_cso_dashboard()
elif page == "Manager Lab":
    create_manager_lab()
elif page == "Data Lab":
    create_data_lab()

# Footer
st.markdown("---")
st.markdown(f"<p style='text-align: center; color: gray;'>Correlli Sales Assistant | Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>", unsafe_allow_html=True)
