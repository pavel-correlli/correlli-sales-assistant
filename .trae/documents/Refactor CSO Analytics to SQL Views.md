# План рефакторинга CSO Dashboard и аналитики

## 1. Анализ проблемы расхождения данных
- **Лимит запроса:** В коде установлен лимит `5000` записей, что покрывает ваши 2000 звонков. Проблема не в лимите.
- **Причина расхождения:** 
    1. **Фильтры UI:** Выбранные даты, рынки и воронки в Streamlit отсекают большую часть звонков.
    2. **Логика "Defined":** Это *подмножество* звонков (успешные). Если конверсия 10%, то 200 из 2000 — это нормально.
    3. **Разница логики:** Python использует поиск подстроки (`in`), а SQL часто требует точного совпадения.
- **Решение:** Перенос логики в SQL с использованием `ILIKE` для надежного поиска, как в Python, и создание специализированных views.

## 2. SQL Рефакторинг (1 View = 1 График)
Создадим новые views в файле `20260117_cso_refactor.sql`. Все view будут агрегированы по **дням**, чтобы в Streamlit работал фильтр дат.

1. **`v_cso_clarity_chart`** (Для графика Clarity & Commitment)
   - Группировка: `date`, `manager`, `market`, `pipeline_name`
   - Метрики: `defined_count`, `vague_count`, `total_calls`
   - Логика: `Defined` = `lesson_scheduled`, `callback_scheduled`, `payment_pending`, `sold` (через ILIKE).

2. **`v_cso_friction_chart`** (Для графика Process Rhythm)
   - Группировка: `date`, `pipeline_name`, `market`
   - Метрики: `intro_primaries`, `intro_followups`, `sales_primaries`, `sales_followups`

3. **`v_cso_efficiency_bubble`** (Для графика Friction vs Defined Rate)
   - Группировка: `date`, `manager`, `market`, `pipeline_name`
   - Метрики: `avg_quality`, `defined_count`, `total_calls`, `friction_index_components`

4. **`v_cso_silence_chart`** (Для графика Silent Lead Ratio)
   - Группировка: `date`, `manager`
   - Метрики: `sterile_count` (без возражений), `vague_count`, `total_calls`

## 3. Обновление Python кода (`views/cso_view.py`)
- Замена загрузки огромного `v_analytics_calls_enhanced` на точечные запросы к новым view для каждого блока.
- **Оптимизация:** Данные будут загружаться быстрее, так как агрегация происходит на уровне БД.
- **Friction vs Defined Rate:** Реализация цветовой схемы "Рынок = Цвет, Воронка = Тон".

## 4. Удаление старых views
- Удалим или пометим как deprecated старые view, которые больше не нужны для CSO дашборда (после проверки, что они не используются в других местах).

Этот план обеспечит точность данных (единая логика в SQL) и ускорит работу дашборда.