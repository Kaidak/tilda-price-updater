import streamlit as st
import pandas as pd
import io
import numpy as np

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
st.set_page_config(page_title="Smart Mover v3.0", page_icon="🚚")

st.title('Умный перенос колонок v3.0 🧠')
st.markdown("""
Перенос данных между колонками с защитой от потери данных.
""")

# 1. Загрузка файла
uploaded_file = st.file_uploader("Загрузите файл (CSV или XLSX)", type=['csv', 'xlsx'])

if uploaded_file:
    df = load_file(uploaded_file)
    
    if df is not None:
        st.success("Файл загружен.")
        all_columns = df.columns.tolist()

        st.divider()

        # 2. Выбор колонок
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("📤 ОТКУДА (Источник)")
            source_col = st.selectbox("Выберите колонку", all_columns, key="src")

        with col2:
            st.warning("📥 КУДА (Приемник)")
            target_col_input = st.text_input("Напишите название", value="Price")
            st.caption(f"Существующие: {', '.join(all_columns)}")

        st.divider()
        
        # 3. Настройки режима
        st.subheader("⚙️ Как переносить данные?")
        
        mode = st.radio(
            "Выберите режим:",
            [
                "🔹 Умное обновление (Рекомендуется)", 
                "⚡ Полная замена (Опасно)", 
                "✨ Заполнить только пропуски"
            ],
            help="Умное: Если в источнике пусто, цена в приемнике останется. Полная: Всё заменится (даже на пустоту). Пропуски: Пишет только туда, где сейчас пусто."
        )
        
        # Логика описания режима для пользователя
        if "Умное" in mode:
            st.caption(f"👉 Если в **{source_col}** есть цена — она скопируется. Если там пусто — в **{target_col_input}** останется старая цена.")
        elif "Полная" in mode:
            st.caption(f"👉 Колонка **{target_col_input}** станет точной копией **{source_col}**. Старые данные сотрутся.")
        else:
            st.caption(f"👉 Данные запишутся только в пустые ячейки **{target_col_input}**. Существующие цены не изменятся.")

        st.divider()

        # Опция удаления
        delete_source = st.checkbox("🗑️ Очистить ИСХОДНУЮ колонку после переноса?", value=True)

        st.divider()

        # 4. Кнопка запуска
        if st.button("🚀 Выполнить перенос", type="primary"):
            
            if source_col not in df.columns:
                st.error("Исходная колонка не найдена!")
            else:
                rows_count = len(df)
                
                # Создаем целевую, если нет
                if target_col_input not in df.columns:
                    df[target_col_input] = None
                
                # ПРЕДОБРАБОТКА: Превращаем пробелы и пустые строки в понятную пустоту (NaN)
                # Это критически важно, чтобы "умный режим" понял, что ячейка пустая
                df[source_col] = df[source_col].replace(r'^\s*$', None, regex=True)
                df[source_col] = df[source_col].replace('', None)
                
                # ЛОГИКА ПЕРЕНОСА
                if "Умное" in mode:
                    # combine_first берет данные из первого df, а если там пусто — из второго.
                    # Мы берем Источник. Заполняем его дырки данными из Приемника.
                    # И результат записываем в Приемник.
                    df[target_col_input] = df[source_col].combine_first(df[target_col_input])
                    
                elif "Полная" in mode:
                    # Просто копируем
                    df[target_col_input] = df[source_col]
                    
                elif "Заполнить" in mode:
                    # Берем Приемник. Если дырка — берем из Источника.
                    df[target_col_input] = df[target_col_input].combine_first(df[source_col])

                # УДАЛЕНИЕ
                if delete_source:
                    df[source_col] = "" # Очищаем
                    msg_del = "Исходная колонка очищена."
                else:
                    msg_del = "Исходная колонка сохранена."

                st.success(f"Готово! {msg_del}")
                
                # Показываем результат (сравнение)
                st.write("👇 **Проверка (Первые 5 строк):**")
                # Для красоты покажем только задействованные колонки
                st.dataframe(df[[source_col, target_col_input]].head(5))

                # 5. Скачивание
                st.subheader("Скачать файл")
                c_d1, c_d2 = st.columns(2)
                
                with c_d1:
                    st.download_button(
                        "📥 Скачать CSV",
                        convert_df_to_csv(df),
                        "moved_smart.csv",
                        "text/csv"
                    )
                with c_d2:
                    st.download_button(
                        "📥 Скачать Excel",
                        convert_df_to_excel(df),
                        "moved_smart.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
