import streamlit as st

from llm import MAX_INPUT_LENGTH, ApiError, generate_shopping_list

st.set_page_config(page_title="Список покупок по блюду")
st.title("Список покупок по блюду")

dish = st.text_area("Что приготовить?", placeholder="Например, борщ или паста карбонара")
people = st.selectbox("На сколько человек", [1, 2, 4, 6])
format_ = st.selectbox("Формат ответа", ["Список продуктов", "Список + шаги"])

if st.button("Сгенерировать список покупок"):
    text = dish.strip()

    # валидация до вызова API: пустой/длинный ввод в запрос не уходит
    if not text:
        st.error("Напишите, что хотите приготовить.")
    elif len(text) > MAX_INPUT_LENGTH:
        st.error("Слишком длинный текст — сократите или разбейте на части.")
    else:
        try:
            with st.spinner("Составляю список покупок..."):
                result = generate_shopping_list(text, str(people), format_)
        except ApiError as e:
            st.error(str(e))
        except Exception:
            # страховка: сырое исключение в интерфейс не показываем
            st.error("Не удалось получить ответ. Попробуйте ещё раз.")
        else:
            st.text(result)