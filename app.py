import streamlit as st
import pandas as pd
import io

# --- ФУНКЦИИ ---
def clean_price(price_str):
    """Превращает строку с ценой в число."""
    if pd.isna(price_str):
        return None
    # Превращаем в строку, убираем пробелы и запятые
    price_str = str(price_str).strip().replace(',', '')
    try:
        return float(price_str)
    except ValueError:
        return None

def process_files(file_tilda, file_new_prices, percent_change, 
                  col_sku_tilda, col_price_tilda, col_sku_new, col_price_new):
    """
    Теперь функция принимает названия колонок как аргументы.
    """
    
    # 1. Читаем файлы (пытаемся угадать кодировку)
    try:
        df_tilda = pd.read_csv(file_tilda, sep=';', encoding='utf-8', dtype=str)
    except UnicodeDecodeError:
        file_tilda.seek(0)
        df_tilda = pd.read_csv(file_tilda, sep=';', encoding='cp1251', dtype=str)

    try:
        df_new = pd.read_csv(file_new_prices, sep=';', encoding='utf-8', dtype=str)
    except UnicodeDecodeError:
        file_new_prices.seek(0)
        df_new = pd.read_csv(file_new_prices, sep=';', encoding='cp1251', dtype=str)

    # 2. Проверка на наличие колонок (используем те имена, что ввел пользователь)
    if col_sku_tilda not in df_tilda.columns or col_price_tilda not in df_tilda.columns:
        return None, f"Ошибка: В файле Тильды не найдены колонки '{col_sku_tilda}' или '{col_price_tilda}'. Проверьте настройки."
    
    if col_sku_new not in df_new.columns or col_price_new not in df_new.columns:
        return None, f"Ошибка: В файле новых цен не найдены колонки '{col_sku_new}' или '{col_price_new}'. Проверьте настройки."

    # 3. Подготовка данных
    df_tilda[col_sku_tilda] = df_tilda[col_sku_tilda].str.strip()
    df_new[col_sku_new] = df_new[col_sku_new].str.strip()
    
    # Очищаем цену
    df_new['clean_price'] = df_new[col_price_new].apply(clean_price)

    # --- ПРИМЕНЯЕМ ПРОЦЕНТ ---
    multiplier = 1 + (percent_change / 100)
    df_new['final_price'] = (df_new['clean_price'] * multiplier).round(2)

    # Создаем справочник
    price_map = df_new.dropna(subset=['final_price']).set_index(col_sku_new)['final_price'].to_dict()

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

    return df_tilda, f"Успешно! Обновлено товаров: {count_updated}. Наценка: {percent_change}%"

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="Tilda Price Updater", page_icon="🛒")

st.title('Обновление цен для Tilda 🛒')
st.markdown("Загрузите файлы, настройте колонки и обновите цены.")

# Блок загрузки файлов
col1, col2 = st.columns(2)
with col1:
    uploaded_tilda = st.file_uploader("1. Файл экспорта из Tilda (CSV)", type="csv")
with col2:
    uploaded_new = st.file_uploader("2. Файл с новыми ценами (CSV)", type="csv")

st.divider()

# --- БЛОК НАСТРОЕК КОЛОНОК (НОВОЕ) ---
with st.expander("⚙️ Настройки названий колонок (Нажмите, чтобы изменить)", expanded=False):
    st.info("Здесь указаны названия колонок, по которым программа ищет данные. Если в ваших файлах они называются иначе — измените их здесь.")
    
    c_set1, c_set2 = st.columns(2)
    
    with c_set1:
        st.markdown("**Файл Тильды**")
        # Значение value — это то, что написано по умолчанию
        u_sku_tilda = st.text_input("Название колонки Артикула", value="SKU")
        u_price_tilda = st.text_input("Название колонки Цены", value="Price")
        
    with c_set2:
        st.markdown("**Файл Новых цен**")
        u_sku_new = st.text_input("Название колонки Артикула (в новом)", value="Артикул")
        u_price_new = st.text_input("Название колонки Цены (в новом)", value="price new 2611")

st.divider()

# Блок процентов
st.subheader("Настройки цен")
percent = st.number_input(
    "На сколько процентов изменить цену?", 
    min_value=-99.0, 
    max_value=1000.0, 
    value=0.0, 
    step=1.0
)

if percent > 0:
    st.info(f"Цены будут увеличены на {percent}%.")
elif percent < 0:
    st.warning(f"Цены будут уменьшены на {abs(percent)}%.")

st.divider()

# Кнопка запуска
if uploaded_tilda and uploaded_new:
    if st.button('Рассчитать и Обновить цены', type="primary"):
        with st.spinner('Обрабатываю...'):
            # Передаем введенные пользователем названия колонок в функцию
            result_df, message = process_files(
                uploaded_tilda, 
                uploaded_new, 
                percent,
                u_sku_tilda, u_price_tilda, u_sku_new, u_price_new
            )
            
            if result_df is not None:
                st.success(message)
                
                csv_buffer = result_df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')
                
                st.download_button(
                    label="📥 Скачать готовый файл",
                    data=csv_buffer,
                    file_name="tilda_updated_prices.csv",
                    mime="text/csv"
                )
            else:
                st.error(message)
