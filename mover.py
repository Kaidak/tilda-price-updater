import streamlit as st
import pandas as pd
import io

# --- ФУНКЦИИ ---
def load_file(uploaded_file):
    """Читает CSV или Excel и возвращает DataFrame."""
    if uploaded_file.name.endswith('.xlsx'):
        try:
            return pd.read_excel(uploaded_file, dtype=str)
        except Exception as e:
            st.error(f"Ошибка Excel: {e}")
            return None
    else:
        # Перебор кодировок для CSV
        try:
            return pd.read_csv(uploaded_file, sep=';', encoding='utf-8', dtype=str)
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, sep=';', encoding='cp1251', dtype=str)
        except Exception as e:
            st.error(f"Ошибка CSV: {e}")
            return None

def convert_df_to_csv(df):
    return df.to_csv(sep=';', index=False, encoding='utf-8-sig').encode('utf-8-sig')

def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="Column Mover", page_icon="🚚")

st.title('Перенос данных между колонками 🚚')
st.markdown("""
Этот инструмент позволяет скопировать данные из одной колонки в другую внутри одного файла.
Удобно, чтобы перенести **Текущую цену** в **Старую цену** перед обновлением.
""")

# 1. Загрузка файла
uploaded_file = st.file_uploader("Загрузите файл (CSV или XLSX)", type=['csv', 'xlsx'])

if uploaded_file:
    # Читаем файл
    df = load_file(uploaded_file)
    
    if df is not None:
        st.success("Файл успешно загружен!")
        st.write("👀 **Предпросмотр данных (первые 3 строки):**")
        st.dataframe(df.head(3))

        st.divider()

        # Получаем список всех колонок
        all_columns = df.columns.tolist()

        # 2. Настройки переноса
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("ОТКУДА берем данные?")
            # Выпадающий список с существующими колонками
            source_col = st.selectbox("Выберите исходную колонку", all_columns)

        with col2:
            st.warning("КУДА вставляем данные?")
            # Можно выбрать существующую или написать новую
            target_col_input = st.text_input("Напишите название целевой колонки (или выберите ниже)", value="Old Price")
            
            # Показываем список, чтобы можно было скопировать название, если нужно
            st.caption(f"Существующие колонки: {', '.join(all_columns)}")

        # Опции
        overwrite_mode = st.checkbox("Перезаписать данные, даже если в целевой колонке что-то есть?", value=True)
        
        st.divider()

        # 3. Кнопка запуска
        if st.button("🚀 Выполнить перенос", type="primary"):
            
            # Проверка
            if source_col not in df.columns:
                st.error("Исходная колонка не найдена!")
            else:
                # Логика переноса
                rows_count = len(df)
                
                # Если целевой колонки нет - создаем
                if target_col_input not in df.columns:
                    df[target_col_input] = None
                    st.info(f"Колонка '{target_col_input}' была создана, так как её не было.")
                
                # Копируем данные
                if overwrite_mode:
                    # Полное копирование
                    df[target_col_input] = df[source_col]
                else:
                    # Копируем только туда, где пусто (fill missing)
                    df[target_col_input] = df[target_col_input].fillna(df[source_col])

                st.success(f"Готово! Обработано строк: {rows_count}")
                st.write("👇 **Результат (первые 3 строки):**")
                st.dataframe(df[[source_col, target_col_input]].head(3))

                # 4. Скачивание
                st.subheader("Скачать результат")
                
                c_d1, c_d2 = st.columns(2)
                
                with c_d1:
                    # Скачать CSV
                    csv_data = convert_df_to_csv(df)
                    st.download_button(
                        label="📥 Скачать как CSV",
                        data=csv_data,
                        file_name="moved_data.csv",
                        mime="text/csv"
                    )
                
                with c_d2:
                    # Скачать Excel
                    try:
                        excel_data = convert_df_to_excel(df)
                        st.download_button(
                            label="📥 Скачать как Excel (.xlsx)",
                            data=excel_data,
                            file_name="moved_data.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    except Exception as e:
                        st.error("Для скачивания в Excel нужна библиотека openpyxl")