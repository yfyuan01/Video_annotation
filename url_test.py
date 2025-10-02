import streamlit as st

st.title("Person Info Interface")

# --- Example dictionary of known people ---
people_dict = {
    "Alice": "ID_001",
    "Bob": "ID_002",
    "Charlie": "ID_003"
    # Add more entries here
}

# --- Top: Name input + Search button ---
col1, col2 = st.columns([3, 1])
with col1:
    name = st.text_input("Enter person's name")
with col2:
    if st.button("Search"):
        if name:
            if name in people_dict:
                person_id = people_dict[name]
                st.session_state['person_id'] = person_id
                st.session_state['name'] = name
            else:
                st.warning("Name not found!")
                st.session_state.pop('person_id', None)
                st.session_state.pop('name', None)
        else:
            st.warning("Please enter a name first.")

# --- Display info and inputs after search ---
if 'person_id' in st.session_state:
    # Split layout: left for ID + topic, right for wiki text
    left_col, right_col = st.columns([1, 2])

    with left_col:
        st.write(f"**Person ID:** {st.session_state['person_id']}")

        # Topic selection
        topics = [f"Topic {i+1}" for i in range(21)]
        selected_topic = st.selectbox("Choose a topic", topics)

        # URL input + Submit
        url = st.text_input("Enter URL")
        if st.button("Submit"):
            if url:
                # Save logic here (e.g., CSV, DB)
                st.success(f"Submitted! Name: {st.session_state['name']}, "
                           f"ID: {st.session_state['person_id']}, "
                           f"Topic: {selected_topic}, URL: {url}")
            else:
                st.warning("Please enter a URL before submitting.")

    with right_col:
        wiki_text = st.text_area("Paste wiki text spans here", height=300)
