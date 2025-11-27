import streamlit as st
import pandas as pd
import io

# --- ФУНКЦИИ ПОМОЩНИКИ ---

def load_file(uploaded_file):
    """
    Умная загрузка: понимает и CSV, и Excel.
    """
    if uploaded_file.name.endswith('.xlsx'):
        try:
            return pd.read_excel(uploaded_file, dtype=str)
        except Exception as e:
            st.error(f"Ошибка при чтении Excel: {e}")
            return None
    else:
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
    """
    if pd.isna(price):
        return price
    return int(price // 10) * 10 + 9

def process_files(file_tilda, file_new_prices, 
                  percent_main, percent_old, update_old_flag,
                  col_sku_tilda, col_price_tilda, col_old_price_tilda,
                  col_sku_new, col_price_new,
                  do_beautiful_prices):
    
    # 1. Загружаем файлы
    df_tilda = load_file(file_tilda)
    df_new = load_file(file_new_prices)
    
    if df_tilda is None or df_new is None:
        return None, None, "Ошибка чтения файлов."

    # 2. Проверка колонок
    required_tilda = [col_sku_tilda, col_price_tilda]
    if update_old_flag:
        required_tilda.append(col_old_price_tilda)

    # Проверяем наличие колонок в Тильде
    for col in required_tilda:
        if col not in df_tilda.columns:
             # Если колонки "Old Price" нет, но мы хотим её обновить, создадим её пустой
            if col == col_old_price_tilda and update_old_flag:
                df_tilda[col_old_price_tilda] = ""
            else:
                return None, None, f"Ошибка: В файле Тильды нет колонки '{col}'"
    
    if col_sku_new not in df_new.columns or col_price_new not in df_new.columns:
        return None, None, f"Ошибка: В новом прайсе нет колонок '{col_sku_new}' или '{col_price_new}'"

    # 3. Подготовка данных
    df_tilda[col_sku_tilda] = df_tilda[col_sku_tilda].str.strip()
    df_new[col_sku_new] = df_new[col_sku_new].str.strip()
    
    # Очищаем базовую цену из прайса
    df_new['clean_price_base'] = df_new[col_price_new].apply(clean_price)
    
    # --- РАСЧЕТ ОСНОВНОЙ ЦЕНЫ ---
    mult_main = 1 + (percent_main / 100)
    df_new['calc_main'] = df_new['clean_price_base'] * mult_main
    
    # --- РАСЧЕТ СТАРОЙ ЦЕНЫ (если нужно) ---
    if update_old_flag:
        mult_old = 1 + (percent_old / 100)
        df_new['calc_old'] = df_new['clean_price_base'] * mult_old
    
    # --- ОКРУГЛЕНИЕ / КРАСИВЫЕ ЦЕНЫ ---
    if do_beautiful_prices:
        df_new['final_main'] = df_new['calc_main'].apply(make_beautiful_price)
        if update_old_flag:
            df_new['final_old'] = df_new['calc_old'].apply(make_beautiful_price)
    else:
        df_new['final_main'] = df_new['calc_main'].round(2)
        if update_old_flag:
            df_new['final_old'] = df_new['calc_old'].round(2)

    # Создаем справочники (Артикул -> Цена)
    # dropna() нужен, чтобы не обновлять товары, где цена не распозналась
    main_price_map = df_new.dropna(subset=['final_main']).set_index(col_sku_new)['final_main'].to_dict()
    
    old_price_map = {}
    if update_old_flag:
        old_price_map = df_new.dropna(subset=['final_old']).set_index(col_sku_new)['final_old'].to_dict()

    # 5. Обновление каталога Тильды
    count_updated = 0
    
    # Мы используем цикл iterrows или apply, но чтобы обновить 2 колонки сразу,
    # проще сделать функцию, которая возвращает Series, или пройтись дважды.
    # Сделаем через apply, возвращая обновленную строку.
    
    def update_row_logic(row):
        sku = row[col_sku_tilda]
        updated = False
        
        # Обновляем основную цену
        if sku in main_price_map:
            row[col_price_tilda] = main_price_map[sku]
            updated = True
            
        # Обновляем старую цену (только если нашли артикул)
        if update_old_flag and sku in old_price_map:
            row[col_old_price_tilda] = old_price_map[sku]
            
        return row, updated

    # Применяем логику. 
    # Внимание: apply с axis=1 и изменением row внутри работает, но чтобы посчитать count_updated,
    # сделаем чуть хитрее.
    
    updated_rows_indices = []
    
    # Проходим по индексу, чтобы изменять конкретные ячейки (это быстрее и надежнее)
    for idx in df_tilda.index:
        sku = df_tilda.at[idx, col_sku_tilda]
        
        # Обновление Main Price
        if sku in main_price_map:
            df_tilda.at[idx, col_price_tilda] = main_price_map[sku]
            
            # Обновление Old Price (если включено)
            if update_old_flag and sku in old_price_map:
                df_tilda.at[idx, col_old_price_tilda] = old_price_map[sku]
            
            count_updated += 1

    # 6. Отчет о новых товарах
    tilda_skus = set(df_tilda[col_sku_tilda])
    missing_items_df = df_new[~df_new[col_sku_new].isin(tilda_skus)].copy()
    
    # Собираем сообщение
    msg_parts = [f"✅ Обновлено товаров: {count_updated}."]
    if update_old_flag:
        msg_parts.append(f" (Включая колонку '{col_old_price_tilda}').")
        
    return df_tilda, missing_items_df, " ".join(msg_parts)

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="Tilda Price Master 4.0", page_icon="🏷️")

st.title('Tilda Price Master 4.0 🏷️')
st.markdown("Обновление **Цены** и **Старой цены** (для скидок). Поддержка Excel и CSV.")

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
        u_old_price_tilda = st.text_input("Колонка 'Старой цены'", value="Old Price")
    with c_set2:
        st.markdown("**Новый прайс**")
        u_sku_new = st.text_input("Колонка Артикула (new)", value="Артикул")
        u_price_new = st.text_input("Колонка Цены (new)", value="price new 2611")

st.divider()

# --- НАСТРОЙКИ ЦЕН (ОСНОВНОЙ БЛОК) ---
st.subheader("Настройки наценки")

# Колонка 1: Основная цена
c_price1, c_price2 = st.columns(2)

with c_price1:
    st.markdown("#### 🔵 Основная цена")
    percent_main = st.number_input(
        "Наценка для 'Price' (%)", 
        min_value=-99.0, max_value=1000.0, value=0.0, step=1.0, key="p_main"
    )
    st.caption("Цена продажи на сайте.")

with c_price2:
    st.markdown("#### 🔴 Старая цена (зачеркнутая)")
    update_old = st.checkbox("Обновлять колонку 'Old Price'", value=False)
    
    if update_old:
        percent_old = st.number_input(
            "Наценка для 'Old Price' (%)", 
            min_value=-99.0, max_value=1000.0, value=20.0, step=1.0, key="p_old"
        )
        st.caption("Эта цена будет выше и зачеркнута.")
    else:
        percent_old = 0.0

st.divider()
st.write("#### 🎨 Оформление")
use_beautiful = st.checkbox("🔥 Сделать цены красивыми (окончание на 9)", value=False)
if use_beautiful:
    st.caption("Применится и к обычной, и к старой цене. Пример: 1542 -> 1549")

st.divider()

# Кнопка запуска
if uploaded_tilda and uploaded_new:
    if st.button('🚀 Рассчитать и Обновить', type="primary"):
        with st.spinner('Считаем скидки...'):
            
            result_df, missing_df, msg = process_files(
                uploaded_tilda, uploaded_new, 
                percent_main, percent_old, update_old,
                u_sku_tilda, u_price_tilda, u_old_price_tilda,
                u_sku_new, u_price_new,
                use_beautiful
            )
            
            if result_df is not None:
                st.success(msg)
                
                # Кнопка скачивания результата
                csv_buffer = result_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button(
                    label="📥 Скачать обновленный КАТАЛОГ",
                    data=csv_buffer,
                    file_name="tilda_updated_sales.csv",
                    mime="text/csv"
                )
                
                # Кнопка скачивания новинок
                if missing_df is not None and not missing_df.empty:
                    st.warning(f"⚠️ Найдено {len(missing_df)} новых товаров.")
                    csv_missing = missing_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button(
                        label="📄 Скачать список НОВИНОК",
                        data=csv_missing,
                        file_name="missing_items.csv",
                        mime="text/csv"
                    )
            else:
                st.error(msg)
