## Проверка логики ТЗ
- ТЗ в целом консистентно: разделить CSO на «оперативный контроль вчера» и «динамику эффективности» — это ровно переход от «отчёта» к «пульту управления».
- Есть одно противоречие в описании «Operations Feed»: в начале ты просишь Summary Bar «по отделам и по pipelines», а ниже добавляешь горизонтальный bar «минуты по менеджерам». Это не конфликт, если трактовать так: Summary Bar = агрегаты верхнего уровня (по типам/пайплайнам), а bar по менеджерам = быстрый список «кто пахал/кто висел».
- «Отдела/департамента» как отдельного поля в данных сейчас нет; наиболее близкая продуктовая интерпретация — разделение по типам звонков (Intro vs Sales) или по стадии (Primary vs Follow-up). В плане ниже закладываю это как “Departments = Intro/Sales”, чтобы не требовать новых полей.

## Новая продуктовая иерархия CSO (что увидит РОП)
1) Data Health & Volume (как есть, сверху, в expander).
2) Daily Operations Feed (вчера/пятница) — первый блок на странице.
3) Manager Productivity Timeline — второй блок на странице.
4) Dialogue Steering Control (бывш. Clarity) — третий блок.
5) Week-to-Date Efficiency (Friction + Bubble Friction vs Defined) — четвёртый блок.
6) Discovery Depth Index (бывш. Silent Lead) — пятый блок.
7) Operational details/Call inspector — оставить, но в самый низ (если нужно — свернуть в expander).

## Данные и правила фильтрации
- Единый источник времени: `call_datetime`.
- Global фильтры из sidebar:
  - Markets/Pipelines/Managers — применяются везде.
  - Date Range — применяется везде, КРОМЕ Daily Operations Feed.
- Smart Yesterday:
  - если сегодня Monday → брать Friday (today - 3 days), иначе yesterday (today - 1 day).
  - фильтрация по дате делается через `call_datetime` → date (в pandas через `.dt.date`).
- Average_quality:
  - в CSO приводить к numeric через `pd.to_numeric(errors="coerce")` перед всеми порогами/агрегациями.

## Реализация: что именно поменять в cso_view.py
### 1) Вынести утилиты и централизовать фильтры
- Внутри файла сделать небольшие чистые функции (без новых файлов):
  - `compute_call_datetime_columns(df)` → приводит call_datetime, добавляет call_date.
  - `apply_filters(df, selected_markets, selected_pipelines, selected_managers, date_range=None)` → применяет все фильтры (date_range опционально).
  - `get_smart_yesterday(today: date) -> date`.
  - `compute_outcome_category(df)` → векторно/через apply как сейчас (оставим как есть, если не критично).

### 2) Daily Operations Feed (первый блок)
- Источник данных: тот же df, что уже загружается, но:
  - сначала применяем market/pipeline/manager,
  - затем принудительно фильтруем по `smart_yesterday`, игнорируя глобальный date_range.
- UI:
  - Дисклеймер: текст/плашка вида: «Внимание: данные за {smart_yesterday}, игнорируя общие фильтры дат».
- Summary Bar:
  - Метрика Total Calls Yesterday.
  - Разбивка «по отделам»: Intro vs Sales (по `call_type`), отдельные st.metric или небольшой bar.
  - Разбивка по pipelines: топ-5 pipelines по количеству (или полный горизонтальный бар, если pipelines мало).
- Tabs:
  - `Critical Anomalies`: `call_duration_sec > 600` AND `next_step_type == "callback_vague"` (или contains("callback") & contains("vague"), если в данных не строгое равенство). Колонки: call_datetime, manager, pipeline_name, call_duration_sec (мин), kommo_link.
  - `Low Quality Calls`: `Average_quality < 4.0`. Колонки: call_datetime, manager, pipeline_name, Average_quality, kommo_link.
- Доп. визуализация (из твоего расширенного текста): горизонтальный bar «Talk minutes вчера» по менеджерам (sum(call_duration_sec)/60). Это ускоряет “кто реально работал” и не противоречит Summary Bar.

### 3) Manager Productivity Timeline (второй блок)
- Данные: df после всех глобальных фильтров, ВКЛЮЧАЯ date_range.
- Гранулярность: day (call_datetime → date).
- Агрегации по (date, manager):
  - `total_minutes` = sum(call_duration_sec)/60.
  - `total_calls` = count(call_id).
  - `intro_calls` = count(call_type == intro_call).
  - `followup_calls` = count(call_type in intro_followup/sales_followup).
  - `avg_quality` = mean(Average_quality).
  - `anomaly_15m` = count(call_duration_sec > 900).
  - `market` = computed_market (как сейчас).
- Визуализация:
  - `px.line` или `go.Figure` с линиями по менеджерам.
  - Маркеры включены, одинакового размера.
  - Цвет = market (CZ/SK/RUK/Others) с существующей color map.
  - Hover Tooltip: дата, менеджер, total_minutes, calls breakdown, avg_quality, anomaly_15m.

### 4) Dialogue Steering Control (третий блок)
- Переименовать заголовок.
- График: 100% stacked bar (proportional) Defined vs Vague по менеджерам.
- Логика outcome оставить существующую (Defined/Vague), но chart сделать именно “доли”, не абсолюты.

### 5) Week-to-Date (четвёртый блок)
- WTD диапазон: Monday of current week → today (по `call_datetime::date`).
- Здесь держим Friction Index и Bubble Friction vs Defined Rate.
- Bubble Chart оставить по ТЗ: X=%Defined, Y=Friction, size=count(call_id), tooltip manager/calls/avg_quality.

### 6) Discovery Depth Index (пятый блок)
- Переименовать.
- Добавить st.info с философией: objections None = провал discovery.
- Визуализацию можно оставить текущую (waterfall) и/или добавить компактный leaderboard sterile_rate.

## Supabase / Views (минимально)
- Проверить, что `call_datetime` и `Average_quality` доступны и корректных типов во view, которые реально используются (как минимум `v_analytics_calls_enhanced`, и то, что дергается для sidebar).
- Если выяснится, что тип `Average_quality` приходит строкой — фиксировать на стороне pandas (быстрее) и параллельно в SQL view.

## Критерии готовности (проверки)
- Daily Operations Feed всегда показывает “вчера/пятница”, даже если date_range выставлен иначе.
- Global market/pipeline/manager фильтры применяются к обоим блокам.
- Timeline строится без тяжелых per-row apply и стабильно работает на 2000+ строк.
- Таблицы anomalies/low quality содержат только нужные поля и всегда имеют рабочий kommo_link.

Если подтверждаешь план, дальше сделаю правки в [views/cso_view.py](file:///c:/Users/PC/Desktop/Correlli%20Engineering/Projects/Correlli-Sales-Assistant/correlli-sales-assistant/views/cso_view.py) и минимально затрону только то, что нужно для CSO (без лишних рефакторингов в других файлах).