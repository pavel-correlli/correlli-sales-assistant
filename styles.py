def get_css(theme: str = "dark"):
    if theme == "light":
        bg = "#F8F9FA"
        secondary = "#F1EFFF"
        text = "#0E1117"
        card_bg = "rgba(255, 255, 255, 0.85)"
        card_border = "rgba(123, 97, 255, 0.20)"
        plot_bg = "rgba(255, 255, 255, 0.85)"
        subtle_text = "rgba(14, 17, 23, 0.75)"
        sidebar_bg = "#FFFFFF"
        sidebar_border = "rgba(123, 97, 255, 0.12)"
    else:
        bg = "#0E1117"
        secondary = "#1E1E2E"
        text = "#FFFFFF"
        card_bg = "rgba(30, 30, 46, 0.75)"
        card_border = "rgba(123, 97, 255, 0.20)"
        plot_bg = "rgba(30, 30, 46, 0.75)"
        subtle_text = "rgba(255, 255, 255, 0.70)"
        sidebar_bg = "#0E1117"
        sidebar_border = "rgba(123, 97, 255, 0.20)"

    primary = "#7B61FF"
    primary_2 = "#8A2BE2"
    accent = "#FFD700"

    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {{
      --bg: {bg};
      --secondary: {secondary};
      --text: {text};
      --subtle: {subtle_text};
      --primary: {primary};
      --primary2: {primary_2};
      --accent: {accent};
      --card-bg: {card_bg};
      --card-border: {card_border};
      --plot-bg: {plot_bg};
      --sidebar-bg: {sidebar_bg};
      --sidebar-border: {sidebar_border};
      --radius-lg: 18px;
      --radius-xl: 22px;
    }}

    html, body, [class*="css"] {{
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
    }}

    .stApp {{
      background:
        radial-gradient(800px circle at 20% 5%, rgba(123, 97, 255, 0.18), transparent 55%),
        radial-gradient(900px circle at 80% 20%, rgba(138, 43, 226, 0.12), transparent 55%),
        radial-gradient(900px circle at 50% 100%, rgba(123, 97, 255, 0.10), transparent 55%),
        var(--bg);
      color: var(--text);
    }}

    [data-testid="stSidebar"] {{
      background: var(--sidebar-bg);
      border-right: 1px solid var(--sidebar-border);
    }}

    .sidebar-brand {{
      position: sticky;
      top: 0;
      z-index: 999;
      padding: 14px 0 10px 0;
      margin: -16px -16px 10px -16px;
      background: linear-gradient(180deg, var(--sidebar-bg) 70%, rgba(0,0,0,0) 100%);
      backdrop-filter: blur(10px);
    }}
    .sidebar-brand-inner {{
      padding: 0 16px;
    }}
    .sidebar-logo {{
      width: 100%;
      max-width: 180px;
      height: auto;
      display: block;
      margin: 0 auto 8px auto;
      filter: drop-shadow(0 6px 18px rgba(123, 97, 255, 0.18));
    }}
    .sidebar-title {{
      text-align: center;
      font-weight: 700;
      letter-spacing: 0.2px;
      color: var(--text);
      margin: 0 0 6px 0;
      font-size: 0.95rem;
    }}
    .sidebar-subtitle {{
      text-align: center;
      color: var(--subtle);
      margin: 0;
      font-size: 0.8rem;
    }}

    [data-testid="stMetric"], .stPlotlyChart {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: var(--radius-xl);
      padding: 16px;
      box-shadow: 0 18px 55px rgba(0,0,0,0.22);
      backdrop-filter: blur(12px);
    }}

    [data-testid="stMetricValue"] {{
      font-weight: 700;
      color: var(--text);
    }}
    [data-testid="stMetricLabel"] {{
      color: var(--subtle);
      font-weight: 500;
    }}

    button[kind="primary"] {{
      background: linear-gradient(135deg, var(--primary), var(--primary2)) !important;
      color: #fff !important;
      border: 1px solid rgba(255,255,255,0.08) !important;
      border-radius: var(--radius-lg) !important;
      font-weight: 700 !important;
      transition: transform 0.15s ease, box-shadow 0.15s ease, opacity 0.15s ease;
      box-shadow: 0 10px 26px rgba(123, 97, 255, 0.22);
    }}
    button[kind="primary"]:hover {{
      transform: translateY(-1px);
      box-shadow: 0 16px 34px rgba(123, 97, 255, 0.28);
    }}

    button[kind="secondary"] {{
      background: rgba(255,255,255,0.06) !important;
      color: var(--text) !important;
      border: 1px solid rgba(123, 97, 255, 0.25) !important;
      border-radius: var(--radius-lg) !important;
      font-weight: 600 !important;
      transition: background 0.15s ease, transform 0.15s ease;
    }}
    button[kind="secondary"]:hover {{
      background: rgba(123, 97, 255, 0.14) !important;
      transform: translateY(-1px);
    }}

    .stCaption {{
      color: var(--subtle);
    }}

    a {{
      color: var(--primary);
    }}

    [data-testid="stSidebarContent"] {{
      height: 100vh;
      overflow-y: auto;
      padding-bottom: 120px;
    }}

    [data-testid="stAppViewContainer"] {{
      overflow-y: auto;
    }}

    div[data-baseweb="menu"] {{
      max-height: 60vh !important;
      overflow: auto !important;
    }}

    div[data-baseweb="popover"] {{
      z-index: 999999 !important;
    }}
    </style>
    """
