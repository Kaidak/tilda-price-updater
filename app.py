import streamlit as st
import pandas as pd
import io

# --- ФУНКЦИИ ПОМОЩНИКИ ---

def load_file(uploaded_file):
    """
    Умная загрузка: понимает и CSV, и Excel.
    Возвращает DataFrame.
    """
    if uploaded_file.name.endswith('.xlsx'):
        # Читаем Excel
        try:
            # dtype=str гарантирует, что артикулы "00123" не превратятся в числа 123
            return pd.read_excel(uploaded_file, dtype=str)
        except Exception as e:
            st.error(f"Ошибка при чтении Excel: {e}")
            return None
    else:
        # Читаем CSV (с перебором кодировок)
        try:
            return pd.read_csv(uploaded_file, sep=';', encoding='utf-8', dtype=str)
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, sep=';', encoding='cp1251', dtype=str)
        except Exception as e:
            st.error(f"Ошибка при чтении CSV: {e}")
            return None

def clean_price(price_str):
    """Превращает строку с ценой в число."""
    if pd.isna(price_str):
        return None
    price_str = str(price_str).strip().replace(',', '')
    try:
        return float(price_str)
    except ValueError:
        return None

def make_beautiful_price(price):
    """
    Делает цену красивой (оканчивает на 9).
    Пример: 1542 -> 1549.
    """
    if pd.isna(price):
        return price
    # Логика: отбрасываем копейки и единицы (делочисленное деление на 10),
    # умножаем обратно на 10 и прибавляем 9.
    return int(price // 10) * 10 + 9

def process_files(file_tilda, file_new_prices, percent_change, 
                  col_sku_tilda, col_price_tilda, col_sku_new, col_price_new,
                  do_beautiful_prices):
    
    # 1. Загружаем файлы
    df_tilda = load_file(file_tilda)
    df_new = load_file(file_new_prices)
    
    if df_tilda is None or df_new is None:
        return None, None, "Ошибка чтения файлов."

    # 2. Проверка колонок
    if col_sku_tilda not in df_tilda.columns or col_price_tilda not in df_tilda.columns:
        return None, None, f"Ошибка: В файле Тильды нет колонок '{col_sku_tilda}' или '{col_price_tilda}'"
    
    if col_sku_new not in df_new.columns or col_price_new not in df_new.columns:
        return None, None, f"Ошибка: В новом прайсе нет колонок '{col_sku_new}' или '{col_price_new}'"

    # 3. Подготовка данных (чистим пробелы в артикулах)
    df_tilda[col_sku_tilda] = df_tilda[col_sku_tilda].str.strip()
    df_new[col_sku_new] = df_new[col_sku_new].str.strip()
    
    # 4. Расчет цен
    df_new['clean_price'] = df_new[col_price_new].apply(clean_price)
    
    # Применяем процент
    multiplier = 1 + (percent_change / 100)
    df_new['calculated_price'] = df_new['clean_price'] * multiplier
    
    # Применяем "Красивые цены" или просто округляем
    if do_beautiful_prices:
        df_new['final_price'] = df_new['calculated_price'].apply(make_beautiful_price)
    else:
        df_new['final_price'] = df_new['calculated_price'].round(2)

    # Создаем справочник цен
    # dropna убирает товары без цены
    valid_prices = df_new.dropna(subset=['final_price'])
    price_map = valid_prices.set_index(col_sku_new)['final_price'].to_dict()

    # 5. Обновление каталога Тильды
    count_updated = 0
    def update_row(row):
        sku = row[col_sku_tilda]
        if sku in price_map:
            nonlocal count_updated
            count_updated += 1
            return price_map[sku]
        else:
            return row[col_price_tilda]

    df_tilda[col_price_tilda] = df_tilda.apply(update_row, axis=1)

    # 6. Поиск НЕНАЙДЕННЫХ товаров (Пункт №3)
    # Берем все артикулы из Тильды в множество (set) для быстрого поиска
    tilda_skus = set(df_tilda[col_sku_tilda])
    
    # Фильтруем новый прайс: оставляем только те, чьих артикулов НЕТ в Тильде
    missing_items_df = valid_prices[~valid_prices[col_sku_new].isin(tilda_skus)].copy()
    
    # Оставляем в отчете только полезные колонки
    cols_to_keep = [col_sku_new, col_price_new, 'final_price']
    # Если есть еще название товара, можно добавить, но мы не знаем его имя колонки точно.
    # Поэтому оставим все колонки нового файла, это безопаснее.
    
    missing_count = len(missing_items_df)

    message = f"✅ Готово! Обновлено товаров: {count_updated}. Новых товаров (нет на сайте): {missing_count}."
    
    return df_tilda, missing_items_df, message

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="Tilda Price Master", page_icon="🛒")

st.title('Обновление цен для Tilda v3.0 🚀')
st.markdown("Поддерживает CSV и Excel (.xlsx). Умеет делать красивые цены и находить новые товары.")

# Загрузка
col1, col2 = st.columns(2)
with col1:
    uploaded_tilda = st.file_uploader("1. Каталог Tilda (CSV/XLSX)", type=['csv', 'xlsx'])
with col2:
    uploaded_new = st.file_uploader("2. Новый прайс (CSV/XLSX)", type=['csv', 'xlsx'])

st.divider()

# Настройки колонок
with st.expander("⚙️ Настройки названий колонок", expanded=False):
    c_set1, c_set2 = st.columns(2)
    with c_set1:
        st.markdown("**Файл Тильды**")
        u_sku_tilda = st.text_input("Колонка Артикула", value="SKU")
        u_price_tilda = st.text_input("Колонка Цены", value="Price")
    with c_set2:
        st.markdown("**Новый прайс**")
        u_sku_new = st.text_input("Колонка Артикула (new)", value="Артикул")
        u_price_new = st.text_input("Колонка Цены (new)", value="price new 2611")

st.divider()

# Настройки цен
st.subheader("Правила обработки")

col_p1, col_p2 = st.columns(2)

with col_p1:
    percent = st.number_input(
        "Изменение цены (%)", 
        min_value=-99.0, max_value=1000.0, value=0.0, step=1.0
    )
    if percent > 0:
        st.caption(f"Цена 1000 -> {1000 * (1 + percent/100)}")

with col_p2:
    st.write("") # Отступ
    st.write("") 
    # Галочка "Красивые цены"
    use_beautiful = st.checkbox("🔥 Сделать цены красивыми (окончание на 9)", value=False)
    if use_beautiful:
        st.caption("Пример: 1543 -> 1549")

st.divider()

# Кнопка запуска
if uploaded_tilda and uploaded_new:
    if st.button('🚀 Рассчитать и Обновить', type="primary"):
        with st.spinner('Анализирую файлы...'):
            
            # Запускаем обработку
            result_df, missing_df, msg = process_files(
                uploaded_tilda, uploaded_new, percent,
                u_sku_tilda, u_price_tilda, u_sku_new, u_price_new,
                use_beautiful
            )
            
            if result_df is not None:
                st.success(msg)
                
                # Кнопка 1: Скачать обновленный каталог
                csv_buffer = result_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button(
                    label="📥 Скачать обновленный КАТАЛОГ",
                    data=csv_buffer,
                    file_name="tilda_updated_full.csv",
                    mime="text/csv"
                )
                
                # Кнопка 2: Скачать недостающие товары (если есть)
                if missing_df is not None and not missing_df.empty:
                    st.warning(f"⚠️ Найдено {len(missing_df)} товаров, которых нет в каталоге Тильды.")
                    
                    csv_missing = missing_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button(
                        label="📄 Скачать список НОВЫХ товаров",
                        data=csv_missing,
                        file_name="missing_items.csv",
                        mime="text/csv"
                    )
            else:
                st.error(msg)
