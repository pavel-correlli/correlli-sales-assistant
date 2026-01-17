## **Диагноз (почему вы видите ~200 вместо 2000+)**
- **`v_ceo_iron_metrics` в Supabase считает по всей таблице за всё время** (в определении view нет фильтра по дате), поэтому там «правильные большие» объёмы.
- **На сайте объём режется раньше графиков** двумя архитектурными факторами:
  1) **Streamlit сохраняет значение `Date Range` в session_state**. Даже если я меняю «дефолт» в коде, у вас в браузере может оставаться прежний диапазон (например, последние 30 дней). Это идеально объясняет пример: *Viktoria Kravec ожидаемо 233, а на сайте ~23*.
  2) **Supabase/PostgREST часто ограничивает количество строк на один запрос** (server-side cap `max_rows`). Даже при `.limit(20000)` API может вернуть только первую «порцию». Это тоже даёт эффект «мало данных», и его нельзя вылечить формулами/графиками.

Я проверил MCP Memory Graph — он сейчас пустой (entities/relations = 0), поэтому «история» там отсутствует.

## **План исправления (делаю так, чтобы сайт гарантированно учитывал все 2000+)**

### 1) Сделать загрузку из Supabase корректной и полной (пагинация)
- Переписать [database.py](file:///c:/Users/PC/Desktop/Correlli%20Engineering/Projects/Correlli-Sales-Assistant/correlli-sales-assistant/database.py) `fetch_view_data`:
  - Использовать **постраничную выборку** через `.range(from_, to_)` в цикле до пустой страницы.
  - Добавить стабильную сортировку (например, по `call_datetime`/`created_at`/`call_id`, что найдётся в таблице) чтобы страницы не «прыгали».
  - Опционально получать `count='exact'`, чтобы в UI показывать «ожидаемо всего строк» vs «загружено».

### 2) Убрать «невидимый» клип по дате и сделать поведение прозрачным
- В [app.py](file:///c:/Users/PC/Desktop/Correlli%20Engineering/Projects/Correlli-Sales-Assistant/correlli-sales-assistant/app.py):
  - Добавить **переключатель `All time`**.
    - Если включён — дата-фильтр вообще не применяется.
  - Добавить кнопку **`Reset filters`**, которая очищает `st.session_state` для ключей фильтров (включая `Date Range`), чтобы изменения дефолтов реально применялись у уже открытой сессии.
  - Дать `date_input` явный `key` (версионированный), чтобы можно было безопасно мигрировать дефолты.

### 3) Диагностика «куда пропали строки» прямо в интерфейсе
- В [cso_view.py](file:///c:/Users/PC/Desktop/Correlli%20Engineering/Projects/Correlli-Sales-Assistant/correlli-sales-assistant/views/cso_view.py):
  - Расширить блок **Data Health & Volume**:
    - `loaded_rows` (сколько пришло из Supabase)
    - `min/max date` в загруженных данных
    - `rows_after_date`, `rows_after_market`, `rows_after_pipeline`, `rows_after_manager` — по шагам
  - В каждом графике в hover добавить:
    - `total_calls_used` (сколько звонков участвует именно в этом столбце/пузыре)
    - при необходимости `call_types_used` (какие типы звонков попали в метрику)

### 4) Сверка с Supabase view (чтобы доказать соответствие)
- В Data Lab или отдельном диагностическом блоке:
  - Показать таблицу сравнения `Algonova_Calls_Raw` vs `v_ceo_iron_metrics` по менеджерам:
    - `raw_total_calls`
    - `iron_total_calls_volume`
    - разница
  - Это сразу выявит: проблема в API-пагинации/дате/нормализации manager name.

### 5) Memory + документация
- После фикса:
  - Сохранить в core memory текущую архитектуру: «пагинация обязательна», «All time toggle», «Data Health диагностика».
  - Добавить `docs/data_consistency.md`: причина, симптомы, как проверять, какие view сравнивать.

Если подтвердите план — сразу внесу правки в код (pagination + All time + Reset + диагностика) и проверю на запущенном Streamlit, что `loaded_rows` показывает 2000+ и что у Viktoria Kravec совпадает порядок величин с Supabase `v_ceo_iron_metrics`.