import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Correlli Sales Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 12px;
        border-radius: 4px;
        margin: 10px 0;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 12px;
        border-radius: 4px;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)

# Data Models
@dataclass
class SalesMetrics:
    """Sales metrics data structure"""
    total_revenue: float
    total_deals: int
    avg_deal_size: float
    pipeline_value: float
    conversion_rate: float
    win_rate: float
    sales_cycle_days: int

class ErrorHandler:
    """Centralized error handling"""
    @staticmethod
    def handle_data_validation(df: pd.DataFrame, required_columns: List[str]) -> tuple[bool, str]:
        """Validate dataframe has required columns"""
        try:
            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                return False, f"Missing required columns: {', '.join(missing_cols)}"
            return True, "Validation successful"
        except Exception as e:
            logger.error(f"Data validation error: {str(e)}")
            return False, f"Validation error: {str(e)}"
    
    @staticmethod
    def safe_divide(numerator: float, denominator: float, default: float = 0) -> float:
        """Safely divide two numbers"""
        try:
            return numerator / denominator if denominator != 0 else default
        except Exception as e:
            logger.error(f"Division error: {str(e)}")
            return default

# Data Visualization Functions
def create_revenue_trend_chart(data: pd.DataFrame) -> go.Figure:
    """Create revenue trend visualization"""
    try:
        fig = px.line(
            data,
            x='date',
            y='revenue',
            title='Revenue Trend',
            markers=True,
            template='plotly_white'
        )
        fig.update_traces(line=dict(color='#1f77b4', width=2))
        return fig
    except Exception as e:
        logger.error(f"Error creating revenue trend chart: {str(e)}")
        return None

def create_deal_pipeline_chart(data: pd.DataFrame) -> go.Figure:
    """Create deal pipeline visualization"""
    try:
        stage_counts = data['stage'].value_counts()
        colors = ['#2ecc71', '#f39c12', '#e74c3c', '#3498db', '#9b59b6']
        
        fig = go.Figure(data=[
            go.Bar(
                x=stage_counts.index,
                y=stage_counts.values,
                marker=dict(color=colors[:len(stage_counts)])
            )
        ])
        fig.update_layout(
            title='Deal Pipeline by Stage',
            xaxis_title='Stage',
            yaxis_title='Number of Deals',
            template='plotly_white'
        )
        return fig
    except Exception as e:
        logger.error(f"Error creating pipeline chart: {str(e)}")
        return None

def create_conversion_funnel(data: pd.DataFrame) -> go.Figure:
    """Create conversion funnel visualization"""
    try:
        stages = ['Prospecting', 'Qualification', 'Proposal', 'Negotiation', 'Closed Won']
        values = [100, 75, 50, 35, 20]  # Example conversion values
        
        fig = go.Figure(go.Funnel(
            y=stages,
            x=values,
            marker=dict(color=['#2ecc71', '#f39c12', '#e74c3c', '#3498db', '#9b59b6'])
        ))
        fig.update_layout(title='Sales Conversion Funnel')
        return fig
    except Exception as e:
        logger.error(f"Error creating funnel chart: {str(e)}")
        return None

def create_territory_performance_chart(data: pd.DataFrame) -> go.Figure:
    """Create territory performance heatmap"""
    try:
        fig = px.bar(
            data,
            x='territory',
            y='quota_attainment',
            color='quota_attainment',
            title='Territory Performance vs Quota',
            color_continuous_scale='RdYlGn',
            template='plotly_white'
        )
        return fig
    except Exception as e:
        logger.error(f"Error creating territory chart: {str(e)}")
        return None

# Sample Data Generation
def generate_sample_sales_data(num_records: int = 50) -> pd.DataFrame:
    """Generate sample sales data for demonstration"""
    try:
        np.random.seed(42)
        dates = pd.date_range(end=datetime.now(), periods=num_records, freq='D')
        
        data = {
            'date': dates,
            'stage': np.random.choice(['Prospecting', 'Qualification', 'Proposal', 'Negotiation', 'Closed Won'], num_records),
            'revenue': np.random.randint(5000, 100000, num_records),
            'territory': np.random.choice(['North', 'South', 'East', 'West'], num_records),
            'quota_attainment': np.random.uniform(60, 150, num_records),
            'deal_size': np.random.randint(10000, 500000, num_records)
        }
        
        return pd.DataFrame(data)
    except Exception as e:
        logger.error(f"Error generating sample data: {str(e)}")
        return pd.DataFrame()

# CMO Dashboard
def render_cmo_dashboard():
    """Chief Marketing Officer Dashboard"""
    st.header("📈 CMO Dashboard")
    
    try:
        # Load or generate data
        data = generate_sample_sales_data(50)
        
        if data.empty:
            st.error("Unable to load sales data")
            return
        
        # Key metrics row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_pipeline = data['revenue'].sum()
            st.metric("Pipeline Value", f"${total_pipeline:,.0f}", "+12%")
        
        with col2:
            avg_deal = data['deal_size'].mean()
            st.metric("Avg Deal Size", f"${avg_deal:,.0f}", "+5%")
        
        with col3:
            num_deals = len(data)
            st.metric("Total Deals", num_deals, "+8")
        
        with col4:
            conversion_rate = len(data[data['stage'] == 'Closed Won']) / len(data) * 100
            st.metric("Conversion Rate", f"{conversion_rate:.1f}%", "-2%")
        
        # Marketing metrics and visualizations
        st.subheader("Campaign Performance")
        col1, col2 = st.columns(2)
        
        with col1:
            trend_fig = create_revenue_trend_chart(data)
            if trend_fig:
                st.plotly_chart(trend_fig, use_container_width=True)
            else:
                st.warning("Could not create revenue trend chart")
        
        with col2:
            funnel_fig = create_conversion_funnel(data)
            if funnel_fig:
                st.plotly_chart(funnel_fig, use_container_width=True)
            else:
                st.warning("Could not create funnel chart")
        
        # Territory analysis
        st.subheader("Territory Analysis")
        territory_fig = create_territory_performance_chart(data)
        if territory_fig:
            st.plotly_chart(territory_fig, use_container_width=True)
        else:
            st.warning("Could not create territory chart")
        
        # Marketing insights
        st.subheader("Key Insights")
        insights_col1, insights_col2, insights_col3 = st.columns(3)
        
        with insights_col1:
            st.markdown("""
            **Lead Quality**: 85% of leads are sales-qualified
            
            Trend: ↑ 5% improvement this month
            """)
        
        with insights_col2:
            st.markdown("""
            **Campaign ROI**: 3.2x average return
            
            Top performer: Digital marketing campaigns
            """)
        
        with insights_col3:
            st.markdown("""
            **Market Share**: Growing in key segments
            
            Next: Focus on enterprise segment
            """)
    
    except Exception as e:
        logger.error(f"CMO Dashboard error: {str(e)}")
        st.error(f"Error rendering CMO Dashboard: {str(e)}")

# CSO Dashboard
def render_cso_dashboard():
    """Chief Sales Officer Dashboard"""
    st.header("💼 CSO Dashboard")
    
    try:
        data = generate_sample_sales_data(100)
        
        if data.empty:
            st.error("Unable to load sales data")
            return
        
        # Executive summary metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            total_revenue = data['revenue'].sum()
            st.metric("YTD Revenue", f"${total_revenue:,.0f}", "+18%")
        
        with col2:
            quota_pct = 94
            st.metric("Quota %", f"{quota_pct}%", "-6%")
        
        with col3:
            win_rate = 28
            st.metric("Win Rate", f"{win_rate}%", "+4%")
        
        with col4:
            avg_cycle = 42
            st.metric("Sales Cycle", f"{avg_cycle} days", "-3 days")
        
        with col5:
            deals_in_pipeline = len(data)
            st.metric("Active Deals", deals_in_pipeline, "+12")
        
        # Sales performance visualizations
        st.subheader("Sales Pipeline Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            pipeline_fig = create_deal_pipeline_chart(data)
            if pipeline_fig:
                st.plotly_chart(pipeline_fig, use_container_width=True)
            else:
                st.warning("Could not create pipeline chart")
        
        with col2:
            # Revenue by stage
            revenue_by_stage = data.groupby('stage')['revenue'].sum().sort_values(ascending=False)
            fig = px.bar(
                x=revenue_by_stage.index,
                y=revenue_by_stage.values,
                title='Revenue by Stage',
                labels={'x': 'Stage', 'y': 'Revenue'},
                template='plotly_white'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Sales team performance
        st.subheader("Team Performance")
        team_metrics = pd.DataFrame({
            'Rep': ['Sarah Chen', 'Mike Johnson', 'Lisa Wong', 'David Park', 'Emma Davis'],
            'Quota': [250000, 200000, 180000, 220000, 190000],
            'Actual': [265000, 175000, 195000, 198000, 210000],
            'Attainment %': [106, 87.5, 108, 90, 111]
        })
        
        col1, col2 = st.columns([3, 1])
        with col1:
            fig = px.bar(
                team_metrics,
                x='Rep',
                y=['Quota', 'Actual'],
                title='Sales Rep Performance vs Quota',
                barmode='group',
                template='plotly_white'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.dataframe(team_metrics[['Rep', 'Attainment %']], use_container_width=True)
        
        # Forecast accuracy
        st.subheader("Sales Forecast vs Actuals")
        forecast_data = pd.DataFrame({
            'Month': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
            'Forecast': [250000, 280000, 310000, 290000, 320000, 350000],
            'Actual': [245000, 275000, 305000, 285000, 315000, None]
        })
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=forecast_data['Month'], y=forecast_data['Forecast'],
                                mode='lines+markers', name='Forecast'))
        fig.add_trace(go.Scatter(x=forecast_data['Month'], y=forecast_data['Actual'],
                                mode='lines+markers', name='Actual'))
        fig.update_layout(title='Forecast Accuracy', template='plotly_white')
        st.plotly_chart(fig, use_container_width=True)
    
    except Exception as e:
        logger.error(f"CSO Dashboard error: {str(e)}")
        st.error(f"Error rendering CSO Dashboard: {str(e)}")

# Manager Lab Dashboard
def render_manager_lab():
    """Manager Lab - Advanced Tools and Analytics"""
    st.header("🔬 Manager Lab")
    
    try:
        # Lab features tabs
        lab_tab1, lab_tab2, lab_tab3, lab_tab4 = st.tabs([
            "Deal Analysis",
            "Pipeline Health",
            "Predictive Analytics",
            "Reports & Export"
        ])
        
        with lab_tab1:
            st.subheader("Deal-by-Deal Analysis")
            
            # Create sample deal data
            deals_data = pd.DataFrame({
                'Deal ID': ['D001', 'D002', 'D003', 'D004', 'D005'],
                'Company': ['Acme Corp', 'TechStart Inc', 'Global Systems', 'Innovation Labs', 'Enterprise Co'],
                'Amount': [150000, 75000, 250000, 100000, 180000],
                'Stage': ['Negotiation', 'Proposal', 'Closed Won', 'Qualification', 'Proposal'],
                'Days in Stage': [45, 30, 5, 15, 20],
                'Next Action': ['Pricing review', 'Demo scheduled', 'Closed', 'Needs assessment', 'Proposal sent'],
                'Risk': ['Medium', 'Low', 'Closed', 'High', 'Medium']
            })
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.dataframe(deals_data, use_container_width=True)
            
            with col2:
                risk_counts = deals_data['Risk'].value_counts()
                fig = px.pie(
                    values=risk_counts.values,
                    names=risk_counts.index,
                    title='Deal Risk Distribution'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Deal health indicators
            st.subheader("Deal Health Indicators")
            with st.expander("View Health Metrics"):
                health_metrics = pd.DataFrame({
                    'Metric': ['Stalled Deals', 'At-Risk Deals', 'High-Value Deals', 'Fast-Moving Deals'],
                    'Count': [3, 5, 8, 12],
                    'Action': ['Follow-up needed', 'Risk mitigation', 'Executive engagement', 'Nurture pipeline']
                })
                st.dataframe(health_metrics, use_container_width=True)
        
        with lab_tab2:
            st.subheader("Pipeline Health Score")
            
            # Pipeline health metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Pipeline Health", "78%", "+5%", delta_color="normal")
            with col2:
                st.metric("Velocity Score", "72%", "+2%")
            with col3:
                st.metric("Quality Score", "84%", "+8%")
            
            # Pipeline distribution
            stages = ['Prospecting', 'Qualification', 'Proposal', 'Negotiation', 'Closed Won']
            values = [15, 25, 20, 18, 12]
            
            fig = go.Figure(data=[
                go.Bar(
                    y=stages,
                    x=values,
                    orientation='h',
                    marker=dict(color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'])
                )
            ])
            fig.update_layout(
                title='Pipeline Distribution by Stage',
                xaxis_title='Number of Deals',
                template='plotly_white'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Stage health
            st.subheader("Stage Health Analysis")
            stage_health = pd.DataFrame({
                'Stage': stages,
                'Deals': values,
                'Avg Value': [45000, 75000, 120000, 180000, 250000],
                'Health': ['Good', 'Fair', 'Good', 'Excellent', 'Excellent']
            })
            st.dataframe(stage_health, use_container_width=True)
        
        with lab_tab3:
            st.subheader("Predictive Analytics")
            
            # Forecast prediction
            st.write("**Revenue Forecast (Next 6 Months)**")
            forecast_months = ['Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            predicted_revenue = [320000, 350000, 380000, 410000, 445000, 480000]
            confidence = [95, 92, 88, 85, 80, 75]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=forecast_months,
                y=predicted_revenue,
                mode='lines+markers',
                name='Predicted Revenue',
                line=dict(color='#2ecc71', width=3)
            ))
            fig.add_trace(go.Scatter(
                x=forecast_months,
                y=[r * 0.9 for r in predicted_revenue],
                mode='lines',
                name='Conservative Estimate',
                line=dict(color='#e74c3c', dash='dash')
            ))
            fig.update_layout(
                title='Revenue Forecast with Confidence Intervals',
                xaxis_title='Month',
                yaxis_title='Revenue ($)',
                template='plotly_white'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Prediction confidence
            st.write("**Forecast Confidence by Month**")
            confidence_df = pd.DataFrame({
                'Month': forecast_months,
                'Confidence %': confidence
            })
            
            fig = px.bar(
                confidence_df,
                x='Month',
                y='Confidence %',
                title='Prediction Confidence Levels',
                color='Confidence %',
                color_continuous_scale='RdYlGn',
                template='plotly_white'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Win probability predictions
            st.subheader("Deal Win Probability")
            with st.expander("View AI-Powered Win Probabilities"):
                win_prob_data = pd.DataFrame({
                    'Deal': ['D001', 'D002', 'D003', 'D004', 'D005'],
                    'Company': ['Acme Corp', 'TechStart', 'Global Sys', 'Innovation', 'Enterprise'],
                    'Win Probability': [75, 45, 92, 35, 68],
                    'Key Factor': ['Strong engagement', 'Budget concerns', 'Exec alignment', 'Competitor threat', 'Timeline risk']
                })
                st.dataframe(win_prob_data, use_container_width=True)
        
        with lab_tab4:
            st.subheader("Reports & Data Export")
            
            # Report generation
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Available Reports**")
                report_options = st.multiselect(
                    "Select reports to generate:",
                    [
                        "Pipeline Summary",
                        "Sales Rep Performance",
                        "Territory Analysis",
                        "Deal Status Report",
                        "Forecast Accuracy",
                        "Conversion Funnel"
                    ],
                    default=["Pipeline Summary", "Sales Rep Performance"]
                )
            
            with col2:
                st.write("**Export Options**")
                export_format = st.radio(
                    "Select export format:",
                    ["CSV", "Excel", "PDF", "Power BI"]
                )
            
            # Generate button
            if st.button("📊 Generate Reports", use_container_width=True):
                st.success(f"✓ Generated {len(report_options)} report(s) in {export_format} format")
                st.info("Reports would be downloaded as files (demo mode)")
            
            # Scheduled reports
            st.subheader("Scheduled Reports")
            scheduled = pd.DataFrame({
                'Report': ['Weekly Pipeline', 'Monthly Forecast', 'Quarterly Review'],
                'Frequency': ['Every Monday', 'Month-end', 'Quarterly'],
                'Last Run': ['2026-01-12', '2026-01-10', '2025-12-31'],
                'Status': ['✓ Scheduled', '✓ Scheduled', '✓ Scheduled']
            })
            st.dataframe(scheduled, use_container_width=True)
    
    except Exception as e:
        logger.error(f"Manager Lab error: {str(e)}")
        st.error(f"Error rendering Manager Lab: {str(e)}")

# Sales Rep Dashboard
def render_sales_rep_dashboard():
    """Individual Sales Rep Dashboard"""
    st.header("👤 Sales Rep Dashboard")
    
    try:
        # Sales rep info
        col1, col2 = st.columns([1, 4])
        with col1:
            st.image("https://api.dicebear.com/7.x/avataaars/svg?seed=Sarah", width=100)
        with col2:
            st.subheader("Sarah Chen")
            st.write("Territory: Pacific Region | Team: Enterprise Sales")
        
        # Personal metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Quota", "$250K", "$265K", "+6%")
        with col2:
            st.metric("Attainment", "106%", "+6%")
        with col3:
            st.metric("Active Deals", 12, "+3")
        with col4:
            st.metric("Close Rate", "32%", "+4%")
        
        # My pipeline
        st.subheader("My Pipeline")
        my_deals = pd.DataFrame({
            'Account': ['Acme Corp', 'TechStart', 'Global Systems', 'InnovateLabs'],
            'Amount': [150000, 75000, 250000, 100000],
            'Stage': ['Negotiation', 'Proposal', 'Closed Won', 'Qualification'],
            'Probability': [85, 45, 100, 25],
            'Next Step': ['Price discussion', 'Technical demo', 'Contract setup', 'Discovery call']
        })
        st.dataframe(my_deals, use_container_width=True)
        
        # Activity tracker
        st.subheader("This Week's Activity")
        activity_col1, activity_col2, activity_col3, activity_col4 = st.columns(4)
        with activity_col1:
            st.metric("Calls", 24, "+5")
        with activity_col2:
            st.metric("Meetings", 8, "+2")
        with activity_col3:
            st.metric("Emails", 67, "+12")
        with activity_col4:
            st.metric("Proposals", 3, "+1")
    
    except Exception as e:
        logger.error(f"Sales Rep Dashboard error: {str(e)}")
        st.error(f"Error rendering Sales Rep Dashboard: {str(e)}")

# Settings and Data Management
def render_settings():
    """Settings and configuration page"""
    st.header("⚙️ Settings")
    
    try:
        settings_tab1, settings_tab2, settings_tab3 = st.tabs([
            "User Preferences",
            "Data Management",
            "System"
        ])
        
        with settings_tab1:
            st.subheader("User Preferences")
            col1, col2 = st.columns(2)
            
            with col1:
                st.selectbox("Dashboard Theme", ["Light", "Dark", "Auto"])
                st.selectbox("Currency", ["USD", "EUR", "GBP", "CAD"])
            
            with col2:
                st.selectbox("Date Format", ["MM/DD/YYYY", "DD/MM/YYYY", "YYYY-MM-DD"])
                st.selectbox("Notification Frequency", ["Real-time", "Hourly", "Daily"])
        
        with settings_tab2:
            st.subheader("Data Management")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📥 Import Data", use_container_width=True):
                    st.success("Import feature enabled - upload CSV files here")
            
            with col2:
                if st.button("📤 Export All Data", use_container_width=True):
                    st.info("Export in progress - would generate comprehensive export")
        
        with settings_tab3:
            st.subheader("System Information")
            st.write(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            st.write(f"Application Version: 1.0.0 MVP")
            st.write(f"Database Status: ✓ Connected")
    
    except Exception as e:
        logger.error(f"Settings error: {str(e)}")
        st.error(f"Error rendering Settings: {str(e)}")

# Main application
def main():
    """Main application function"""
    st.sidebar.title("📊 Correlli Sales Assistant")
    
    # Navigation
    page = st.sidebar.radio(
        "Select Dashboard",
        [
            "CMO Dashboard",
            "CSO Dashboard",
            "Sales Rep Dashboard",
            "Manager Lab",
            "Settings"
        ],
        index=0
    )
    
    # Page routing
    try:
        if page == "CMO Dashboard":
            render_cmo_dashboard()
        elif page == "CSO Dashboard":
            render_cso_dashboard()
        elif page == "Sales Rep Dashboard":
            render_sales_rep_dashboard()
        elif page == "Manager Lab":
            render_manager_lab()
        elif page == "Settings":
            render_settings()
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        st.error(f"An error occurred: {str(e)}")
        st.info("Please try refreshing the page or contact support.")
    
    # Footer
    st.sidebar.divider()
    st.sidebar.write(f"*Last synced: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    st.sidebar.write("*Correlli Sales Assistant v1.0.0*")

if __name__ == "__main__":
    main()
