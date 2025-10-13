import streamlit as st

# 初始化 session_state
if "label_text" not in st.session_state:
    st.session_state.label_text = "aa"
if "radio_index" not in st.session_state:
    st.session_state.radio_index = 1  # 对应 2

numbers = [1, 2, 3]
print(st.session_state)
# 显示 label
st.write("Label:", st.session_state.label_text)

# 显示 radio，使用 index 控制选中项
st.session_state.radio_index = st.radio(
    "Select a number",
    options=numbers,
    index=st.session_state.radio_index,
    key="radio_widget"
)

# Clear 按钮
if st.button("Clear"):
    st.session_state.label_text = ""
    st.session_state.radio_index = 0  # 对应数字 1
    st.rerun()
