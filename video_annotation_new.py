import json
import streamlit as st
import pandas as pd
import os
from datetime import datetime
import re

from pygments.lexer import combined
from text_highlighter import text_highlighter

st.set_page_config(
    page_title="Political Argument Annotation Tool",
    layout="wide",  # Wide screen model
    initial_sidebar_state="expanded"
)

# 🔥 第二步：添加自定义 CSS 减少边距
st.markdown("""
<style>
    /* 减少主容器的padding */
    .main .block-container {
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 100% !important;
    }

    /* 扩展内容区域 */
    .stApp {
        max-width: 100% !important;
    }

    /* 调整文本区域宽度 */
    section[data-testid="stSidebar"] {
        width: 300px !important;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# User credentials
USER_CREDENTIALS = {
    "test": {"password": "test123", "role": "test", "videos": "0-4"},  # 前5个视频 (索引0-4)
    "annotator1": {"password": "anno1pass", "role": "annotator", "videos": "split1"},
    "annotator2": {"password": "anno2pass", "role": "annotator", "videos": "split2"}
}

# -----------------------------
# -----------------------------
# File paths
URL_FILE = "video_links.txt"
INFO_FILE = 'video_info.json'
SAVE_FILE = "annotations.csv"


# ---------- 读取VTT字幕 ----------
def load_vtt_with_time(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    subtitles = []
    buffer = []
    current_time = ""
    for line in lines:
        line = line.strip()
        if line.isdigit():
            if buffer and current_time:
                text = ' '.join(buffer).strip()
                subtitles.append({"time": current_time, "text": text})
                buffer = []
                current_time = ""
        elif "-->" in line:
            current_time = line
        elif line:
            buffer.append(line)
    if buffer and current_time:
        text = ' '.join(buffer).strip()
        subtitles.append({"time": current_time, "text": text})

    return subtitles


# ---------- 将字幕转换为纯文本 ----------
def subtitles_to_text(subtitles):
    """将字幕列表转换为带时间戳的纯文本"""
    lines = []
    for i, sub in enumerate(subtitles, start=1):
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', sub['text'])
        text = text.strip('WEBVTT ')
        lines.append(f"[{sub['time']}] {text}")
    return "\n".join(lines)


# ---------- Load video data ----------
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
            "original_idx": i,
            "url": url,
            "clip_info": '',
            "title": info["title"],
            "basic_info": info["description"]
        })
    return data


def get_user_videos(all_videos, username):
    """根据用户身份返回可见的视频列表"""
    user_info = USER_CREDENTIALS.get(username)
    if not user_info:
        return []

    video_range = user_info["videos"]

    # 测试用户：前5个视频
    if video_range == "0-4":
        return all_videos[:5]

    # 正式标注员：均分视频
    # 跳过前5个测试视频，剩余的视频均分
    available_videos = all_videos  # 从第6个开始
    mid_point = len(available_videos) // 2

    if video_range == "split1":
        return available_videos[:mid_point]
    elif video_range == "split2":
        return available_videos[mid_point:]

    return []

def save_annotation(video_info, annotations_list, username):
    """保存所有标注记录"""
    records = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for idx, anno in enumerate(annotations_list, start=1):
        record = {
            "timestamp": timestamp,
            "username": username,
            "video_idx":  video_info['original_idx'],
            "video_url": video_info['url'],
            "video_title": video_info['title'],
            "video_basic_info": video_info['basic_info'],
            "annotation_order": idx,
            "argument_type": anno['type'],
            "claim": anno['claim'],
            "premise": anno['premise'],
        }
        records.append(record)

    if not records:
        st.warning("No annotations to save!")
        return False

    if os.path.exists(SAVE_FILE):
        df_existing = pd.read_csv(SAVE_FILE)
        df_existing = df_existing[
            ~((df_existing["video_idx"] == video_info['original_idx']) &
              (df_existing["username"] == username))
        ]
        # df_existing = df_existing[df_existing["video_idx"] != st.session_state.idx]
        df_new = pd.DataFrame(records)
        df = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df = pd.DataFrame(records)

    df.to_csv(SAVE_FILE, index=False)

    backup_file = f"annotations_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(backup_file, index=False)

    return True


def get_last_annotated_video(username, video_data):
    """获取用户最后标注的视频索引"""
    if not os.path.exists(SAVE_FILE):
        return 0  # 如果没有保存文件，从第一个视频开始

    try:
        df = pd.read_csv(SAVE_FILE)

        # 筛选出该用户的标注记录
        user_annotations = df[df['username'] == username]

        if user_annotations.empty:
            return 0  # 该用户没有标注记录，从第一个视频开始

        # 获取最后一次标注的 original_video_idx
        last_video_idx = user_annotations.iloc[-1]['video_idx']

        # 在过滤后的 video_data 中找到对应的位置
        for i, video in enumerate(video_data):
            if video['original_idx'] == last_video_idx:
                return i  # 返回在过滤后列表中的位置

        # 如果没找到（比如该视频不在用户的可见范围内），返回0
        return 0

    except Exception as e:
        print(f"Error loading last position: {e}")
        return 0

# -----------------------------
# Initialize session state
if "idx" not in st.session_state:
    st.session_state.idx = 0
if "selectbox_idx" not in st.session_state:
    st.session_state.selectbox_idx = 0
if "annotations" not in st.session_state:
    st.session_state.annotations = {}
if "highlighter_annotations" not in st.session_state:
    st.session_state.highlighter_annotations = {}
if "current_argument_type" not in st.session_state:
    st.session_state.current_argument_type = "N/A"
if "highlighter_key" not in st.session_state:
    st.session_state.highlighter_key = {}
# 侧边栏选择模式
page = st.sidebar.radio("Mode", ["Annotation", "Admin Dashboard"])

# if page == "Annotation":
#     st.title("Political Argument Annotation Tool")
#
#     # 添加说明
#     st.info(
#         "💡 **How to use:** \n"
#         "1. Select a label (Claim/Premise) below\n"
#         "2. Click and drag to highlight text in the subtitle area\n"
#         "3. Choose argument type and click 'Add Annotation' to save this pair\n"
#         "4. The highlights in text will remain, but Claim/Premise/Type selections will reset for next annotation"
#     )
if page == "Annotation":
    # 🔥 新增：登录系统
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None

    if not st.session_state.logged_in:
        st.title("🔐 Login")
        st.markdown("### Political Argument Annotation Tool")

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")

            if st.button("Login", type="primary", use_container_width=True):
                if username in USER_CREDENTIALS and USER_CREDENTIALS[username]["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.user_role = USER_CREDENTIALS[username]["role"]
                    st.session_state.need_restore_position = True
                    st.success(f"✅ Welcome, {username}!")
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password!")

        st.stop()  # 未登录时停止执行后续代码

    # 🔥 显示当前登录用户
    st.sidebar.markdown(f"**👤 User:** {st.session_state.username}")
    st.sidebar.markdown(f"**📋 Role:** {st.session_state.user_role}")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.sidebar.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.rerun()
    with col2:
        if st.sidebar.button("🔄 Start Over"):
            st.session_state.idx = 0
            st.session_state.current_argument_type = "N/A"
            st.success("Reset to first video!")
            st.rerun()
    st.sidebar.markdown("---")

    st.title("Political Argument Annotation Tool")

    # 添加说明
    st.info(
        "💡 **How to use:** \n"
        "1. Select a label (Claim/Premise) below\n"
        "2. Click and drag to highlight text in the subtitle area\n"
        "3. Choose argument type and click 'Add Annotation' to save this pair\n"
        "4. The highlights in text will remain, but Claim/Premise/Type selections will reset for next annotation"
    )

    # 🔥 修改：加载所有视频，然后根据用户过滤
    all_video_data = load_video_data(URL_FILE, INFO_FILE)
    video_data = get_user_videos(all_video_data, st.session_state.username)

    if not video_data:
        st.warning("No video data available for your account.")
    else:
        # 🔥 新增：恢复上次标注位置
        if st.session_state.get('need_restore_position', False):
            last_position = get_last_annotated_video(st.session_state.username, video_data)
            st.session_state.idx = last_position
            st.session_state.need_restore_position = False  # 只恢复一次

            if last_position > 0:
                st.success(f"✅ Restored to your last position: Video #{last_position + 1}")

        # 🔥 显示用户可见的视频范围
        if st.session_state.user_role == "test":
            st.info(f"📹 **Test Account**: You can annotate videos 1-5 (Total: {len(video_data)} videos)")
        else:
            st.info(f"📹 **Your assigned videos**: Total {len(video_data)} videos")

        # Dropdown selection（其余代码保持不变）
    # video_data = load_video_data(URL_FILE, INFO_FILE)

    # if not video_data:
    #     st.warning("No video data found in the txt file.")
    # else:
        # Dropdown selection
        def update_idx():
            if st.session_state.selectbox_idx != st.session_state.idx:
                st.session_state.idx = st.session_state.selectbox_idx
                st.session_state.current_argument_type = "N/A"  # 重置类型


        selected_idx = st.selectbox(
            "Select video to annotate",
            range(len(video_data)),
            index=st.session_state.idx,
            format_func=lambda x: video_data[x]["title"],
            # key="selectbox_idx",
            # on_change=update_idx
        )
        if selected_idx != st.session_state.idx:
            st.session_state.idx = selected_idx
            st.session_state.current_argument_type = "N/A"
            st.rerun()

        # Current video
        video = video_data[st.session_state.idx]
        video_idx = st.session_state.idx
        original_video_idx = video['original_idx']  # 🔥 这是原始索引

        st.subheader("Video Information")
        st.markdown(f"**Title:** {video['title']}")
        st.markdown(f"**Basic Info:** {video['basic_info']}")
        st.markdown(f"**Video URL:** {video['url']}")

        st.markdown("---")
        st.subheader("📝 Subtitle Text - Highlight to Annotate")

        # 加载字幕并转换为文本
        # original_video_idx = video['original_idx']
        # subtitles = load_vtt_with_time(f"subtitles/{original_video_idx}.vtt")
        # subtitle_text = subtitles_to_text(subtitles)
        subtitle_text = ''.join(open(f"subtitles/{original_video_idx}.vtt").readlines())

        # 初始化当前视频的高亮标注
        if original_video_idx not in st.session_state.highlighter_annotations:
            st.session_state.highlighter_annotations[original_video_idx] = []
        if original_video_idx not in st.session_state.highlighter_key:
            st.session_state.highlighter_key[original_video_idx] = 0
        # if video_idx not in st.session_state.saved_annotation_ids:
        #     st.session_state.saved_annotation_ids[video_idx] = set()
        # if "annotation_count" not in st.session_state:
        #     st.session_state.annotation_count = 0
        if "current_claims" not in st.session_state:
            st.session_state.current_claims = []
        if "current_premises" not in st.session_state:
            st.session_state.current_premises = []
        if "saved_annotation_ids" not in st.session_state:
            st.session_state.saved_annotation_ids = {}  # {video_idx: set(annotation_ids)}
        if "current_argument_type" not in st.session_state:
            st.session_state.current_argument_type = "N/A"
        # 使用 text_highlighter 组件
        if original_video_idx not in st.session_state.saved_annotation_ids:
            st.session_state.saved_annotation_ids[original_video_idx] = set()
        highlighted = text_highlighter(
            text=subtitle_text,
            labels=[
                ("Claim", "#FFB6C1"),  # 浅粉色
                ("Premise", "#87CEEB"),  # 浅蓝色
            ],
            annotations=st.session_state.highlighter_annotations[original_video_idx],
            key=f"highlighter_{original_video_idx}_{st.session_state.highlighter_key[original_video_idx]}",
            show_label_selector=True,
            text_height=400
        )
        if highlighted != st.session_state.highlighter_annotations[original_video_idx]:
            st.session_state.highlighter_annotations[original_video_idx] = highlighted
        def get_annotation_id(anno):
            """生成标注的唯一ID"""
            return f"{anno['start']}_{anno['end']}_{anno['tag']}"
        all_claims = [anno for anno in highlighted if anno.get('tag') == 'Claim']
        all_premises = [anno for anno in highlighted if anno.get('tag') == 'Premise']
        saved_ids = st.session_state.saved_annotation_ids[original_video_idx]
        current_claims = [anno for anno in all_claims if get_annotation_id(anno) not in saved_ids]
        current_premises = [anno for anno in all_premises if get_annotation_id(anno) not in saved_ids]
        st.markdown("---")
        st.subheader("➕ Create New Annotation")
        # 三元组输入区域
        st.markdown("**Current Annotation Triplet (Claim + Premise + Label):**")

        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            st.markdown("**📌 Claim**")
            # print(claims)
            if current_claims:
                claim_texts = [subtitle_text[anno['start']:anno['end']] for anno in current_claims]
                combined_claim = "\n\n".join(claim_texts)
                st.text_area(
                    "Claim content",
                    value=combined_claim,
                    height=120,
                    # key="current_claim_display",
                    disabled=True,
                    label_visibility="collapsed"
                )
            else:
                st.info("👆 Please highlight Claim text above")

        with col2:
            st.markdown("**📝 Premise**")
            if current_premises:
                premise_texts = [subtitle_text[anno['start']:anno['end']] for anno in current_premises]
                combined_premise = "\n\n".join(premise_texts)
                st.text_area(
                    "Premise content",
                    value=combined_premise,
                    height=120,
                    # key="current_premise_display",
                    disabled=True,
                    label_visibility="collapsed"
                )
            else:
                st.info("👆 Please highlight Premise text above")
            use_previous_premise = st.checkbox(
                "Same as previous?",
                value=False,
                key=f"use_previous_premise_{original_video_idx}_{st.session_state.highlighter_key[original_video_idx]}",
                help="Use premise from the most recent annotation"
            )

        with col3:
            st.markdown("**🏷️ Type**")
            radio_key = f"argument_type_radio_{st.session_state.idx}_{st.session_state.highlighter_key[original_video_idx]}"
            # 使用 session_state 来控制默认值
            argument_type = st.radio(
                "Argument Type",
                ["Positive", "Neutral", "Negative", "N/A"],
                index=["Positive", "Neutral", "Negative", "N/A"].index(st.session_state.current_argument_type),
                key=radio_key,
                label_visibility="collapsed"
            )
            # 更新 session_state
            st.session_state.current_argument_type = argument_type

        # 添加按钮
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("✅ Add Annotation", type="primary", use_container_width=True):
                if current_claims and (current_premises or use_previous_premise):
                    # 获取文本内容
                    claim_texts = [subtitle_text[anno['start']:anno['end']] for anno in current_claims]
                    claim_ids = [get_annotation_id(anno) for anno in current_claims]
                    if use_previous_premise and original_video_idx in st.session_state.annotations and len(st.session_state.annotations[original_video_idx]) > 0:
                        last_anno = st.session_state.annotations[original_video_idx][-1]
                        premise_texts = [last_anno['premise']]
                        premise_ids = last_anno.get('premise_ids', [])
                    else:
                        premise_texts = [subtitle_text[anno['start']:anno['end']] for anno in current_premises]
                        premise_ids = [get_annotation_id(anno) for anno in current_premises]
                    # 创建新标注（三元组）
                    new_annotation = {
                        'type': st.session_state.current_argument_type,
                        'claim': "\n\n".join(claim_texts),
                        'premise': "\n\n".join(premise_texts),
                        'claim_ids': claim_ids,  # 🔥 新增
                        'premise_ids': premise_ids  # 🔥 新增
                    }
                    # 添加到标注列表
                    if original_video_idx not in st.session_state.annotations:
                        st.session_state.annotations[original_video_idx] = []
                    st.session_state.annotations[original_video_idx].append(new_annotation)
                    for anno in current_claims + current_premises:
                        st.session_state.saved_annotation_ids[original_video_idx].add(get_annotation_id(anno))

                    st.session_state.current_claims = []
                    st.session_state.current_premises = []
                    st.session_state.current_argument_type = "N/A"
                    st.session_state.highlighter_key[original_video_idx] += 1
                    # st.session_state.annotation_count = st.session_state.get("annotation_count", 0) + 1
                    # st.success(f"✅ Added annotation #{len(st.session_state.annotations[original_video_idx])}")
                    st.rerun()
                else:
                    st.error(
                        "⚠️ Please highlight at least one claim, and either select Premise or check 'Same as previous'.")

        with col2:
            if st.button("🗑️ Clear Current Selection", use_container_width=True):
                # 只清除当前的 Claim 和 Premise
                # print(st.session_state.saved_annotation_ids[original_video_idx])
                st.session_state.highlighter_annotations[original_video_idx] = [
                    anno for anno in st.session_state.highlighter_annotations[original_video_idx]
                    if get_annotation_id(anno) in st.session_state.saved_annotation_ids[original_video_idx]
                ]
                # print(st.session_state.highlighter_annotations[original_video_idx])
                st.session_state.current_argument_type = "N/A"
                st.session_state.highlighter_key[original_video_idx] += 1
                # st.session_state.annotation_count = st.session_state.get("annotation_count", 0) + 1
                st.rerun()

        with col3:
            if st.button("🧹 Clear All Highlights", use_container_width=True):
                st.session_state.highlighter_annotations[original_video_idx] = []
                st.session_state.saved_annotation_ids[original_video_idx] = set()
                if original_video_idx in st.session_state.annotations:
                    st.session_state.annotations[original_video_idx] = []
                st.session_state.current_argument_type = "N/A"
                st.session_state.highlighter_key[original_video_idx] += 1
                st.rerun()

        # 显示已保存的标注
        st.markdown("---")
        st.subheader("📋 Saved Annotations")

        current_annotations = st.session_state.annotations.get(original_video_idx, [])

        if current_annotations:
            st.write(f"**Total: {len(current_annotations)} annotation(s)**")
            for idx, anno in enumerate(current_annotations):
                with st.expander(
                        f"#{idx + 1}: [{anno['type']}] {anno['claim'][:50]}...",
                        expanded=False
                ):
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.markdown(f"**🏷️ Type:** `{anno['type']}`")
                        st.markdown("**📌 Claim:**")
                        st.text_area(
                            "claim",
                            value=anno['claim'],
                            height=80,
                            key=f"saved_claim_{idx}",
                            disabled=True,
                            label_visibility="collapsed"
                        )
                        st.markdown("**📝 Premise:**")
                        st.text_area(
                            "premise",
                            value=anno['premise'],
                            height=80,
                            key=f"saved_premise_{idx}",
                            disabled=True,
                            label_visibility="collapsed"
                        )
                    with col2:
                        if st.button("🗑️", key=f"delete_{idx}", help="Delete this annotation"):
                            deleted_anno = st.session_state.annotations[original_video_idx][idx]
                            # 🔥 获取所有相关的 annotation IDs
                            all_ids = deleted_anno.get('claim_ids', []) + deleted_anno.get('premise_ids', [])

                            # 🔥 从 saved_annotation_ids 中移除
                            for anno_id in all_ids:
                                st.session_state.saved_annotation_ids[original_video_idx].discard(anno_id)

                            # 🔥 从 highlighter_annotations 中移除对应的高亮
                            st.session_state.highlighter_annotations[original_video_idx] = [
                                anno for anno in st.session_state.highlighter_annotations[original_video_idx]
                                if get_annotation_id(anno) not in all_ids
                            ]

                            # 删除 annotation
                            st.session_state.annotations[original_video_idx].pop(idx)

                            # 🔥 刷新组件
                            st.session_state.highlighter_key[original_video_idx] += 1
                            st.rerun()
                            # st.session_state.annotations[video_idx].pop(idx)
                            # st.rerun()
        else:
            st.info("No annotations saved yet. Create your first annotation above!")

        # 底部操作按钮
        st.markdown("---")
        col1, col2 = st.columns([1, 1])

        with col1:
            if st.button("💾 Save All Annotations to File", type="primary", use_container_width=True):
                current_annotations = st.session_state.annotations.get(original_video_idx, [])

                if len(current_annotations) == 0:
                    st.warning("No annotations to save for this video!")
                else:
                    success = save_annotation(video, current_annotations, st.session_state.username)
                    if success:
                        st.success(f"✅ Saved {len(current_annotations)} annotation(s) to {SAVE_FILE}!")
                        with st.expander("📄 View saved annotations"):
                            for idx, anno in enumerate(current_annotations, start=1):
                                st.write(f"{idx}. **[{anno['type']}]** {anno['claim'][:50]}...")

        with col2:
            if st.button("➡️ Next Video", use_container_width=True):
                current_annotations = st.session_state.annotations.get(original_video_idx, [])
                if len(current_annotations) > 0:
                    success = save_annotation(video, current_annotations, st.session_state.username)
                    if success:
                        st.success(f"✅ Auto-saved {len(current_annotations)} annotation(s)!")
                if video_idx < len(video_data) - 1:
                    st.session_state.idx += 1
                    # st.session_state.selectbox_idx = st.session_state.idx
                    st.session_state.current_argument_type = "N/A"
                    st.rerun()
                else:
                    st.info("✨ This is the last video.")

elif page == "Admin Dashboard":
    st.title("📊 Annotation Dashboard")

    if 'admin_authenticated' not in st.session_state:
        st.session_state.admin_authenticated = False

    if not st.session_state.admin_authenticated:
        password = st.text_input("Enter admin password:", type="password")
        if st.button("Login"):
            if password == "admin":
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("Wrong password!")
        st.stop()

    if os.path.exists(SAVE_FILE):
        df = pd.read_csv(SAVE_FILE)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Annotations", len(df))
        with col2:
            st.metric("Annotated Videos", df['video_idx'].nunique())
        with col3:
            st.metric("Active Users", df['username'].nunique() if 'username' in df.columns else "N/A")
        with col4:
            avg_per_video = len(df) / df['video_idx'].nunique() if df['video_idx'].nunique() > 0 else 0
            st.metric("Avg Annotations/Video", f"{avg_per_video:.1f}")
        if 'username' in df.columns:
            st.subheader("👥 Annotations by User")
            user_stats = df.groupby('username').size().reset_index(name='count')
            import plotly.express as px

            fig_users = px.bar(user_stats, x='username', y='count', title='Annotations per User')
            st.plotly_chart(fig_users, use_container_width=True)
        st.subheader("📈 Annotation Type Distribution")
        import plotly.express as px

        fig = px.pie(df, names='argument_type', title='Argument Types')
        st.plotly_chart(fig, use_container_width=True)

        if 'timestamp' in df.columns:
            st.subheader("📅 Annotation Timeline")
            df['date'] = pd.to_datetime(df['timestamp']).dt.date
            daily_counts = df.groupby('date').size().reset_index(name='count')
            fig2 = px.line(daily_counts, x='date', y='count', title='Daily Annotations')
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("📋 All Annotations")

        col1, col2 = st.columns(2)
        with col1:
            filter_type = st.multiselect("Filter by Type", df['argument_type'].unique())
        with col2:
            filter_video = st.multiselect("Filter by Video", df['video_title'].unique())

        filtered_df = df.copy()
        if filter_type:
            filtered_df = filtered_df[filtered_df['argument_type'].isin(filter_type)]
        if filter_video:
            filtered_df = filtered_df[filtered_df['video_title'].isin(filter_video)]

        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "premise": st.column_config.TextColumn("Premise", width="large"),
                "timestamp": st.column_config.DatetimeColumn("Timestamp", format="YYYY-MM-DD HH:mm"),
            }
        )

        st.subheader("💾 Export Data")
        col1, col2, col3 = st.columns(3)

        with col1:
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"annotations_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

        with col2:
            from io import BytesIO

            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                filtered_df.to_excel(writer, index=False, sheet_name='Annotations')
            st.download_button(
                label="📥 Download Excel",
                data=buffer.getvalue(),
                file_name=f"annotations_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with col3:
            json_data = filtered_df.to_json(orient='records', indent=2)
            st.download_button(
                label="📥 Download JSON",
                data=json_data,
                file_name=f"annotations_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json"
            )

    else:
        st.info("No annotations found yet.")