import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from pygwalker.api.streamlit import StreamlitRenderer

# 1. Инициализация страницы
st.set_page_config(page_title="Correlli Intelligence", layout="wide", page_icon="🦅")

# Скрываем стандартное меню Streamlit для "дорогого" вида
hide_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
"""
st.markdown(hide_style, unsafe_allow_html=True)

# 2. Подключение к Supabase
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

# 3. Загрузка данных (используем нашу View из прошлых шагов)
@st.cache_data(ttl=600)
def load_data(view_name):
    response = supabase.table(view_name).select("*").execute()
    return pd.DataFrame(response.data)

# Загружаем основную аналитику и сырые данные
df_market = load_data("ceo_market_analytics")
# ВАЖНО: загрузи основную таблицу для конструктора
# response_raw = supabase.table("Algonova_Calls_Raw").select("*").limit(1000).execute()
# df_raw = pd.DataFrame(response_raw.data)

# 4. Боковая панель (Навигация)
st.sidebar.image("https://via.placeholder.com/150?text=CORRELLI", width=150) # Замени на свой лого
st.sidebar.title("Correlli Platform")
role = st.sidebar.selectbox("Выберите роль:", ["CEO (Стратег)", "CMO (Маркетинг)", "CSO (Продажи)", "Data Lab (Конструктор)"])

st.sidebar.markdown("---")
market_filter = st.sidebar.multiselect("Рынок:", df_market['market'].unique(), default=df_market['market'].unique())

# Фильтруем данные
df_filtered = df_market[df_market['market'].isin(market_filter)]

# 5. Отрисовка интерфейса в зависимости от роли
if role == "CEO (Стратег)":
    st.title("🦅 Executive Dashboard")
    st.subheader("Состояние бизнеса в реальном времени")

    # Метрики с динамикой (имитация дельты для MVP)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Среднее качество", f"{df_filtered['avg_market_quality'].mean():.1f}", delta="1.2%", help="Сравнение с прошлой неделей")
    with col2:
        st.metric("Friction Index", f"{df_filtered['friction_index'].mean():.2f}", delta="-0.05", delta_color="normal")
    with col3:
        st.metric("Вязкость (Vague)", f"{df_filtered['vague_ratio_percent'].mean():.1f}%", delta="2.1%", delta_color="inverse")
    with col4:
        st.metric("Всего звонков", f"{df_filtered['total_calls'].sum()}", delta="140")

    st.markdown("---")

    # График Friction Index по рынкам
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Индекс трения по рынкам")
        fig_friction = px.bar(df_filtered, x='market', y='friction_index', color='market', 
                             text_auto=True, title="Чем выше бар, тем сложнее закрывать сделки")
        st.plotly_chart(fig_friction, use_container_width=True)
    
    with c2:
        st.subheader("Качество vs Вязкость")
        fig_scatter = px.scatter(df_filtered, x='avg_market_quality', y='vague_ratio_percent', size='total_calls', 
                                color='market', hover_name='market', title="Идеальная зона: Справа внизу")
        st.plotly_chart(fig_scatter, use_container_width=True)

elif role == "CMO (Маркетинг)":
    st.title("🎯 Marketing Intelligence")
    st.info("Здесь анализируется резонанс лидов и эффективность UTM-меток.")
    # Тут можно добавить графики по buying_intent из основной таблицы
    st.warning("Подключите UTM-данные для полной визуализации резонанса.")

elif role == "CSO (Продажи)":
    st.title("📈 Sales Operations")
    st.subheader("Эффективность отделов и РОПов")
    
    # Таблица эффективности
    st.dataframe(df_filtered[['market', 'total_calls', 'avg_market_quality', 'friction_index']].sort_values(by='avg_market_quality', ascending=False), 
                 use_container_width=True)

elif role == "Data Lab (Конструктор)":
    st.title("🧬 Лаборатория данных")
    st.markdown("Перетаскивайте поля слева, чтобы создать любой график самостоятельно.")
    
    # Инициализируем PyGWalker (Визуальный конструктор для клиента)
    # Используем df_filtered для примера
    renderer = StreamlitRenderer(df_filtered)
    renderer.explorer()

# 6. Подвал
st.sidebar.markdown(f"**Аккаунт:** Algonova Admin")
st.sidebar.write("2026 © Correlli AI Intelligence")