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

def process_files(file_tilda, file_new_prices, percent_change):
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

    # 2. Настройки колонок
    col_sku_tilda = 'SKU'
    col_price_tilda = 'Price'
    col_sku_new = 'Артикул'
    col_price_new = 'price new 2611'

    # Проверка на наличие колонок
    if col_sku_tilda not in df_tilda.columns or col_price_tilda not in df_tilda.columns:
        return None, f"Ошибка: В файле каталога нет колонок {col_sku_tilda} или {col_price_tilda}"
    
    if col_sku_new not in df_new.columns or col_price_new not in df_new.columns:
        return None, f"Ошибка: В файле цен нет колонок {col_sku_new} или {col_price_new}"

    # 3. Подготовка данных
    df_tilda[col_sku_tilda] = df_tilda[col_sku_tilda].str.strip()
    df_new[col_sku_new] = df_new[col_sku_new].str.strip()
    
    # Очищаем цену (превращаем в число)
    df_new['clean_price'] = df_new[col_price_new].apply(clean_price)

    # --- НОВАЯ ЛОГИКА: ПРИМЕНЯЕМ ПРОЦЕНТ ---
    # Коэффициент: если 10%, то умножаем на 1.10. Если -10%, то на 0.90
    multiplier = 1 + (percent_change / 100)
    
    # Считаем финальную цену и округляем до 2 знаков
    df_new['final_price'] = (df_new['clean_price'] * multiplier).round(2)

    # Создаем справочник: Артикул -> Финальная цена (с учетом процента)
    price_map = df_new.dropna(subset=['final_price']).set_index(col_sku_new)['final_price'].to_dict()

    count_updated = 0
    
    def update_row(row):
        sku = row[col_sku_tilda]
        if sku in price_map:
            nonlocal count_updated
            count_updated += 1
            # Возвращаем новую цену из справочника
            return price_map[sku]
        else:
            # Оставляем старую
            return row[col_price_tilda]

    df_tilda[col_price_tilda] = df_tilda.apply(update_row, axis=1)

    return df_tilda, f"Успешно! Обновлено товаров: {count_updated}. Применена наценка: {percent_change}%"

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="Tilda Price Updater", page_icon="🛒")

st.title('Обновление цен для Tilda 🛒')
st.markdown("""
Этот инструмент берет цены из новой таблицы, применяет к ним **наценку или скидку**, 
и вставляет их в файл каталога Tilda по Артикулу.
""")

# Загрузчики файлов
col1, col2 = st.columns(2)
with col1:
    uploaded_tilda = st.file_uploader("1. Файл экспорта из Tilda (CSV)", type="csv")
with col2:
    uploaded_new = st.file_uploader("2. Файл с новыми ценами (CSV)", type="csv")

st.divider()

# --- НОВЫЙ БЛОК В ИНТЕРФЕЙСЕ ---
st.subheader("Настройки цен")
percent = st.number_input(
    "На сколько процентов изменить цену?", 
    min_value=-99.0, 
    max_value=1000.0, 
    value=0.0, 
    step=1.0,
    help="Введи положительное число для наценки (например, 10) или отрицательное для скидки (например, -15)."
)

if percent > 0:
    st.info(f"Цены из новой таблицы будут увеличены на {percent}%.")
elif percent < 0:
    st.warning(f"Цены из новой таблицы будут уменьшены на {abs(percent)}%.")
else:
    st.write("Цены будут взяты из таблицы как есть (без изменений).")

st.divider()

if uploaded_tilda and uploaded_new:
    if st.button('Рассчитать и Обновить цены', type="primary"):
        with st.spinner('Магия чисел...'):
            # Передаем процент в функцию
            result_df, message = process_files(uploaded_tilda, uploaded_new, percent)
            
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