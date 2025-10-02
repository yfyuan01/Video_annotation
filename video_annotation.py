import json
import streamlit as st
import pandas as pd
import os

# -----------------------------
# File paths
URL_FILE = "video_links.txt"
INFO_FILE = 'video_info.json'
SAVE_FILE = "annotations.csv"


# -----------------------------
# Load video data
def load_video_data(url_path, info_path):
    data = []
    urls = [line.strip() for line in open(url_path, "r").readlines()]
    infos = []
    with open(info_path, "r", encoding="utf-8") as f:
        buffer = ""
        for line in f:
            line = line.strip()
            if not line:
                continue
            buffer += line
            if line.endswith("}"):
                try:
                    obj = json.loads(buffer)
                    infos.append(obj)
                    buffer = ""
                except json.JSONDecodeError:
                    pass
    for i, url in enumerate(urls):
        info = infos[i]
        data.append({
            "url": url,
            "clip_info": '',
            "title": info["title"],
            "basic_info": info["description"]
        })
    return data


# -----------------------------
# Save annotation
def save_annotation(annotation):
    if os.path.exists(SAVE_FILE):
        df = pd.read_csv(SAVE_FILE)
        # remove old entry for same URL
        df = df[df["url"] != annotation["url"]]
        df = pd.concat([df, pd.DataFrame([annotation])], ignore_index=True)
    else:
        df = pd.DataFrame([annotation])
    df.to_csv(SAVE_FILE, index=False)


# -----------------------------
# Initialize session state
if "idx" not in st.session_state:
    st.session_state.idx = 0
if "selectbox_idx" not in st.session_state:
    st.session_state.selectbox_idx = 0

st.title("Political Argument Annotation Tool")

video_data = load_video_data(URL_FILE, INFO_FILE)

if not video_data:
    st.warning("No video data found in the txt file.")
else:
    # -------------------------
    # 先处理按钮点击（在创建任何 widget 之前）
    # 检查是否点击了 Next 按钮（通过一个临时标记）
    if st.session_state.get('next_clicked', False):
        if st.session_state.idx < len(video_data) - 1:
            st.session_state.idx += 1
            st.session_state.selectbox_idx = st.session_state.idx
        st.session_state.next_clicked = False
        st.rerun()


    # -------------------------
    # Dropdown selection synced with session state
    def update_idx():
        if st.session_state.selectbox_idx != st.session_state.idx:
            st.session_state.idx = st.session_state.selectbox_idx


    st.selectbox(
        "Select video to annotate",
        range(len(video_data)),
        index=st.session_state.idx,
        format_func=lambda x: video_data[x]["title"],
        key="selectbox_idx",
        on_change=update_idx
    )

    # -------------------------
    # Current video
    print(st.session_state.idx)
    print('---')
    video = video_data[st.session_state.idx]

    st.subheader("Video Information")
    st.markdown(f"**Title:** {video['title']}")
    st.markdown(f"**Basic Info:** {video['basic_info']}")
    st.markdown(f"**Video URL:** {video['url']}")
    clip_info = st.text_area("Clip Info", value=video['clip_info'], height=150)

    st.subheader("Annotation")
    argument_type = st.radio("Political Argument Type", ["Positive", "Neutral", "Negative", "N/A"])
    target = st.text_input("Target")
    evidence = st.text_area("Evidence", height=100)

    # -------------------------
    # Buttons: Save / Next
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Save Annotation"):
            annotation = {
                "url": video['url'],
                "clip_info": clip_info,
                "title": video['title'],
                "basic_info": video['basic_info'],
                "argument_type": argument_type,
                "target": target,
                "evidence": evidence
            }
            save_annotation(annotation)
            st.success("Annotation saved!")

    with col2:
        if st.button("Next Video"):
            print('clicked')
            if st.session_state.idx < len(video_data) - 1:
                st.session_state.next_clicked = True
                st.rerun()
            else:
                st.info("This is the last video.")