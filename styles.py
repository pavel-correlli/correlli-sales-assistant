def get_css():
    return """
    <style>
    .main {
        background-color: #f8f9fa;
    }
    /* Metric Cards */
    [data-testid="stMetric"] {
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid #e9ecef;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 600;
        color: #2c3e50;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        color: #6c757d;
    }
    /* Charts */
    .stPlotlyChart {
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid #e9ecef;
    }
    /* Volumetric Buttons in Sidebar */
    div.stButton > button {
        width: 100%;
        border-radius: 6px;
        font-weight: 500;
        border: 1px solid #ced4da;
        background-color: #ffffff;
        color: #495057;
        transition: all 0.2s;
    }
    div.stButton > button:hover {
        background-color: #e9ecef;
        border-color: #adb5bd;
    }
    div.stButton > button:focus {
        box-shadow: 0 0 0 0.2rem rgba(72, 85, 99, 0.25);
    }
    /* Active Button Style (applied via Python logic ideally, but basic CSS here) */
    </style>
    """
